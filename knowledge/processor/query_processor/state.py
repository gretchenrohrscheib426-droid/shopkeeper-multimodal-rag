from typing import TypedDict
import copy


class QueryGraphState(TypedDict, total=False):
    session_id: str
    task_id: str
    message_id: str
    owner: str
    original_query: str
    rewritten_query: str
    selected_document_ids: list[str]
    document_scope: list[dict]
    item_names: list[str]
    embedding_chunks: list[dict]
    hyde_embedding_chunks: list[dict]
    rrf_chunks: list[dict]
    web_search_docs: list[dict]
    reranked_docs: list[dict]
    hybrid_status: str
    hyde_status: str
    web_status: str
    hyde_text: str
    hyde_usage: dict
    rewrite_usage: dict
    answer_usage: dict
    answer_attempts: list[dict]
    history: list[dict]
    answer: str
    citations: list[dict]
    clarification_options: list[dict]
    answer_kind: str
    is_stream: bool
    retrieval_mode: str
    candidate_limit: int
    join_count: int
    history_saved: bool


DEFAULT_STATE: QueryGraphState = {
    "session_id": "",
    "task_id": "",
    "owner": "local",
    "original_query": "",
    "embedding_chunks": [],
    "hyde_embedding_chunks": [],
    "rrf_chunks": [],
    "web_search_docs": [],
    "reranked_docs": [],
    "item_names": [],
    "history": [],
    "answer": "",
    "is_stream": False,
    "citations": [],
    "clarification_options": [],
    "retrieval_mode": "rerank",
    "candidate_limit": 10,
}


def create_default_state(**overrides) -> QueryGraphState:
    state = copy.deepcopy(DEFAULT_STATE)
    state.update(overrides)
    return state


def get_default_state() -> QueryGraphState:
    return copy.deepcopy(DEFAULT_STATE)


graph_default_state = DEFAULT_STATE
