"""Version-scoped dense/sparse topic retrieval; scores are ranking heuristics."""

import math
from pymilvus import AnnSearchRequest, WeightedRanker
from knowledge.core.configuration import required
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors
from knowledge.utils.retrieval import scope_filter


def retrieve_topics(
    query: str, owner: str, documents: list[dict], limit: int = 3
) -> list[dict]:
    indexed = [d for d in documents if d.get("entity_vector_id")]
    if not indexed:
        return []  # Explicit compatibility: older manifests have no topic index.
    if any(
        d["embedding_revision"] != required("EMBEDDING_MODEL_REVISION") for d in indexed
    ):
        raise ValueError("Entity/query embedding revision mismatch")
    vectors = generate_bge_m3_hybrid_vectors(AIClients.get_bge_m3_client(), [query])
    expr = scope_filter(owner, indexed)
    requests = [
        AnnSearchRequest(
            data=vectors["dense"],
            anns_field="dense_vector",
            param={"metric_type": "COSINE"},
            expr=expr,
            limit=limit,
        ),
        AnnSearchRequest(
            data=vectors["sparse"],
            anns_field="sparse_vector",
            param={"metric_type": "IP"},
            expr=expr,
            limit=limit,
        ),
    ]
    hits = StorageClients.get_milvus_client().hybrid_search(
        required("ENTITY_NAME_COLLECTION"),
        reqs=requests,
        ranker=WeightedRanker(0.5, 0.5),
        limit=limit,
        output_fields=["chunk_id", "document_id", "version", "owner"],
        consistency_level="Strong",
    )
    allowed = {d["entity_vector_id"]: d for d in indexed}
    results = []
    for hit in hits[0] if hits else []:
        # MilvusClient 2.5 returns the schema primary-key name, not always `id`.
        identity = hit["entity"].get("chunk_id") or hit.get("chunk_id") or hit.get("id")
        if identity is None:
            raise ValueError("Topic result is missing its primary key")
        document = allowed.get(str(identity))
        score = float(hit["distance"])
        if not document:
            continue
        if hit["entity"]["owner"] != owner:
            raise PermissionError("Unauthorized topic result")
        if not math.isfinite(score):
            raise ValueError("Invalid topic retrieval score")
        results.append(
            {
                "document_id": document["document_id"],
                "label": document["file_title"],
                "item_name": document["item_name"],
                "retrieval_score": score,
            }
        )
    return results
