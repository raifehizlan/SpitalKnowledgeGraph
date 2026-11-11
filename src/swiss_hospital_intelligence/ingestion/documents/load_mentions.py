"""Write candidate assertions for explicit document mentions.

The same passage and the same mention update one row. Site stays empty.
"""

from __future__ import annotations

import hashlib
import sys
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Assertion, EntityCrosswalk, Evidence
from swiss_hospital_intelligence.ingestion.documents.extract_mentions import METHOD, extract_mentions


class ExtractResult(BaseModel):
    assertions: int
    by_predicate: dict[str, int]


def load_mentions(session: Session) -> ExtractResult:
    counts: dict[str, int] = {}
    total = 0
    rows = session.execute(
        text(
            """
            SELECT c.text, c.page_number, c.section, d.id, d.organization_id,
                   d.source_url, d.source_file_id
            FROM document_chunk AS c
            JOIN document AS d ON d.id = c.document_id
            WHERE length(btrim(c.text)) > 0
               OR (c.section IS NOT NULL AND length(btrim(c.section)) > 0)
            """
        )
    )
    for row in rows:
        if row.source_file_id is None:
            continue
        for mention in extract_mentions(row.text or "", row.section):
            fingerprint = _fingerprint(
                str(row.id),
                mention.predicate,
                mention.object_value,
                str(row.page_number or ""),
                row.section or "",
            )
            _upsert(
                session,
                source_file_id=row.source_file_id,
                fingerprint=fingerprint,
                document_id=row.id,
                organization_id=row.organization_id,
                source_url=row.source_url,
                page_number=row.page_number,
                section=row.section,
                predicate=mention.predicate,
                object_value=mention.object_value,
                excerpt=mention.excerpt,
            )
            counts[mention.predicate] = counts.get(mention.predicate, 0) + 1
            total += 1
    session.flush()
    return ExtractResult(assertions=total, by_predicate=counts)


def _upsert(
    session: Session,
    *,
    source_file_id: UUID,
    fingerprint: str,
    document_id: UUID | None,
    organization_id: UUID | None,
    source_url: str | None,
    page_number: int | None,
    section: str | None,
    predicate: str,
    object_value: str,
    excerpt: str,
    extraction_method: str = METHOD,
    model_name: str | None = None,
    prompt_version: str | None = None,
    method: str = METHOD,
) -> None:
    existing_id = session.scalar(
        select(EntityCrosswalk.target_id).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == fingerprint,
        )
    )
    if existing_id is not None:
        return
    evidence = Evidence(
        document_id=document_id,
        source_file_id=source_file_id,
        excerpt=excerpt,
        page_number=page_number,
        section=section,
        source_url=source_url,
        extraction_method=extraction_method,
    )
    session.add(evidence)
    session.flush()
    assertion = Assertion(
        evidence_id=evidence.id,
        organization_id=organization_id,
        site_id=None,
        predicate=predicate,
        object_value=object_value,
        fact_status="candidate",
        assertion_mode="extracted",
        model_name=model_name,
        prompt_version=prompt_version,
    )
    session.add(assertion)
    session.flush()
    session.add(
        EntityCrosswalk(
            source_file_id=source_file_id,
            source_row_fingerprint=fingerprint,
            target_table="assertion",
            target_id=assertion.id,
            match_status="candidate",
            method=method,
        )
    )


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    with DbSession(engine) as session:
        result = load_mentions(session)
        session.commit()
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"assertions: {result.assertions}")
    for predicate, count in sorted(result.by_predicate.items()):
        print(f"{predicate}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
