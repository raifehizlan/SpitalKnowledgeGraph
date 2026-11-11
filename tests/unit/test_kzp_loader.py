"""The key-figure loader updates the same rows on a second run."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Base,
    HospitalOrganization,
    HospitalSite,
    OrganizationCodeSet,
    StatisticObservation,
)
from swiss_hospital_intelligence.ingestion.structured.load_kzp import load_key_figures
from tests.unit.test_kzp_parser import _workbook


def test_second_load_keeps_the_same_ids(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_kzp.xlsx"
    _workbook(path)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = load_key_figures(session, path)
        session.commit()
        organization_ids = set(session.scalars(select(HospitalOrganization.id)))
        site_ids = set(session.scalars(select(HospitalSite.id)))
        statistic_ids = set(session.scalars(select(StatisticObservation.id)))
        code_count = session.scalar(select(func.count()).select_from(OrganizationCodeSet))
        load_key_figures(session, path)
        session.commit()

        assert session.scalar(select(func.count()).select_from(HospitalOrganization)) == 2
        assert session.scalar(select(func.count()).select_from(HospitalSite)) == 3
        assert set(session.scalars(select(HospitalOrganization.id))) == organization_ids
        assert set(session.scalars(select(HospitalSite.id))) == site_ids
        assert set(session.scalars(select(StatisticObservation.id))) == statistic_ids
        assert session.scalar(select(func.count()).select_from(OrganizationCodeSet)) == code_count
        assert (
            session.scalar(
                select(func.count())
                .select_from(StatisticObservation)
                .where(StatisticObservation.site_id.is_not(None))
            )
            == 0
        )
        other_canton = session.scalar(
            select(HospitalSite).where(HospitalSite.postal_place == "8880 Example")
        )
        assert other_canton is not None
        assert other_canton.canton_code == "SG"
        equipment = session.scalars(
            select(OrganizationCodeSet.code).where(OrganizationCodeSet.code_set == "equipment")
        ).all()
        assert "MRI" in equipment
        assert first.organizations == 2
        assert first.excluded_national_rows == 1
