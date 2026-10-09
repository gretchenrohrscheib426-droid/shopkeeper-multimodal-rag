import math
import numpy as np
from knowledge.processor.query_processor.base import BaseNode
from knowledge.utils.client.ai_clients import AIClients


def normalize_scores(raw, count: int) -> list[float]:
    values = np.asarray(raw, dtype=float).reshape(-1)
    if len(values) != count or not np.isfinite(values).all():
        raise ValueError("Reranker score count or values are invalid")
    return [float(v) for v in values]


def sigmoid(value: float) -> float:
    return (
        1 / (1 + math.exp(-value))
        if value >= 0
        else math.exp(value) / (1 + math.exp(value))
    )


class RerankerNode(BaseNode):
    name = "reranker_node"

    def process(self, state):
        # Course detailed design: only local+HyDE enter RRF; Web joins here.
        docs = [*state.get("rrf_chunks", []), *state.get("web_search_docs", [])]
        unique = {d["chunk_id"]: d for d in docs}
        docs = list(unique.values())
        if not docs:
            return {"reranked_docs": []}
        if state.get("retrieval_mode") != "rerank":
            return {"reranked_docs": docs[: self.config.rerank_max_top_k]}
        scores = normalize_scores(
            AIClients.get_bge_m3_rerank_client().compute_score(
                [[state["rewritten_query"], d["content"]] for d in docs]
            ),
            len(docs),
        )
        ranked = sorted(
            [
                {**d, "rerank_score": s, "rerank_normalized": sigmoid(s)}
                for d, s in zip(docs, scores, strict=True)
            ],
            key=lambda d: (-d["rerank_score"], d["chunk_id"]),
        )
        maximum = self.config.rerank_max_top_k
        minimum = self.config.rerank_min_top_k
        if not 1 <= minimum <= maximum:
            raise ValueError("Invalid rerank top-k settings")
        chosen = ranked[:maximum]
        for index in range(minimum, len(chosen)):
            gap = (
                chosen[index - 1]["rerank_normalized"]
                - chosen[index]["rerank_normalized"]
            )
            if (
                gap >= self.config.rerank_gap_abs
                and gap
                >= self.config.rerank_gap_ratio
                * max(chosen[index - 1]["rerank_normalized"], 1e-12)
            ):
                chosen = chosen[:index]
                break
        return {"reranked_docs": chosen}
