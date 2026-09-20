"""系统设置 · 自定义大模型提供商接入 + 本地 CLI 接入（OpenClaw / AnyGen / WorkBuddy）。

设计原则（与全系统一致）：
- 全部为「可选增强」：未配置任何 Key 时系统仍以规则化 + 证据驱动的确定性逻辑运行，
  不会产生编造数据；
- Key 只落本地 Shared Context（backend/data/settings.json 或 GEO_DATA_DIR），
  对外接口只返回掩码，不回显明文；
- 本地 CLI 仅以 shell=False 调用白名单可执行文件，参数经 shlex 解析，输出截断；
  所有 CLI 产出均标记 verification_status=unverified，需人工审核后才可对外使用。
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from . import net
from .util import now_iso, uid

LLM_KEY = "llm"
LOCAL_KEY = "local_cli"

# ---------------- 大模型提供商 ----------------
PROVIDER_TYPES = ("openai", "openai_compatible", "anthropic")

TYPE_HINTS = {
    "openai": "OpenAI 官方接口 /v1",
    "openai_compatible": "OpenAI 兼容接口：DeepSeek / 通义 / 智谱 / Moonshot / 本地 vLLM / Ollama / 自建网关",
    "anthropic": "Anthropic Messages API /v1",
}

BUILTIN_PROVIDERS: list[dict] = [
    {"id": "openai", "name": "OpenAI", "type": "openai",
     "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
     "api_key": "", "enabled": False, "env_var": "OPENAI_API_KEY", "builtin": True},
    {"id": "anthropic", "name": "Anthropic", "type": "anthropic",
     "base_url": "https://api.anthropic.com/v1", "model": "claude-3-5-sonnet-latest",
     "api_key": "", "enabled": False, "env_var": "ANTHROPIC_API_KEY", "builtin": True},
]

BUILTIN_IDS = tuple(p["id"] for p in BUILTIN_PROVIDERS)


def mask(key: str | None) -> str:
    if not key:
        return ""
    return f"{key[:6]}…{key[-4:]}" if len(key) > 14 else "••••"


def llm_settings(settings: dict | None = None) -> dict:
    """settings['llm'] = {"providers": [...], "default": provider_id}"""
    s = (settings or {}).get(LLM_KEY) or {}
    return {"providers": list(s.get("providers") or []), "default": s.get("default")}


def _merge_builtins(providers: list[dict]) -> list[dict]:
    """内置提供商始终存在；用户配置按 id 覆盖同 id 项，自定义项追加在后。"""
    merged: dict[str, dict] = {p["id"]: dict(p) for p in BUILTIN_PROVIDERS}
    for p in providers or []:
        pid = p.get("id")
        if not pid:
            continue
        merged[pid] = {**merged.get(pid, {}), **p}
    # 内置项排在前面，自定义项保持原有顺序
    ordered = [merged[i] for i in BUILTIN_IDS if i in merged]
    ordered += [p for p in (providers or []) if p.get("id") and p["id"] not in BUILTIN_IDS]
    return ordered


def _api_key(cfg: dict) -> tuple[str, str]:
    """返回 (api_key, source)；source ∈ config / env / none。"""
    if cfg.get("api_key"):
        return str(cfg["api_key"]), "config"
    env_var = cfg.get("env_var") or ""
    if env_var and os.getenv(env_var):
        return os.getenv(env_var, ""), "env"
    return "", "none"


def public_provider(cfg: dict, default_id: str | None = None) -> dict:
    key, source = _api_key(cfg)
    return {
        "id": cfg.get("id"),
        "name": cfg.get("name") or cfg.get("id"),
        "type": cfg.get("type") or "openai_compatible",
        "base_url": cfg.get("base_url") or "",
        "model": cfg.get("model") or "",
        "enabled": bool(cfg.get("enabled")),
        "ready": bool(key),
        "is_default": cfg.get("id") == default_id,
        "builtin": bool(cfg.get("builtin")),
        "env_var": cfg.get("env_var") or "",
        "api_key_masked": mask(key),
        "key_source": source,
    }


def provider_ids(settings: dict | None = None) -> list[str]:
    """全部可用提供商 id（含内置）。"""
    return [p["id"] for p in _merge_builtins(llm_settings(settings)["providers"])]


def llm_state(settings: dict | None = None) -> dict:
    cfg = llm_settings(settings)
    default_id = cfg.get("default")
    providers = [public_provider(p, default_id) for p in _merge_builtins(cfg["providers"])]
    active = active_provider(settings)
    return {
        "providers": providers,
        "default": default_id,
        "active": {"id": active["id"], "name": active.get("name"),
                   "type": active.get("type"), "model": active.get("model")} if active else None,
        "types": PROVIDER_TYPES,
        "type_hints": TYPE_HINTS,
        "note": None if active else
                "未启用任何大模型提供商：系统以规则化 + 证据驱动的确定性逻辑运行（无 Key 也可完整跑通）。",
    }


def llm_candidates(settings: dict | None = None) -> list[dict]:
    """按「默认优先、其余按配置顺序」返回已启用且有 Key 的提供商（含解析后的 api_key）。"""
    cfg = llm_settings(settings)
    providers = _merge_builtins(cfg["providers"])
    ordered: list[dict] = []
    if cfg.get("default"):
        ordered += [p for p in providers if p.get("id") == cfg["default"]]
    ordered += [p for p in providers if p.get("id") != cfg["default"]]
    out = []
    for p in ordered:
        key, _ = _api_key(p)
        if p.get("enabled") and key:
            item = dict(p)
            item["api_key"] = key
            out.append(item)
    return out


def active_provider(settings: dict | None = None) -> dict | None:
    candidates = llm_candidates(settings)
    return candidates[0] if candidates else None


def upsert_provider(providers: list[dict], payload: dict) -> dict:
    """新增或更新提供商（按 id；无 id 时自动生成）。原地修改 providers 并返回该条。"""
    pid = (payload.get("id") or "").strip()
    existing = next((p for p in providers if p.get("id") == pid), None) if pid else None
    base = dict(existing) if existing else {"id": pid or uid("PRV")}
    for field in ("name", "type", "base_url", "model", "api_key", "env_var"):
        value = payload.get(field)
        if value is not None:
            base[field] = value.strip() if isinstance(value, str) else value
    if payload.get("enabled") is not None:
        base["enabled"] = bool(payload["enabled"])
    if base.get("type") not in PROVIDER_TYPES:
        base["type"] = "openai_compatible"
    if base.get("base_url"):
        base["base_url"] = str(base["base_url"]).rstrip("/")
    if not base.get("name"):
        base["name"] = base["id"]
    if not existing:
        providers.append(base)
    else:
        existing.update(base)
    return base


def test_provider(cfg: dict, timeout: int = 20) -> dict:
    """连通性测试：优先 GET /models，不支持时回退最小 chat/completions 调用。"""
    key, source = _api_key(cfg)
    name = cfg.get("name") or cfg.get("id") or "provider"
    if not key:
        return {"ok": False, "mode": "disabled", "provider": name,
                "error": "未配置 API Key（可直接在配置中填写，或用 env_var 指向环境变量）"}
    ptype = cfg.get("type") or "openai_compatible"
    base = (cfg.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "mode": "error", "provider": name, "type": ptype,
                "error": "缺少 base_url（示例：https://api.openai.com/v1）"}
    started = time.time()

    def _done(ok: bool, mode: str, **extra: Any) -> dict:
        return {"ok": ok, "mode": mode, "provider": name, "type": ptype,
                "base_url": base, "model": cfg.get("model") or "", "key_source": source,
                "latency_ms": int((time.time() - started) * 1000), **extra}

    try:
        if ptype == "anthropic":
            status, data, text = net.json_request(
                "GET", f"{base}/models",
                {"x-api-key": key, "anthropic-version": "2023-06-01",
                 "Authorization": f"Bearer {key}"}, timeout=timeout)
            if status >= 400:
                return _done(False, "error", http_status=status,
                             error=f"HTTP {status}: {text[:200]}")
            models = [m.get("id") for m in (data or {}).get("data", []) if isinstance(m, dict)]
            return _done(True, "live", http_status=status, models=models[:30],
                         detail="Anthropic /models 可达")

        status, data, text = net.json_request(
            "GET", f"{base}/models",
            {"Authorization": f"Bearer {key}"}, timeout=timeout)
        if status == 200 and isinstance(data, dict):
            models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
            return _done(True, "live", http_status=status, models=models[:30],
                         detail="/models 可达")
        if status in (401, 403):
            return _done(False, "error", http_status=status,
                         error=f"鉴权失败 HTTP {status}：请检查 API Key 与网关鉴权方式")
        if status in (404, 405, 400, 422):
            # 网关可能不提供 /models：用最小 chat 调用验证
            status2, data2, text2 = net.json_request(
                "POST", f"{base}/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                {"model": cfg.get("model") or "gpt-4o-mini",
                 "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8},
                timeout=timeout)
            if status2 < 400 and isinstance(data2, dict):
                content = ((data2.get("choices") or [{}])[0].get("message") or {}).get("content")
                return _done(True, "live", http_status=status2,
                             detail="chat/completions 调用成功（网关未提供 /models）",
                             sample=str(content)[:120] if content else "")
            return _done(False, "error", http_status=status2,
                         error=f"HTTP {status2}: {text2[:200]}")
        return _done(False, "error", http_status=status, error=f"HTTP {status}: {text[:200]}")
    except Exception as e:  # noqa: BLE001
        return _done(False, "error", error=f"{type(e).__name__}: {e}"[:300])


# ---------------- 本地 CLI 接入 ----------------
DEFAULT_TIMEOUT = 20
MAX_TIMEOUT = 120
OUTPUT_LIMIT = 8000

EXTRA_BIN_DIRS = ("~/.codebuddy/bin", "~/.local/bin", "/opt/homebrew/bin",
                  "/usr/local/bin", "/opt/local/bin")

LOCAL_CLIENTS: dict[str, dict] = {
    "openclaw": {
        "name": "OpenClaw",
        "command": "openclaw",
        "probe_args": "--version",
        "desc": "本地 OpenClaw CLI：Agent / 技能 / 会话运行时，全部在本机执行，业务数据不出本机。",
        "install_hint": "确认终端可执行 `openclaw --version`；不在 PATH 时填写绝对路径（如 ~/.codebuddy/bin/openclaw）。",
        "capabilities": ["agent.run", "skills.list", "session.run"],
    },
    "anygen": {
        "name": "AnyGen",
        "command": "anygen",
        "probe_args": "--version",
        "desc": "本地 AnyGen CLI：素材与内容批量生成；产出只作为草稿，需人工审核后发布。",
        "install_hint": "确认终端可执行 `anygen --version`；不在 PATH 时填写绝对路径。",
        "capabilities": ["content.generate", "batch.render"],
    },
    "workbuddy": {
        "name": "WorkBuddy",
        "command": "workbuddy",
        "probe_args": "--version",
        "desc": "本地 WorkBuddy CLI：任务编排与自动化执行；输出进入审核队列后方可对外。",
        "install_hint": "确认终端可执行 `workbuddy --version`；不在 PATH 时填写绝对路径。",
        "capabilities": ["task.run", "workflow.list"],
    },
}

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def local_settings(settings: dict | None = None) -> dict:
    return dict((settings or {}).get(LOCAL_KEY) or {})


def _default_cfg(client_id: str) -> dict:
    meta = LOCAL_CLIENTS.get(client_id, {})
    return {"enabled": False, "command": meta.get("command", ""),
            "probe_args": meta.get("probe_args", "--version"), "workdir": "",
            "timeout": DEFAULT_TIMEOUT, "env": {}}


def clean_local_cfg(cfg: dict) -> dict:
    """校验并归一化本地 CLI 配置（超时夹紧、env key 白名单、路径去空格）。"""
    out = dict(cfg or {})
    out["enabled"] = bool(out.get("enabled"))
    out["command"] = str(out.get("command") or "").strip()
    out["probe_args"] = str(out.get("probe_args") or "").strip()
    out["workdir"] = str(out.get("workdir") or "").strip()
    try:
        out["timeout"] = max(1, min(MAX_TIMEOUT, int(out.get("timeout") or DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        out["timeout"] = DEFAULT_TIMEOUT
    env: dict[str, str] = {}
    raw_env = out.get("env") or {}
    if isinstance(raw_env, dict):
        for k, v in raw_env.items():
            if isinstance(k, str) and ENV_KEY_RE.match(k):
                env[k] = str(v)
    out["env"] = env
    return out


def resolve_command(command: str) -> str | None:
    """解析可执行文件路径：绝对路径直接校验，命令名走 PATH + 常见安装目录。"""
    raw = (command or "").strip()
    if not raw:
        return None
    path = Path(os.path.expanduser(raw))
    if path.is_absolute() or "/" in raw:
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    found = shutil.which(raw)
    if found:
        return found
    for d in EXTRA_BIN_DIRS:
        cand = Path(os.path.expanduser(d)) / raw
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def client_cfg(client_id: str, settings: dict | None = None) -> dict:
    """内置默认 + 用户配置 + 归一化校验（命令/探测参数为空时回落到默认值）。"""
    cfg = clean_local_cfg({**_default_cfg(client_id),
                           **(local_settings(settings).get(client_id) or {})})
    meta = LOCAL_CLIENTS.get(client_id, {})
    if not cfg["command"]:
        cfg["command"] = meta.get("command", "")
    if not cfg["probe_args"]:
        cfg["probe_args"] = meta.get("probe_args", "--version")
    return cfg


def provider_by_id(provider_id: str, settings: dict | None = None) -> dict | None:
    """按 id 取提供商（含内置默认值）。"""
    return next((p for p in _merge_builtins(llm_settings(settings)["providers"])
                 if p.get("id") == provider_id), None)


def local_state(settings: dict | None = None) -> dict:
    cfg_all = local_settings(settings)
    out: dict[str, dict] = {}
    for cid, meta in LOCAL_CLIENTS.items():
        cfg = client_cfg(cid, settings)
        resolved = resolve_command(cfg["command"])
        out[cid] = {
            "id": cid,
            "name": meta["name"],
            "desc": meta["desc"],
            "install_hint": meta["install_hint"],
            "capabilities": meta["capabilities"],
            "enabled": cfg["enabled"],
            "command": cfg["command"],
            "probe_args": cfg["probe_args"],
            "workdir": cfg["workdir"],
            "timeout": cfg["timeout"],
            "env_keys": sorted(cfg["env"].keys()),
            "resolved": resolved,
            "installed": bool(resolved),
            "ready": bool(resolved) and cfg["enabled"],
            "last_probe": cfg.get("last_probe"),
        }
    return out


def _split(args: str | None) -> list[str]:
    text = (args or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _truncate(text: str | None) -> str:
    s = text or ""
    return s if len(s) <= OUTPUT_LIMIT else s[:OUTPUT_LIMIT] + "\n…(输出已截断)"


def run_local(client_id: str, settings: dict | None = None, args: str | None = None,
              timeout: int | None = None) -> dict:
    """以 shell=False 执行本地 CLI（args 为空时使用探测参数）。"""
    meta = LOCAL_CLIENTS.get(client_id)
    if not meta:
        return {"ok": False, "mode": "error", "client": client_id,
                "error": f"未知本地 CLI：{client_id}"}
    cfg = client_cfg(client_id, settings)
    base = {"client": client_id, "name": meta["name"]}
    if not cfg["enabled"]:
        return {"ok": False, "mode": "disabled", **base,
                "error": f"{meta['name']} 连接器未启用"}
    executable = resolve_command(cfg["command"])
    if not executable:
        return {"ok": False, "mode": "error", **base, "command": cfg["command"],
                "error": f"未找到可执行文件：{cfg['command'] or '(空)'}",
                "hint": meta["install_hint"]}
    argv = [executable] + _split(args if args is not None else cfg["probe_args"])
    limit = max(1, min(MAX_TIMEOUT, int(timeout or cfg["timeout"])))
    cwd = None
    if cfg["workdir"]:
        wd = Path(os.path.expanduser(cfg["workdir"]))
        if not wd.is_dir():
            return {"ok": False, "mode": "error", **base, "command": " ".join(argv),
                    "error": f"工作目录不存在：{cfg['workdir']}"}
        cwd = str(wd)
    env = os.environ.copy()
    env.update(cfg["env"])
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                              timeout=limit, shell=False, check=False)
        return {"ok": proc.returncode == 0, "mode": "live", **base,
                "command": " ".join(argv), "exit_code": proc.returncode,
                "stdout": _truncate(proc.stdout), "stderr": _truncate(proc.stderr),
                "duration_ms": int((time.time() - started) * 1000),
                "verification_status": "unverified"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "mode": "error", **base, "command": " ".join(argv),
                "error": f"执行超时（>{limit}s）", "duration_ms": int((time.time() - started) * 1000)}
    except (OSError, ValueError) as e:
        return {"ok": False, "mode": "error", **base, "command": " ".join(argv),
                "error": f"{type(e).__name__}: {e}"[:300]}


def probe_local(client_id: str, settings: dict | None = None) -> dict:
    return run_local(client_id, settings)


def probe_summary(result: dict) -> dict:
    return {"ok": bool(result.get("ok")), "mode": result.get("mode"),
            "at": now_iso(), "detail": result.get("error") or result.get("stdout", "")[:200]}
