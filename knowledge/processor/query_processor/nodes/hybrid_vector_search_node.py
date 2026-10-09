from knowledge.processor.query_processor.base import BaseNode
from knowledge.utils.retrieval import retrieve


class HybridVectorSearch(BaseNode):
    name = "hybrid_vector_search_node"

    def process(self, state):
        try:
            docs = retrieve(
                state["rewritten_query"],
                state,
                "dense" if state.get("retrieval_mode") == "dense" else "hybrid",
            )
            return {"embedding_chunks": docs, "hybrid_status": "completed"}
        except Exception as exc:
            return {
                "embedding_chunks": [],
                "hybrid_status": "failed:" + type(exc).__name__,
            }
