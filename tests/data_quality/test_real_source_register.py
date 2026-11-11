"""Every 2024 Graubünden establishment has a source-register row."""

from __future__ import annotations

from pathlib import Path

import pytest

from swiss_hospital_intelligence.ingestion.documents.gr_websites import (
    SITE_PRAETTIGAU,
    SITE_SUDTAELER,
    WEBSITES,
)
from swiss_hospital_intelligence.ingestion.documents.source_register import build_source_register
from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures

ROOT = Path(__file__).resolve().parents[2]


def _workbook() -> Path | None:
    for relative in ("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx"):
        path = ROOT / relative
        if path.is_file():
            return path
    return None


@pytest.mark.skipif(_workbook() is None, reason="BAG key-figure workbook is not on disk")
def test_real_graubuenden_register_covers_every_establishment() -> None:
    path = _workbook()
    assert path is not None
    register = build_source_register(parse_key_figures(path), WEBSITES)
    establishments = register.establishments()
    assert len(establishments) == 18
    assert {row.url_status for row in establishments} == {"found"}
    assert all(row.url and row.source for row in establishments)
    assert register.unused_records == []
    assert register.annual_reports == "not_reviewed"

    by_key = {(row.organization_name, row.site_name): row for row in register.rows}
    walenstadt = by_key[("Kantonsspital Graubünden", "Spital Walenstadt")]
    assert walenstadt.url_status == "found"
    assert walenstadt.url == "https://www.ksgr.ch/standorte"
    assert walenstadt.site_canton == "SG"
    gut = by_key[("Klinik Gut St. Moritz AG", None)]
    assert "Via Arona 34" in gut.note
    assert by_key[("Psychiatrische Dienste Graubünden", "PDGR Jugendstation")].url_status == "not_found"
    assert by_key[("Psychiatrische Dienste Graubünden", SITE_PRAETTIGAU)].url_status == "not_found"
    assert by_key[("Psychiatrische Dienste Graubünden", SITE_SUDTAELER)].url_status == "not_found"
    glarus = by_key[("Psychiatrische Dienste Graubünden", "PDGR Tagesklinik Glarus")]
    assert glarus.url_status == "found"
    assert "pdgl" in glarus.note
