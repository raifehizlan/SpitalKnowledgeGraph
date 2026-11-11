"""A clinic is accepted only when the index and a parent mandate share the label."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    Evidence,
    HospitalOrganization,
    OrganizationName,
    ServiceMandate,
)
from swiss_hospital_intelligence.knowledge_graph.accept import accept_corroborated_claims


def test_exact_index_label_is_accepted_and_a_near_miss_stays_candidate() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        hospital = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        session.add(hospital)
        session.flush()
        session.add(
            OrganizationName(
                organization_id=hospital.id,
                name="Example Hospital",
                name_role="source_primary",
                match_status="exact",
            )
        )
        session.add(
            ServiceMandate(
                organization_id=hospital.id,
                list_kind="akutsomatik",
                edition="April 2026",
                canton_scope="in_canton",
                source_name="Example Hospital, Example",
                code="GYN1",
                label="Gynäkologie",
                match_status="exact",
                source_row_fingerprint="gyn",
            )
        )
        session.add(
            ServiceMandate(
                organization_id=hospital.id,
                list_kind="akutsomatik",
                edition="April 2026",
                canton_scope="in_canton",
                source_name="Example Hospital, Example",
                code="GYN1.1",
                label="Gynäkologische Onkologie",
                match_status="exact",
                source_row_fingerprint="gyn-sub",
            )
        )
        exact = _claim(session, hospital.id, "Gynäkologie", "catalog_link")
        near = _claim(session, hospital.id, "Klinik für Gynäkologie", "catalog_link")
        sentence = _claim(session, hospital.id, "Gynäkologie", "explicit_phrase")
        subcode_only = _claim(session, hospital.id, "Gynäkologische Onkologie", "homepage_menu")
        session.commit()
        assert accept_corroborated_claims(session) == 1
        session.commit()
        assert exact.fact_status == "accepted"
        assert exact.assertion_mode == "reviewed"
        assert near.fact_status == "candidate"
        assert sentence.fact_status == "candidate"
        assert subcode_only.fact_status == "candidate"
        assert accept_corroborated_claims(session) == 0


def _claim(session: Session, organization_id, label: str, method: str) -> Assertion:
    evidence = Evidence(excerpt=label, extraction_method=method, source_url="https://example.test/")
    session.add(evidence)
    session.flush()
    assertion = Assertion(
        evidence_id=evidence.id,
        organization_id=organization_id,
        predicate="hasDepartment",
        object_value=label,
        fact_status="candidate",
        assertion_mode="extracted",
    )
    session.add(assertion)
    session.flush()
    return assertion
