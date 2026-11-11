"""Only a normalized exact 2024 name links a quality institution."""

from __future__ import annotations

from pathlib import Path

import pytest

from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.name_link import (
    MATCH_METHOD,
    link_institution_names,
    normalize_name,
)
from swiss_hospital_intelligence.ingestion.structured.qip import parse_quality_indicators

ESTABLISHMENTS = [
    "Kantonsspital Graubünden",
    "Flury Stiftung Spital Schiers",
    "Spital Davos AG Akutabteilung",
    "Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
]


def test_whitespace_and_case_match_but_a_near_miss_does_not() -> None:
    links = {
        link.source_name: link
        for link in link_institution_names(
            [
                "  Kantonsspital   Graubünden ",
                "kantonsspital graubünden",
                "Flury Stiftung - Spital Schiers",
                "Spital Davos",
                "Gesundheitszentrum Unterengadin",
            ],
            ESTABLISHMENTS,
        )
    }
    assert links["  Kantonsspital   Graubünden "].match_status == "exact"
    assert links["  Kantonsspital   Graubünden "].organization_name == "Kantonsspital Graubünden"
    assert links["  Kantonsspital   Graubünden "].method == MATCH_METHOD
    assert links["kantonsspital graubünden"].match_status == "exact"
    assert links["Flury Stiftung - Spital Schiers"].match_status == "unmatched"
    assert links["Flury Stiftung - Spital Schiers"].organization_name is None
    assert links["Spital Davos"].match_status == "unmatched"
    assert links["Gesundheitszentrum Unterengadin"].match_status == "unmatched"


def test_two_establishments_with_the_same_normalized_name_stay_unmatched() -> None:
    links = link_institution_names(["Shared Name"], ["Shared Name", "shared   name"])
    assert links[0].match_status == "unmatched"
    assert normalize_name("Shared Name") == normalize_name("shared   name")


def _existing(*relative_paths: str) -> Path | None:
    root = Path(__file__).resolve().parents[2]
    for relative in relative_paths:
        path = root / relative
        if path.is_file():
            return path
    return None


@pytest.mark.skipif(
    _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx") is None
    or _existing("data/raw/qip24_tabdaten.csv", "_discovery/raw/qip24_tabdaten_head.csv") is None,
    reason="BAG key-figure and quality files are not both on disk",
)
def test_real_2024_names_link_only_when_normalized_text_matches() -> None:
    key_figures = _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx")
    quality = _existing("data/raw/qip24_tabdaten.csv", "_discovery/raw/qip24_tabdaten_head.csv")
    assert key_figures is not None and quality is not None
    establishments = [row.name for row in parse_key_figures(key_figures).establishments]
    institutions = sorted({row.institution for row in parse_quality_indicators(quality).rows})
    links = {link.source_name: link for link in link_institution_names(institutions, establishments)}

    assert links["Kantonsspital Graubünden"].match_status == "exact"
    assert links["Flury Stiftung Spital Schiers"].organization_name == "Flury Stiftung Spital Schiers"
    for name in ("Spital Oberengadin", "Spital Thusis", "Spital Davos AG Akutabteilung"):
        assert links[name].match_status == "exact"
    assert "Spital Davos" not in links or links["Spital Davos"].match_status == "unmatched"
    for link in links.values():
        if link.match_status != "exact":
            continue
        assert link.organization_name is not None
        assert normalize_name(link.source_name) == normalize_name(link.organization_name)
