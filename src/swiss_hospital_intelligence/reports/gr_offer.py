"""Graubünden establishments with linked mandates and candidate clinic names.

A parent mandate has no dotted subcode. A clinic name is still a candidate.
A missing index is written as not found. Beds stay on the establishment.
"""

from __future__ import annotations

import sys
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Evidence,
    HospitalOrganization,
    OrganizationName,
    ServiceMandate,
    StatisticObservation,
)

CLINIC_METHODS = ("catalog_link", "homepage_menu")
BED_MEASURE = "BettenStatA"


class MandateLine(BaseModel):
    list_kind: str
    code: str | None
    label: str


class OrganizationOffer(BaseModel):
    organization_name: str
    acute_beds: Decimal | None
    mandates: list[MandateLine] = Field(default_factory=list)
    clinics: list[str] = Field(default_factory=list)

    def parents(self) -> list[MandateLine]:
        return [row for row in self.mandates if row.code is None or "." not in row.code]


def load_gr_offer(session: Session) -> list[OrganizationOffer]:
    organizations = session.execute(
        select(HospitalOrganization.id, OrganizationName.name)
        .join(OrganizationName, OrganizationName.organization_id == HospitalOrganization.id)
        .where(
            HospitalOrganization.home_canton_code == "GR",
            OrganizationName.name_role == "source_primary",
        )
        .order_by(OrganizationName.name)
    ).all()
    beds = {
        organization_id: value
        for organization_id, value in session.execute(
            select(StatisticObservation.organization_id, StatisticObservation.value_numeric).where(
                StatisticObservation.measure_code == BED_MEASURE,
                StatisticObservation.scope == "establishment",
            )
        )
        if organization_id is not None
    }
    mandates: dict = {}
    for row in session.scalars(
        select(ServiceMandate).where(ServiceMandate.match_status.in_(("exact", "reviewed")))
    ):
        if row.organization_id is None:
            continue
        mandates.setdefault(row.organization_id, []).append(
            MandateLine(list_kind=row.list_kind, code=row.code, label=row.label)
        )
    clinics: dict = {}
    clinic_rows = session.execute(
        select(Assertion.organization_id, Assertion.object_value)
        .join(Evidence, Evidence.id == Assertion.evidence_id)
        .where(
            Evidence.extraction_method.in_(CLINIC_METHODS),
            Assertion.fact_status == "candidate",
            Assertion.object_value.is_not(None),
        )
    )
    for organization_id, label in clinic_rows:
        if organization_id is None or not label:
            continue
        clinics.setdefault(organization_id, set()).add(label.strip())
    offers: list[OrganizationOffer] = []
    for organization_id, name in organizations:
        rows = sorted(
            mandates.get(organization_id, []),
            key=lambda item: (item.list_kind, item.code or "", item.label),
        )
        offers.append(
            OrganizationOffer(
                organization_name=name,
                acute_beds=beds.get(organization_id),
                mandates=rows,
                clinics=sorted(clinics.get(organization_id, set()), key=str.casefold),
            )
        )
    return offers


def render_gr_offer(offers: list[OrganizationOffer]) -> str:
    lines = ["Graubünden offer", ""]
    for offer in offers:
        lines.append(offer.organization_name)
        lines.append(f"  acute beds: {_beds(offer.acute_beds)}")
        parents = offer.parents()
        lines.append(f"  mandates: {len(offer.mandates)} linked, {len(parents)} parent rows")
        if not parents:
            lines.append("  parent mandates: none linked")
        else:
            for kind in ("akutsomatik", "psychiatrie", "rehabilitation"):
                group = [row for row in parents if row.list_kind == kind]
                if not group:
                    continue
                shown = "; ".join(_mandate(row) for row in group)
                lines.append(f"  {kind}: {shown}")
        if offer.clinics:
            lines.append(f"  clinics (candidate, {len(offer.clinics)}): {'; '.join(offer.clinics)}")
        else:
            lines.append("  clinics: not found on the saved index")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mandate(row: MandateLine) -> str:
    if row.code:
        return f"{row.code} {row.label}"
    return row.label


def _beds(value: Decimal | None) -> str:
    if value is None:
        return "not published"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession

    engine = create_engine("postgresql+psycopg://shi:shi@localhost:5432/shi")
    with DbSession(engine) as session:
        offers = load_gr_offer(session)
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_gr_offer(offers), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
