"""Global Eagle GEO - 可选 LLM 适配器.

系统默认全部使用「规则化 + 证据驱动」的确定性生成，保证无 Key 也可运行。
配置 OPENAI_API_KEY / ANTHROPIC_API_KEY 后可用于润色 AI Answer（仍受证据约束）。
"""
from __future__ import annotations

import json
import os
import urllib.request

TIMEOUT = 30


class LLMAdapter:
    def __init__(self) -> None:
        self.provider = None
        if os.getenv("OPENAI_API_KEY"):
            self.provider = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            self.provider = "anthropic"

    @property
    def available(self) -> bool:
        return self.provider is not None

    def complete(self, system: str, user: str, max_tokens: int = 900) -> str | None:
        if not self.available:
            return None
        try:
            if self.provider == "openai":
                return self._openai(system, user, max_tokens)
            return self._anthropic(system, user, max_tokens)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _post(url: str, headers: dict, payload: dict) -> str:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", "ignore")

    def _openai(self, system: str, user: str, max_tokens: int) -> str | None:
        raw = self._post("https://api.openai.com/v1/chat/completions",
                         {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
                         {"model": os.getenv("GEO_OPENAI_MODEL", "gpt-4o-mini"),
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user}],
                          "max_tokens": max_tokens})
        data = json.loads(raw)
        return data.get("choices", [{}])[0].get("message", {}).get("content")

    def _anthropic(self, system: str, user: str, max_tokens: int) -> str | None:
        raw = self._post("https://api.anthropic.com/v1/messages",
                         {"x-api-key": os.getenv("ANTHROPIC_API_KEY") or "",
                          "anthropic-version": "2023-06-01"},
                         {"model": os.getenv("GEO_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                          "system": system, "max_tokens": max_tokens,
                          "messages": [{"role": "user", "content": user}]})
        data = json.loads(raw)
        return "".join(b.get("text", "") for b in data.get("content", []))
