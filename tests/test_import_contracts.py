import numpy as np
import pytest
from scipy.sparse import csr_array
from knowledge.core.configuration import resolve_values
from knowledge.processor.import_processor.nodes.entry_node import EntryNode
from knowledge.processor.import_processor.nodes.document_split_node import (
    DocumentSplitNode,
)
from knowledge.processor.import_processor.config import ImportConfig
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors
from knowledge.utils.image_refs import image_references, resolve_image


def test_alias_precedence_and_conflict():
    values = resolve_values(
        {"OPENAI_API_BASE": "https://one.test"}, {"OPENAI_BASE_URL": "https://two.test"}
    )
    assert values["OPENAI_API_BASE"] == values["OPENAI_BASE_URL"] == "https://two.test"
    with pytest.raises(ValueError, match="Conflicting"):
        resolve_values({"OPENAI_API_BASE": "one", "OPENAI_BASE_URL": "two"}, {})


def test_file_model_tuple_rejects_stale_environment_overrides():
    configured = {
        "MODEL_CONFIG_SOURCE": "file",
        "OPENAI_API_BASE": "https://workspace.test/v1",
        "OPENAI_API_KEY": "local-test-key",
        "LLM_DEFAULT_MODEL": "qwen-plus",
        "VL_MODEL": "qwen3-vl-plus",
        "ITEM_MODEL": "qwen-plus",
    }
    stale = {
        "OPENAI_API_BASE": "https://old.test",
        "OPENAI_BASE_URL": "https://another.test",
        "OPENAI_API_KEY": "old-test-key",
        "MODEL": "old-model",
        "MINIO_ENDPOINT": "test-storage:9000",
    }
    resolved = resolve_values(configured, stale)
    assert resolved["OPENAI_API_KEY"] == "local-test-key"
    assert (
        resolved["OPENAI_API_BASE"]
        == resolved["OPENAI_BASE_URL"]
        == "https://workspace.test/v1"
    )
    assert resolved["MODEL"] == resolved["LLM_DEFAULT_MODEL"] == "qwen-plus"
    assert resolved["MINIO_ENDPOINT"] == "test-storage:9000"
    del configured["OPENAI_API_KEY"]
    with pytest.raises(ValueError, match="Missing file-authoritative"):
        resolve_values(configured, stale)


def test_input_is_file_and_has_correct_signature(tmp_path):
    with pytest.raises(ValueError, match="existing file"):
        EntryNode().process(
            {"import_file_path": str(tmp_path), "file_dir": str(tmp_path)}
        )
    path = tmp_path / "中文 空格.PDF"
    path.write_text("not a PDF")
    with pytest.raises(ValueError, match="signature"):
        EntryNode().process({"import_file_path": str(path), "file_dir": str(tmp_path)})


def test_image_refs_titles_encoding_fences_and_confinement(tmp_path):
    image = tmp_path / "中文 空格.png"
    image.write_bytes(b"fixture")
    text = '```md\n![example](missing.png)\n```\n![图](<中文 空格.png> "标题")\n![复用](中文%20空格.png "说明")'
    refs = image_references(text)
    assert len(refs) == 2
    assert {resolve_image(tmp_path, r.destination) for r in refs} == {image}
    with pytest.raises(ValueError, match="escapes"):
        resolve_image(tmp_path, "../outside.png")
    with pytest.raises(ValueError, match="Remote"):
        resolve_image(tmp_path, "http://127.0.0.1/private.png")


def test_version_changes_with_image_bytes_and_id_stays_stable(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"one")
    path = tmp_path / "manual.MD"
    path.write_text("# 标题\n![图](image.png)", encoding="utf-8")
    state = {
        "import_file_path": str(path),
        "file_dir": str(tmp_path),
        "owner": "owner-a",
    }
    first = EntryNode().process(state)
    image.write_bytes(b"two")
    second = EntryNode().process(state)
    assert first["document_id"] == second["document_id"]
    assert first["version"] != second["version"]


def test_split_exact_spans_bounds_and_fenced_heading(tmp_path):
    text = (
        "# 文档\n\n"
        + ("第一句话。第二句话。\n" * 70)
        + "\n```python\n# 不是标题\nprint(1)\n```\n\n## 下一节\n尾部内容。"
    )
    state = {
        "md_content": text,
        "file_title": "文档",
        "file_dir": str(tmp_path),
        "document_id": "a",
        "source_id": "a",
        "version": "b",
        "owner": "o",
        "images": [],
    }
    chunks = DocumentSplitNode(
        ImportConfig(max_content_length=180, min_content_length=60)
    ).process(state)["chunks"]
    assert len(chunks) > 3
    assert all(
        0 < len(c["content"]) <= 180
        and c["content"] == text[c["char_start"] : c["char_end"]]
        for c in chunks
    )
    assert not any(c["title"] == "不是标题" for c in chunks)
    assert sum("```python" in c["content"] for c in chunks) == 1
    covered = set().union(*(set(range(c["char_start"], c["char_end"])) for c in chunks))
    assert covered == set(range(len(text)))


@pytest.mark.parametrize("bad", ["count", "dimension", "nan", "sparse_count", "zero"])
def test_embedding_rejects_invalid_vectors(bad):
    dense = np.ones((1, 1024), dtype=np.float32)
    sparse = csr_array([[0, 1.0]])
    if bad == "count":
        dense = np.ones((2, 1024))
    if bad == "dimension":
        dense = np.ones((1, 768))
    if bad == "nan":
        dense[0, 0] = np.nan
    if bad == "zero":
        dense[:] = 0
    if bad == "sparse_count":
        sparse = csr_array([[1.0], [1.0]])

    class Model:
        def encode_documents(self, documents):
            return {"dense": dense, "sparse": sparse}

    with pytest.raises(ValueError):
        generate_bge_m3_hybrid_vectors(Model(), ["有效输入"])
