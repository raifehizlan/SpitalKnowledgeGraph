"""The local BAG files produce the Phase 1 structured quality report."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.qip import parse_quality_indicators
from swiss_hospital_intelligence.reports.gr_cantonal_page import NAMES, PAGE_NOTE, PAGE_URL
from swiss_hospital_intelligence.reports.reviewed_aliases import ALIASES, METHOD
from swiss_hospital_intelligence.reports.structured_quality import (
    ReportSource,
    build_structured_quality_report,
    key_figure_sources,
    render_structured_quality_report,
)

ROOT = Path(__file__).resolve().parents[2]


def _existing(*relative_paths: str) -> Path | None:
    for relative in relative_paths:
        path = ROOT / relative
        if path.is_file():
            return path
    return None


KEY_FIGURES = _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx")
QUALITY = _existing(
    "data/raw/qip24_tabdaten.csv",
    "_discovery/raw/qip24_tabdaten.csv",
    "_discovery/raw/qip24_tabdaten_head.csv",
)


@pytest.mark.skipif(
    KEY_FIGURES is None or QUALITY is None,
    reason="BAG key-figure and quality files are not both on disk",
)
def test_real_files_report_270_organizations_and_unmatched_cantonal_names() -> None:
    assert KEY_FIGURES is not None and QUALITY is not None
    sources = key_figure_sources(KEY_FIGURES.name)
    sources.append(
        ReportSource(
            role="quality indicators",
            filename=QUALITY.name,
            note="Acute-hospital quality file.",
        )
    )
    sources.append(
        ReportSource(
            role="Graubünden cantonal page",
            filename=None,
            url=PAGE_URL,
            note=PAGE_NOTE,
        )
    )
    report = build_structured_quality_report(
        parse_key_figures(KEY_FIGURES),
        NAMES,
        quality=parse_quality_indicators(QUALITY),
        sources=sources,
        reviewed_aliases=ALIASES,
    )

    assert report.organization_count == 270
    assert report.quality_institution_count == 162
    assert [failure.reason for failure in report.quality_failures] == ["fewer than 10 fields"] * 3
    assert sum(row.quality_file == "present" for row in report.establishments) == 12
    assert sum(row.quality_file == "absent" for row in report.establishments) == 6
    assert report.excluded_national_rows == 1
    assert report.graubuenden_home_canton_count == 18
    assert report.manual_review_names == []
    reviewed = {
        item.source_name: item.organization_name
        for item in report.cantonal_names
        if item.match_status == "reviewed"
    }
    assert reviewed == {alias.source_name: alias.organization_name for alias in ALIASES}
    assert all(
        item.method == METHOD and item.evidence
        for item in report.cantonal_names
        if item.match_status == "reviewed"
    )
    exact = {
        item.source_name: item.organization_name
        for item in report.cantonal_names
        if item.match_status == "exact"
    }
    assert exact == {
        "Kantonsspital Graubünden": "Kantonsspital Graubünden",
        "Spital Oberengadin": "Spital Oberengadin",
        "Spital Thusis": "Spital Thusis",
        "Psychiatrische Dienste Graubünden": "Psychiatrische Dienste Graubünden",
    }

    by_name = {row.name: row for row in report.establishments}
    ksgr = by_name["Kantonsspital Graubünden"]
    assert ksgr.acute_beds == Decimal("343")
    assert "MRI" in ksgr.equipment
    assert ksgr.quality_file == "present"
    walenstadt = next(site for site in ksgr.sites if site.name == "Spital Walenstadt")
    assert walenstadt.canton_code == "SG"
    flury = by_name["Flury Stiftung Spital Schiers"]
    assert flury.acute_beds is not None
    assert flury.acute_beds != flury.acute_beds.to_integral_value()
    assert by_name["Psychiatrische Dienste Graubünden"].quality_file == "absent"
    assert any(
        site.canton_code == "GL"
        for row in report.establishments
        for site in row.sites
    )
    text = render_structured_quality_report(report)
    assert "organizations: 270" in text
    assert "Spital Walenstadt [SG]" in text
    assert "reviewed: Spital Davos -> Spital Davos AG Akutabteilung (reviewed_same_establishment)" in text
