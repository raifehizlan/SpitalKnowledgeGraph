"""Load a parsed key-figure workbook into PostgreSQL.

The same file checksum and the same row fingerprint update the existing ids.
A second run does not create another organization, site, or statistic.
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
    HospitalOrganization,
    HospitalSite,
    MeasureDefinition,
    OrganizationCodeSet,
    OrganizationName,
    SiteName,
    Source,
    SourceFile,
    StatisticObservation,
)
from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.measures import (
    PUBLISHED_MEASURES,
    UNPUBLISHED_MEASURES,
)
from swiss_hospital_intelligence.ingestion.structured.records import (
    KeyFigureParse,
    MeasureObservation,
    ParsedEstablishment,
    ParsedSite,
    require_establishment_scope,
)

SOURCE_CODE = "BAG-KZP-2024"
SOURCE_NAME = "Kennzahlen der Schweizer Spitäler 2024"
MATCH_METHOD = "exact_normalized_name_2024"


class LoadResult(BaseModel):
    source_file_id: UUID
    organizations: int
    sites: int
    statistics: int
    excluded_national_rows: int


def load_key_figures(session: Session, path: Path | str) -> LoadResult:
    workbook = Path(path)
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
    return load_key_figure_parse(
        session,
        parse_key_figures(workbook),
        checksum=digest,
        filename=workbook.name,
    )


def load_key_figure_parse(
    session: Session,
    parsed: KeyFigureParse,
    *,
    checksum: str,
    filename: str,
) -> LoadResult:
    source_file = _source_file(session, checksum, filename)
    _ensure_measures(session)
    organizations = {
        row.name: _upsert_organization(session, source_file.id, row) for row in parsed.establishments
    }
    for row in parsed.establishments:
        _replace_codes(session, source_file.id, organizations[row.name], row)
        for measure in row.measures:
            _upsert_statistic(session, source_file.id, organizations[row.name], row, measure)
    for site in parsed.sites:
        parent = organizations.get(site.parent_name)
        if parent is None:
            continue
        _upsert_site(session, source_file.id, parent, site)
    session.flush()
    return LoadResult(
        source_file_id=source_file.id,
        organizations=len(parsed.establishments),
        sites=len(parsed.sites),
        statistics=sum(len(row.measures) for row in parsed.establishments),
        excluded_national_rows=parsed.excluded_national_rows,
    )


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


def _ensure_measures(session: Session) -> None:
    for spec in PUBLISHED_MEASURES.values():
        _measure_definition(session, spec.code, spec.unit, spec.activity_type, "published")
    for code in sorted(UNPUBLISHED_MEASURES):
        _measure_definition(session, code, "undeclared", None, "present_but_not_published")


def _measure_definition(
    session: Session,
    code: str,
    unit: str,
    activity_type: str | None,
    publication_status: str,
) -> None:
    if session.get(MeasureDefinition, code) is not None:
        return
    session.add(
        MeasureDefinition(
            code=code,
            unit=unit,
            activity_type=activity_type,
            scope="establishment",
            publication_status=publication_status,
        )
    )


def _upsert_organization(
    session: Session,
    source_file_id: UUID,
    row: ParsedEstablishment,
) -> HospitalOrganization:
    fingerprint = _fingerprint("organization", str(row.reference_year), row.name)
    existing_id = _linked_id(session, source_file_id, fingerprint)
    if existing_id is None:
        organization = HospitalOrganization(
            home_canton_code=row.home_canton,
            typology_code=row.typology_code,
            legal_form_code=row.legal_form_code,
            street=row.street,
            postal_place=row.postal_place,
            reference_year=row.reference_year,
            verification_status="verified",
        )
        session.add(organization)
        session.flush()
        session.add(
            OrganizationName(
                organization_id=organization.id,
                name=row.name,
                name_role="source_primary",
                match_status="exact",
                source_file_id=source_file_id,
            )
        )
        _link(session, source_file_id, fingerprint, "hospital_organization", organization.id)
        return organization
    organization = session.get(HospitalOrganization, existing_id)
    if organization is None:
        raise KeyError(fingerprint)
    organization.home_canton_code = row.home_canton
    organization.typology_code = row.typology_code
    organization.legal_form_code = row.legal_form_code
    organization.street = row.street
    organization.postal_place = row.postal_place
    organization.reference_year = row.reference_year
    return organization


def _upsert_site(
    session: Session,
    source_file_id: UUID,
    organization: HospitalOrganization,
    row: ParsedSite,
) -> HospitalSite:
    fingerprint = _fingerprint(
        "site",
        str(row.reference_year),
        row.parent_name,
        row.name,
        row.street or "",
        row.postal_place or "",
    )
    existing_id = _linked_id(session, source_file_id, fingerprint)
    if existing_id is None:
        site = HospitalSite(
            organization_id=organization.id,
            canton_code=row.canton_code,
            street=row.street,
            postal_place=row.postal_place,
            reference_year=row.reference_year,
        )
        session.add(site)
        session.flush()
        session.add(
            SiteName(
                site_id=site.id,
                name=row.name,
                name_role="source_primary",
                source_file_id=source_file_id,
            )
        )
        _link(session, source_file_id, fingerprint, "hospital_site", site.id)
        return site
    site = session.get(HospitalSite, existing_id)
    if site is None:
        raise KeyError(fingerprint)
    site.canton_code = row.canton_code
    site.street = row.street
    site.postal_place = row.postal_place
    site.reference_year = row.reference_year
    return site


def _replace_codes(
    session: Session,
    source_file_id: UUID,
    organization: HospitalOrganization,
    row: ParsedEstablishment,
) -> None:
    wanted = {
        ("activity", code) for code in row.activities
    } | {
        ("specific_service", code) for code in row.specific_services
    } | {
        ("training", code) for code in row.training
    } | {
        ("equipment", code) for code in row.equipment
    } | {
        ("service_offer", code) for code in row.service_offer
    }
    existing = session.scalars(
        select(OrganizationCodeSet).where(
            OrganizationCodeSet.organization_id == organization.id,
            OrganizationCodeSet.source_file_id == source_file_id,
            OrganizationCodeSet.reference_year == row.reference_year,
        )
    ).all()
    seen = {(item.code_set, item.code) for item in existing}
    for item in existing:
        if (item.code_set, item.code) not in wanted:
            session.delete(item)
    for code_set, code in sorted(wanted - seen):
        session.add(
            OrganizationCodeSet(
                organization_id=organization.id,
                code_set=code_set,
                code=code,
                reference_year=row.reference_year,
                source_file_id=source_file_id,
            )
        )


def _upsert_statistic(
    session: Session,
    source_file_id: UUID,
    organization: HospitalOrganization,
    row: ParsedEstablishment,
    measure: MeasureObservation,
) -> None:
    require_establishment_scope(measure, None)
    fingerprint = _fingerprint("statistic", str(row.reference_year), row.name, measure.code)
    existing_id = _linked_id(session, source_file_id, fingerprint)
    if existing_id is None:
        statistic = StatisticObservation(
            organization_id=organization.id,
            site_id=None,
            measure_code=measure.code,
            reference_year=row.reference_year,
            activity_type=measure.activity_type,
            scope=measure.scope,
            value_numeric=measure.value_numeric,
            raw_value=measure.raw_value,
            value_state=measure.value_state,
            unit=measure.unit,
            source_file_id=source_file_id,
            source_row_fingerprint=fingerprint,
        )
        session.add(statistic)
        session.flush()
        _link(session, source_file_id, fingerprint, "statistic_observation", statistic.id)
        return
    statistic = session.get(StatisticObservation, existing_id)
    if statistic is None:
        raise KeyError(fingerprint)
    statistic.value_numeric = measure.value_numeric
    statistic.raw_value = measure.raw_value
    statistic.value_state = measure.value_state
    statistic.unit = measure.unit
    statistic.activity_type = measure.activity_type
    statistic.site_id = None


def _linked_id(session: Session, source_file_id: UUID, fingerprint: str) -> UUID | None:
    return session.scalar(
        select(EntityCrosswalk.target_id).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == fingerprint,
        )
    )


def _link(
    session: Session,
    source_file_id: UUID,
    fingerprint: str,
    table: str,
    target_id: UUID,
) -> None:
    session.add(
        EntityCrosswalk(
            source_file_id=source_file_id,
            source_row_fingerprint=fingerprint,
            target_table=table,
            target_id=target_id,
            match_status="exact",
            method=MATCH_METHOD,
        )
    )


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
