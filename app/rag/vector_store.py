"""Tiny in-memory store: chunks + BM25 index + optional dense embeddings (numpy).
495 chunks don't need a vector database; a matrix product is instant."""
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an the of in on at to for and or is are was were be do does did what which who whom how where when "
           "with by from as it its this that these those i you we they me my your can could would should about "
           "tell give show any there their has have had not no yes".split())


def tokenize(text: str) -> list[str]:
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())        # 1,050,000 -> 1050000
    toks = _TOKEN.findall(text)
    toks = [t for t in toks if t not in STOP]
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks]   # crude plural stemming


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avg = float(self.len.mean()) or 1.0
        df = Counter(t for d in self.tf for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        s = np.zeros(len(self.tf), dtype=np.float32)
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s


class VectorStore:
    def __init__(self, chunks_path: str, embeddings_path: str):
        self.chunks = [json.loads(l) for l in open(chunks_path, encoding="utf-8")]
        self.bm25 = BM25([tokenize(c["text"]) for c in self.chunks])
        p = Path(embeddings_path)
        self.emb = np.load(p) if p.exists() else None
        if self.emb is not None and len(self.emb) != len(self.chunks):
            raise ValueError("embeddings.npy is out of date: re-run python -m app.rag.build_index")
