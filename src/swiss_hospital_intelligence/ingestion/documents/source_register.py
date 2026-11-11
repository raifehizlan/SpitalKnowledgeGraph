"""Source register for pilot establishments. No pages are downloaded here."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from swiss_hospital_intelligence.ingestion.structured.records import KeyFigureParse

UrlStatus = Literal["found", "not_found", "retrieval_blocked"]
IN_SCOPE_PAGE_TYPES = (
    "organization",
    "locations",
    "departments",
    "clinics",
    "services",
    "professionals",
    "equipment",
    "quality",
    "publications",
)


class WebsiteRecord(BaseModel):
    organization_name: str
    site_name: str | None = None
    url_status: UrlStatus = "found"
    url: str | None = None
    language: str | None = None
    source: str
    note: str = ""


class RegisterRow(BaseModel):
    organization_name: str
    site_name: str | None
    home_canton: str
    site_canton: str | None
    url_status: UrlStatus
    url: str | None
    language: str | None
    source: str | None
    note: str


class SourceRegister(BaseModel):
    in_scope_page_types: list[str] = Field(default_factory=lambda: list(IN_SCOPE_PAGE_TYPES))
    annual_reports: str = "not_reviewed"
    rows: list[RegisterRow]
    unused_records: list[str] = Field(default_factory=list)

    def establishments(self) -> list[RegisterRow]:
        return [row for row in self.rows if row.site_name is None]


def build_source_register(
    key_figures: KeyFigureParse,
    websites: list[WebsiteRecord],
    *,
    home_canton: str = "GR",
) -> SourceRegister:
    establishments = [row for row in key_figures.establishments if row.home_canton == home_canton]
    known = {(item.organization_name, item.site_name) for item in websites}
    used: set[tuple[str, str | None]] = set()
    rows: list[RegisterRow] = []
    for establishment in sorted(establishments, key=lambda item: item.name):
        rows.append(_row(establishment.name, None, establishment.home_canton, None, websites, used))
        for site in key_figures.sites:
            if site.parent_name != establishment.name:
                continue
            rows.append(
                _row(establishment.name, site.name, establishment.home_canton, site.canton_code, websites, used)
            )
    unused = sorted(
        f"{organization} / {site or 'establishment'}"
        for organization, site in known - used
    )
    return SourceRegister(rows=rows, unused_records=unused)


def render_source_register(register: SourceRegister) -> str:
    lines = [
        "Graubünden source register",
        "annual_reports: not_reviewed",
        "in_scope: " + ", ".join(register.in_scope_page_types),
        "",
    ]
    for row in register.rows:
        label = row.organization_name if row.site_name is None else f"{row.organization_name} / {row.site_name}"
        place = row.home_canton if row.site_canton is None else row.site_canton
        lines.append(f"{row.url_status} [{place}] {label}")
        if row.url:
            lines.append(f"  url: {row.url}")
        if row.note:
            lines.append(f"  note: {row.note}")
    if register.unused_records:
        lines.extend(["", "Unused website records"])
        lines.extend(f"- {item}" for item in register.unused_records)
    return "\n".join(lines) + "\n"


def _row(
    organization: str,
    site: str | None,
    home_canton: str,
    site_canton: str | None,
    websites: list[WebsiteRecord],
    used: set[tuple[str, str | None]],
) -> RegisterRow:
    matches = [
        item
        for item in websites
        if item.organization_name == organization and item.site_name == site
    ]
    if len(matches) != 1:
        return RegisterRow(
            organization_name=organization,
            site_name=site,
            home_canton=home_canton,
            site_canton=site_canton,
            url_status="not_found",
            url=None,
            language=None,
            source=None,
            note="No official website was recorded for this row.",
        )
    used.add((organization, site))
    record = matches[0]
    return RegisterRow(
        organization_name=organization,
        site_name=site,
        home_canton=home_canton,
        site_canton=site_canton,
        url_status=record.url_status,
        url=record.url,
        language=record.language,
        source=record.source,
        note=record.note,
    )
