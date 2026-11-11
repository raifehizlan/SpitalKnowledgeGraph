"""Read clinic names from a saved Fachgebiete or Angebot index.

Only the index page is used. A link is kept when its text names a specialty
or a clinic. A news title and a class such as baby swimming are left out.
The link does not assign a site.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Evidence,
    OrganizationName,
    Source,
    SourceFile,
)
from swiss_hospital_intelligence.ingestion.documents.extract_mentions import (
    CLINIC_WORD,
    GENERIC_HEADINGS,
    REJECT_HEADING,
    SPECIALTY,
    Mention,
)
from swiss_hospital_intelligence.ingestion.documents.link_documents import (
    _host,
    establishment_scopes,
    organization_name_for_url,
)
from swiss_hospital_intelligence.ingestion.documents.load_mentions import _fingerprint, _upsert
from swiss_hospital_intelligence.ingestion.documents.source_register import SourceRegister

SOURCE_CODE = "GR-CATALOG-LINKS"
SOURCE_NAME = "Graubünden clinic index pages"
METHOD = "catalog_link"
MENU_METHOD = "homepage_menu"
MENU_TITLES = {
    "angebote",
    "fachbereiche",
    "fachbereiche / zentren",
    "leistungen",
    "medizinische leistungen",
    "medizinische versorgung",
    "offerta",
    "offerta sanitaria",
    "prestazioni",
    "spezifische angebote",
}
MENU_NOISE = re.compile(
    r"gastronom|@|^(?:über|ueber|zur|zuweiser|vorstellung|verordnung)\b|\bleiter(?:in)?\b",
    re.IGNORECASE,
)
JUNK_PATH = (
    "altersheim",
    "bildungsangebot",
    "casa-anziani",
    "datenschutz",
    "impressum",
    "jobs",
    "karriere",
    "lungodegenza",
    "spitex",
    "stellen",
)
CLINIC_SUFFIX = re.compile(r"(klinik|clinica|clinique|reparto|clinic)$", re.IGNORECASE)
LANGUAGE_SEGMENTS = {"de", "fr", "it", "rm", "en"}
INDEX_SEGMENTS = {
    "angebot",
    "fachbereiche",
    "fachgebiet",
    "fachgebiete",
    "leistungen",
    "leistungsangebot",
    "offerta",
    "reparti",
    "servizi",
}


class CatalogLoadResult(BaseModel):
    pages: int
    assertions: int
    by_predicate: dict[str, int] = Field(default_factory=dict)


class _IndexLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[str] = []
        self.anchors: list[str] = []
        self._row_depth = 0
        self._in_anchor = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = dict(attrs).get("class", "")
        if tag == "div" and "views-row" in classes.split():
            self._row_depth = 1
        elif self._row_depth and tag == "div":
            self._row_depth += 1
        if tag == "a":
            self._in_anchor = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            text = " ".join("".join(self._parts).split())
            if text:
                self.anchors.append(text)
                if self._row_depth:
                    self.rows.append(text)
            self._in_anchor = False
        if self._row_depth and tag == "div":
            self._row_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._parts.append(data)


def is_catalog_index(url: str, root_prefix: str | None = None) -> bool:
    segments = [segment.casefold() for segment in urlparse(url).path.split("/") if segment]
    if not segments or segments[-1] not in INDEX_SEGMENTS:
        return False
    body = [segment for segment in segments[:-1] if segment not in LANGUAGE_SEGMENTS]
    if not body:
        return True
    return root_prefix is not None and body == [root_prefix.strip("/").casefold()]


def catalog_mentions(html: str) -> list[Mention]:
    parser = _IndexLinks()
    parser.feed(html)
    labels = parser.rows or parser.anchors
    found: list[Mention] = []
    seen: set[str] = set()
    for label in labels:
        mention = _mention(label)
        if mention is None:
            continue
        key = mention.object_value.casefold()
        if key in seen:
            continue
        seen.add(key)
        found.append(mention)
    return found


def load_catalog_mentions(
    session: Session,
    directory: Path,
    register: SourceRegister,
) -> CatalogLoadResult:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    scopes = establishment_scopes(register)
    names = _establishment_ids(session)
    counts: dict[str, int] = {}
    total = 0
    pages = 0
    for url, page in manifest.items():
        address = page.get("final_url") or url
        scope = scopes.get(_host(address))
        prefix = scope.path_prefix if scope is not None else None
        if not is_catalog_index(address, prefix):
            continue
        checksum = page.get("checksum")
        html = _html_body(directory, page)
        if html is None or not checksum:
            continue
        mentions = catalog_mentions(html)
        if not mentions:
            continue
        pages += 1
        source_file = _source_file(session, checksum, url)
        organization_name = organization_name_for_url(page.get("final_url") or url, scopes)
        organization_id = names.get(organization_name) if organization_name is not None else None
        for mention in mentions:
            fingerprint = _fingerprint("catalog", url, mention.predicate, mention.object_value)
            _upsert(
                session,
                source_file_id=source_file.id,
                fingerprint=fingerprint,
                document_id=None,
                organization_id=organization_id,
                source_url=page.get("final_url") or url,
                page_number=None,
                section=None,
                predicate=mention.predicate,
                object_value=mention.object_value,
                excerpt=mention.excerpt,
                extraction_method=METHOD,
                method=METHOD,
            )
            counts[mention.predicate] = counts.get(mention.predicate, 0) + 1
            total += 1
    session.flush()
    return CatalogLoadResult(pages=pages, assertions=total, by_predicate=counts)


def _mention(label: str) -> Mention | None:
    folded = " ".join(label.casefold().split())
    if not folded or folded in GENERIC_HEADINGS or folded in MENU_TITLES or REJECT_HEADING.search(label):
        return None
    if len(folded) < 3 or len(folded) > 80:
        return None
    clinic = CLINIC_WORD.search(label) or CLINIC_SUFFIX.search(folded)
    if not SPECIALTY.search(label) and not clinic:
        return None
    predicate = "hasClinic" if clinic else "hasDepartment"
    return Mention(predicate=predicate, object_value=label.strip(), excerpt=label.strip())


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._parts).split())
            if text:
                self.found.append((self._href, text))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)


def menu_mentions(page_url: str, html: str) -> list[Mention]:
    return [mention for _, mention in _page_mentions(page_url, html, menu=True)]


def load_homepage_menus(
    session: Session,
    directory: Path,
    register: SourceRegister,
) -> CatalogLoadResult:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    names = _establishment_ids(session)
    covered = set(
        session.scalars(
            select(Assertion.organization_id)
            .join(Evidence, Evidence.id == Assertion.evidence_id)
            .where(Evidence.extraction_method == METHOD, Assertion.organization_id.is_not(None))
        )
    )
    counts: dict[str, int] = {}
    total = 0
    pages = 0
    for row in register.establishments():
        organization_id = names.get(row.organization_name)
        if organization_id in covered or not row.url:
            continue
        found = _find_page(manifest, row.url)
        if found is None:
            continue
        url, page = found
        html = _html_body(directory, page)
        checksum = page.get("checksum")
        if html is None or not checksum:
            continue
        chosen = _menu_or_child(directory, manifest, page.get("final_url") or url, html)
        if not chosen:
            continue
        pages += 1
        source_file = _source_file(session, checksum, url)
        for source_url, mention in chosen:
            fingerprint = _fingerprint("menu", source_url, mention.predicate, mention.object_value)
            _upsert(
                session,
                source_file_id=source_file.id,
                fingerprint=fingerprint,
                document_id=None,
                organization_id=organization_id,
                source_url=source_url,
                page_number=None,
                section=None,
                predicate=mention.predicate,
                object_value=mention.object_value,
                excerpt=mention.excerpt,
                extraction_method=MENU_METHOD,
                method=MENU_METHOD,
            )
            counts[mention.predicate] = counts.get(mention.predicate, 0) + 1
            total += 1
    session.flush()
    return CatalogLoadResult(pages=pages, assertions=total, by_predicate=counts)


def _menu_or_child(
    directory: Path,
    manifest: dict,
    page_url: str,
    html: str,
) -> list[tuple[str, Mention]]:
    child_rows: list[tuple[str, Mention]] = []
    for link in _index_links(page_url, html):
        found = _find_page(manifest, link)
        if found is None:
            continue
        child_url, child_page = found
        child_html = _html_body(directory, child_page)
        if child_html is None:
            continue
        address = child_page.get("final_url") or child_url
        for mention in catalog_mentions(child_html):
            if MENU_NOISE.search(mention.object_value):
                continue
            child_rows.append((address, mention))
    rows = child_rows or _page_mentions(page_url, html, menu=True)
    unique: list[tuple[str, Mention]] = []
    seen: set[tuple[str, str]] = set()
    for source_url, mention in rows:
        key = (mention.predicate, mention.object_value.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append((source_url, mention))
    return unique


def _page_mentions(page_url: str, html: str, *, menu: bool) -> list[tuple[str, Mention]]:
    parser = _Anchors()
    parser.feed(html)
    found: list[tuple[str, Mention]] = []
    for href, text in parser.found:
        absolute = urljoin(page_url, href)
        if _host(absolute) != _host(page_url):
            continue
        path = urlparse(absolute).path.casefold()
        if any(token in path for token in JUNK_PATH):
            continue
        if menu and not MENU_NOISE.search(text):
            mention = _mention(text)
            if mention is not None:
                found.append((absolute, mention))
    return found


def _index_links(page_url: str, html: str) -> list[str]:
    parser = _Anchors()
    parser.feed(html)
    links: list[str] = []
    seen: set[str] = set()
    for href, text in parser.found:
        folded = " ".join(text.casefold().split())
        if folded not in MENU_TITLES and folded not in INDEX_SEGMENTS:
            continue
        absolute = urljoin(page_url, href).split("?")[0].rstrip("/")
        if _host(absolute) != _host(page_url) or absolute in seen:
            continue
        path = urlparse(absolute).path.casefold()
        if any(token in path for token in JUNK_PATH):
            continue
        if path.rstrip("/") == urlparse(page_url).path.casefold().rstrip("/"):
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


def _find_page(manifest: dict, url: str) -> tuple[str, dict] | None:
    key = url.split("?")[0].rstrip("/")
    for item_url, page in manifest.items():
        final = (page.get("final_url") or item_url).split("?")[0].rstrip("/")
        if final == key or item_url.split("?")[0].rstrip("/") == key:
            return item_url, page
    return None


def _html_body(directory: Path, page: dict) -> str | None:
    checksum = page.get("checksum")
    if not checksum:
        return None
    path = directory / "bodies" / checksum
    if not path.is_file():
        return None
    content_type = (page.get("content_type") or "").casefold()
    if content_type and "html" not in content_type:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if content_type or text.lstrip().startswith("<"):
        return text
    return None


def _establishment_ids(session: Session) -> dict[str, UUID]:
    rows = session.execute(
        select(OrganizationName.name, OrganizationName.organization_id).where(
            OrganizationName.name_role == "source_primary"
        )
    )
    return {name: organization_id for name, organization_id in rows}


def _source_file(session: Session, checksum: str, url: str) -> SourceFile:
    source = session.scalar(select(Source).where(Source.code == SOURCE_CODE))
    if source is None:
        source = Source(
            code=SOURCE_CODE,
            name=SOURCE_NAME,
            url=None,
            reliability_class="official_hospital_website",
        )
        session.add(source)
        session.flush()
    existing = session.scalar(
        select(SourceFile).where(SourceFile.source_id == source.id, SourceFile.checksum == checksum)
    )
    if existing is not None:
        return existing
    created = SourceFile(source_id=source.id, checksum=checksum, filename=url)
    session.add(created)
    session.flush()
    return created


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    from swiss_hospital_intelligence.ingestion.documents.gr_websites import WEBSITES
    from swiss_hospital_intelligence.ingestion.documents.source_register import build_source_register
    from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures

    directory = Path("data/documents/gr")
    if not (directory / "manifest.json").is_file():
        print("No saved pages yet.", file=sys.stderr)
        return 2
    workbook = next(
        (path for path in (Path("data/raw/kzp24_data.xlsx"), Path("_discovery/raw/kzp24_data.xlsx")) if path.is_file()),
        None,
    )
    if workbook is None:
        print("Key-figure workbook is not on disk.", file=sys.stderr)
        return 2
    register = build_source_register(parse_key_figures(workbook), WEBSITES)
    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    with DbSession(engine) as session:
        catalog = load_catalog_mentions(session, directory, register)
        menus = load_homepage_menus(session, directory, register)
        session.commit()
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"catalog_pages: {catalog.pages}")
    print(f"catalog_assertions: {catalog.assertions}")
    print(f"menu_pages: {menus.pages}")
    print(f"menu_assertions: {menus.assertions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
