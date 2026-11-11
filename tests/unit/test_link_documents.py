"""A page is linked by the official website host. A site is not guessed."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Base, Document, DocumentChunk, HospitalOrganization
from swiss_hospital_intelligence.ingestion.documents.link_documents import (
    establishment_scopes,
    load_parsed_documents,
)
from swiss_hospital_intelligence.ingestion.documents.parse_documents import ParsedChunk, ParsedDocument
from swiss_hospital_intelligence.ingestion.documents.source_register import RegisterRow, SourceRegister


def _row(name: str, url: str) -> RegisterRow:
    return RegisterRow(
        organization_name=name,
        site_name=None,
        home_canton="GR",
        site_canton=None,
        url_status="found",
        url=url,
        language="de",
        source=url,
        note="",
    )


def _page(url: str, text: str = "Innere Medizin") -> ParsedDocument:
    return ParsedDocument(
        source_url=url,
        checksum=url,
        media_type="html",
        title="Spital",
        language="de",
        processing_status="parsed",
        chunks=[
            ParsedChunk(
                text=text,
                page_number=None,
                section="Innere Medizin",
                language="de",
                ordinal=1,
                status="parsed",
            )
        ],
    )


def test_host_link_does_not_guess_a_site_and_second_load_keeps_the_id() -> None:
    register = SourceRegister(
        rows=[
            _row("Kantonsspital Graubünden", "https://www.ksgr.ch/"),
            _row("Rehazentrum Chur", "https://valens.ch/reha-chur/"),
            _row("One", "https://shared.example/"),
            _row("Two", "https://shared.example/other"),
        ]
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ksgr = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        chur = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        session.add_all([ksgr, chur])
        session.flush()
        ids = {"Kantonsspital Graubünden": ksgr.id, "Rehazentrum Chur": chur.id}
        scopes = establishment_scopes(register)
        pages = [
            _page("https://www.ksgr.ch/fachgebiete/innere-medizin"),
            _page("https://valens.ch/reha-chur/angebot"),
            _page("https://valens.ch/wp-content/uploads/jahresbericht.pdf"),
            _page("https://shared.example/team"),
            _page("https://unknown.example/team"),
        ]
        first = load_parsed_documents(session, pages, scopes, ids)
        session.commit()
        document_ids = set(session.scalars(select(Document.id)))
        ksgr_document = session.scalar(select(Document).where(Document.source_url.contains("innere-medizin")))
        assert ksgr_document is not None
        assert ksgr_document.organization_id == ksgr.id
        chur_document = session.scalar(select(Document).where(Document.source_url.contains("reha-chur")))
        assert chur_document is not None
        assert chur_document.organization_id == chur.id
        group_report = session.scalar(select(Document).where(Document.source_url.contains("jahresbericht")))
        assert group_report is not None
        assert group_report.organization_id is None
        assert first.linked == 2
        assert first.unlinked == 3
        load_parsed_documents(session, pages, scopes, ids)
        session.commit()
        assert set(session.scalars(select(Document.id))) == document_ids
        assert session.scalar(select(func.count()).select_from(DocumentChunk)) == 5
