import time
import math
import pytest
from knowledge.processor.query_processor.nodes.rrf_merge_node import fuse, RrfMergeNode
from knowledge.processor.query_processor.nodes.reranker_node import (
    normalize_scores,
    sigmoid,
)
from knowledge.processor.query_processor.nodes.answer_output_node import validate_claims
from knowledge.processor.query_processor.nodes.answer_output_node import (
    generate_grounded_answer,
)
from knowledge.processor.query_processor.nodes.answer_output_node import source_quote
from knowledge.processor.query_processor import main_graph
from knowledge.processor.query_processor.state import create_default_state


def test_rrf_identity_duplicate_and_budget():
    result = fuse(
        [[{"id": 0}, {"id": "a"}, {"id": 0}], [{"id": "a"}, {"id": 0}]], 60, 10
    )
    assert {x["chunk_id"] for x in result} == {"0", "a"}
    assert math.isclose(result[0]["rrf_score"], 1 / 61 + 1 / 62)
    assert fuse([], 60, 0) == []
    assert fuse([[], [{"id": 0}]], 60, 10)[0]["chunk_id"] == "0"
    with pytest.raises(RuntimeError):
        RrfMergeNode().process(
            {
                "hybrid_status": "failed:TimeoutError",
                "hyde_status": "failed:TimeoutError",
            }
        )


@pytest.mark.parametrize(
    "scores,count", [(float("nan"), 1), ([1, 2], 1), ([], 1), ([float("inf")], 1)]
)
def test_rerank_rejects_invalid_contract(scores, count):
    with pytest.raises(ValueError):
        normalize_scores(scores, count)


def test_rerank_scalar_and_extremes():
    assert normalize_scores(-2.3, 1) == [-2.3]
    assert sigmoid(-1000) == 0 and sigmoid(1000) == 1


def test_citations_cannot_invent_source_or_quote():
    evidence = {
        "1": {
            "content": "单个上传文件大小上限为 40 MiB。",
            "chunk_id": "real",
            "owner": "local",
        }
    }
    result = {
        "answerable": True,
        "claims": [
            {
                "text": "上限为 40 MiB。",
                "evidence_id": "1",
                "quote": "大小上限为 40 MiB",
            }
        ],
    }
    answer, citations = validate_claims(result, evidence)
    assert (
        "[1]" in answer
        and citations[0]["chunk_id"] == "real"
        and "owner" not in citations[0]
    )
    result["claims"][0]["evidence_id"] = "injected"
    with pytest.raises(ValueError):
        validate_claims(result, evidence)
    result["claims"][0].update(evidence_id="1", quote="捏造的 400 MiB")
    with pytest.raises(ValueError):
        validate_claims(result, evidence)
    assert validate_claims({"answerable": False}, evidence)[1] == []


def test_actual_langgraph_parallel_barrier_once(monkeypatch):
    monkeypatch.setattr(
        main_graph.ItemNameConfirmedNode,
        "process",
        lambda self, s: {"rewritten_query": "question"},
    )

    def hybrid(self, s):
        time.sleep(0.02)
        return {"embedding_chunks": [{"chunk_id": "a"}], "hybrid_status": "completed"}

    def hyde(self, s):
        time.sleep(0.05)
        return {
            "hyde_embedding_chunks": [{"chunk_id": "b"}],
            "hyde_status": "completed",
        }

    def web(self, s):
        return {"web_search_docs": [], "web_status": "disabled"}

    monkeypatch.setattr(main_graph.HybridVectorSearch, "process", hybrid)
    monkeypatch.setattr(main_graph.HyDeVectorSearchNode, "process", hyde)
    monkeypatch.setattr(main_graph.WebMcpSearchNode, "process", web)
    monkeypatch.setattr(
        main_graph.RerankerNode,
        "process",
        lambda self, s: {"reranked_docs": s["rrf_chunks"]},
    )
    monkeypatch.setattr(
        main_graph.AnswerOutPutNode,
        "process",
        lambda self, s: {"answer": "unit contract", "history_saved": True},
    )
    result = main_graph.create_query_graph().invoke(
        create_default_state(original_query="question")
    )
    assert result["join_count"] == 1
    assert (
        result["hybrid_status"] == "completed"
        and result["hyde_status"] == "completed"
        and result["web_status"] == "disabled"
    )
    assert {x["chunk_id"] for x in result["rrf_chunks"]} == {"a", "b"}


def test_join_rejects_total_outage_but_allows_partial_retrieval():
    with pytest.raises(RuntimeError):
        main_graph.join_search_results(
            {
                "hybrid_status": "failed:ConnectionError",
                "hyde_status": "disabled",
                "web_status": "disabled",
            }
        )
    assert (
        main_graph.join_search_results(
            {"hybrid_status": "completed", "hyde_status": "failed:TimeoutError"}
        )["join_count"]
        == 1
    )


def test_citation_repair_is_bounded_and_counts_both_calls():
    from types import SimpleNamespace
    import json

    evidence = {"1": {"content": "单个上传文件大小上限为 40 MiB。", "chunk_id": "real"}}

    class UnitClient:
        def __init__(self, always_invalid=False):
            self.calls = 0
            self.always_invalid = always_invalid

        def invoke(self, messages):
            self.calls += 1
            quote = (
                "不存在的400 MiB"
                if self.calls == 1 or self.always_invalid
                else "大小上限为 40 MiB"
            )
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "answerable": True,
                        "claims": [
                            {
                                "text": "上限为40 MiB。",
                                "evidence_id": "1",
                                "quote": quote,
                            }
                        ],
                    }
                ),
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                },
                id="unit-response",
            )

    client = UnitClient()
    answer, citations, usage, attempts = generate_grounded_answer(client, [], evidence)
    assert client.calls == 2 and len(citations) == 1 and usage["total_tokens"] == 60
    assert [a["status"] for a in attempts] == ["invalid", "valid"]
    bad = UnitClient(True)
    with pytest.raises(ValueError):
        generate_grounded_answer(bad, [], evidence)
    assert bad.calls == 2


def test_docx_typographic_spaces_recover_exact_original_quote():
    source = "它接收一个列表\u00a0numbers\u00a0作为参数，并返回结果。"
    quote, aligned = source_quote("一个列表 numbers 作为参数", source)
    assert aligned and quote in source and "\u00a0" in quote
    with pytest.raises(ValueError):
        source_quote("一个列表 values 作为参数", source)
    with pytest.raises(ValueError):
        source_quote("列表numbers", source)


def test_entity_retrieval_supports_schema_primary_key(monkeypatch):
    from knowledge.utils import entity_retrieval as module
    from types import SimpleNamespace

    document = {
        "entity_vector_id": "topic-1",
        "document_id": "doc-1",
        "version": "v1",
        "embedding_revision": "unit",
        "file_title": "Manual",
        "item_name": "Topic",
    }
    monkeypatch.setattr(module, "required", lambda name: "unit")
    monkeypatch.setattr(module.AIClients, "get_bge_m3_client", lambda: object())
    monkeypatch.setattr(
        module,
        "generate_bge_m3_hybrid_vectors",
        lambda *a: {"dense": [[0.1]], "sparse": [{1: 0.2}]},
    )
    monkeypatch.setattr(
        module.StorageClients,
        "get_milvus_client",
        lambda: SimpleNamespace(
            hybrid_search=lambda *a, **k: [
                [
                    {
                        "chunk_id": "topic-1",
                        "distance": 0.7,
                        "entity": {"chunk_id": "topic-1", "owner": "local"},
                    }
                ]
            ]
        ),
    )
    result = module.retrieve_topics("topic", "local", [document])
    assert result[0]["document_id"] == "doc-1"


def test_reranker_respects_real_model_position_limit():
    from knowledge.utils.client.local_models import LocalReranker
    from types import SimpleNamespace

    recorded = {}

    def score(pairs, **kwargs):
        recorded.update(kwargs)
        return [0.4]

    client = object.__new__(LocalReranker)
    client.model = SimpleNamespace(compute_score=score)
    assert client.compute_score([["q", "d"]]) == [0.4]
    assert recorded["max_length"] == 512
