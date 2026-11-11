"""Quality-indicator cells keep suppression and dashes distinct from zero."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from swiss_hospital_intelligence.ingestion.structured.qip import (
    QualityParseError,
    parse_quality_indicators,
)

SAMPLE = """\
institution;indicator;taux observé 2019-2023;taux attendu 2019-2023;SMR 2019-2023;nombre de cas 2019-2023;taux observé 2024;taux attendu 2024;SMR 2024;nombre de cas 2024
Synthetic Hospital;A Maladies cardiaques; ; ; ; ; ; ; ; 
Synthetic Hospital;A.1.1.M Mortality;5.0%;*;1.1;2'819;0.0%;4.1%;-;532;A comment with; an extra semicolon
Synthetic Hospital;A.1.2.M Empty history;;;;;3.6%;3.7%;1.0;15
Synthetic Hospital;J.2.8.P Sepsis;*;*;*;...;*;*;*;...
too-short;A.1.1.M Mortality;1
institution;indicator;durée de séjours (jours) 2019-2023;;;nombre de cas 2019-2023;durée de séjours (jours) 2024;;;nombre de cas 2024
Synthetic Hospital;A.1.12.X Stay;9.2;;;100;7.9;;;40
"""


def test_parser_preserves_suppression_dash_zero_and_comment(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_qip.csv"
    path.write_text(SAMPLE, encoding="utf-8")
    parsed = parse_quality_indicators(path)

    assert parsed.header_count == 2
    assert len(parsed.failures) == 1
    assert parsed.failures[0].reason == "fewer than 10 fields"

    heading = next(row for row in parsed.rows if row.indicator.startswith("A Maladies"))
    assert heading.row_kind == "heading"
    assert heading.components == []

    mortality = parsed.rows_for("Synthetic Hospital", "A.1.1.M")[0]
    assert mortality.comment == "A comment with; an extra semicolon"
    observed_2019 = next(
        item for item in mortality.components if item.role == "observed_rate" and item.window == "2019_2023"
    )
    suppressed = next(
        item for item in mortality.components if item.role == "expected_rate" and item.window == "2019_2023"
    )
    cases = next(item for item in mortality.components if item.role == "case_count" and item.window == "2019_2023")
    zero = next(item for item in mortality.components if item.role == "observed_rate" and item.window == "2024")
    dash = next(item for item in mortality.components if item.role == "smr" and item.window == "2024")
    assert observed_2019.value_numeric == Decimal("5.0")
    assert suppressed.value_state == "suppressed"
    assert suppressed.value_numeric is None
    assert cases.value_numeric == Decimal("2819")
    assert zero.value_numeric == Decimal("0.0")
    assert zero.value_state == "value"
    assert dash.value_state == "dash"
    assert dash.value_numeric is None

    history = parsed.rows_for("Synthetic Hospital", "A.1.2.M")[0]
    missing = next(
        item for item in history.components if item.role == "observed_rate" and item.window == "2019_2023"
    )
    assert missing.value_state == "not_available_in_source"
    assert missing.value_numeric is None

    sepsis = parsed.rows_for("Synthetic Hospital", "J.2.8.P")[0]
    ellipsis = next(item for item in sepsis.components if item.raw_value == "...")
    assert ellipsis.value_state == "unknown"
    assert ellipsis.value_numeric is None

    stay = parsed.rows_for("Synthetic Hospital", "A.1.12.X")[0]
    days = next(item for item in stay.components if item.role == "length_of_stay_days" and item.window == "2024")
    assert days.value_numeric == Decimal("7.9")
    assert all(item.role != "smr" for item in stay.components)


def test_file_without_a_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("Synthetic Hospital;A.1.1.M Mortality;1;2;3;4;5;6;7;8\n", encoding="utf-8")
    with pytest.raises(QualityParseError):
        parse_quality_indicators(path)


ROOT = Path(__file__).resolve().parents[2]
REAL = (
    ROOT / "data" / "raw" / "qip24_tabdaten.csv",
    ROOT / "_discovery" / "raw" / "qip24_tabdaten_head.csv",
)


def _real() -> Path | None:
    for path in REAL:
        if path.is_file():
            return path
    return None


@pytest.mark.skipif(_real() is None, reason="BAG quality indicator file is not on disk")
def test_real_quality_file_keeps_ksgr_rate_and_comments() -> None:
    path = _real()
    assert path is not None
    parsed = parse_quality_indicators(path)
    matches = parsed.rows_for("Kantonsspital Graubünden", "A.1.1.M")
    assert matches
    observed = next(
        item for item in matches[0].components if item.role == "observed_rate" and item.window == "2024"
    )
    assert observed.value_numeric == Decimal("3.0")
    assert observed.value_state == "value"
    commented = [row for row in parsed.rows if row.comment]
    assert commented
    assert parsed.header_count > 3
