"""Real FlagEmbedding adapters, shared by ingestion and retrieval.

The sparse weights are learned BGE-M3 lexical weights, not BM25.
Imports are deferred until first use; missing dependencies remain explicit errors.
"""

import os
from pathlib import Path
from threading import RLock
from typing import TypedDict
import numpy as np
from scipy.sparse import csr_array

GPU_LOCK = RLock()
DIMENSION = 1024


class HybridVectors(TypedDict):
    dense: np.ndarray
    sparse: csr_array


def model_directory(value: str) -> str:
    path = Path(value).resolve()
    if not path.is_dir() or not (path / "config.json").is_file():
        raise FileNotFoundError("Local model directory is missing or incomplete")
    if (
        not any(path.glob("*.safetensors"))
        and not (path / "pytorch_model.bin").is_file()
    ):
        raise FileNotFoundError("Local model weights are missing")
    return str(path)


class BGEM3EmbeddingFunction:
    def __init__(self, model_name: str, device: str, use_fp16: bool):
        from FlagEmbedding import BGEM3FlagModel

        with GPU_LOCK:
            self.model = BGEM3FlagModel(
                model_directory(model_name), devices=device, use_fp16=use_fp16
            )
        self.dim = {"dense": DIMENSION}

    def encode_documents(self, documents: list[str]) -> HybridVectors:
        if not documents or any(
            not isinstance(x, str) or not x.strip() for x in documents
        ):
            raise ValueError("Embedding requires nonempty text strings")
        with GPU_LOCK:
            result = self.model.encode(
                documents,
                batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "4")),
                max_length=int(os.getenv("EMBEDDING_MAX_LENGTH", "2048")),
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
        dense = np.asarray(result["dense_vecs"], dtype=np.float32)
        weights = result["lexical_weights"]
        if dense.shape != (len(documents), DIMENSION) or not np.isfinite(dense).all():
            raise ValueError("BGE dense vector count, dimension or values are invalid")
        if len(weights) != len(documents):
            raise ValueError("BGE sparse vector count mismatch")
        data, indices, indptr = [], [], [0]
        for row in weights:
            if not row:
                raise ValueError("BGE returned an empty sparse vector")
            for key, value in sorted(row.items(), key=lambda item: int(item[0])):
                index, weight = int(key), float(value)
                if index < 0 or not np.isfinite(weight) or weight <= 0:
                    raise ValueError("BGE returned an invalid sparse weight")
                indices.append(index)
                data.append(weight)
            indptr.append(len(data))
        sparse = csr_array(
            (
                np.asarray(data, dtype=np.float32),
                np.asarray(indices),
                np.asarray(indptr),
            ),
            shape=(len(documents), max(indices) + 1),
        )
        return {"dense": dense, "sparse": sparse}

    encode_queries = encode_documents


class LocalReranker:
    def __init__(self, path: str, device: str, use_fp16: bool):
        from FlagEmbedding import FlagReranker

        with GPU_LOCK:
            self.model = FlagReranker(
                model_directory(path), devices=device, use_fp16=use_fp16
            )

    def compute_score(self, pairs: list[list[str]]):
        with GPU_LOCK:
            # BGE-reranker-large is an XLM-R encoder with a 512-token pair budget.
            # Larger values can trigger position overflow hidden by FlagEmbedding's batch retry.
            return self.model.compute_score(
                pairs, batch_size=4, max_length=512, normalize=False
            )
