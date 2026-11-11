"""Load cantonal-list membership.

A 2024 row is linked to a key-figure establishment only when
`exact_normalized_name_2024` matches one name. Earlier years are not linked
with that method. The organization id is stored on the crosswalk, not copied
onto the membership row. The same file checksum updates the same rows.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    EntityCrosswalk,
    ListMembership,
    Source,
    SourceFile,
)
from swiss_hospital_intelligence.ingestion.structured.hosp_list import (
    ParsedListMembership,
    parse_cantonal_list,
)
from swiss_hospital_intelligence.ingestion.structured.load_kzp import SOURCE_CODE, SOURCE_NAME
from swiss_hospital_intelligence.ingestion.structured.name_link import (
    MATCH_METHOD,
    link_institution_names,
)

LINK_YEAR = 2024


class CantonalListLoadResult(BaseModel):
    source_file_id: UUID
    memberships: int
    exact_links: int
    undeclared_rows: int


def load_cantonal_list(
    session: Session,
    path: Path | str,
    establishment_ids: dict[str, UUID] | None = None,
) -> CantonalListLoadResult:
    workbook = Path(path)
    parsed = parse_cantonal_list(workbook)
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
    source_file = _source_file(session, digest, workbook.name)
    names = establishment_ids or {}
    exact = {
        link.source_name: link.organization_name
        for link in link_institution_names(
            [row.institution for row in parsed.memberships if row.reference_year == LINK_YEAR],
            list(names),
        )
        if link.match_status == "exact" and link.organization_name is not None
    }
    linked = 0
    for row in parsed.memberships:
        fingerprint = _fingerprint(row)
        membership = _upsert_membership(session, source_file.id, fingerprint, row)
        organization_name = exact.get(row.institution) if row.reference_year == LINK_YEAR else None
        organization_id = names.get(organization_name) if organization_name is not None else None
        if _reconcile_link(session, source_file.id, fingerprint, organization_id):
            linked += 1
        membership.organization_id = None
    session.flush()
    return CantonalListLoadResult(
        source_file_id=source_file.id,
        memberships=len(parsed.memberships),
        exact_links=linked,
        undeclared_rows=sum(
            1
            for row in parsed.memberships
            if row.home_list_state == "undeclared" or row.other_list_state == "undeclared"
        ),
    )


def _upsert_membership(
    session: Session,
    source_file_id: UUID,
    fingerprint: str,
    row: ParsedListMembership,
) -> ListMembership:
    existing = session.scalar(
        select(ListMembership).where(
            ListMembership.source_file_id == source_file_id,
            ListMembership.source_row_fingerprint == fingerprint,
        )
    )
    if existing is None:
        created = ListMembership(
            organization_id=None,
            source_name=row.institution,
            reference_year=row.reference_year,
            street=row.street,
            postal_place=row.postal_place,
            home_list_state=row.home_list_state,
            other_list_state=row.other_list_state,
            source_file_id=source_file_id,
            source_row_fingerprint=fingerprint,
        )
        session.add(created)
        session.flush()
        return created
    existing.source_name = row.institution
    existing.street = row.street
    existing.postal_place = row.postal_place
    existing.home_list_state = row.home_list_state
    existing.other_list_state = row.other_list_state
    existing.reference_year = row.reference_year
    return existing


def _reconcile_link(
    session: Session,
    source_file_id: UUID,
    fingerprint: str,
    organization_id: UUID | None,
) -> bool:
    link_fingerprint = _link_fingerprint(fingerprint)
    existing = session.scalars(
        select(EntityCrosswalk).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == link_fingerprint,
        )
    ).all()
    if organization_id is None:
        for item in existing:
            session.delete(item)
        return False
    if (
        len(existing) == 1
        and existing[0].target_id == organization_id
        and existing[0].match_status == "exact"
        and existing[0].method == MATCH_METHOD
    ):
        return True
    for item in existing:
        session.delete(item)
    session.add(
        EntityCrosswalk(
            source_file_id=source_file_id,
            source_row_fingerprint=link_fingerprint,
            target_table="hospital_organization",
            target_id=organization_id,
            match_status="exact",
            method=MATCH_METHOD,
        )
    )
    return True


def _source_file(session: Session, checksum: str, filename: str) -> SourceFile:
    source = session.scalar(select(Source).where(Source.code == SOURCE_CODE))
    if source is None:
        source = Source(
            code=SOURCE_CODE,
            name=SOURCE_NAME,
            url="https://opendata.swiss/de/dataset/kennzahlen-der-schweizer-spitaler-2024",
            reliability_class="official_federal_publication",
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


def _fingerprint(row: ParsedListMembership) -> str:
    return hashlib.sha256(
        "\n".join(
            (
                "list-membership",
                str(row.reference_year),
                row.institution,
                row.street or "",
                row.postal_place,
            )
        ).encode("utf-8")
    ).hexdigest()


def _link_fingerprint(membership_fingerprint: str) -> str:
    return hashlib.sha256(f"name-link\n{membership_fingerprint}".encode("utf-8")).hexdigest()
