from pathlib import Path

import numpy as np

from app.config import settings
from app.rag.embeddings import embed
from app.rag.vector_store import VectorStore


def main():
    store = VectorStore(settings.chunks_path, "does-not-exist")
    vecs = embed([c["text"] for c in store.chunks])
    Path(settings.embeddings_path).parent.mkdir(parents=True, exist_ok=True)
    np.save(settings.embeddings_path, vecs)
    print("saved", vecs.shape, "->", settings.embeddings_path)


if __name__ == "__main__":
    main()

