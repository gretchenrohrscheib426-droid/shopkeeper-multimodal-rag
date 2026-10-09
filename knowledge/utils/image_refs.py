"""Markdown image references with exact replacement spans and local path confinement."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re


@dataclass(frozen=True)
class ImageReference:
    start: int
    end: int
    alt: str
    destination: str


def image_references(text: str) -> list[ImageReference]:
    refs = []
    offset = 0
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            offset += len(line)
            continue
        if fence is not None:
            offset += len(line)
            continue
        for match in re.finditer(r"!\[([^\]]*)\]\(", line):
            start = match.end()
            pos = start
            level = 1
            escaped = False
            in_angle = False
            while pos < len(line):
                c = line[pos]
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == "<":
                    in_angle = True
                elif c == ">":
                    in_angle = False
                elif not in_angle and c == "(":
                    level += 1
                elif not in_angle and c == ")":
                    level -= 1
                    if level == 0:
                        break
                pos += 1
            if level:
                raise ValueError("Malformed image reference")
            raw = line[start:pos].strip()
            if raw.startswith("<"):
                end = raw.find(">")
                if end < 0:
                    raise ValueError("Malformed angle image reference")
                destination = raw[1:end]
            else:
                destination = re.sub(r"""\s+(?:"[^"]*"|'[^']*')\s*$""", "", raw)
            refs.append(
                ImageReference(
                    offset + match.start(),
                    offset + pos + 1,
                    match.group(1),
                    destination,
                )
            )
        offset += len(line)
    return refs


def resolve_image(root: Path, destination: str) -> Path:
    if urlsplit(destination).scheme or destination.startswith("//"):
        raise ValueError(
            "Remote images are not fetched automatically; include a local licensed copy"
        )
    path = (root / unquote(destination)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Image escapes the document directory")
    if not path.is_file():
        raise FileNotFoundError("Referenced image is missing: " + path.name)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        raise ValueError("Unsupported image type")
    return path
