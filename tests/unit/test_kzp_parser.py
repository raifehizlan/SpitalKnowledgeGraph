"""Synthetic key-figure workbook. Every name in this file is fictional."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.records import (
    ScopeError,
    require_establishment_scope,
)


def _workbook(path: Path) -> None:
    book = Workbook()
    establishments = book.active
    assert establishments is not None
    establishments.title = "KZ2024_KZP24"
    establishment_headers = [
        "JAHR",
        "KT",
        "Inst",
        "Adr",
        "Ort",
        "Typ",
        "RForm",
        "Akt",
        "SL",
        "WB",
        "AnzStand",
        "SA",
        "LA",
        "BettenStatA",
        "PersA",
        "AmbPatKont",
        "PflegetageT",
        "FutureFlag",
    ]
    establishments.append(establishment_headers)
    establishments.append(
        [
            2024,
            None,
            "Alle Betriebe - Tous les établissements - Tutti gli stabilimenti",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            9999,
            None,
            None,
            None,
            None,
        ]
    )
    establishments.append(
        [
            2024,
            "GR",
            "Synthetic Hospital One",
            "Example Street 1",
            "7000 Example",
            "K112",
            "R2",
            "A",
            "NF, IPS",
            "Arzt",
            2,
            "MRI, CT",
            "Amb, Stat",
            32.95,
            10.5,
            None,
            None,
            "ignore-me",
        ]
    )
    establishments.append(
        [
            2024,
            "GR",
            "Synthetic Hospital Two",
            None,
            "7500 Example",
            "K123",
            "R4",
            "A, R",
            None,
            None,
            1,
            None,
            "Stat",
            4,
            None,
            12,
            None,
            None,
        ]
    )
    sites = book.create_sheet("Standorte_KZ2024_KZP24")
    sites.append(
        [
            "JAHR",
            "KT",
            "Inst",
            "Adr",
            "Ort",
            "AnzStand",
            "KT_Standort",
            "Standort",
            "Adr_Standort",
            "Ort_Standort",
            "LA_Standort",
        ]
    )
    sites.append(
        [2024, "GR", "Synthetic Hospital One", "Example Street 1", "7000 Example", 2, "GR", "Synthetic Site Chur", "Example Street 1", "7000 Example", "Amb, Stat"]
    )
    sites.append(
        [2024, "GR", "Synthetic Hospital One", "Example Street 1", "7000 Example", 2, "SG", "Synthetic Site Other Canton", "Other Street 5", "8880 Example", "Amb, Stat"]
    )
    sites.append(
        [2024, "GR", "Synthetic Hospital Two", None, "7500 Example", 1, "GR", "Synthetic Site Two", None, "7500 Example", "Stat"]
    )
    sites.append(
        [2024, "ZH", "Missing Parent Hospital", "Nowhere 1", "8000 Example", 1, "ZH", "Orphan Site", "Nowhere 1", "8000 Example", "Stat"]
    )
    book.save(path)


def test_parser_keeps_scope_and_states(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_kzp.xlsx"
    _workbook(path)
    parsed = parse_key_figures(path)

    assert parsed.excluded_national_rows == 1
    assert [row.name for row in parsed.establishments] == [
        "Synthetic Hospital One",
        "Synthetic Hospital Two",
    ]
    assert "FutureFlag" in parsed.unknown_columns
    assert parsed.sites_without_establishment == ["Missing Parent Hospital"]

    first = parsed.establishment("Synthetic Hospital One")
    assert first.street == "Example Street 1"
    assert first.activities == ["A"]
    assert first.specific_services == ["NF", "IPS"]
    assert first.equipment == ["MRI", "CT"]
    assert first.reported_site_count == 2
    beds = next(item for item in first.measures if item.code == "BettenStatA")
    assert beds.value_state == "value"
    assert beds.activity_type == "A"
    assert beds.unit == "bed_operating_average"
    assert str(beds.value_numeric) == "32.95"
    physicians = next(item for item in first.measures if item.code == "PersA")
    assert physicians.activity_type is None
    assert physicians.unit == "fte"
    contacts = next(item for item in first.measures if item.code == "AmbPatKont")
    assert contacts.value_state == "not_available_in_source"
    assert contacts.value_numeric is None
    assert all(item.code != "PflegetageT" for item in first.measures)

    second = parsed.establishment("Synthetic Hospital Two")
    assert second.street is None
    assert second.activities == ["A", "R"]
    assert second.equipment == []

    first_sites = [site for site in parsed.sites if site.parent_name == "Synthetic Hospital One"]
    assert [site.canton_code for site in first_sites] == ["GR", "SG"]
    assert first_sites[1].name == "Synthetic Site Other Canton"
    empty_street = next(site for site in parsed.sites if site.parent_name == "Synthetic Hospital Two")
    assert empty_street.street is None


def test_establishment_measure_cannot_be_stored_on_a_site(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_kzp.xlsx"
    _workbook(path)
    beds = next(
        item
        for item in parse_key_figures(path).establishment("Synthetic Hospital One").measures
        if item.code == "BettenStatA"
    )
    require_establishment_scope(beds, None)
    try:
        require_establishment_scope(beds, "site-walenstadt")
    except ScopeError as error:
        assert "BettenStatA" in str(error)
    else:
        raise AssertionError("site assignment was accepted")
