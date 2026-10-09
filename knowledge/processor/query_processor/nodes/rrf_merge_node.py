from knowledge.processor.query_processor.base import BaseNode


def fuse(routes: list[list[dict]], k: int = 60, limit: int = 10) -> list[dict]:
    if k < 1 or limit < 0:
        raise ValueError("Invalid RRF k or limit")
    if limit == 0:
        return []
    merged = {}
    for route_index, route in enumerate(routes):
        seen = set()
        for rank, hit in enumerate(route, 1):
            doc = hit.get("entity", hit)
            identity = doc.get("chunk_id", hit.get("id"))
            if identity is None:
                raise ValueError("RRF candidate has no stable identity")
            identity = str(identity)
            if identity in seen:
                continue
            seen.add(identity)
            item = merged.setdefault(
                identity,
                {**doc, "chunk_id": identity, "rrf_score": 0.0, "route_ranks": {}},
            )
            item["rrf_score"] += 1 / (k + rank)
            item["route_ranks"][str(route_index)] = rank
    return sorted(merged.values(), key=lambda d: (-d["rrf_score"], d["chunk_id"]))[
        :limit
    ]


class RrfMergeNode(BaseNode):
    name = "rrf_merge_node"

    def process(self, state):
        statuses = [state.get("hybrid_status", ""), state.get("hyde_status", "")]
        if not any(s == "completed" for s in statuses):
            raise RuntimeError("All local retrieval branches failed")
        return {
            "rrf_chunks": fuse(
                [
                    state.get("embedding_chunks", []),
                    state.get("hyde_embedding_chunks", []),
                ],
                self.config.rrf_k,
                state.get("candidate_limit", self.config.rrf_max_results),
            )
        }
