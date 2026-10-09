"""Heading-aware bounded chunks; spans refer to immutable processed Markdown."""

import hashlib
import json
import re
from pathlib import Path
from knowledge.processor.import_processor.base import BaseNode
from knowledge.processor.import_processor.state import ImportGraphState, Chunk


def sections_and_atoms(text: str, file_title: str):
    sections = []
    atoms = []
    stack = []
    offset = 0
    start = 0
    title = file_title
    parent = file_title
    fence = None
    fence_start = 0
    table_start = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
                fence_start = offset
            elif token[0] == fence[0] and len(token) >= len(fence):
                atoms.append((fence_start, offset + len(line)))
                fence = None
        if fence is None and not marker:
            match = re.match(r"^(#{1,6})\s+(.+)", line)
            if match:
                if offset > start:
                    sections.append((start, offset, title, parent))
                level = len(match.group(1))
                heading = match.group(2).strip()
                stack = [(n, t) for n, t in stack if n < level]
                parent = stack[-1][1] if stack else file_title
                stack.append((level, heading))
                title = heading
                start = offset
            is_table = (
                line.lstrip().startswith("|")
                or "<table" in line
                or (
                    table_start is not None
                    and "</table>" not in line
                    and not line.strip()
                )
            )
            if is_table and table_start is None:
                table_start = offset
            if table_start is not None and (not is_table or "</table>" in line):
                atoms.append(
                    (table_start, offset + len(line) if "</table>" in line else offset)
                )
                table_start = None
            if "![" in line:
                atoms.append((offset, offset + len(line)))
        offset += len(line)
    if fence is not None:
        raise ValueError("Unclosed code fence")
    if table_start is not None:
        atoms.append((table_start, len(text)))
    if start < len(text):
        sections.append((start, len(text), title, parent))
    return sections, atoms


class DocumentSplitNode(BaseNode):
    name = "document_split_node"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        text = state.get("md_content", "")
        maximum = self.config.max_content_length
        if not text.strip():
            raise ValueError("No Markdown content to split")
        if not 0 < self.config.min_content_length < maximum:
            raise ValueError("Invalid chunk lengths")
        sections, atoms = sections_and_atoms(text, state["file_title"])
        chunks: list[Chunk] = []
        if any(end - start > maximum for start, end in atoms):
            raise ValueError(
                "A table, image reference or code block exceeds the chunk character limit; split that block explicitly"
            )
        for begin, end, title, parent in sections:
            cursor = begin
            while cursor < end:
                stop = min(cursor + maximum, end)
                if stop < end:
                    for a, b in atoms:
                        if a < stop < b:
                            stop = a if a > cursor else b
                            break
                    if not any(a < stop < b for a, b in atoms):
                        candidates = [
                            m.end() + cursor
                            for m in re.finditer(r"[。！？；\n]", text[cursor:stop])
                        ]
                        candidates = [
                            v
                            for v in candidates
                            if v - cursor >= maximum // 2
                            and not any(a < v < b for a, b in atoms)
                        ]
                        if candidates:
                            stop = candidates[-1]
                if stop <= cursor:
                    raise ValueError("Splitter failed to advance")
                if text[cursor:stop].strip():
                    index = len(chunks)
                    chunk_id = hashlib.sha256(
                        f"{state['document_id']}:{state['version']}:{index}".encode()
                    ).hexdigest()
                    content = text[cursor:stop]
                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "document_id": state["document_id"],
                            "source_id": state["source_id"],
                            "owner": state["owner"],
                            "version": state["version"],
                            "content": content,
                            "title": title,
                            "parent_title": parent,
                            "file_title": state["file_title"],
                            "char_start": cursor,
                            "char_end": stop,
                            "span_basis": "processed_markdown",
                            "source_url": f"/sources/{state['document_id']}/{state['version']}/{chunk_id}",
                            "image_ids": [
                                x["image_id"]
                                for x in state.get("images", [])
                                if x["resource_url"] in content
                            ],
                        }
                    )
                if stop == end:
                    break
                # One preceding sentence, at most 100 characters, without cutting an atomic block.
                overlap = 0
                if self.config.overlap_sentences:
                    sentence = list(
                        re.finditer(
                            r"[。！？；\n]", text[max(cursor, stop - 100) : stop - 1]
                        )
                    )
                    if sentence:
                        overlap = stop - (max(cursor, stop - 100) + sentence[-1].end())
                next_cursor = stop - overlap
                if any(a < next_cursor < b for a, b in atoms):
                    next_cursor = stop
                cursor = max(cursor + 1, next_cursor)
        if not chunks:
            raise ValueError("No searchable chunks")
        (Path(state["file_dir"]) / "chunks.json").write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"chunks": chunks, "chunk_count": len(chunks)}
