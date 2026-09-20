"""Global Eagle GEO - Shared Context 持久化存储.

所有 Agent 共享同一份 Context（实体库 / 证据库 / 运行记录 / 线索 / 审核队列 / 审计日志）。
任何 Agent 不得建立孤立事实库；所有输出均可回写 Shared Context。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable

LIST_COLLECTIONS = (
    "entities", "sources", "claims", "runs", "leads", "rfqs",
    "approvals", "audit", "monitoring", "feedback", "weights_history",
)
DICT_COLLECTIONS = ("settings", "weights", "company", "graph_cache")


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.data: dict[str, Any] = {}
        for name in LIST_COLLECTIONS:
            self.data[name] = self._load(name, [])
        for name in DICT_COLLECTIONS:
            self.data[name] = self._load(name, {})

    # ---------- persistence ----------
    def _path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def _load(self, name: str, default: Any) -> Any:
        p = self._path(name)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return default
        return default

    def save(self, name: str | None = None) -> None:
        with self._lock:
            names = [name] if name else list(self.data.keys())
            for n in names:
                self._path(n).write_text(
                    json.dumps(self.data[n], ensure_ascii=False, indent=2), encoding="utf-8"
                )

    # ---------- generic ops ----------
    def all(self, name: str) -> list[dict]:
        with self._lock:
            return list(self.data.get(name, []))

    def add(self, name: str, item: dict) -> dict:
        with self._lock:
            self.data.setdefault(name, []).append(item)
            self.save(name)
            return item

    def add_many(self, name: str, items: Iterable[dict]) -> list[dict]:
        items = list(items)
        with self._lock:
            self.data.setdefault(name, []).extend(items)
            self.save(name)
        return items

    def update(self, name: str, item_id: str, patch: dict, id_key: str = "id") -> dict | None:
        with self._lock:
            for item in self.data.get(name, []):
                if item.get(id_key) == item_id:
                    item.update(patch)
                    self.save(name)
                    return item
        return None

    def get(self, name: str, item_id: str, id_key: str = "id") -> dict | None:
        for item in self.all(name):
            if item.get(id_key) == item_id:
                return item
        return None

    def find(self, name: str, **kwargs) -> list[dict]:
        out = []
        for item in self.all(name):
            if all(item.get(k) == v for k, v in kwargs.items()):
                out.append(item)
        return out

    def set_dict(self, name: str, patch: dict) -> dict:
        with self._lock:
            self.data.setdefault(name, {}).update(patch)
            self.save(name)
            return self.data[name]

    # ---------- domain helpers ----------
    def claims_for_entity(self, entity_id: str) -> list[dict]:
        return [c for c in self.all("claims") if c.get("entity_id") == entity_id]

    def sources_by_ids(self, ids: list[str]) -> list[dict]:
        return [s for s in self.all("sources") if s.get("id") in set(ids)]

    def reset(self, keep: tuple[str, ...] = ()) -> None:
        for name in LIST_COLLECTIONS:
            if name in keep:
                continue
            self.data[name] = []
        for name in DICT_COLLECTIONS:
            if name in keep:
                continue
            self.data[name] = {}
        self.save()
