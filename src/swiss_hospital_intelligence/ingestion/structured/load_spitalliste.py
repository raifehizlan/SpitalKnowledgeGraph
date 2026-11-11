"""Load Spitalliste mandates.

A printed name links by exact_normalized_name_2024. If that misses and the
text before the first comma is itself an exact 2024 name, that prefix links
the row. A remaining name links only when it is a reviewed alias for one
establishment. Zürcher RehaZentren stays unmatched. The same file checksum
and the same row update one mandate. Nothing is written as a department or a site.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    EntityCrosswalk,
    OrganizationName,
    ServiceMandate,
    Source,
    SourceFile,
)
from swiss_hospital_intelligence.ingestion.structured.name_link import (
    MATCH_METHOD,
    link_institution_names,
)
from swiss_hospital_intelligence.reports.reviewed_aliases import (
    ALIASES,
    SPITALLISTE_ALIASES,
    ReviewedAlias,
)
from swiss_hospital_intelligence.ingestion.structured.spitalliste import (
    ParsedMandate,
    parse_spitalliste,
)

SOURCE_CODE = "GR-SPITALLISTE"
SOURCE_NAME = "Spitalliste des Kantons Graubünden"
SOURCE_URL = (
    "https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/"
    "InstitutionenGesundeitswesens/Spitaeler/Seiten/SpitallisteSpitalplanung.aspx"
)
COMMA_METHOD = "name_before_comma_exact_2024"


class SpitallisteLoadResult(BaseModel):
    source_file_id: UUID
    mandates: int
    exact_links: int
    reviewed_links: int
    unmatched: int


def load_spitalliste(
    session: Session,
    path: Path | str,
    establishment_ids: dict[str, UUID] | None = None,
    aliases: list[ReviewedAlias] | None = None,
) -> SpitallisteLoadResult:
    file_path = Path(path)
    parsed = parse_spitalliste(file_path)
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    source_file = _source_file(session, digest, file_path.name)
    names = establishment_ids if establishment_ids is not None else _establishment_ids(session)
    source_names = list(dict.fromkeys(row.source_name for row in parsed.mandates))
    exact = _exact_links(source_names, list(names))
    prefixes = {name: _before_comma(name) for name in source_names}
    prefix_links = _exact_links([prefix for prefix in prefixes.values() if prefix], list(names))
    reviewed = _reviewed_links(
        [*ALIASES, *SPITALLISTE_ALIASES] if aliases is None else aliases,
        names,
    )
    exact_count = 0
    reviewed_count = 0
    unmatched = 0
    for row in parsed.mandates:
        fingerprint = _fingerprint(row)
        organization_name, method = _linked_name(row.source_name, exact, prefixes, prefix_links, reviewed)
        organization_id = names.get(organization_name) if organization_name is not None else None
        if _upsert(session, source_file.id, fingerprint, row, organization_id, method):
            if method == "reviewed_same_establishment":
                reviewed_count += 1
            else:
                exact_count += 1
        else:
            unmatched += 1
    session.flush()
    return SpitallisteLoadResult(
        source_file_id=source_file.id,
        mandates=len(parsed.mandates),
        exact_links=exact_count,
        reviewed_links=reviewed_count,
        unmatched=unmatched,
    )


def _exact_links(source_names: list[str], establishment_names: list[str]) -> dict[str, str]:
    return {
        link.source_name: link.organization_name
        for link in link_institution_names(source_names, establishment_names)
        if link.match_status == "exact" and link.organization_name is not None
    }


def _before_comma(name: str) -> str | None:
    if "," not in name:
        return None
    prefix = name.split(",", 1)[0].strip()
    if not prefix or prefix == name:
        return None
    return prefix


def _reviewed_links(aliases: list[ReviewedAlias], establishment_ids: dict[str, UUID]) -> dict[str, str]:
    found: dict[str, str] = {}
    for alias in aliases:
        if alias.organization_name not in establishment_ids or alias.source_name in found:
            continue
        found[alias.source_name] = alias.organization_name
    return found


def _linked_name(
    source_name: str,
    exact: dict[str, str],
    prefixes: dict[str, str | None],
    prefix_links: dict[str, str],
    reviewed: dict[str, str],
) -> tuple[str | None, str]:
    if source_name in exact:
        return exact[source_name], MATCH_METHOD
    prefix = prefixes.get(source_name)
    if prefix and prefix in prefix_links:
        return prefix_links[prefix], COMMA_METHOD
    if source_name in reviewed:
        return reviewed[source_name], "reviewed_same_establishment"
    return None, "unmatched_name"


def _upsert(
    session: Session,
    source_file_id: UUID,
    fingerprint: str,
    row: ParsedMandate,
    organization_id: UUID | None,
    method: str,
) -> bool:
    if organization_id is None:
        status = "unmatched"
    elif method == "reviewed_same_establishment":
        status = "reviewed"
    else:
        status = "exact"
    existing = session.scalar(
        select(EntityCrosswalk).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        mandate = session.get(ServiceMandate, existing.target_id)
        if mandate is not None:
            mandate.organization_id = organization_id
            mandate.match_status = status
        existing.match_status = status
        existing.method = method
        return organization_id is not None
    mandate = ServiceMandate(
        organization_id=organization_id,
        source_file_id=source_file_id,
        list_kind=row.list_kind,
        edition=row.edition,
        canton_scope=row.canton_scope,
        source_name=row.source_name,
        code=row.code,
        label=row.label,
        match_status=status,
        source_row_fingerprint=fingerprint,
    )
    session.add(mandate)
    session.flush()
    session.add(
        EntityCrosswalk(
            source_file_id=source_file_id,
            source_row_fingerprint=fingerprint,
            target_table="service_mandate",
            target_id=mandate.id,
            match_status=status,
            method=method,
        )
    )
    return organization_id is not None


def _establishment_ids(session: Session) -> dict[str, UUID]:
    rows = session.execute(
        select(OrganizationName.name, OrganizationName.organization_id).where(
            OrganizationName.name_role == "source_primary"
        )
    )
    return {name: organization_id for name, organization_id in rows}


def _source_file(session: Session, checksum: str, filename: str) -> SourceFile:
    source = session.scalar(select(Source).where(Source.code == SOURCE_CODE))
    if source is None:
        source = Source(
            code=SOURCE_CODE,
            name=SOURCE_NAME,
            url=SOURCE_URL,
            reliability_class="official_cantonal_publication",
        )
        session.add(source)
        session.flush()
    existing = session.scalar(
        select(SourceFile).where(SourceFile.source_id == source.id, SourceFile.checksum == checksum)
    )
    if existing is not None:
        return existing
    created = SourceFile(source_id=source.id, checksum=checksum, filename=filename)
    session.add(created)
    session.flush()
    return created


def _fingerprint(row: ParsedMandate) -> str:
    code = row.code or ""
    text = "\n".join([row.list_kind, row.canton_scope, row.source_name, code, row.label])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    directory = Path("data/raw/spitalliste")
    files = sorted(directory.glob("*.pdf"))
    if not files:
        print("No Spitalliste PDF is on disk.", file=sys.stderr)
        return 2
    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    sys.stdout.reconfigure(encoding="utf-8")
    with DbSession(engine) as session:
        for path in files:
            result = load_spitalliste(session, path)
            print(
                f"{path.name}: mandates {result.mandates}, "
                f"exact {result.exact_links}, reviewed {result.reviewed_links}, "
                f"unmatched {result.unmatched}"
            )
        session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
