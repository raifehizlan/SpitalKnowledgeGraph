"""PostgreSQL tables. The database is the system of record."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Source(Base):
    __tablename__ = "source"

    id: Mapped[uuid.UUID] = _id()
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    reliability_class: Mapped[str | None] = mapped_column(String(64))


class SourceFile(Base):
    __tablename__ = "source_file"

    id: Mapped[uuid.UUID] = _id()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    checksum: Mapped[str] = mapped_column(String(128))
    filename: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HospitalOrganization(Base):
    __tablename__ = "hospital_organization"

    id: Mapped[uuid.UUID] = _id()
    home_canton_code: Mapped[str] = mapped_column(String(2))
    typology_code: Mapped[str | None] = mapped_column(String(8))
    legal_form_code: Mapped[str | None] = mapped_column(String(8))
    street: Mapped[str | None] = mapped_column(Text)
    postal_place: Mapped[str | None] = mapped_column(Text)
    reference_year: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(32), default="verified")


class OrganizationName(Base):
    __tablename__ = "organization_name"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital_organization.id"))
    name: Mapped[str] = mapped_column(Text)
    name_role: Mapped[str] = mapped_column(String(32))
    match_status: Mapped[str] = mapped_column(String(32))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))


class HospitalSite(Base):
    __tablename__ = "hospital_site"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital_organization.id"))
    canton_code: Mapped[str] = mapped_column(String(2))
    street: Mapped[str | None] = mapped_column(Text)
    postal_place: Mapped[str | None] = mapped_column(Text)
    reference_year: Mapped[int] = mapped_column(Integer)


class SiteName(Base):
    __tablename__ = "site_name"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital_site.id"))
    name: Mapped[str] = mapped_column(Text)
    name_role: Mapped[str] = mapped_column(String(32))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))


class EntityCrosswalk(Base):
    __tablename__ = "entity_crosswalk"

    id: Mapped[uuid.UUID] = _id()
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_file.id"))
    source_row_fingerprint: Mapped[str] = mapped_column(String(128))
    target_table: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True))
    match_status: Mapped[str] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(64))


class OrganizationCodeSet(Base):
    __tablename__ = "organization_code_set"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital_organization.id"))
    code_set: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(32))
    reference_year: Mapped[int] = mapped_column(Integer)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))


class ListMembership(Base):
    __tablename__ = "list_membership"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    source_name: Mapped[str] = mapped_column(Text)
    reference_year: Mapped[int] = mapped_column(Integer)
    street: Mapped[str | None] = mapped_column(Text)
    postal_place: Mapped[str | None] = mapped_column(Text)
    home_list_state: Mapped[str] = mapped_column(String(32))
    other_list_state: Mapped[str] = mapped_column(String(32))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))
    source_row_fingerprint: Mapped[str | None] = mapped_column(String(128))


class ServiceMandate(Base):
    """One official Leistungsauftrag. This is not a department and not a site."""

    __tablename__ = "service_mandate"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))
    list_kind: Mapped[str] = mapped_column(String(32))
    edition: Mapped[str] = mapped_column(String(32))
    canton_scope: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(Text)
    match_status: Mapped[str] = mapped_column(String(32))
    source_row_fingerprint: Mapped[str] = mapped_column(String(128))


class MeasureDefinition(Base):
    __tablename__ = "measure_definition"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit: Mapped[str] = mapped_column(String(32))
    activity_type: Mapped[str | None] = mapped_column(String(1))
    scope: Mapped[str] = mapped_column(String(32))
    publication_status: Mapped[str] = mapped_column(String(32))


class StatisticObservation(Base):
    __tablename__ = "statistic_observation"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'establishment' AND organization_id IS NOT NULL AND site_id IS NULL) "
            "OR (scope = 'national' AND organization_id IS NULL AND site_id IS NULL) "
            "OR (scope = 'site' AND site_id IS NOT NULL AND organization_id IS NULL)",
            name="statistic_scope_ck",
        ),
    )

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_site.id"))
    measure_code: Mapped[str] = mapped_column(ForeignKey("measure_definition.code"))
    reference_year: Mapped[int] = mapped_column(Integer)
    activity_type: Mapped[str | None] = mapped_column(String(1))
    scope: Mapped[str] = mapped_column(String(32))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    raw_value: Mapped[str | None] = mapped_column(Text)
    value_state: Mapped[str] = mapped_column(String(32))
    unit: Mapped[str] = mapped_column(String(32))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))
    source_row_fingerprint: Mapped[str] = mapped_column(String(128))


class QualityIndicator(Base):
    __tablename__ = "quality_indicator"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(16))


class QualityObservation(Base):
    __tablename__ = "quality_observation"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_site.id"))
    indicator_code: Mapped[str] = mapped_column(ForeignKey("quality_indicator.code"))
    time_window: Mapped[str] = mapped_column(String(16))
    source_institution_name: Mapped[str] = mapped_column(Text)
    match_status: Mapped[str] = mapped_column(String(32))
    observed_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    observed_rate_state: Mapped[str] = mapped_column(String(32))
    expected_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    expected_rate_state: Mapped[str] = mapped_column(String(32))
    smr: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    smr_state: Mapped[str] = mapped_column(String(32))
    case_count: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    case_count_state: Mapped[str] = mapped_column(String(32))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))
    title: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(8))
    checksum: Mapped[str | None] = mapped_column(String(128))
    processing_status: Mapped[str] = mapped_column(String(32), default="registered")


class DocumentChunk(Base):
    __tablename__ = "document_chunk"

    id: Mapped[uuid.UUID] = _id()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"))
    text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    ordinal: Mapped[int] = mapped_column(Integer)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = _id()
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document.id"))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_file.id"))
    excerpt: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(64))


class Assertion(Base):
    __tablename__ = "assertion"

    id: Mapped[uuid.UUID] = _id()
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_organization.id"))
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospital_site.id"))
    predicate: Mapped[str] = mapped_column(String(64))
    object_value: Mapped[str | None] = mapped_column(Text)
    fact_status: Mapped[str] = mapped_column(String(32))
    assertion_mode: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
