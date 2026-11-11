"""Coverage names a saved corpus and leaves a missing report explicit."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    Document,
    DocumentChunk,
    Evidence,
    HospitalOrganization,
    OrganizationName,
)
from swiss_hospital_intelligence.reports.gr_coverage import (
    PAGES_GAP,
    REPORT_GAP,
    load_gr_coverage,
    render_gr_coverage,
)


def test_missing_pages_and_a_saved_annual_report_are_both_visible() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        hospital = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        empty = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        other = HospitalOrganization(home_canton_code="SG", reference_year=2024)
        session.add_all([hospital, empty, other])
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
                    organization_id=empty.id,
                    name="Empty Hospital",
                    name_role="source_primary",
                    match_status="exact",
                ),
                OrganizationName(
                    organization_id=other.id,
                    name="Other Canton",
                    name_role="source_primary",
                    match_status="exact",
                ),
            ]
        )
        page = Document(
            organization_id=hospital.id,
            title="Fachgebiete",
            source_url="https://example.test/fachgebiete",
            document_type="html",
            processing_status="parsed",
        )
        report = Document(
            organization_id=hospital.id,
            title="Jahresbericht 2023",
            source_url="https://example.test/jahresbericht.pdf",
            document_type="pdf",
            processing_status="parsed",
        )
        failed = Document(
            organization_id=hospital.id,
            title=None,
            source_url="https://example.test/missing.pdf",
            document_type="pdf",
            processing_status="failed",
        )
        session.add_all(
            [
                page,
                report,
                failed,
                Document(
                    organization_id=None,
                    source_url="https://valens.ch/other",
                    document_type="html",
                    processing_status="parsed",
                ),
                Document(
                    organization_id=other.id,
                    title="Other",
                    document_type="html",
                    processing_status="parsed",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                DocumentChunk(document_id=page.id, text="Innere Medizin", ordinal=1),
                DocumentChunk(document_id=report.id, text="Bericht", ordinal=1),
                DocumentChunk(document_id=failed.id, text="", ordinal=1),
            ]
        )
        evidence = Evidence(excerpt="Chirurgie", extraction_method="catalog_link")
        accepted = Evidence(excerpt="accepted", extraction_method="reviewed")
        session.add_all([evidence, accepted])
        session.flush()
        session.add_all(
            [
                Assertion(
                    evidence_id=evidence.id,
                    organization_id=hospital.id,
                    predicate="hasDepartment",
                    object_value="Chirurgie",
                    fact_status="candidate",
                    assertion_mode="extracted",
                ),
                Assertion(
                    evidence_id=accepted.id,
                    organization_id=hospital.id,
                    predicate="hasDepartment",
                    object_value="Medizin",
                    fact_status="accepted",
                    assertion_mode="reviewed",
                ),
            ]
        )
        session.commit()
        coverage = load_gr_coverage(session)

    assert [row.organization_name for row in coverage.rows] == ["Empty Hospital", "Example Hospital"]
    example = coverage.rows[1]
    assert example.documents == 3
    assert example.html_documents == 1
    assert example.pdf_documents == 2
    assert example.failed_documents == 1
    assert example.chunks == 3
    assert example.empty_chunks == 1
    assert example.report_documents == 1
    assert example.candidate_assertions == 1
    assert example.accepted_assertions == 1
    assert PAGES_GAP not in example.gaps()
    assert REPORT_GAP not in example.gaps()
    assert example.gaps() == ["failed pages: 1"]
    assert coverage.rows[0].gaps() == [PAGES_GAP, REPORT_GAP]
    assert coverage.unlinked_documents == 1
    text = render_gr_coverage(coverage)
    assert "assertions: candidate 1, accepted 1" in text
    assert "annual or quality report: 1" in text
    assert PAGES_GAP in text
    assert "Other Canton" not in text
