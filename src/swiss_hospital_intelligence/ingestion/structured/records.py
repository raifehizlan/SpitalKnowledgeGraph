"""Parsed key-figure records. These are not database rows yet."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

ValueState = Literal["value", "not_available_in_source"]


class MeasureObservation(BaseModel):
    code: str
    unit: str
    activity_type: str | None
    scope: Literal["establishment"] = "establishment"
    value_numeric: Decimal | None
    raw_value: str | None
    value_state: ValueState


class ParsedEstablishment(BaseModel):
    reference_year: int
    home_canton: str
    name: str
    street: str | None
    postal_place: str | None
    typology_code: str | None
    legal_form_code: str | None
    activities: list[str] = Field(default_factory=list)
    specific_services: list[str] = Field(default_factory=list)
    training: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    service_offer: list[str] = Field(default_factory=list)
    reported_site_count: int | None
    measures: list[MeasureObservation] = Field(default_factory=list)


class ParsedSite(BaseModel):
    reference_year: int
    parent_name: str
    parent_home_canton: str
    name: str
    street: str | None
    postal_place: str | None
    canton_code: str
    service_offer: list[str] = Field(default_factory=list)
    reported_site_count: int | None


class KeyFigureParse(BaseModel):
    """A workbook parse. The national total row is counted and excluded."""

    establishments: list[ParsedEstablishment]
    sites: list[ParsedSite]
    excluded_national_rows: int
    unknown_columns: list[str] = Field(default_factory=list)
    sites_without_establishment: list[str] = Field(default_factory=list)

    def establishment(self, name: str) -> ParsedEstablishment:
        matches = [row for row in self.establishments if row.name == name]
        if len(matches) != 1:
            raise KeyError(name)
        return matches[0]


class ScopeError(ValueError):
    """An establishment measure was pointed at a site."""


def require_establishment_scope(observation: MeasureObservation, site_id: str | None) -> None:
    """Refuse to store a key-figure measure on a site.

    The 2024 workbook publishes these numbers for the establishment only.
    """

    if observation.scope == "establishment" and site_id is not None:
        raise ScopeError(
            f"{observation.code} is establishment-scoped and cannot be stored on site {site_id}"
        )
