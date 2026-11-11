"""Save registered public pages.

A robots.txt disallow is recorded and does not stop the save. An HTTP error is
also recorded. A refusal from the server is not bypassed. The same checksum
is not written twice.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from pydantic import BaseModel, Field

from swiss_hospital_intelligence.ingestion.documents.source_register import SourceRegister

USER_AGENT = "SwissHospitalIntelligence/0.1"
BODY_LIMIT = 20_000_000


class SavedPage(BaseModel):
    url: str
    final_url: str | None
    http_status: int | None
    checksum: str | None
    robots_allowed: bool | None
    saved_despite_robots: bool
    byte_length: int
    content_type: str | None
    retrieved_at: str
    error: str | None = None


class SaveResult(BaseModel):
    pages: list[SavedPage] = Field(default_factory=list)


def save_registered_pages(
    register: SourceRegister,
    directory: Path,
    *,
    fetch=None,
    robots_allowed_for=None,
    delay_seconds: float = 0,
) -> SaveResult:
    return save_urls(
        _urls(register),
        directory,
        fetch=fetch,
        robots_allowed_for=robots_allowed_for,
        delay_seconds=delay_seconds,
    )


def save_urls(
    urls: list[str],
    directory: Path,
    *,
    fetch=None,
    robots_allowed_for=None,
    delay_seconds: float = 0,
) -> SaveResult:
    fetcher = fetch or _fetch
    robots_cache: dict[str, RobotFileParser | None] = {}

    def allowed(url: str) -> bool | None:
        if robots_allowed_for is not None:
            return robots_allowed_for(url)
        return _robots_allowed(url, fetcher, robots_cache)

    directory.mkdir(parents=True, exist_ok=True)
    bodies = directory / "bodies"
    bodies.mkdir(exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest = _read_manifest(manifest_path)
    pages: list[SavedPage] = []
    for url in urls:
        allowed_by_robots = allowed(url)
        status, body, content_type, final_url, error = fetcher(url)
        checksum = None
        if body:
            digest = hashlib.sha256(body).hexdigest()
            target = bodies / digest
            if not target.exists():
                target.write_bytes(body)
            checksum = digest
        saved = SavedPage(
            url=url,
            final_url=final_url,
            http_status=status,
            checksum=checksum,
            robots_allowed=allowed_by_robots,
            saved_despite_robots=allowed_by_robots is False and checksum is not None,
            byte_length=len(body),
            content_type=content_type,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            error=error,
        )
        manifest[url] = saved.model_dump()
        pages.append(saved)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        if delay_seconds:
            time.sleep(delay_seconds)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return SaveResult(pages=pages)


def _urls(register: SourceRegister) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for row in register.rows:
        if row.url_status != "found" or not row.url or row.url in seen:
            continue
        seen.add(row.url)
        urls.append(row.url)
    return urls


def _fetch(url: str) -> tuple[int | None, bytes, str | None, str | None, str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read(BODY_LIMIT + 1)
            if len(body) > BODY_LIMIT:
                return response.status, b"", response.headers.get_content_type(), response.geturl(), "body exceeds 20 MB"
            return response.status, body, response.headers.get_content_type(), response.geturl(), None
    except HTTPError as error:
        body = error.read(BODY_LIMIT + 1)
        if len(body) > BODY_LIMIT:
            body = b""
        return error.code, body, None, error.geturl(), None
    except URLError as error:
        return None, b"", None, None, str(error.reason)


def _robots_allowed(url: str, fetch, cache: dict[str, RobotFileParser | None]) -> bool | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        cache[origin] = _robots_parser(origin, fetch)
    parser = cache[origin]
    if parser is None:
        return None
    return parser.can_fetch(USER_AGENT, url)


def _robots_parser(origin: str, fetch) -> RobotFileParser | None:
    status, body, _, _, error = fetch(f"{origin}/robots.txt")
    if error is not None or status is None or status >= 400 or not body:
        return None
    parser = RobotFileParser()
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    return parser


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    import sys

    from swiss_hospital_intelligence.ingestion.documents.gr_websites import WEBSITES
    from swiss_hospital_intelligence.ingestion.documents.source_register import build_source_register
    from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures

    path = next(
        (
            candidate
            for candidate in (Path("data/raw/kzp24_data.xlsx"), Path("_discovery/raw/kzp24_data.xlsx"))
            if candidate.is_file()
        ),
        None,
    )
    if path is None:
        print("Key-figure workbook is not on disk.", file=sys.stderr)
        return 2
    register = build_source_register(parse_key_figures(path), WEBSITES)
    result = save_registered_pages(register, Path("data/documents/gr"), delay_seconds=1)
    saved = [page for page in result.pages if page.checksum]
    blocked = [page for page in result.pages if page.saved_despite_robots]
    failed = [page for page in result.pages if page.checksum is None]
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"urls: {len(result.pages)}")
    print(f"saved: {len(saved)}")
    print(f"saved_despite_robots: {len(blocked)}")
    print(f"not_saved: {len(failed)}")
    for page in failed:
        print(f"- {page.http_status} {page.url} {page.error or ''}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
