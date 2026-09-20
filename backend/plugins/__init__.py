"""外部插件 / 连接器命名空间。

插件统一遵循两条底线：
1. Evidence First：未配置凭据时返回 mode='disabled'，绝不返回编造数据。
2. Human-in-the-loop：对外发布类动作只生成草稿，需人工审核后使用。
"""
from __future__ import annotations

from . import redditgrow  # noqa: F401

__all__ = ["redditgrow"]
