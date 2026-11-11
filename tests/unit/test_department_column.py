"""The acute first column replaces department claims for that hospital."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    Evidence,
    HospitalOrganization,
    Source,
    SourceFile,
)
from swiss_hospital_intelligence.ingestion.structured.load_department_column import (
    METHOD,
    _replace_departments,
)


def test_column_names_replace_page_departments_and_a_second_run_keeps_them() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    organization_id = uuid4()
    with Session(engine) as session:
        source = Source(code="GR-SPITALLISTE", name="Spitalliste")
        session.add(source)
        session.flush()
        source_file = SourceFile(source_id=source.id, checksum="abc", filename="akutsomatik.pdf")
        session.add(source_file)
        session.add(
            HospitalOrganization(
                id=organization_id,
                home_canton_code="GR",
                reference_year=2024,
                verification_status="verified",
            )
        )
        page = Evidence(excerpt="Gynäkologie und mehr", extraction_method="homepage_menu")
        clinic = Evidence(excerpt="Notfall", extraction_method="homepage_menu")
        session.add_all([page, clinic])
        session.flush()
        session.add_all(
            [
                Assertion(
                    evidence_id=page.id,
                    organization_id=organization_id,
                    predicate="hasDepartment",
                    object_value="Unsere Fachbereiche und ein langer Satz",
                    fact_status="candidate",
                    assertion_mode="extracted",
                ),
                Assertion(
                    evidence_id=clinic.id,
                    organization_id=organization_id,
                    predicate="hasClinic",
                    object_value="Notfall",
                    fact_status="candidate",
                    assertion_mode="extracted",
                ),
            ]
        )
        session.flush()
        removed = _replace_departments(
            session,
            source_file.id,
            organization_id,
            ["Gynäkologie", "Herz"],
        )
        session.commit()
        assert removed == 1
        departments = session.scalars(
            select(Assertion).where(Assertion.predicate == "hasDepartment")
        ).all()
        assert sorted(row.object_value for row in departments) == ["Gynäkologie", "Herz"]
        assert {row.fact_status for row in departments} == {"verified"}
        assert {row.assertion_mode for row in departments} == {"documented"}
        clinic_row = session.scalar(select(Assertion).where(Assertion.predicate == "hasClinic"))
        assert clinic_row is not None and clinic_row.object_value == "Notfall"
        again = _replace_departments(
            session,
            source_file.id,
            organization_id,
            ["Gynäkologie", "Herz"],
        )
        session.commit()
        assert again == 0
        assert session.scalar(
            select(func.count()).select_from(Assertion).where(Assertion.predicate == "hasDepartment")
        ) == 2
        excerpts = set(
            session.scalars(select(Evidence.excerpt).where(Evidence.extraction_method == METHOD))
        )
        assert excerpts == {"Gynäkologie", "Herz"}
