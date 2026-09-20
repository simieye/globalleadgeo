"""Global Eagle GEO - 可选 LLM 适配器（支持自定义大模型提供商）。

系统默认全部使用「规则化 + 证据驱动」的确定性生成，保证无 Key 也可运行。
在系统设置中配置提供商（OpenAI / Anthropic / 任意 OpenAI 兼容网关）后，
可用于润色 AI Answer（仍受证据约束，不生成未证实结论）。

优先级：系统设置中的提供商 > 环境变量（OPENAI_API_KEY / ANTHROPIC_API_KEY）。
多个已启用提供商按「默认优先」顺序尝试，任一成功即返回。
"""
from __future__ import annotations

import time
from typing import Any

from . import net, settings as settings_core


class LLMAdapter:
    def __init__(self, providers: list[dict] | None = None, default: str | None = None,
                 settings: dict | None = None, timeout: int = 45) -> None:
        if settings is None and (providers or default):
            settings = {settings_core.LLM_KEY: {"providers": providers or [], "default": default}}
        self.candidates: list[dict] = settings_core.llm_candidates(settings)
        self.timeout = timeout
        self.provider: str | None = self.candidates[0]["id"] if self.candidates else None
        self.last_latency_ms: int = 0

    @classmethod
    def from_store(cls, store: Any) -> "LLMAdapter":
        """从 Shared Context 的 settings 构建（设置在界面修改后立即生效）。"""
        return cls(settings=store.data.get("settings", {}))

    @property
    def available(self) -> bool:
        return bool(self.candidates)

    def complete(self, system: str, user: str, max_tokens: int = 900) -> str | None:
        if not self.available:
            return None
        for cfg in self.candidates:
            started = time.time()
            try:
                if cfg.get("type") == "anthropic":
                    out = self._anthropic(cfg, system, user, max_tokens)
                else:
                    out = self._chat(cfg, system, user, max_tokens)
            except Exception:  # noqa: BLE001 - 单个提供商失败时回退下一个
                out = None
            if out:
                self.provider = cfg.get("id")
                self.last_latency_ms = int((time.time() - started) * 1000)
                return out
        return None

    # ---------- transports ----------
    def _chat(self, cfg: dict, system: str, user: str, max_tokens: int) -> str | None:
        base = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        status, data, _ = net.json_request(
            "POST", f"{base}/chat/completions",
            {"Authorization": f"Bearer {cfg.get('api_key', '')}",
             "Content-Type": "application/json"},
            {"model": cfg.get("model") or "gpt-4o-mini",
             "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": user}],
             "max_tokens": max_tokens},
            timeout=self.timeout)
        if status >= 400 or not isinstance(data, dict):
            return None
        choices = data.get("choices") or []
        if not choices:
            return None
        return (choices[0].get("message") or {}).get("content")

    def _anthropic(self, cfg: dict, system: str, user: str, max_tokens: int) -> str | None:
        base = (cfg.get("base_url") or "https://api.anthropic.com/v1").rstrip("/")
        status, data, _ = net.json_request(
            "POST", f"{base}/messages",
            {"x-api-key": cfg.get("api_key", ""),
             "Authorization": f"Bearer {cfg.get('api_key', '')}",
             "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            {"model": cfg.get("model") or "claude-3-5-sonnet-latest",
             "system": system, "max_tokens": max_tokens,
             "messages": [{"role": "user", "content": user}]},
            timeout=self.timeout)
        if status >= 400 or not isinstance(data, dict):
            return None
        return "".join(b.get("text", "") for b in data.get("content", [])
                       if isinstance(b, dict))
