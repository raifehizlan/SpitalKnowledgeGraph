"""Accept a clinic name only when two official texts use the same label.

The hospital's own index and a parent Spitalliste mandate must match after
the same normalization used for 2024 names. A sentence extraction and a near
miss stay candidates. A mandate is not copied in as a department.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Assertion, Evidence, ServiceMandate
from swiss_hospital_intelligence.ingestion.structured.name_link import normalize_name

INDEX_METHODS = ("catalog_link", "homepage_menu")
INDEX_PREDICATES = ("hasDepartment", "hasClinic")
ACCEPTED = "accepted"
REVIEWED = "reviewed"


def accept_corroborated_claims(session: Session) -> int:
    labels: dict[UUID, set[str]] = defaultdict(set)
    mandates = session.scalars(
        select(ServiceMandate).where(ServiceMandate.match_status.in_(("exact", "reviewed")))
    )
    for mandate in mandates:
        if mandate.organization_id is None or not _parent(mandate.code):
            continue
        labels[mandate.organization_id].add(normalize_name(mandate.label))
    rows = session.execute(
        select(Assertion, Evidence)
        .join(Evidence, Evidence.id == Assertion.evidence_id)
        .where(
            Evidence.extraction_method.in_(INDEX_METHODS),
            Assertion.predicate.in_(INDEX_PREDICATES),
            Assertion.fact_status != ACCEPTED,
        )
    ).all()
    accepted = 0
    for assertion, _evidence in rows:
        if assertion.organization_id is None or not assertion.object_value:
            continue
        if normalize_name(assertion.object_value) not in labels[assertion.organization_id]:
            continue
        assertion.fact_status = ACCEPTED
        assertion.assertion_mode = REVIEWED
        accepted += 1
    session.flush()
    return accepted


def _parent(code: str | None) -> bool:
    return code is None or "." not in code
