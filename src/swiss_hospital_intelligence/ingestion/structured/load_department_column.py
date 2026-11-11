"""Load department names from the three Graubünden Spitalliste PDFs.

The acute list uses the first column. The psychiatry and rehabilitation
lists use the service line under Leistungsauftrag. A billing code stays a
service mandate. For each linked hospital, the department claims from that
file become one verified row per name. A website claim with the same
predicate is removed and its crosswalk is left in place, so a later page
load does not write that claim again.
"""

from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    EntityCrosswalk,
    Evidence,
)
from swiss_hospital_intelligence.ingestion.structured.load_spitalliste import (
    _establishment_ids,
    _exact_links,
    _linked_name,
    _reviewed_links,
    _source_file,
)
from swiss_hospital_intelligence.ingestion.structured.load_spitalliste import (
    _before_comma as _prefix,
)
from swiss_hospital_intelligence.ingestion.structured.name_link import normalize_name
from swiss_hospital_intelligence.ingestion.structured.spitalliste import (
    parse_acute_departments,
    parse_prose_departments,
)
from swiss_hospital_intelligence.reports.reviewed_aliases import (
    ALIASES,
    SPITALLISTE_ALIASES,
    SPITALLISTE_URL,
    ReviewedAlias,
)

METHOD = "spitalliste_department_column"
LIST_URLS = {
    "psychiatrie.pdf": (
        "https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/"
        "InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste%20Psychiatrie.pdf"
    ),
    "rehabilitation.pdf": (
        "https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/"
        "InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste_Rehabilitation.pdf"
    ),
}


class DepartmentColumnResult(BaseModel):
    hospitals: int
    linked_hospitals: int
    unmatched_hospitals: int
    departments: int
    removed_claims: int
    unmatched_names: list[str]


def load_department_column(
    session: Session,
    path: Path | str,
    establishment_ids: dict[str, UUID] | None = None,
    aliases: list[ReviewedAlias] | None = None,
) -> DepartmentColumnResult:
    return _load_rows(session, path, parse_acute_departments(path), SPITALLISTE_URL, "first column", establishment_ids, aliases)


def load_prose_departments(
    session: Session,
    path: Path | str,
    establishment_ids: dict[str, UUID] | None = None,
    aliases: list[ReviewedAlias] | None = None,
) -> DepartmentColumnResult:
    file_path = Path(path)
    return _load_rows(
        session,
        file_path,
        parse_prose_departments(file_path),
        LIST_URLS.get(file_path.name, SPITALLISTE_URL),
        file_path.stem,
        establishment_ids,
        aliases,
    )


def _load_rows(
    session: Session,
    path: Path | str,
    rows: list[tuple[str, str]],
    source_url: str,
    section: str,
    establishment_ids: dict[str, UUID] | None,
    aliases: list[ReviewedAlias] | None,
) -> DepartmentColumnResult:
    file_path = Path(path)
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    source_file = _source_file(session, digest, file_path.name)
    names = establishment_ids if establishment_ids is not None else _establishment_ids(session)
    by_hospital: dict[str, list[str]] = defaultdict(list)
    for hospital, department in rows:
        by_hospital[hospital].append(department)
    source_names = list(by_hospital)
    exact = _exact_links(source_names, list(names))
    prefixes = {name: _prefix(name) for name in source_names}
    prefix_links = _exact_links([prefix for prefix in prefixes.values() if prefix], list(names))
    reviewed = _reviewed_links(
        [*ALIASES, *SPITALLISTE_ALIASES] if aliases is None else aliases,
        names,
    )
    linked: dict[UUID, list[str]] = {}
    unmatched: list[str] = []
    for hospital, departments in by_hospital.items():
        organization_name, _method = _linked_name(hospital, exact, prefixes, prefix_links, reviewed)
        organization_id = names.get(organization_name) if organization_name is not None else None
        if organization_id is None:
            unmatched.append(hospital)
            continue
        linked.setdefault(organization_id, [])
        for department in departments:
            key = normalize_name(department)
            if all(normalize_name(existing) != key for existing in linked[organization_id]):
                linked[organization_id].append(department)
    removed = 0
    written = 0
    for organization_id, departments in linked.items():
        removed += _replace_departments(
            session,
            source_file.id,
            organization_id,
            departments,
            source_url,
            section,
        )
        written += len(departments)
    session.flush()
    return DepartmentColumnResult(
        hospitals=len(by_hospital),
        linked_hospitals=len(linked),
        unmatched_hospitals=len(unmatched),
        departments=written,
        removed_claims=removed,
        unmatched_names=unmatched,
    )


def _replace_departments(
    session: Session,
    source_file_id: UUID,
    organization_id: UUID,
    departments: list[str],
    source_url: str = SPITALLISTE_URL,
    section: str = "first column",
) -> int:
    wanted = {normalize_name(name): name for name in departments}
    existing = session.execute(
        select(Assertion, Evidence)
        .join(Evidence, Evidence.id == Assertion.evidence_id)
        .where(
            Assertion.organization_id == organization_id,
            Assertion.predicate == "hasDepartment",
        )
    ).all()
    kept: set[str] = set()
    removed = 0
    for assertion, evidence in existing:
        key = normalize_name(assertion.object_value or "")
        official = evidence.extraction_method == METHOD
        if official and evidence.source_file_id != source_file_id:
            kept.add(key)
            continue
        if official and key in wanted:
            assertion.object_value = wanted[key]
            assertion.fact_status = "verified"
            assertion.assertion_mode = "documented"
            evidence.excerpt = wanted[key]
            evidence.section = section
            evidence.source_url = source_url
            kept.add(key)
            continue
        _drop_claim(session, assertion, evidence, organization_id, source_file_id)
        removed += 1
    for key, name in wanted.items():
        if key in kept:
            continue
        _insert_department(session, source_file_id, organization_id, name, source_url, section)
    return removed


def _drop_claim(
    session: Session,
    assertion: Assertion,
    evidence: Evidence,
    organization_id: UUID,
    source_file_id: UUID,
) -> None:
    if evidence.extraction_method == METHOD:
        fingerprint = _fingerprint(organization_id, assertion.object_value or "")
        crosswalk = session.scalar(
            select(EntityCrosswalk).where(
                EntityCrosswalk.source_file_id == source_file_id,
                EntityCrosswalk.source_row_fingerprint == fingerprint,
            )
        )
        if crosswalk is not None:
            session.delete(crosswalk)
    session.delete(assertion)
    session.flush()
    still = session.scalar(select(Assertion.id).where(Assertion.evidence_id == evidence.id))
    if still is None:
        session.delete(evidence)


def _insert_department(
    session: Session,
    source_file_id: UUID,
    organization_id: UUID,
    name: str,
    source_url: str,
    section: str,
) -> None:
    fingerprint = _fingerprint(organization_id, name)
    evidence = Evidence(
        source_file_id=source_file_id,
        excerpt=name,
        section=section,
        source_url=source_url,
        extraction_method=METHOD,
    )
    session.add(evidence)
    session.flush()
    assertion = Assertion(
        evidence_id=evidence.id,
        organization_id=organization_id,
        predicate="hasDepartment",
        object_value=name,
        fact_status="verified",
        assertion_mode="documented",
    )
    session.add(assertion)
    session.flush()
    crosswalk = session.scalar(
        select(EntityCrosswalk).where(
            EntityCrosswalk.source_file_id == source_file_id,
            EntityCrosswalk.source_row_fingerprint == fingerprint,
        )
    )
    if crosswalk is None:
        session.add(
            EntityCrosswalk(
                source_file_id=source_file_id,
                source_row_fingerprint=fingerprint,
                target_table="assertion",
                target_id=assertion.id,
                match_status="exact",
                method=METHOD,
            )
        )
        return
    crosswalk.target_id = assertion.id
    crosswalk.target_table = "assertion"
    crosswalk.match_status = "exact"
    crosswalk.method = METHOD


def _fingerprint(organization_id: UUID, name: str) -> str:
    text = f"department\n{organization_id}\n{normalize_name(name)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    directory = Path("data/raw/spitalliste")
    files = [directory / name for name in ("akutsomatik.pdf", "psychiatrie.pdf", "rehabilitation.pdf")]
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        print("Missing Spitalliste PDF: " + ", ".join(missing), file=sys.stderr)
        return 2
    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    sys.stdout.reconfigure(encoding="utf-8")
    with DbSession(engine) as session:
        results = [load_department_column(session, files[0])]
        results.extend(load_prose_departments(session, path) for path in files[1:])
        session.commit()
    for path, result in zip(files, results, strict=True):
        print(
            f"{path.name}: hospitals {result.hospitals}, linked {result.linked_hospitals}, "
            f"unmatched {result.unmatched_hospitals}, departments {result.departments}, "
            f"removed {result.removed_claims}"
        )
        for name in result.unmatched_names:
            print(f"unmatched: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
