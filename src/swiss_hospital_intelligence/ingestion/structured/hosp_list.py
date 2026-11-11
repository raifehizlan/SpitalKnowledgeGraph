"""Parse cantonal hospital-list membership.

From 2010 the readme defines `1` as yes and `2` as no. 2008 and 2009 use an
older variable, and that readme does not repeat the 1/2 coding, so those years
stay undeclared whatever the cell contains. There is no canton column.
"""

from __future__ import annotations

import numbers
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

SHEET = "Spitalliste_2008-2024"
CODED_FROM_YEAR = 2010
REQUIRED_COLUMNS = (
    "JAHR",
    "Institution",
    "Strasse",
    "Ort",
    "SPITALLISTE_HOME",
    "SPITALLISTE_OTHERS",
)

ListState = Literal["yes", "no", "undeclared", "not_available_in_source"]


class CantonalListParseError(ValueError):
    """The workbook does not match the inspected hospital-list layout."""


class ParsedListMembership(BaseModel):
    reference_year: int
    institution: str
    street: str | None
    postal_place: str
    home_list_state: ListState
    other_list_state: ListState


class CantonalListParse(BaseModel):
    memberships: list[ParsedListMembership] = Field(default_factory=list)


def parse_cantonal_list(path: Path | str) -> CantonalListParse:
    workbook = pd.ExcelFile(path)
    if SHEET not in workbook.sheet_names:
        raise CantonalListParseError(f"missing sheet {SHEET}")
    frame = pd.read_excel(workbook, SHEET)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise CantonalListParseError(f"{SHEET} is missing columns: {', '.join(missing)}")

    memberships: list[ParsedListMembership] = []
    seen: set[tuple[int, str, str, str]] = set()
    for record in frame.to_dict(orient="records"):
        row = _membership(record)
        key = (row.reference_year, row.institution, row.street or "", row.postal_place)
        if key in seen:
            raise CantonalListParseError(
                f"duplicate membership for {row.institution} in {row.reference_year}"
            )
        seen.add(key)
        memberships.append(row)
    return CantonalListParse(memberships=memberships)


def _membership(record: dict[str, object]) -> ParsedListMembership:
    year = _year(record.get("JAHR"))
    institution = _text(record.get("Institution"))
    if institution is None:
        raise CantonalListParseError(f"membership row for {year} has no institution")
    postal_place = _text(record.get("Ort"))
    if postal_place is None:
        raise CantonalListParseError(f"{institution} in {year} has no place")
    if year >= CODED_FROM_YEAR:
        home = _coded_state(record.get("SPITALLISTE_HOME"), year, institution, "SPITALLISTE_HOME")
        other = _coded_state(record.get("SPITALLISTE_OTHERS"), year, institution, "SPITALLISTE_OTHERS")
    else:
        home = "undeclared"
        other = "undeclared"
    return ParsedListMembership(
        reference_year=year,
        institution=institution,
        street=_text(record.get("Strasse")),
        postal_place=postal_place,
        home_list_state=home,
        other_list_state=other,
    )


def _coded_state(value: object, year: int, institution: str, column: str) -> ListState:
    if _missing(value):
        return "not_available_in_source"
    code = _integer(value)
    if code == 1:
        return "yes"
    if code == 2:
        return "no"
    raise CantonalListParseError(
        f"{institution} in {year} has {column}={value!r}; only 1 and 2 are defined from {CODED_FROM_YEAR}"
    )


def _year(value: object) -> int:
    parsed = _integer(value)
    if parsed is None:
        raise CantonalListParseError(f"membership year is not an integer: {value!r}")
    return parsed


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
        return None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if number.is_integer():
            return int(number)
    return None


def _text(value: object) -> str | None:
    if _missing(value):
        return None
    text = str(value).strip()
    return text or None


def _missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return bool(pd.isna(value))
