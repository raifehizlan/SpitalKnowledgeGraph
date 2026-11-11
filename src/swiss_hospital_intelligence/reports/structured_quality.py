"""Structured quality report for the 2024 tables.

Counts come from the parsed files. An exact normalized 2024 name is `exact`.
A reviewed alias is applied only when its target establishment is present.
Every other cantonal-page name stays `manual_review`. A missing quality row
is `absent`, not a zero.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from swiss_hospital_intelligence.ingestion.structured.kzp import ESTABLISHMENT_SHEET, SITE_SHEET
from swiss_hospital_intelligence.ingestion.structured.name_link import (
    MATCH_METHOD,
    link_institution_names,
)
from swiss_hospital_intelligence.ingestion.structured.qip import QualityParse
from swiss_hospital_intelligence.ingestion.structured.records import (
    KeyFigureParse,
    ParsedEstablishment,
)
from swiss_hospital_intelligence.reports.reviewed_aliases import ReviewedAlias

QualityCoverageStatus = Literal["present", "absent", "source_not_opened"]
NameReviewStatus = Literal["exact", "reviewed", "manual_review"]


class ReportSource(BaseModel):
    role: str
    filename: str | None
    sheet: str | None = None
    url: str | None = None
    note: str


class CantonalNameReview(BaseModel):
    source_name: str
    match_status: NameReviewStatus
    organization_name: str | None
    method: str | None
    evidence: str | None = None


class SiteLine(BaseModel):
    name: str
    canton_code: str
    postal_place: str | None


class EstablishmentLine(BaseModel):
    name: str
    home_canton: str
    sites: list[SiteLine]
    acute_beds: Decimal | None
    acute_beds_state: str | None
    acute_beds_unit: str | None
    equipment: list[str]
    quality_file: QualityCoverageStatus


class QualityFailureLine(BaseModel):
    line_number: int
    reason: str


class StructuredQualityReport(BaseModel):
    organization_count: int
    excluded_national_rows: int
    graubuenden_home_canton_count: int
    quality_institution_count: int | None
    quality_failures: list[QualityFailureLine] = Field(default_factory=list)
    cantonal_names: list[CantonalNameReview]
    establishments: list[EstablishmentLine]
    sources: list[ReportSource] = Field(default_factory=list)

    @property
    def manual_review_names(self) -> list[str]:
        return [item.source_name for item in self.cantonal_names if item.match_status == "manual_review"]


def build_structured_quality_report(
    key_figures: KeyFigureParse,
    cantonal_names: list[str],
    *,
    quality: QualityParse | None,
    sources: list[ReportSource],
    reviewed_aliases: list[ReviewedAlias] | None = None,
) -> StructuredQualityReport:
    establishment_names = [row.name for row in key_figures.establishments]
    aliases = _alias_index(reviewed_aliases or [])
    reviews = [
        _review(link.source_name, link.match_status, link.organization_name, link.method, aliases, establishment_names)
        for link in link_institution_names(cantonal_names, establishment_names)
    ]
    quality_names = sorted({row.institution for row in quality.rows}) if quality is not None else []
    quality_links = {
        link.organization_name: link.source_name
        for link in link_institution_names(quality_names, establishment_names)
        if link.match_status == "exact" and link.organization_name is not None
    }
    graubuenden = [row for row in key_figures.establishments if row.home_canton == "GR"]
    lines = [
        _establishment(row, key_figures, quality, quality_links)
        for row in sorted(graubuenden, key=lambda item: item.name)
    ]
    return StructuredQualityReport(
        organization_count=len(key_figures.establishments),
        excluded_national_rows=key_figures.excluded_national_rows,
        graubuenden_home_canton_count=len(graubuenden),
        quality_institution_count=len(quality_names) if quality is not None else None,
        quality_failures=[
            QualityFailureLine(line_number=failure.line_number, reason=failure.reason)
            for failure in quality.failures
        ]
        if quality is not None
        else [],
        cantonal_names=reviews,
        establishments=lines,
        sources=sources,
    )


def render_structured_quality_report(report: StructuredQualityReport) -> str:
    lines = [
        "Structured quality report",
        f"organizations: {report.organization_count}",
        f"excluded_national_rows: {report.excluded_national_rows}",
        f"graubuenden_home_canton: {report.graubuenden_home_canton_count}",
        f"quality_institutions: {_count(report.quality_institution_count)}",
        f"quality_failures: {_count(None if report.quality_institution_count is None else len(report.quality_failures))}",
        "",
        "Sources",
    ]
    for source in report.sources:
        location = ", ".join(
            part
            for part in (source.filename, source.sheet, source.url)
            if part
        )
        lines.append(f"- {source.role}: {location}. {source.note}")
    if report.quality_failures:
        lines.extend(["", "Quality lines that were not read as institutions"])
        for failure in report.quality_failures:
            lines.append(f"- line {failure.line_number}: {failure.reason}")
    lines.extend(["", "Cantonal names"])
    for review in report.cantonal_names:
        if review.match_status == "manual_review":
            lines.append(f"- manual_review: {review.source_name}")
            continue
        lines.append(
            f"- {review.match_status}: {review.source_name} -> {review.organization_name} ({review.method})"
        )
        if review.evidence:
            lines.append(f"  evidence: {review.evidence}")
    lines.extend(["", "Graubünden establishments"])
    for row in report.establishments:
        if row.acute_beds_state is None:
            beds = "not_in_source"
        elif row.acute_beds_state != "value":
            beds = row.acute_beds_state
        else:
            beds = f"{row.acute_beds} {row.acute_beds_unit}"
        sites = "; ".join(f"{site.name} [{site.canton_code}]" for site in row.sites) or "none"
        equipment = ", ".join(row.equipment) or "none"
        lines.append(row.name)
        lines.append(f"  sites: {sites}")
        lines.append(f"  BettenStatA: {beds}")
        lines.append(f"  equipment: {equipment}")
        lines.append(f"  quality_file: {row.quality_file}")
    cross_canton = [
        (row.name, site)
        for row in report.establishments
        for site in row.sites
        if site.canton_code != row.home_canton
    ]
    lines.extend(["", "Sites outside the home canton"])
    if not cross_canton:
        lines.append("- none")
    for organization, site in cross_canton:
        lines.append(f"- {site.name} [{site.canton_code}], home {organization}")
    return "\n".join(lines) + "\n"


def key_figure_sources(filename: str) -> list[ReportSource]:
    return [
        ReportSource(
            role="key figures",
            filename=filename,
            sheet=ESTABLISHMENT_SHEET,
            note="Establishment statistics. The national total row is excluded.",
        ),
        ReportSource(
            role="sites",
            filename=filename,
            sheet=SITE_SHEET,
            note="Site canton comes from this sheet. Beds are not on this sheet.",
        ),
    ]


def _alias_index(aliases: list[ReviewedAlias]) -> dict[str, ReviewedAlias]:
    index: dict[str, ReviewedAlias] = {}
    for alias in aliases:
        if alias.source_name in index:
            raise ValueError(f"duplicate reviewed alias for {alias.source_name}")
        index[alias.source_name] = alias
    return index


def _review(
    source_name: str,
    match_status: str,
    organization_name: str | None,
    method: str | None,
    aliases: dict[str, ReviewedAlias],
    establishment_names: list[str],
) -> CantonalNameReview:
    if match_status == "exact" and organization_name is not None and method == MATCH_METHOD:
        return CantonalNameReview(
            source_name=source_name,
            match_status="exact",
            organization_name=organization_name,
            method=method,
        )
    alias = aliases.get(source_name)
    if alias is not None and establishment_names.count(alias.organization_name) == 1:
        return CantonalNameReview(
            source_name=source_name,
            match_status="reviewed",
            organization_name=alias.organization_name,
            method=alias.method,
            evidence=alias.evidence,
        )
    return CantonalNameReview(
        source_name=source_name,
        match_status="manual_review",
        organization_name=None,
        method=None,
    )


def _establishment(
    row: ParsedEstablishment,
    key_figures: KeyFigureParse,
    quality: QualityParse | None,
    quality_links: dict[str, str],
) -> EstablishmentLine:
    beds = next((item for item in row.measures if item.code == "BettenStatA"), None)
    if quality is None:
        quality_file: QualityCoverageStatus = "source_not_opened"
    elif row.name in quality_links:
        quality_file = "present"
    else:
        quality_file = "absent"
    return EstablishmentLine(
        name=row.name,
        home_canton=row.home_canton,
        sites=[
            SiteLine(name=site.name, canton_code=site.canton_code, postal_place=site.postal_place)
            for site in key_figures.sites
            if site.parent_name == row.name
        ],
        acute_beds=beds.value_numeric if beds is not None else None,
        acute_beds_state=beds.value_state if beds is not None else None,
        acute_beds_unit=beds.unit if beds is not None else None,
        equipment=list(row.equipment),
        quality_file=quality_file,
    )


def _count(value: int | None) -> str:
    if value is None:
        return "source_not_opened"
    return str(value)
