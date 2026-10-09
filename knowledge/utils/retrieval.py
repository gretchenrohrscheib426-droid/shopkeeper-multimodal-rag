import json
from pymilvus import AnnSearchRequest, WeightedRanker
from knowledge.core.configuration import required
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors

OUTPUT_FIELDS = [
    "chunk_id",
    "document_id",
    "source_id",
    "version",
    "owner",
    "content",
    "title",
    "parent_title",
    "file_title",
    "item_name",
    "entity_type",
    "char_start",
    "char_end",
    "span_basis",
    "source_url",
    "image_ids",
    "embedding_model",
    "embedding_revision",
]


def scope_filter(owner: str, scope: list[dict]) -> str:
    if not scope:
        raise ValueError("Retrieval requires an authorized document scope")
    parts = [
        f"(document_id == {json.dumps(d['document_id'])} and version == {json.dumps(d['version'])})"
        for d in scope
    ]
    return f"owner == {json.dumps(owner)} and (" + " or ".join(parts) + ")"


def retrieve(
    text: str, state: dict, route: str, collection: str | None = None
) -> list[dict]:
    if not text.strip():
        raise ValueError("Empty retrieval query")
    limit = state.get("candidate_limit", 10)
    if not 1 <= limit <= 50:
        raise ValueError("Invalid candidate budget")
    scope = state["document_scope"]
    revision = required("EMBEDDING_MODEL_REVISION")
    if any(d["embedding_revision"] != revision for d in scope):
        raise ValueError("Index/query embedding revision mismatch")
    vectors = generate_bge_m3_hybrid_vectors(AIClients.get_bge_m3_client(), [text])
    client = StorageClients.get_milvus_client()
    collection = collection or required("CHUNKS_COLLECTION")
    expr = scope_filter(state["owner"], scope)
    if state.get("retrieval_mode") == "dense":
        hits = client.search(
            collection,
            data=vectors["dense"],
            anns_field="dense_vector",
            filter=expr,
            search_params={"metric_type": "COSINE"},
            limit=limit,
            output_fields=OUTPUT_FIELDS,
            consistency_level="Strong",
        )
    else:
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
        hits = client.hybrid_search(
            collection,
            reqs=requests,
            ranker=WeightedRanker(0.5, 0.5),
            limit=limit,
            output_fields=OUTPUT_FIELDS,
            consistency_level="Strong",
        )
    allowed = {c for d in scope for c in d["chunk_ids"]}
    docs = []
    for rank, hit in enumerate(hits[0] if hits else [], 1):
        entity = dict(hit["entity"])
        identity = str(entity.get("chunk_id") or hit["id"])
        if identity not in allowed:
            continue
        if entity.get("owner") != state["owner"]:
            raise PermissionError("Unauthorized retrieval result")
        docs.append(
            {
                **entity,
                "chunk_id": identity,
                "source": "local",
                "retrieval_route": route,
                "retrieval_rank": rank,
                "retrieval_score": float(hit["distance"]),
            }
        )
    return docs
