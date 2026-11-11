"""The opened cantonal-list workbook keeps 2008–2009 undeclared."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Base, ListMembership
from swiss_hospital_intelligence.ingestion.structured.hosp_list import (
    ParsedListMembership,
    parse_cantonal_list,
)
from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.load_hosp_list import load_cantonal_list
from swiss_hospital_intelligence.ingestion.structured.name_link import link_institution_names

ROOT = Path(__file__).resolve().parents[2]


def _existing(*relative_paths: str) -> Path | None:
    for relative in relative_paths:
        path = ROOT / relative
        if path.is_file():
            return path
    return None


LIST_FILE = _existing("data/raw/kzp24_hospListCT.xlsx", "_discovery/raw/kzp24_hospListCT.xlsx")


@pytest.mark.skipif(LIST_FILE is None, reason="BAG cantonal-list workbook is not on disk")
def test_real_list_codes_follow_the_2010_readme() -> None:
    assert LIST_FILE is not None
    parsed = parse_cantonal_list(LIST_FILE)
    assert len(parsed.memberships) == 4901
    assert {row.reference_year for row in parsed.memberships} == set(range(2008, 2025))
    for row in parsed.memberships:
        if row.reference_year < 2010:
            assert row.home_list_state == "undeclared"
            assert row.other_list_state == "undeclared"
        else:
            assert row.home_list_state in {"yes", "no", "not_available_in_source"}
            assert row.other_list_state in {"yes", "no", "not_available_in_source"}
    assert "canton" not in ParsedListMembership.model_fields

    ksgr = [
        row
        for row in parsed.memberships
        if row.reference_year == 2024 and row.institution == "Kantonsspital Graubünden"
    ]
    assert len(ksgr) == 1
    assert ksgr[0].home_list_state == "yes"
    assert ksgr[0].other_list_state == "yes"
    assert ksgr[0].postal_place == "7000 Chur"

    ambra = [
        row
        for row in parsed.memberships
        if row.reference_year == 2024 and row.institution == "Geburtshaus ambra GmbH"
    ]
    assert len(ambra) == 1
    assert ambra[0].home_list_state == "not_available_in_source"
    assert ambra[0].other_list_state == "not_available_in_source"


@pytest.mark.skipif(
    LIST_FILE is None
    or _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx") is None,
    reason="BAG list and key-figure files are not both on disk",
)
def test_real_2024_list_names_do_not_pull_earlier_years_into_the_link() -> None:
    assert LIST_FILE is not None
    key_figures = _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx")
    assert key_figures is not None
    parsed = parse_cantonal_list(LIST_FILE)
    establishments = [row.name for row in parse_key_figures(key_figures).establishments]
    current = [row.institution for row in parsed.memberships if row.reference_year == 2024]
    expected_links = sum(
        1
        for link in link_institution_names(current, establishments)
        if link.match_status == "exact"
    )
    assert expected_links < len(current)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        loaded = load_cantonal_list(
            session,
            LIST_FILE,
            {name: uuid4() for name in establishments},
        )
        session.commit()
        assert loaded.memberships == 4901
        assert loaded.exact_links == expected_links
        assert loaded.undeclared_rows == sum(
            1 for row in parsed.memberships if row.reference_year < 2010
        )
        stored = session.scalars(select(ListMembership)).all()
        assert all(row.organization_id is None for row in stored)
        assert any(
            row.reference_year == 2008
            and row.source_name == "Kantonsspital Graubünden"
            and row.home_list_state == "undeclared"
            for row in stored
        )
