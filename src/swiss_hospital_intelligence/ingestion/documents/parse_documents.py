"""Parse a saved hospital page into sections, or a PDF into pages.

The whole file is not one text field. A page with no extractable text stays
as a failed chunk. Language comes from the page or its URL path. Nothing is
translated.
"""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

LANGUAGE_CODES = {"de", "fr", "it", "rm", "en"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "form"}
BLOCK_TAGS = HEADINGS | {"p", "div", "li", "tr", "br", "section", "article"}


class ParsedChunk(BaseModel):
    text: str
    page_number: int | None
    section: str | None
    language: str | None
    ordinal: int
    status: Literal["parsed", "failed"]
    failure_reason: str | None = None


class ParsedDocument(BaseModel):
    source_url: str | None
    checksum: str | None
    media_type: Literal["html", "pdf", "other"]
    title: str | None
    language: str | None
    processing_status: Literal["parsed", "parsed_with_failures", "failed"]
    chunks: list[ParsedChunk] = Field(default_factory=list)


class _Sections(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.language: str | None = None
        self.title_parts: list[str] = []
        self.sections: list[tuple[str | None, str]] = []
        self._skip = 0
        self._in_head = False
        self._in_title = False
        self._in_heading = False
        self._heading_parts: list[str] = []
        self._current_heading: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "html":
            language = dict(attrs).get("lang")
            if language:
                self.language = _primary_language(language)
        if tag == "head":
            self._in_head = True
        if tag == "title":
            self._in_title = True
        if tag in SKIP_TAGS:
            self._skip += 1
        if self._skip or self._in_head:
            return
        if tag in HEADINGS:
            self._flush()
            self._in_heading = True
            self._heading_parts = []
        elif tag in BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "head":
            self._in_head = False
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
            return
        if self._skip or self._in_head:
            return
        if tag in HEADINGS and self._in_heading:
            self._current_heading = _collapse(" ".join(self._heading_parts)) or None
            self._in_heading = False
            self._heading_parts = []
        elif tag in BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._skip or self._in_head:
            return
        if self._in_heading:
            self._heading_parts.append(data)
            return
        self._parts.append(data)

    def finish(self) -> None:
        self._flush()

    def _flush(self) -> None:
        text = _collapse(" ".join(self._parts))
        self._parts = []
        if not text and self._current_heading:
            text = self._current_heading
        if text:
            self.sections.append((self._current_heading, text))


MAX_PASSAGE_CHARS = 1200


def split_passage(text: str, *, limit: int = MAX_PASSAGE_CHARS) -> list[str]:
    """Split a long section or page into passages."""
    if len(text) <= limit:
        return [text] if text else []
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + limit)
        if end < len(text):
            cut = max(text.rfind(". ", start, end), text.rfind("! ", start, end), text.rfind("? ", start, end))
            if cut >= start + limit // 3:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end <= start:
            end = start + limit
        start = end
    return pieces


def parse_html(html: str, url: str | None = None) -> ParsedDocument:
    parser = _Sections()
    parser.feed(html)
    parser.finish()
    language = parser.language or _language_from_url(url)
    title = _collapse(" ".join(parser.title_parts)) or None
    chunks: list[ParsedChunk] = []
    for section, text in parser.sections:
        for piece in split_passage(text):
            chunks.append(
                ParsedChunk(
                    text=piece,
                    page_number=None,
                    section=section,
                    language=language,
                    ordinal=len(chunks) + 1,
                    status="parsed",
                )
            )
    if not chunks:
        chunks = [_failed(1, language, "no_text")]
    return ParsedDocument(
        source_url=url,
        checksum=None,
        media_type="html",
        title=title,
        language=language,
        processing_status=_status(chunks),
        chunks=chunks,
    )


def parse_pdf(data: bytes, url: str | None = None) -> ParsedDocument:
    import pymupdf

    language = _language_from_url(url)
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        chunk = _failed(1, language, "pdf_open_failed", page_number=None)
        chunk.failure_reason = f"pdf_open_failed: {error.__class__.__name__}"
        return _document("pdf", url, language, None, [chunk])
    chunks: list[ParsedChunk] = []
    title = _collapse(document.metadata.get("title") or "") or None
    for index, page in enumerate(document, start=1):
        text = _collapse(page.get_text("text"))
        if text:
            for piece in split_passage(text):
                chunks.append(
                    ParsedChunk(
                        text=piece,
                        page_number=index,
                        section=None,
                        language=language,
                        ordinal=len(chunks) + 1,
                        status="parsed",
                    )
                )
        else:
            chunks.append(_failed(len(chunks) + 1, language, "no_extractable_text", page_number=index))
    document.close()
    if not chunks:
        chunks = [_failed(1, language, "no_extractable_text", page_number=1)]
    return _document("pdf", url, language, title, chunks)


def parse_saved_page(
    url: str,
    body: bytes | None,
    *,
    content_type: str | None,
    http_status: int | None,
    error: str | None,
    checksum: str | None,
) -> ParsedDocument:
    language = _language_from_url(url)
    if http_status is None or http_status >= 400 or not body:
        reason = error or (f"http_{http_status}" if http_status else "body_not_stored")
        document = _document("other", url, language, None, [_failed(1, language, reason)])
        document.checksum = checksum
        return document
    kind = _media_type(url, content_type, body)
    if kind == "pdf":
        document = parse_pdf(body, url)
    elif kind == "html":
        document = parse_html(body.decode("utf-8", errors="replace"), url)
    else:
        document = _document("other", url, language, None, [_failed(1, language, "unsupported_type")])
    document.checksum = checksum
    document.source_url = url
    return document


def write_parsed_corpus(directory: Path, output: Path | None = None) -> dict[str, int]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    target = output or directory.parent.parent / "processed" / "gr" / "parsed_documents.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = {"documents": 0, "chunks": 0, "failed_chunks": 0}
    with target.open("w", encoding="utf-8") as handle:
        for url, page in manifest.items():
            checksum = page.get("checksum")
            body = None
            if checksum:
                body_path = directory / "bodies" / checksum
                if body_path.is_file():
                    body = body_path.read_bytes()
            parsed = parse_saved_page(
                url,
                body,
                content_type=page.get("content_type"),
                http_status=page.get("http_status"),
                error=page.get("error"),
                checksum=checksum,
            )
            handle.write(parsed.model_dump_json() + "\n")
            counts["documents"] += 1
            counts["chunks"] += len(parsed.chunks)
            counts["failed_chunks"] += sum(chunk.status == "failed" for chunk in parsed.chunks)
            counts[parsed.media_type] = counts.get(parsed.media_type, 0) + 1
    counts["output_written"] = 1
    return counts


def _document(media_type, url, language, title, chunks: list[ParsedChunk]) -> ParsedDocument:
    return ParsedDocument(
        source_url=url,
        checksum=None,
        media_type=media_type,
        title=title,
        language=language,
        processing_status=_status(chunks),
        chunks=chunks,
    )


def _failed(ordinal: int, language: str | None, reason: str, page_number: int | None = None) -> ParsedChunk:
    return ParsedChunk(
        text="",
        page_number=page_number,
        section=None,
        language=language,
        ordinal=ordinal,
        status="failed",
        failure_reason=reason,
    )


def _status(chunks: list[ParsedChunk]) -> Literal["parsed", "parsed_with_failures", "failed"]:
    failed = sum(chunk.status == "failed" for chunk in chunks)
    if failed == 0:
        return "parsed"
    if failed == len(chunks):
        return "failed"
    return "parsed_with_failures"


def _media_type(url: str, content_type: str | None, body: bytes) -> str:
    kind = (content_type or "").split(";")[0].strip().lower()
    path = urlparse(url).path.lower()
    if kind == "application/pdf" or path.endswith(".pdf") or body.startswith(b"%PDF"):
        return "pdf"
    if kind in {"text/html", "application/xhtml+xml"} or path.endswith((".html", ".htm")) or body.lstrip().startswith(b"<"):
        return "html"
    return "other"


def _language_from_url(url: str | None) -> str | None:
    if not url:
        return None
    for segment in urlparse(url).path.split("/"):
        code = segment.casefold()
        if code in LANGUAGE_CODES:
            return code
    return None


def _primary_language(value: str) -> str | None:
    primary = value.strip().replace("_", "-").split("-")[0].casefold()
    if primary in LANGUAGE_CODES:
        return primary
    return None


def _collapse(value: str) -> str:
    return " ".join(value.split())


def main() -> int:
    directory = Path("data/documents/gr")
    if not (directory / "manifest.json").is_file():
        print("No saved pages yet.", file=sys.stderr)
        return 2
    counts = write_parsed_corpus(directory)
    sys.stdout.reconfigure(encoding="utf-8")
    for key in ("documents", "html", "pdf", "other", "chunks", "failed_chunks"):
        print(f"{key}: {counts.get(key, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
