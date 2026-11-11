"""Parse the BAG key-figure workbook without inventing values."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from swiss_hospital_intelligence.ingestion.structured.measures import (
    IDENTITY_COLUMNS,
    PUBLISHED_MEASURES,
    UNPUBLISHED_MEASURES,
)
from swiss_hospital_intelligence.ingestion.structured.records import (
    KeyFigureParse,
    MeasureObservation,
    ParsedEstablishment,
    ParsedSite,
)

ESTABLISHMENT_SHEET = "KZ2024_KZP24"
SITE_SHEET = "Standorte_KZ2024_KZP24"
NATIONAL_NAME_PREFIX = "Alle Betriebe"

REQUIRED_ESTABLISHMENT_COLUMNS = (
    "JAHR",
    "KT",
    "Inst",
    "Adr",
    "Ort",
    "Typ",
    "RForm",
    "Akt",
    "SL",
    "WB",
    "AnzStand",
    "SA",
    "LA",
)
REQUIRED_SITE_COLUMNS = (
    "JAHR",
    "KT",
    "Inst",
    "Standort",
    "Adr_Standort",
    "Ort_Standort",
    "KT_Standort",
    "LA_Standort",
    "AnzStand",
)


class KeyFigureParseError(ValueError):
    """The workbook does not match the inspected 2024 layout."""


def parse_key_figures(path: Path | str) -> KeyFigureParse:
    workbook = pd.ExcelFile(path)
    _require_sheet(workbook, ESTABLISHMENT_SHEET)
    _require_sheet(workbook, SITE_SHEET)
    establishments_frame = pd.read_excel(workbook, ESTABLISHMENT_SHEET)
    sites_frame = pd.read_excel(workbook, SITE_SHEET)
    _require_columns(establishments_frame, REQUIRED_ESTABLISHMENT_COLUMNS, ESTABLISHMENT_SHEET)
    _require_columns(sites_frame, REQUIRED_SITE_COLUMNS, SITE_SHEET)

    unknown = [
        column
        for column in establishments_frame.columns
        if column not in IDENTITY_COLUMNS
        and column not in PUBLISHED_MEASURES
        and column not in UNPUBLISHED_MEASURES
    ]
    establishments: list[ParsedEstablishment] = []
    excluded = 0
    for record in establishments_frame.to_dict(orient="records"):
        if _is_national_total(record):
            excluded += 1
            continue
        establishments.append(_establishment(record))
    if excluded < 1:
        raise KeyFigureParseError("national total row is missing")

    known_names = {row.name for row in establishments}
    sites: list[ParsedSite] = []
    missing_parents: list[str] = []
    for record in sites_frame.to_dict(orient="records"):
        parent = _text(record.get("Inst"))
        if parent is None or parent not in known_names:
            missing_parents.append(parent or "")
            continue
        sites.append(_site(record))

    return KeyFigureParse(
        establishments=establishments,
        sites=sites,
        excluded_national_rows=excluded,
        unknown_columns=unknown,
        sites_without_establishment=missing_parents,
    )


def _establishment(record: dict[str, object]) -> ParsedEstablishment:
    canton = _text(record.get("KT"))
    name = _text(record.get("Inst"))
    if canton is None or name is None:
        raise KeyFigureParseError("establishment row is missing canton or name")
    measures: list[MeasureObservation] = []
    for code, spec in PUBLISHED_MEASURES.items():
        if code not in record:
            continue
        measures.append(_measure(code, spec.unit, spec.activity_type, record.get(code)))
    for code in UNPUBLISHED_MEASURES:
        if code not in record or _is_missing(record.get(code)):
            continue
        measures.append(_measure(code, "undeclared", None, record.get(code)))
    return ParsedEstablishment(
        reference_year=_year(record.get("JAHR")),
        home_canton=canton,
        name=name,
        street=_text(record.get("Adr")),
        postal_place=_text(record.get("Ort")),
        typology_code=_text(record.get("Typ")),
        legal_form_code=_text(record.get("RForm")),
        activities=_tokens(record.get("Akt")),
        specific_services=_tokens(record.get("SL")),
        training=_tokens(record.get("WB")),
        equipment=_tokens(record.get("SA")),
        service_offer=_tokens(record.get("LA")),
        reported_site_count=_optional_int(record.get("AnzStand")),
        measures=measures,
    )


def _site(record: dict[str, object]) -> ParsedSite:
    parent = _text(record.get("Inst"))
    name = _text(record.get("Standort"))
    canton = _text(record.get("KT_Standort"))
    home = _text(record.get("KT"))
    if parent is None or name is None or canton is None or home is None:
        raise KeyFigureParseError("site row is missing parent, name, or canton")
    return ParsedSite(
        reference_year=_year(record.get("JAHR")),
        parent_name=parent,
        parent_home_canton=home,
        name=name,
        street=_text(record.get("Adr_Standort")),
        postal_place=_text(record.get("Ort_Standort")),
        canton_code=canton,
        service_offer=_tokens(record.get("LA_Standort")),
        reported_site_count=_optional_int(record.get("AnzStand")),
    )


def _measure(
    code: str,
    unit: str,
    activity_type: str | None,
    raw: object,
) -> MeasureObservation:
    if _is_missing(raw):
        return MeasureObservation(
            code=code,
            unit=unit,
            activity_type=activity_type,
            value_numeric=None,
            raw_value=None,
            value_state="not_available_in_source",
        )
    numeric = _decimal(raw)
    return MeasureObservation(
        code=code,
        unit=unit,
        activity_type=activity_type,
        value_numeric=numeric,
        raw_value=_raw_text(raw),
        value_state="value",
    )


def _is_national_total(record: dict[str, object]) -> bool:
    name = _text(record.get("Inst")) or ""
    return name.startswith(NATIONAL_NAME_PREFIX)


def _require_sheet(workbook: pd.ExcelFile, sheet: str) -> None:
    if sheet not in workbook.sheet_names:
        raise KeyFigureParseError(f"missing sheet {sheet}")


def _require_columns(frame: pd.DataFrame, required: tuple[str, ...], sheet: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyFigureParseError(f"{sheet} is missing columns: {', '.join(missing)}")


def _tokens(value: object) -> list[str]:
    text = _text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _text(value: object) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _raw_text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise KeyFigureParseError(f"measure value is not numeric: {value!r}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    text = str(value).strip().replace("'", "").replace("’", "")
    return Decimal(text)


def _year(value: object) -> int:
    if _is_missing(value):
        raise KeyFigureParseError("reference year is missing")
    return int(value)


def _optional_int(value: object) -> int | None:
    if _is_missing(value):
        return None
    return int(value)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return bool(pd.isna(value))
