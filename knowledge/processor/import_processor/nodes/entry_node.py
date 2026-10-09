import hashlib
import json
import os
from pathlib import Path
from zipfile import is_zipfile
from knowledge.processor.import_processor.base import BaseNode
from knowledge.processor.import_processor.state import ImportGraphState
from knowledge.utils.image_refs import image_references, resolve_image


class EntryNode(BaseNode):
    name = "entry_node"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        if not state.get("import_file_path") or not state.get("file_dir"):
            raise ValueError("import_file_path and file_dir are required")
        source = Path(state["import_file_path"]).resolve()
        output = Path(state["file_dir"]).resolve()
        if not source.is_file():
            raise ValueError("Input must be an existing file")
        if not output.is_dir():
            raise ValueError("Output must be an existing directory")
        if source.stat().st_size == 0:
            raise ValueError("Input file is empty")
        suffix = source.suffix.lower()
        if suffix not in {".pdf", ".md", ".docx"}:
            raise ValueError("Supported inputs: PDF, Markdown, DOCX")
        raw = source.read_bytes()
        if suffix == ".pdf" and not raw.startswith(b"%PDF-"):
            raise ValueError("PDF signature mismatch")
        if suffix == ".docx" and not is_zipfile(source):
            raise ValueError("DOCX signature mismatch")
        digest = hashlib.sha256(raw)
        if suffix == ".md":
            content = raw.decode("utf-8-sig")
            if not content.strip():
                raise ValueError("Markdown is empty")
            for image in sorted(
                {
                    resolve_image(source.parent, r.destination)
                    for r in image_references(content)
                }
            ):
                digest.update(image.relative_to(source.parent).as_posix().encode())
                digest.update(image.read_bytes())
        profile = {
            "schema": "v2-entity-index",
            "splitter": "bounded-spans-v1",
            "max_chars": self.config.max_content_length,
            "overlap_sentences": self.config.overlap_sentences,
            "parser_backend": os.getenv("MINERU_BACKEND", "hybrid-auto-engine")
            if suffix == ".pdf"
            else suffix,
            "embedding": os.getenv("EMBEDDING_MODEL_REVISION", ""),
            "vlm": self.config.vl_model,
            "entity_model": self.config.item_model,
        }
        if suffix == ".docx":
            profile["docx_adapter"] = "word-styles-literal-comments-v2"
        digest.update(json.dumps(profile, sort_keys=True).encode())
        owner = state.get("owner", "local")
        label = state.get("source_label") or source.name.casefold()
        document_id = hashlib.sha256((owner + "\0" + label).encode()).hexdigest()[:32]
        version = digest.hexdigest()
        return {
            "owner": owner,
            "document_id": document_id,
            "source_id": document_id,
            "version": version,
            "file_title": source.stem,
            "is_pdf_read_enabled": suffix == ".pdf",
            "is_md_read_enabled": suffix == ".md",
            "is_docx_read_enabled": suffix == ".docx",
            "pdf_path": str(source) if suffix == ".pdf" else "",
            "md_path": str(source) if suffix == ".md" else "",
        }
