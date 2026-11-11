"""The real 2024 workbook, when a local copy is already on disk."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = (
    ROOT / "data" / "raw" / "kzp24_data.xlsx",
    ROOT / "_discovery" / "raw" / "kzp24_data.xlsx",
)


def _workbook() -> Path | None:
    for path in CANDIDATES:
        if path.is_file():
            return path
    return None


@pytest.mark.skipif(_workbook() is None, reason="BAG key-figure workbook is not on disk")
def test_real_2024_key_figures_match_the_inspected_counts() -> None:
    path = _workbook()
    assert path is not None
    parsed = parse_key_figures(path)

    assert parsed.excluded_national_rows == 1
    assert len(parsed.establishments) == 270
    graubuenden = [row for row in parsed.establishments if row.home_canton == "GR"]
    assert len(graubuenden) == 18
    assert parsed.sites_without_establishment == []
    assert parsed.unknown_columns == []

    ksgr = parsed.establishment("Kantonsspital Graubünden")
    beds = next(item for item in ksgr.measures if item.code == "BettenStatA")
    assert beds.value_numeric == Decimal("343")
    assert "MRI" in ksgr.equipment
    ksgr_sites = [site for site in parsed.sites if site.parent_name == ksgr.name]
    assert len(ksgr_sites) == 2
    walenstadt = next(site for site in ksgr_sites if site.name == "Spital Walenstadt")
    assert walenstadt.canton_code == "SG"
    assert walenstadt.parent_home_canton == "GR"

    flury = parsed.establishment("Flury Stiftung Spital Schiers")
    assert flury.street is None
    flury_beds = next(item for item in flury.measures if item.code == "BettenStatA")
    assert flury_beds.value_numeric != flury_beds.value_numeric.to_integral_value()
