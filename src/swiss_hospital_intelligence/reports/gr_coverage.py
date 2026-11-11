"""Document coverage for every 2024 Graubünden establishment.

Counts come from saved pages already linked to an organization. A missing
page set or a missing annual or quality report is an explicit gap. Candidate
assertions stay in the count and are not treated as accepted.
"""

from __future__ import annotations

import sys

from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Document,
    DocumentChunk,
    HospitalOrganization,
    OrganizationName,
)

REPORT_TOKENS = (
    "jahresbericht",
    "geschäftsbericht",
    "geschaeftsbericht",
    "qualitätsbericht",
    "qualitaetsbericht",
)
PAGES_GAP = "pages: not_found_in_reviewed_documents"
REPORT_GAP = "annual_or_quality_report: not_found_in_reviewed_documents"


class EstablishmentCoverage(BaseModel):
    organization_name: str
    documents: int
    html_documents: int
    pdf_documents: int
    other_documents: int
    failed_documents: int
    chunks: int
    empty_chunks: int
    candidate_assertions: int
    accepted_assertions: int
    report_documents: int

    def gaps(self) -> list[str]:
        gaps: list[str] = []
        if self.documents == 0:
            gaps.append(PAGES_GAP)
        if self.failed_documents:
            gaps.append(f"failed pages: {self.failed_documents}")
        if self.report_documents == 0:
            gaps.append(REPORT_GAP)
        return gaps


class CoverageReport(BaseModel):
    rows: list[EstablishmentCoverage]
    unlinked_documents: int

    @property
    def candidate_assertions(self) -> int:
        return sum(row.candidate_assertions for row in self.rows)

    @property
    def accepted_assertions(self) -> int:
        return sum(row.accepted_assertions for row in self.rows)


def load_gr_coverage(session: Session) -> CoverageReport:
    organizations = session.execute(
        select(HospitalOrganization.id, OrganizationName.name)
        .join(OrganizationName, OrganizationName.organization_id == HospitalOrganization.id)
        .where(
            HospitalOrganization.home_canton_code == "GR",
            OrganizationName.name_role == "source_primary",
        )
        .order_by(OrganizationName.name)
    ).all()
    documents = _document_counts(session)
    chunks = _chunk_counts(session)
    assertions = _assertion_counts(session)
    reports = _report_counts(session)
    unlinked = session.scalar(select(func.count()).select_from(Document).where(Document.organization_id.is_(None)))
    rows: list[EstablishmentCoverage] = []
    for organization_id, name in organizations:
        document_row = documents.get(organization_id, (0, 0, 0, 0, 0))
        chunk_row = chunks.get(organization_id, (0, 0))
        assertion_row = assertions.get(organization_id, {})
        rows.append(
            EstablishmentCoverage(
                organization_name=name,
                documents=document_row[0],
                html_documents=document_row[1],
                pdf_documents=document_row[2],
                other_documents=document_row[3],
                failed_documents=document_row[4],
                chunks=chunk_row[0],
                empty_chunks=chunk_row[1],
                candidate_assertions=assertion_row.get("candidate", 0),
                accepted_assertions=assertion_row.get("accepted", 0),
                report_documents=reports.get(organization_id, 0),
            )
        )
    return CoverageReport(rows=rows, unlinked_documents=int(unlinked or 0))


def render_gr_coverage(report: CoverageReport) -> str:
    lines = [
        "Graubünden document coverage",
        f"establishments: {len(report.rows)}",
        f"unlinked documents: {report.unlinked_documents}",
        f"assertions: candidate {report.candidate_assertions}, accepted {report.accepted_assertions}",
        "",
    ]
    for row in report.rows:
        lines.append(row.organization_name)
        lines.append(
            "  documents: "
            f"{row.documents} (html {row.html_documents}, pdf {row.pdf_documents}, "
            f"other {row.other_documents}, failed {row.failed_documents})"
        )
        lines.append(f"  chunks: {row.chunks} (empty {row.empty_chunks})")
        lines.append(f"  assertions: candidate {row.candidate_assertions}, accepted {row.accepted_assertions}")
        lines.append(f"  annual or quality report: {row.report_documents}")
        gaps = row.gaps()
        if gaps:
            lines.append(f"  gaps: {'; '.join(gaps)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _document_counts(session: Session) -> dict:
    html = _flag(Document.document_type == "html")
    pdf = _flag(Document.document_type == "pdf")
    other = _flag(Document.document_type == "other")
    failed = _flag(Document.processing_status == "failed")
    rows = session.execute(
        select(
            Document.organization_id,
            func.count(),
            html,
            pdf,
            other,
            failed,
        )
        .where(Document.organization_id.is_not(None))
        .group_by(Document.organization_id)
    ).all()
    return {
        organization_id: (int(total), int(html_count), int(pdf_count), int(other_count), int(failed_count))
        for organization_id, total, html_count, pdf_count, other_count, failed_count in rows
    }


def _chunk_counts(session: Session) -> dict:
    empty = _flag(func.trim(DocumentChunk.text) == "")
    rows = session.execute(
        select(Document.organization_id, func.count(DocumentChunk.id), empty)
        .join(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.organization_id.is_not(None))
        .group_by(Document.organization_id)
    ).all()
    return {
        organization_id: (int(total), int(empty_count))
        for organization_id, total, empty_count in rows
    }


def _assertion_counts(session: Session) -> dict:
    rows = session.execute(
        select(Assertion.organization_id, Assertion.fact_status, func.count())
        .where(Assertion.organization_id.is_not(None))
        .group_by(Assertion.organization_id, Assertion.fact_status)
    ).all()
    counts: dict = {}
    for organization_id, status, total in rows:
        counts.setdefault(organization_id, {})[status] = int(total)
    return counts


def _report_counts(session: Session) -> dict:
    rows = session.execute(
        select(Document.organization_id, func.count())
        .where(Document.organization_id.is_not(None), _report_match())
        .group_by(Document.organization_id)
    ).all()
    return {organization_id: int(total) for organization_id, total in rows}


def _report_match():
    clauses = []
    for column in (Document.title, Document.source_url):
        lowered = func.lower(func.coalesce(column, ""))
        clauses.extend(lowered.contains(token) for token in REPORT_TOKENS)
    return or_(*clauses)


def _flag(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    with DbSession(engine) as session:
        report = load_gr_coverage(session)
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_gr_coverage(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
