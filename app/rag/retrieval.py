"""Hybrid retrieval: BM25 (exact words/numbers) + dense embeddings (meaning), merged by reciprocal rank fusion."""
import re

import numpy as np

from app.config import settings
from app.rag.vector_store import VectorStore, tokenize

MAX_PER_URL = 3


class Retriever:
    def __init__(self):
        self.store = VectorStore(settings.chunks_path, settings.embeddings_path)

    @property
    def has_dense(self) -> bool:
        return self.store.emb is not None

    @staticmethod
    def _source_filter(q: str):
        ql = q.lower()
        wasalt, dar = "wasalt" in ql, "darglobal" in ql or "dar global" in ql
        if wasalt and not dar:
            return "Wasalt"
        if dar and not wasalt:
            return "DarGlobal"
        return None

    def search(self, query: str, k: int | None = None) -> list[dict]:
        k = k or settings.top_k
        s = self.store
        n = len(s.chunks)
        src = self._source_filter(query)
        mask = np.array([(src is None or c["source"] == src) for c in s.chunks])

        rankings = [np.where(mask, s.bm25.scores(tokenize(query)), -1)]
        if self.has_dense:
            from app.rag.embeddings import embed
            rankings.append(np.where(mask, s.emb @ embed([query])[0], -1))

        fused = np.zeros(n)
        for sc in rankings:
            for rank, i in enumerate(np.argsort(-sc)[:30]):
                if sc[i] > 0:
                    fused[i] += 1.0 / (60 + rank)

        # structured boost: listings that match the requested bedroom count / sale-vs-rent intent
        ql = query.lower()
        m = re.search(r"(\d+)\s*[- ]?\s*(?:bed|br\b)", ql)
        beds = m.group(1) if m else None
        purpose = "rent" if re.search(r"\b(rent|rental|lease)\b", ql) else \
                  "sale" if re.search(r"\b(buy|sale|purchase)\b", ql) else None
        if beds or purpose:
            for i, c in enumerate(s.chunks):
                if c["kind"] != "listing" or fused[i] <= 0:
                    continue
                if beds and re.search(rf"\b{beds} bedrooms?\b", c["text"][:400].lower()):
                    fused[i] += 0.02
                if purpose and c.get("purpose") == purpose:
                    fused[i] += 0.02

        out, per_url = [], {}
        for i in np.argsort(-fused):
            if fused[i] <= 0 or len(out) >= k:
                break
            c = s.chunks[i]
            if per_url.get(c["url"], 0) >= MAX_PER_URL:
                continue
            per_url[c["url"]] = per_url.get(c["url"], 0) + 1
            out.append({**c, "score": float(fused[i])})
        return out
