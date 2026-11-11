"""A Graubünden offer lists parent mandates and leaves a missing clinic explicit."""

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    Evidence,
    HospitalOrganization,
    MeasureDefinition,
    OrganizationName,
    ServiceMandate,
    StatisticObservation,
)
from swiss_hospital_intelligence.reports.gr_offer import load_gr_offer, render_gr_offer


def test_parent_mandates_and_a_missing_clinic_are_both_visible() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            MeasureDefinition(
                code="BettenStatA",
                unit="beds",
                activity_type="A",
                scope="establishment",
                publication_status="published",
            )
        )
        hospital = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        other = HospitalOrganization(home_canton_code="SG", reference_year=2024)
        empty = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        session.add_all([hospital, other, empty])
        session.flush()
        session.add_all(
            [
                OrganizationName(
                    organization_id=hospital.id,
                    name="Example Hospital",
                    name_role="source_primary",
                    match_status="exact",
                ),
                OrganizationName(
                    organization_id=other.id,
                    name="Other Canton",
                    name_role="source_primary",
                    match_status="exact",
                ),
                OrganizationName(
                    organization_id=empty.id,
                    name="Empty Hospital",
                    name_role="source_primary",
                    match_status="exact",
                ),
            ]
        )
        session.add(
            StatisticObservation(
                organization_id=hospital.id,
                measure_code="BettenStatA",
                reference_year=2024,
                activity_type="A",
                scope="establishment",
                value_numeric=Decimal("32.50"),
                raw_value="32.5",
                value_state="published",
                unit="beds",
                source_row_fingerprint="bed",
            )
        )
        session.add_all(
            [
                ServiceMandate(
                    organization_id=hospital.id,
                    list_kind="akutsomatik",
                    edition="April 2026",
                    canton_scope="in_canton",
                    source_name="Example Hospital, Example",
                    code="KAR1",
                    label="Kardiologie",
                    match_status="reviewed",
                    source_row_fingerprint="kar",
                ),
                ServiceMandate(
                    organization_id=hospital.id,
                    list_kind="akutsomatik",
                    edition="April 2026",
                    canton_scope="in_canton",
                    source_name="Example Hospital, Example",
                    code="KAR1.1",
                    label="Interventionelle Kardiologie",
                    match_status="reviewed",
                    source_row_fingerprint="kar-sub",
                ),
                ServiceMandate(
                    organization_id=other.id,
                    list_kind="akutsomatik",
                    edition="April 2026",
                    canton_scope="outside_canton",
                    source_name="Other Canton, Other",
                    code="NEU1",
                    label="Neurologie",
                    match_status="exact",
                    source_row_fingerprint="other",
                ),
            ]
        )
        evidence = Evidence(excerpt="Chirurgie", extraction_method="homepage_menu", source_url="https://example.test/")
        session.add(evidence)
        session.flush()
        session.add(
            Assertion(
                evidence_id=evidence.id,
                organization_id=hospital.id,
                predicate="hasDepartment",
                object_value="Chirurgie",
                fact_status="candidate",
                assertion_mode="extracted",
            )
        )
        session.commit()
        offers = load_gr_offer(session)

    assert [item.organization_name for item in offers] == ["Empty Hospital", "Example Hospital"]
    example = offers[1]
    assert example.acute_beds == Decimal("32.50")
    assert [row.code for row in example.parents()] == ["KAR1"]
    assert example.clinics == ["Chirurgie"]
    text = render_gr_offer(offers)
    assert "acute beds: 32.5" in text
    assert "KAR1 Kardiologie" in text
    assert "KAR1.1" not in text
    assert "clinics (candidate, 1): Chirurgie" in text
    assert "clinics: not found on the saved index" in text
    assert "Other Canton" not in text
