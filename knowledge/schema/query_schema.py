from typing import Literal
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(
        default=None, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    )
    is_stream: bool = False
    selected_document_ids: list[str] = Field(default_factory=list, max_length=30)
    retrieval_mode: Literal["dense", "hybrid", "hyde", "rerank"] = "rerank"
    candidate_limit: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class StreamSubmitResponse(BaseModel):
    message: str
    session_id: str
    task_id: str


class QueryResponse(BaseModel):
    message: str
    session_id: str
    answer: str = ""


class HistoryItem(BaseModel):
    """Legacy response schema retained; active history also carries validated citations."""

    id: str = Field(default="", alias="_id")
    session_id: str = ""
    role: str = ""
    text: str = ""
    rewritten_query: str = ""
    item_names: list[str] = Field(default_factory=list)
    ts: float | None = None
    citations: list[dict] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    session_id: str
    items: list[HistoryItem]
