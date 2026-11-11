"""Synthetic hospital-list workbook. Every name in this file is fictional."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Base, EntityCrosswalk, ListMembership
from swiss_hospital_intelligence.ingestion.structured.hosp_list import (
    CantonalListParseError,
    ParsedListMembership,
    parse_cantonal_list,
)
from swiss_hospital_intelligence.ingestion.structured.load_hosp_list import load_cantonal_list
from swiss_hospital_intelligence.ingestion.structured.name_link import MATCH_METHOD


def _workbook(path: Path, *, home_2010: object = 1, others_2010: object = 2) -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Spitalliste_2008-2024"
    sheet.append(
        ["JAHR", "Institution", "Strasse", "Ort", "SPITALLISTE_HOME", "SPITALLISTE_OTHERS"]
    )
    sheet.append([2008, "Example Hospital", "Example Street 1", "7000 Example", 1, 0])
    sheet.append([2009, "Example Hospital", "Example Street 1", "7000 Example", 1, 1])
    sheet.append([2010, "Example Hospital", "Example Street 1", "7000 Example", home_2010, others_2010])
    sheet.append([2010, "Blank Codes", None, "7001 Example", None, None])
    sheet.append([2024, "Example Hospital", "Example Street 1", "7000 Example", 1, 1])
    sheet.append([2024, "Example Hospital Annex", "Example Street 2", "7002 Example", 2, 2])
    book.save(path)


def test_old_years_stay_undeclared_and_no_canton_is_invented(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_list.xlsx"
    _workbook(path)
    parsed = parse_cantonal_list(path)
    by_year = {
        (row.reference_year, row.institution): row
        for row in parsed.memberships
    }
    old = by_year[(2008, "Example Hospital")]
    assert old.home_list_state == "undeclared"
    assert old.other_list_state == "undeclared"
    assert by_year[(2009, "Example Hospital")].home_list_state == "undeclared"
    coded = by_year[(2010, "Example Hospital")]
    assert coded.home_list_state == "yes"
    assert coded.other_list_state == "no"
    blank = by_year[(2010, "Blank Codes")]
    assert blank.home_list_state == "not_available_in_source"
    assert blank.other_list_state == "not_available_in_source"
    assert blank.street is None
    assert old.postal_place == "7000 Example"
    assert "canton" not in ParsedListMembership.model_fields


def test_a_zero_from_2010_is_not_read_as_no(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_list.xlsx"
    _workbook(path, home_2010=0, others_2010=1)
    with pytest.raises(CantonalListParseError):
        parse_cantonal_list(path)


def test_second_load_links_only_the_2024_exact_name(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_list.xlsx"
    _workbook(path)
    organization_id = uuid4()
    other_id = uuid4()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    establishments = {
        "Example Hospital": organization_id,
        "Example Hospital AG Akutabteilung": other_id,
    }
    with Session(engine) as session:
        first = load_cantonal_list(session, path, establishments)
        session.commit()
        membership_ids = set(session.scalars(select(ListMembership.id)))
        link_ids = set(session.scalars(select(EntityCrosswalk.id)))
        load_cantonal_list(session, path, establishments)
        session.commit()

        assert session.scalar(select(func.count()).select_from(ListMembership)) == 6
        assert set(session.scalars(select(ListMembership.id))) == membership_ids
        assert set(session.scalars(select(EntityCrosswalk.id))) == link_ids
        assert first.exact_links == 1
        assert first.undeclared_rows == 2
        assert session.scalar(select(func.count()).select_from(EntityCrosswalk)) == 1
        link = session.scalar(select(EntityCrosswalk))
        assert link is not None
        assert link.target_id == organization_id
        assert link.target_table == "hospital_organization"
        assert link.method == MATCH_METHOD
        assert link.match_status == "exact"
        linked_row = session.scalar(
            select(ListMembership).where(
                ListMembership.reference_year == 2024,
                ListMembership.source_name == "Example Hospital",
            )
        )
        assert linked_row is not None
        assert linked_row.organization_id is None
        old = session.scalar(
            select(ListMembership).where(ListMembership.reference_year == 2008)
        )
        assert old is not None
        assert old.home_list_state == "undeclared"
        assert old.organization_id is None
        near_miss = session.scalar(
            select(ListMembership).where(ListMembership.source_name == "Example Hospital Annex")
        )
        assert near_miss is not None
        assert near_miss.organization_id is None
