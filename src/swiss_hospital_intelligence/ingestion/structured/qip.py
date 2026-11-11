"""Parse the BAG acute-hospital quality indicator CSV.

The file repeats its header in German, French, and Italian, and the columns
change between sections. A trailing comment is kept. Suppression (`*`) and a
dash (`-`) stay distinct from zero and from an empty cell.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

QualityRole = Literal["observed_rate", "expected_rate", "smr", "case_count", "length_of_stay_days"]
QualityWindow = Literal["2019_2023", "2024"]
QualityValueState = Literal["value", "not_available_in_source", "suppressed", "dash", "unknown"]
HEADER_NAMES = {"institution", "instituzione"}
INDICATOR_CODE = re.compile(r"^[A-Z](?:\.\d+)*(?:\.[A-Za-z0-9]+)?$")


class QualityComponent(BaseModel):
    role: QualityRole
    window: QualityWindow
    value_numeric: Decimal | None
    raw_value: str | None
    value_state: QualityValueState


class QualityRow(BaseModel):
    line_number: int
    institution: str
    indicator: str
    indicator_code: str | None
    row_kind: Literal["heading", "measure"]
    components: list[QualityComponent] = Field(default_factory=list)
    comment: str | None = None


class QualityFailure(BaseModel):
    line_number: int
    reason: str
    raw_line: str


class QualityColumn(BaseModel):
    role: QualityRole | None
    window: QualityWindow | None


class QualityParse(BaseModel):
    rows: list[QualityRow]
    failures: list[QualityFailure]
    header_count: int

    def rows_for(self, institution: str, code: str) -> list[QualityRow]:
        return [
            row
            for row in self.rows
            if row.institution == institution and row.indicator_code == code and row.row_kind == "measure"
        ]


class QualityParseError(ValueError):
    """The file has no usable header."""


def parse_quality_indicators(path: Path | str) -> QualityParse:
    rows: list[QualityRow] = []
    failures: list[QualityFailure] = []
    header: list[QualityColumn] | None = None
    header_count = 0
    text = Path(path).read_text(encoding="utf-8-sig")
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        fields = raw_line.split(";")
        if _is_header(fields):
            try:
                header = _header(fields)
            except QualityParseError as error:
                failures.append(QualityFailure(line_number=line_number, reason=str(error), raw_line=raw_line))
                header = None
                continue
            header_count += 1
            continue
        if header is None:
            failures.append(
                QualityFailure(line_number=line_number, reason="row appears before a header", raw_line=raw_line)
            )
            continue
        if len(fields) < 10:
            failures.append(QualityFailure(line_number=line_number, reason="fewer than 10 fields", raw_line=raw_line))
            continue
        parsed = _row(line_number, fields, header)
        if isinstance(parsed, QualityFailure):
            parsed.raw_line = raw_line
            failures.append(parsed)
            continue
        rows.append(parsed)
    if header_count == 0:
        raise QualityParseError("quality file has no header")
    return QualityParse(rows=rows, failures=failures, header_count=header_count)


def _is_header(fields: list[str]) -> bool:
    if len(fields) < 2:
        return False
    return fields[0].strip().casefold() in HEADER_NAMES and fields[1].strip().casefold() in {
        "indicator",
        "indikator",
        "indicatore",
    }


def _header(fields: list[str]) -> list[QualityColumn]:
    if len(fields) != 10:
        raise QualityParseError(f"header has {len(fields)} fields")
    columns: list[QualityColumn] = []
    for label in fields[2:]:
        columns.append(_column(label.strip()))
    return columns


def _column(label: str) -> QualityColumn:
    if not label:
        return QualityColumn(role=None, window=None)
    if "2019" in label:
        window: QualityWindow = "2019_2023"
    elif "2024" in label:
        window = "2024"
    else:
        raise QualityParseError(f"header column has no year: {label}")
    folded = label.casefold()
    if "smr" in folded:
        role: QualityRole = "smr"
    elif any(token in folded for token in ("cas", "fallzahl", "casi")):
        role = "case_count"
    elif any(token in folded for token in ("séjour", "sejour", "aufenthalt", "degenza")):
        role = "length_of_stay_days"
    elif any(token in folded for token in ("attendu", "erwartet", "atteso")):
        role = "expected_rate"
    elif any(token in folded for token in ("taux", "rate", "tasso")):
        role = "observed_rate"
    else:
        raise QualityParseError(f"unrecognized header column: {label}")
    return QualityColumn(role=role, window=window)


def _row(line_number: int, fields: list[str], header: list[QualityColumn]) -> QualityRow | QualityFailure:
    institution = fields[0].strip()
    indicator = fields[1].strip()
    measure_fields = fields[2:10]
    comment = ";".join(fields[10:]).strip() or None
    if not institution or not indicator:
        return QualityFailure(line_number=line_number, reason="institution or indicator is empty", raw_line="")
    components: list[QualityComponent] = []
    labeled_blanks = 0
    labeled_columns = 0
    for cell, column in zip(measure_fields, header, strict=True):
        raw = cell.strip()
        if column.role is None or column.window is None:
            if raw:
                return QualityFailure(
                    line_number=line_number,
                    reason="value in an unlabeled column",
                    raw_line="",
                )
            continue
        labeled_columns += 1
        component = _component(column.role, column.window, raw)
        if component.value_state == "not_available_in_source":
            labeled_blanks += 1
        components.append(component)
    kind: Literal["heading", "measure"] = "heading" if labeled_columns == labeled_blanks else "measure"
    code = indicator.split(" ", 1)[0]
    return QualityRow(
        line_number=line_number,
        institution=institution,
        indicator=indicator,
        indicator_code=code if INDICATOR_CODE.match(code) else None,
        row_kind=kind,
        components=[] if kind == "heading" else components,
        comment=comment,
    )


def _component(role: QualityRole, window: QualityWindow, raw: str) -> QualityComponent:
    if raw == "":
        state: QualityValueState = "not_available_in_source"
        numeric = None
    elif raw == "*":
        state = "suppressed"
        numeric = None
    elif raw == "-":
        state = "dash"
        numeric = None
    else:
        try:
            numeric = _decimal(raw)
        except ValueError:
            return QualityComponent(
                role=role,
                window=window,
                value_numeric=None,
                raw_value=raw,
                value_state="unknown",
            )
        state = "value"
    return QualityComponent(
        role=role,
        window=window,
        value_numeric=numeric,
        raw_value=raw or None,
        value_state=state,
    )


def _decimal(raw: str) -> Decimal:
    cleaned = raw.replace("%", "").replace("'", "").replace("’", "").replace(" ", "")
    try:
        return Decimal(cleaned)
    except Exception as error:
        raise ValueError(raw) from error
