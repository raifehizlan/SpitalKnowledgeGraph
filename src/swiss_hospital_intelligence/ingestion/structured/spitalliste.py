"""Parse a Graubünden Spitalliste into Leistungsauftrag rows.

Acute pages are read by column. A group heading is not a mandate. The same
heading is the department name in the first column. Psychiatry and
rehabilitation pages are read as lines. The service line under
Leistungsauftrag is the department name. A lettered footnote is not a
mandate. The town printed after a hospital name is not a site.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ListKind = Literal["akutsomatik", "psychiatrie", "rehabilitation"]
CantonScope = Literal["in_canton", "outside_canton", "undeclared"]

CODE = re.compile(r"^(?:BP|[A-Z]{2,8}\d+(?:\.\d+)*|[A-Z]{3,8})$")
DIAGNOSIS_CODE = re.compile(
    r"^(?:F\d+(?:\s*-\s*\d+)?(?:\s*,\s*F\d+(?:\s*-\s*\d+)?)*)\s+",
    re.IGNORECASE,
)
RESTRICTION = re.compile(
    r"\s*\((?:beschränkt|beschraenkt|provisorisch)\b[^)]*\)\s*$",
    re.IGNORECASE,
)
EDITION = re.compile(r"Stand\s+([A-Za-zäöüÄÖÜ]+ \d{4})")
NUMBERED = re.compile(r"^(\d+)\.\s*(.*)$")
SECTION_HEAD = re.compile(r"^[A-Z]\.")
SECTION_IN = re.compile(r"Standort im Kanton", re.IGNORECASE)
SECTION_OUT = re.compile(r"ausserhalb", re.IGNORECASE)
SECTION_OTHER = re.compile(r"^[A-Z]\.\s+Übrige", re.IGNORECASE)
HEADER = re.compile(r"leistungsauftrag", re.IGNORECASE)
FOOTNOTE = re.compile(
    r"^[a-z]\)|^\d+\s+Der Leistungsauftrag|^Zugewiesene Bettenzahl",
    re.IGNORECASE,
)
SERVICE = re.compile(
    r"rehabilitation|störung|stoerung|psychiatr|psychotherap|geronto|abhängig|"
    r"abhaengig|forensisch|psychosomat|hometreatment|kinder|querschnitt|"
    r"frührehab|fruehrehab|wachkoma|\bF\d",
    re.IGNORECASE,
)
CODE_X = (150.0, 210.0)
LABEL_X = (210.0, 480.0)


class SpitallisteParseError(ValueError):
    """The PDF does not match a Graubünden Spitalliste."""


class ParsedMandate(BaseModel):
    list_kind: ListKind
    edition: str
    canton_scope: CantonScope
    source_name: str
    code: str | None
    label: str


class SpitallisteParse(BaseModel):
    list_kind: ListKind
    edition: str
    mandates: list[ParsedMandate] = Field(default_factory=list)


def parse_spitalliste(path: Path | str) -> SpitallisteParse:
    import pymupdf

    document = pymupdf.open(Path(path))
    pages = [page.get_text("text") or "" for page in document]
    head = "\n".join(pages[:2])
    edition = _edition(head)
    if "Akutsomatik" in head:
        words = [_page_words(page) for page in document]
        return _acute(words, edition)
    if "Psychiatrie" in head:
        return _prose("\n".join(pages), "psychiatrie", edition)
    if "Rehabilitation" in head:
        return _prose("\n".join(pages), "rehabilitation", edition)
    raise SpitallisteParseError("missing Akutsomatik, Psychiatrie, or Rehabilitation title")


def parse_acute_lines(lines: list[list[tuple[float, str]]], edition: str) -> SpitallisteParse:
    return _acute_lines(lines, edition)


def parse_prose_list(text: str, list_kind: ListKind, edition: str) -> SpitallisteParse:
    return _prose(text, list_kind, edition)


def parse_prose_departments(path: Path | str) -> list[tuple[str, str]]:
    """Service lines under each hospital in the psychiatry or rehabilitation list."""
    parsed = parse_spitalliste(path)
    if parsed.list_kind == "akutsomatik":
        return []
    return department_names(parsed)


def department_names(parsed: SpitallisteParse) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in parsed.mandates:
        label = _department_label(row.label)
        if label is None:
            continue
        key = (row.source_name, label.casefold())
        if key in seen:
            continue
        seen.add(key)
        found.append((row.source_name, label))
    return found


def _department_label(label: str) -> str | None:
    text = " ".join(label.split()).strip(" .")
    if not text or text[0].isdigit():
        return None
    if FOOTNOTE.search(text) or re.match(r"^[a-z]\)", text):
        return None
    if re.match(r"^(?:beschränkt|beschraenkt|zugewiesene|der leistungsauftrag)\b", text, re.IGNORECASE):
        return None
    if text[0].islower() and SERVICE.search(text) is None:
        return None
    text = DIAGNOSIS_CODE.sub("", text)
    text = RESTRICTION.sub("", text).strip(" .")
    if len(text) < 3:
        return None
    if text[0].islower() and SERVICE.search(text) is None:
        return None
    return text


def parse_acute_departments(path: Path | str) -> list[tuple[str, str]]:
    """First-column headings of the acute table: one department name per group."""
    import pymupdf

    document = pymupdf.open(Path(path))
    try:
        head = "\n".join((page.get_text("text") or "") for page in document[:2])
        if "Akutsomatik" not in head:
            return []
        lines: list[list[tuple[float, str]]] = []
        for page in document:
            lines.extend(_page_words(page))
    finally:
        document.close()
    return departments_from_lines(lines)


def departments_from_lines(lines: list[list[tuple[float, str]]]) -> list[tuple[str, str]]:
    """Hospital heading, then each first-column name. A billing code is omitted."""
    hospital: str | None = None
    current: str | None = None
    confirmed = False
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def keep(name: str | None, backed: bool) -> None:
        if hospital is None or not name or not backed:
            return
        cleaned = _repair_column_wrap(" ".join(name.split()))
        key = (hospital, cleaned.casefold())
        if cleaned and key not in seen:
            seen.add(key)
            found.append((hospital, cleaned))

    for index, line in enumerate(lines):
        if _department_hospital(lines, index):
            keep(current, confirmed)
            current = None
            confirmed = False
            hospital = _hospital_name(_line_text(line))
            continue
        if hospital is None:
            continue
        left = _left_column(line)
        if not left or _skipped_left(left):
            if _code(line):
                confirmed = True
            continue
        if current and _department_continues(current, left):
            current = _join_department(current, left)
            if _code(line):
                confirmed = True
            continue
        keep(current, confirmed)
        current = left
        confirmed = _code(line) is not None
    keep(current, confirmed)
    return found


def _acute(pages: list[list[list[tuple[float, str]]]], edition: str) -> SpitallisteParse:
    lines: list[list[tuple[float, str]]] = []
    for page in pages:
        lines.extend(page)
    return _acute_lines(lines, edition)


def _acute_lines(lines: list[list[tuple[float, str]]], edition: str) -> SpitallisteParse:
    scope: CantonScope = "undeclared"
    hospital: str | None = None
    mandates: list[ParsedMandate] = []
    index = 0
    while index < len(lines):
        text = _line_text(lines[index])
        detected = _scope(text)
        if detected is not None:
            scope = detected
        elif _numbered_hospital(lines, index):
            hospital = _hospital_name(text)
        else:
            code = _code(lines[index])
            label = _label(lines[index])
            if label.casefold() == "bezeichnung":
                index += 1
                continue
            if hospital and code and label:
                mandates.append(
                    ParsedMandate(
                        list_kind="akutsomatik",
                        edition=edition,
                        canton_scope=scope,
                        source_name=hospital,
                        code=code,
                        label=label,
                    )
                )
            elif (
                hospital
                and mandates
                and mandates[-1].source_name == hospital
                and not code
                and label
                and _continues(mandates[-1].label)
            ):
                mandates[-1] = mandates[-1].model_copy(
                    update={"label": f"{mandates[-1].label} {label}"}
                )
        index += 1
    return SpitallisteParse(list_kind="akutsomatik", edition=edition, mandates=mandates)


def _prose(text: str, list_kind: ListKind, edition: str) -> SpitallisteParse:
    lines = _prose_lines(text)
    scope: CantonScope = "undeclared"
    mandates: list[ParsedMandate] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"[A-Z]\.", line):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            detected = _scope(f"{line} {following}")
            if detected is not None:
                scope = detected
            index += 1
            continue
        detected = _scope(line)
        if detected is not None:
            scope = detected
            index += 1
            continue
        if _prose_hospital(lines, index):
            numbered = NUMBERED.match(line)
            name = numbered.group(2) if numbered else line
            name, index = _name_until_header(lines, index + 1, name)
            index = _read_mandates(lines, index, list_kind, edition, scope, name, mandates)
            continue
        index += 1
    return SpitallisteParse(list_kind=list_kind, edition=edition, mandates=mandates)


def _read_mandates(
    lines: list[str],
    index: int,
    list_kind: ListKind,
    edition: str,
    scope: CantonScope,
    name: str,
    mandates: list[ParsedMandate],
) -> int:
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"[A-Z]\.", line) or _scope(line) is not None:
            return index
        if _prose_hospital(lines, index):
            return index
        if HEADER.search(line) or FOOTNOTE.search(line):
            index += 1
            continue
        if not SERVICE.search(line) and _header_before_number(lines, index):
            name, index = _name_until_header(lines, index + 1, line)
            continue
        if mandates and mandates[-1].source_name == name and _continues(mandates[-1].label):
            mandates[-1] = mandates[-1].model_copy(update={"label": f"{mandates[-1].label} {line}"})
        else:
            mandates.append(
                ParsedMandate(
                    list_kind=list_kind,
                    edition=edition,
                    canton_scope=scope,
                    source_name=name,
                    code=None,
                    label=line,
                )
            )
        index += 1
    return index


def _name_until_header(lines: list[str], index: int, name: str) -> tuple[str, int]:
    parts = [name] if name else []
    while index < len(lines) and not HEADER.search(lines[index]):
        if not NUMBERED.match(lines[index]):
            parts.append(lines[index])
        index += 1
    joined = re.sub(r"(?<=[A-Za-zäöüÄÖÜ])\d$", "", " ".join(parts))
    return " ".join(joined.split()), index


def _prose_hospital(lines: list[str], index: int) -> bool:
    if NUMBERED.match(lines[index]) is None:
        return False
    return _header_before_number(lines, index + 1)


def _header_before_number(lines: list[str], index: int) -> bool:
    for line in lines[index : index + 8]:
        if HEADER.search(line):
            return True
        if NUMBERED.match(line):
            return False
    return False


def _department_hospital(lines: list[list[tuple[float, str]]], index: int) -> bool:
    """A numbered heading whose next lines open the Leistungsauftrag table."""
    words = lines[index]
    if not words or words[0][0] >= 120 or NUMBERED.match(words[0][1]) is None:
        return False
    for line in lines[index + 1 : index + 8]:
        if any(origin < CODE_X[0] and HEADER.search(text) for origin, text in line):
            return True
        if line and line[0][0] < 120 and NUMBERED.match(line[0][1]):
            return False
    return False


def _numbered_hospital(lines: list[list[tuple[float, str]]], index: int) -> bool:
    words = lines[index]
    if not words or words[0][0] >= 120 or NUMBERED.match(words[0][1]) is None:
        return False
    for line in lines[index + 1 : index + 6]:
        if HEADER.search(_line_text(line)):
            return True
        if line and line[0][0] < 120 and NUMBERED.match(line[0][1]):
            return False
    return False


def _scope(text: str) -> CantonScope | None:
    if SECTION_HEAD.match(text) is None:
        return None
    if SECTION_OUT.search(text):
        return "outside_canton"
    if SECTION_IN.search(text) or SECTION_OTHER.search(text):
        return "in_canton"
    return None


def _hospital_name(text: str) -> str:
    match = NUMBERED.match(text)
    name = match.group(2) if match else text
    name = re.sub(r"(?<=[A-Za-zäöüÄÖÜ])\d$", "", name)
    return " ".join(name.split())


def _code(line: list[tuple[float, str]]) -> str | None:
    for origin, text in line:
        if CODE_X[0] <= origin < CODE_X[1] and CODE.match(text):
            return text
    return None


def _label(line: list[tuple[float, str]]) -> str:
    parts = [text for origin, text in line if LABEL_X[0] <= origin < LABEL_X[1]]
    return " ".join(parts).strip()


def _left_column(line: list[tuple[float, str]]) -> str:
    parts = [text for origin, text in line if origin < CODE_X[0]]
    return " ".join(parts).strip()


def _skipped_left(text: str) -> bool:
    if HEADER.search(text) or FOOTNOTE.search(text) or SECTION_HEAD.match(text):
        return True
    if text[0].isdigit():
        return True
    tokens = [token.strip(",.;") for token in text.split()]
    tokens = [token for token in tokens if token]
    if tokens and all(_code_token(token) for token in tokens):
        return True
    return False


def _code_token(token: str) -> bool:
    if CODE.match(token):
        return True
    return bool(re.fullmatch(r"[A-Z]\d[\dA-Z.]*", token))


def _department_continues(current: str, extra: str) -> bool:
    if current.endswith("-"):
        return True
    return extra[:1].islower()


def _repair_column_wrap(name: str) -> str:
    if name.endswith(" chirurgis"):
        return f"{name[: -len(' chirurgis')]} chirurgisch"
    return name


def _join_department(current: str, extra: str) -> str:
    if current.endswith("-") and extra[:1].islower():
        return current[:-1] + extra
    return f"{current} {extra}"


def _continues(label: str) -> bool:
    folded = label.rstrip()
    return folded.endswith((",", "-", " und", "("))


def _line_text(line: list[tuple[float, str]]) -> str:
    return " ".join(text for _, text in line)


def _prose_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if line and not re.fullmatch(r"\d+", line):
            lines.append(line)
    return lines


def _edition(text: str) -> str:
    match = EDITION.search(text)
    if match is None:
        raise SpitallisteParseError("missing Stand line")
    return match.group(1)


def _page_words(page) -> list[list[tuple[float, str]]]:
    rows: dict[int, list[tuple[float, float, str]]] = {}
    for word in page.get_text("words"):
        rows.setdefault(round(word[1]), []).append((word[0], word[1], word[4]))
    lines: list[list[tuple[float, str]]] = []
    for key in sorted(rows):
        ordered = sorted(rows[key], key=lambda item: (item[1], item[0]))
        lines.append([(origin, text) for origin, _, text in ordered])
    return lines
