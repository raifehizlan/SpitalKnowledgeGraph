"""Attach saved pages to a 2024 establishment.

The host must belong to exactly one official website. A page on that host
gets the establishment id. It does not get a site id. A Valens URL is linked
only under /reha-chur, because that host publishes the whole group.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Document,
    DocumentChunk,
    EntityCrosswalk,
    Source,
    SourceFile,
)
from swiss_hospital_intelligence.ingestion.documents.parse_documents import ParsedDocument
from swiss_hospital_intelligence.ingestion.documents.source_register import SourceRegister

SOURCE_CODE = "GR-WEB-PAGES"
SOURCE_NAME = "Graubünden hospital websites"
LANGUAGE_CODES = {"de", "fr", "it", "rm", "en"}
METHOD = "official_website_host"


class Scope(BaseModel):
    organization_name: str
    path_prefix: str | None


class DocumentLoadResult(BaseModel):
    documents: int
    linked: int
    unlinked: int
    chunks: int


def establishment_scopes(register: SourceRegister) -> dict[str, Scope | None]:
    found: dict[str, set[str]] = {}
    prefixes: dict[tuple[str, str], str | None] = {}
    for row in register.rows:
        if row.site_name is not None or row.url_status != "found" or not row.url:
            continue
        host = _host(row.url)
        found.setdefault(host, set()).add(row.organization_name)
        prefixes[(host, row.organization_name)] = _path_prefix(row.url)
    scopes: dict[str, Scope | None] = {}
    for host, names in found.items():
        if len(names) != 1:
            scopes[host] = None
            continue
        name = next(iter(names))
        scopes[host] = Scope(organization_name=name, path_prefix=prefixes[(host, name)])
    return scopes


def organization_name_for_url(url: str, scopes: dict[str, Scope | None]) -> str | None:
    host = _host(url)
    scope = scopes.get(host)
    if scope is None:
        return None
    path = urlparse(url).path.casefold()
    if scope.path_prefix and not (path == scope.path_prefix or path.startswith(scope.path_prefix + "/")):
        return None
    return scope.organization_name


def load_parsed_documents(
    session: Session,
    documents: list[ParsedDocument],
    scopes: dict[str, Scope | None],
    organization_ids: dict[str, UUID],
) -> DocumentLoadResult:
    linked = 0
    unlinked = 0
    chunks = 0
    for parsed in documents:
        name = organization_name_for_url(parsed.source_url or "", scopes)
        organization_id = organization_ids.get(name) if name else None
        if organization_id is None:
            unlinked += 1
        else:
            linked += 1
        source_file_id = _source_file(
            session, parsed.checksum, parsed.source_url or parsed.checksum or "page"
        ).id
        document = _upsert_document(session, source_file_id, parsed, organization_id)
        chunks += _replace_chunks(session, document, parsed)
    session.flush()
    return DocumentLoadResult(
        documents=len(documents),
        linked=linked,
        unlinked=unlinked,
        chunks=chunks,
    )


def load_parsed_jsonl(
    session: Session,
    path: Path,
    scopes: dict[str, Scope | None],
    organization_ids: dict[str, UUID],
) -> DocumentLoadResult:
    documents = [
        ParsedDocument.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    return load_parsed_documents(session, documents, scopes, organization_ids)


def _upsert_document(
    session: Session,
    source_file_id: UUID,
    parsed: ParsedDocument,
    organization_id: UUID | None,
) -> Document:
    fingerprint = _fingerprint(parsed.source_url or parsed.checksum or "")
    existing_id = session.scalar(
        select(EntityCrosswalk.target_id).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == fingerprint,
        )
    )
    if existing_id is None:
        document = Document(
            organization_id=organization_id,
            source_file_id=source_file_id,
            title=parsed.title,
            source_url=parsed.source_url,
            document_type=parsed.media_type,
            language=parsed.language,
            checksum=parsed.checksum,
            processing_status=parsed.processing_status,
        )
        session.add(document)
        session.flush()
        session.add(
            EntityCrosswalk(
                source_file_id=source_file_id,
                source_row_fingerprint=fingerprint,
                target_table="document",
                target_id=document.id,
                match_status="exact" if organization_id else "unlinked",
                method=METHOD,
            )
        )
        return document
    document = session.get(Document, existing_id)
    if document is None:
        raise KeyError(fingerprint)
    document.organization_id = organization_id
    document.title = parsed.title
    document.source_url = parsed.source_url
    document.document_type = parsed.media_type
    document.language = parsed.language
    document.checksum = parsed.checksum
    document.processing_status = parsed.processing_status
    return document


def _replace_chunks(session: Session, document: Document, parsed: ParsedDocument) -> int:
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    for chunk in parsed.chunks:
        session.add(
            DocumentChunk(
                document_id=document.id,
                text=chunk.text,
                page_number=chunk.page_number,
                section=chunk.section,
                language=chunk.language,
                ordinal=chunk.ordinal,
            )
        )
    return len(parsed.chunks)


def _source_file(session: Session, checksum: str | None, filename: str) -> SourceFile:
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
    digest = checksum or _fingerprint(filename)
    existing = session.scalar(
        select(SourceFile).where(SourceFile.source_id == source.id, SourceFile.checksum == digest)
    )
    if existing is not None:
        return existing
    created = SourceFile(source_id=source.id, checksum=digest, filename=filename[:500])
    session.add(created)
    session.flush()
    return created


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        return host[4:]
    return host


def _path_prefix(url: str) -> str | None:
    segments = [segment for segment in urlparse(url).path.split("/") if segment]
    if not segments or segments[0].casefold() in LANGUAGE_CODES:
        return None
    return "/" + segments[0].casefold()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_organization_ids(session: Session) -> dict[str, UUID]:
    from swiss_hospital_intelligence.database.schema import OrganizationName

    rows = session.execute(
        select(OrganizationName.name, OrganizationName.organization_id).where(
            OrganizationName.name_role == "source_primary"
        )
    ).all()
    counts: dict[str, int] = {}
    for name, _organization_id in rows:
        counts[name] = counts.get(name, 0) + 1
    return {name: organization_id for name, organization_id in rows if counts[name] == 1}


def main() -> int:
    import sys

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    from swiss_hospital_intelligence.ingestion.documents.gr_websites import WEBSITES
    from swiss_hospital_intelligence.ingestion.documents.source_register import build_source_register
    from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
    from swiss_hospital_intelligence.ingestion.structured.load_kzp import load_key_figures

    workbook = next(
        (
            candidate
            for candidate in (Path("data/raw/kzp24_data.xlsx"), Path("_discovery/raw/kzp24_data.xlsx"))
            if candidate.is_file()
        ),
        None,
    )
    parsed_path = Path("data/processed/gr/parsed_documents.jsonl")
    if workbook is None or not parsed_path.is_file():
        print("Workbook or parsed documents are missing.", file=sys.stderr)
        return 2
    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    with DbSession(engine) as session:
        figures = load_key_figures(session, workbook)
        register = build_source_register(parse_key_figures(workbook), WEBSITES)
        result = load_parsed_jsonl(session, parsed_path, establishment_scopes(register), read_organization_ids(session))
        session.commit()
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"organizations: {figures.organizations}")
    print(f"sites: {figures.sites}")
    print(f"documents: {result.documents}")
    print(f"linked: {result.linked}")
    print(f"unlinked: {result.unlinked}")
    print(f"chunks: {result.chunks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
