"""Global Eagle GEO - 轻量向量召回（TF-IDF + 余弦相似度，零外部依赖）.

生产环境可替换为 Milvus / pgvector，接口保持一致：fit(docs) -> search(query, top_k)。
"""
from __future__ import annotations

import math
from collections import Counter

from .util import tokenize


class TfidfIndex:
    """内存倒排索引。docs: {doc_id: text}"""

    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.tf: dict[str, Counter] = {}
        self.idf: dict[str, float] = {}
        self.norm: dict[str, float] = {}

    def fit(self, docs: dict[str, str]) -> "TfidfIndex":
        self.docs = dict(docs)
        self.tf = {k: Counter(tokenize(v)) for k, v in docs.items()}
        n = max(len(docs), 1)
        df: Counter = Counter()
        for counter in self.tf.values():
            df.update(counter.keys())
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}
        self.norm = {}
        for k, counter in self.tf.items():
            vec = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in counter.items()}
            self.norm[k] = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.tf[k] = vec  # type: ignore[assignment]
        return self

    def _vector(self, text: str) -> dict[str, float]:
        counter = Counter(tokenize(text))
        return {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in counter.items()}

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        qv = self._vector(query)
        if not qv:
            return []
        qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0
        scores = []
        for doc_id, vec in self.tf.items():  # type: ignore[assignment]
            common = set(qv) & set(vec)
            num = sum(qv[t] * vec[t] for t in common)
            denom = qn * (self.norm.get(doc_id) or 1.0)
            if denom:
                scores.append((doc_id, num / denom))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(d, s) for d, s in scores if s > 0][:top_k]
