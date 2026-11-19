"""all-MiniLM-L6-v2 via onnxruntime + tokenizers directly (no chromadb, no torch)."""
import tarfile
from pathlib import Path

import httpx
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
BASE = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
MODEL_DIR = BASE / "onnx"
_sess = _tok = None


def _load():
    global _sess, _tok
    if _sess is not None:
        return
    if not (MODEL_DIR / "model.onnx").exists():
        BASE.mkdir(parents=True, exist_ok=True)
        tgz = BASE / "onnx.tar.gz"
        with httpx.stream("GET", URL, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            with open(tgz, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        with tarfile.open(tgz) as t:
            t.extractall(BASE, filter="data")
        tgz.unlink()
    _tok = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    _tok.enable_truncation(max_length=256)
    _tok.enable_padding(pad_id=0, pad_token="[PAD]")
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.enable_cpu_mem_arena = False          # lower RAM on small instances
    so.intra_op_num_threads = 1
    _sess = ort.InferenceSession(str(MODEL_DIR / "model.onnx"), so, providers=["CPUExecutionProvider"])


def embed(texts: list[str], batch: int = 32) -> np.ndarray:
    _load()
    out = []
    for i in range(0, len(texts), batch):
        enc = _tok.encode_batch(texts[i:i + batch])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        hid = _sess.run(None, {"input_ids": ids, "attention_mask": mask,
                               "token_type_ids": np.zeros_like(ids)})[0]
        m = mask[..., None].astype(np.float32)
        out.append((hid * m).sum(1) / np.clip(m.sum(1), 1e-9, None))   # masked mean pooling
    v = np.vstack(out).astype(np.float32)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)