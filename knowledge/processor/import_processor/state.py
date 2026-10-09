from typing import TypedDict
import copy


class ImageArtifact(TypedDict):
    image_id: str
    name: str
    object_key: str
    sha256: str
    mime_type: str
    summary: str
    resource_url: str
    model: str
    token_usage: dict[str, int]
    response_id: str


class Chunk(TypedDict, total=False):
    chunk_id: str
    document_id: str
    source_id: str
    version: str
    owner: str
    content: str
    title: str
    parent_title: str
    file_title: str
    item_name: str
    entity_type: str
    char_start: int
    char_end: int
    span_basis: str
    source_url: str
    image_ids: list[str]
    embedding_model: str
    embedding_revision: str
    dense_vector: list[float]
    sparse_vector: dict[int, float]
    rrf_score: float
    rerank_score: float


class ImportGraphState(TypedDict, total=False):
    task_id: str
    owner: str
    source_label: str
    document_id: str
    source_id: str
    version: str
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool
    is_docx_read_enabled: bool
    import_file_path: str
    file_dir: str
    pdf_path: str
    md_path: str
    new_md_path: str
    file_title: str
    item_name: str
    entity_type: str
    md_content: str
    chunks: list[Chunk]
    entity_vector: dict
    images: list[ImageArtifact]
    original_object_key: str
    processed_object_key: str
    committed: bool
    chunk_count: int
    already_imported: bool


GRAPH_DEFAULT_STATE: ImportGraphState = {
    "task_id": "",
    "owner": "local",
    "chunks": [],
    "images": [],
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "is_docx_read_enabled": False,
}


def create_default_state(**overrides) -> ImportGraphState:
    state = copy.deepcopy(GRAPH_DEFAULT_STATE)
    state.update(overrides)
    return state


def get_default_state() -> ImportGraphState:
    return copy.deepcopy(GRAPH_DEFAULT_STATE)
