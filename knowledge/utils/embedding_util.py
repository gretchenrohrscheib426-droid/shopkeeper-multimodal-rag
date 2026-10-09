"""Validate the complete dense/sparse contract before any database write."""

from typing import Protocol, TypedDict
import numpy as np
from knowledge.utils.client.local_models import HybridVectors, DIMENSION


class EmbeddingModel(Protocol):
    def encode_documents(self, documents: list[str]) -> HybridVectors: ...


class VectorLists(TypedDict):
    dense: list[list[float]]
    sparse: list[dict[int, float]]


def generate_bge_m3_hybrid_vectors(
    model: EmbeddingModel, embedding_documents: list[str]
) -> VectorLists:
    if not embedding_documents or any(
        not isinstance(x, str) or not x.strip() for x in embedding_documents
    ):
        raise ValueError("Embedding input must contain nonempty text strings")
    result = model.encode_documents(embedding_documents)
    dense = np.asarray(result["dense"], dtype=np.float32)
    sparse = result["sparse"].tocsr()
    if (
        dense.shape != (len(embedding_documents), DIMENSION)
        or not np.isfinite(dense).all()
    ):
        raise ValueError("Dense count/dimension/values are invalid")
    if np.any(np.linalg.norm(dense, axis=1) == 0):
        raise ValueError("Zero dense vector is invalid")
    if (
        sparse.shape[0] != len(embedding_documents)
        or not np.isfinite(sparse.data).all()
    ):
        raise ValueError("Sparse count/values are invalid")
    rows = []
    for i in range(len(embedding_documents)):
        start, end = sparse.indptr[i : i + 2]
        row = {
            int(k): float(v)
            for k, v in zip(
                sparse.indices[start:end], sparse.data[start:end], strict=True
            )
        }
        if not row or any(k < 0 or v <= 0 for k, v in row.items()):
            raise ValueError("Sparse vector must contain positive finite weights")
        rows.append(row)
    return {"dense": dense.tolist(), "sparse": rows}
