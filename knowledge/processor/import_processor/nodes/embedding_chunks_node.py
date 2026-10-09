import hashlib
from knowledge.core.configuration import required
from knowledge.core.task_store import get_store
from knowledge.processor.import_processor.base import BaseNode
from knowledge.processor.import_processor.state import ImportGraphState
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors


class EmbeddingChunksNode(BaseNode):
    name = "embedding_chunks_node"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        if not state.get("chunks"):
            raise ValueError("No chunks to embed")
        model = AIClients.get_bge_m3_client()
        chunks = []
        batch_size = self.config.embedding_batch_size
        if batch_size < 1:
            raise ValueError("Invalid embedding batch size")
        for start in range(0, len(state["chunks"]), batch_size):
            get_store().check(state.get("task_id", ""))
            batch = state["chunks"][start : start + batch_size]
            vectors = generate_bge_m3_hybrid_vectors(
                model, [c["content"] for c in batch]
            )
            for chunk, dense, sparse in zip(
                batch, vectors["dense"], vectors["sparse"], strict=True
            ):
                chunks.append(
                    {
                        **chunk,
                        "dense_vector": dense,
                        "sparse_vector": sparse,
                        "embedding_model": "BAAI/bge-m3",
                        "embedding_revision": required("EMBEDDING_MODEL_REVISION"),
                    }
                )
        entity_text = state["item_name"] + "\n" + state["file_title"]
        entity_vectors = generate_bge_m3_hybrid_vectors(model, [entity_text])
        entity = {
            "chunk_id": hashlib.sha256(
                (state["document_id"] + state["version"] + "entity").encode()
            ).hexdigest(),
            "document_id": state["document_id"],
            "version": state["version"],
            "owner": state["owner"],
            "item_name": state["item_name"],
            "content": entity_text,
            "embedding_revision": required("EMBEDDING_MODEL_REVISION"),
            "dense_vector": entity_vectors["dense"][0],
            "sparse_vector": entity_vectors["sparse"][0],
        }
        return {"chunks": chunks, "entity_vector": entity}
