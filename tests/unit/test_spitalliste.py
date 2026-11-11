"""A Spitalliste row is a mandate. A town after the name is not a site."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Base, EntityCrosswalk, ServiceMandate
from swiss_hospital_intelligence.ingestion.structured.load_spitalliste import (
    COMMA_METHOD,
    load_spitalliste,
)
from swiss_hospital_intelligence.reports.reviewed_aliases import ReviewedAlias
from swiss_hospital_intelligence.ingestion.structured.spitalliste import (
    ParsedMandate,
    SpitallisteParse,
    department_names,
    departments_from_lines,
    parse_acute_departments,
    parse_acute_lines,
    parse_prose_departments,
    parse_prose_list,
    parse_spitalliste,
)

PROSE = """
Spitalliste
Psychiatrie
Stand August 2025
1. Leistungsgruppenkonzept
Die Planung beschreibt die Psychiatrie.
A. Kliniken mit Standort im Kanton Graubünden
1.
Example Klinik, Example
Leistungsauftrag für
Akutpsychiatrie / Psychotherapie
F3 Affektive Störungen
a) beschränkt auf die Behandlung psychosomatischer Krankheitsbilder
Zugewiesene Bettenzahl für Bündner KVG Patienten: 5 Betten
B. Kliniken mit Standort ausserhalb des Kantons Graubünden
1. Other Klinik, Other
Leistungsauftrag für
Kinder und Jugendliche
"""

ACUTE_LINES = [
    [(67.0, "1."), (85.0, "Leistungsgruppenkonzept")],
    [(85.0, "Die"), (110.0, "Planung")],
    [(67.0, "A."), (85.0, "Spitäler"), (140.0, "mit"), (170.0, "Standort"), (240.0, "im"), (270.0, "Kanton")],
    [(67.0, "1."), (85.0, "Example"), (140.0, "Hospital,"), (200.0, "Example")],
    [(85.0, "Leistungsauftrag"), (170.0, "für")],
    [(177.0, "Kürzel"), (218.0, "Bezeichnung")],
    [(87.0, "Herz"), (177.0, "KAR1"), (218.0, "Kardiologie"), (280.0, "(inkl."), (320.0, "Schrittmacher)"), (496.0, "1")],
    [(177.0, "VIS1"), (218.0, "Viszeralchirurgie,")],
    [(218.0, "grosse"), (260.0, "Eingriffe")],
    [(67.0, "2."), (85.0, "Annex"), (130.0, "Klinik")],
    [(85.0, "Leistungsauftrag"), (170.0, "für")],
    [(177.0, "NEU1"), (218.0, "Neurologie")],
]


def test_prose_keeps_mandates_and_drops_footnotes() -> None:
    parsed = parse_prose_list(PROSE, "psychiatrie", "August 2025")
    rows = [(row.canton_scope, row.source_name, row.label) for row in parsed.mandates]
    assert ("in_canton", "Example Klinik, Example", "Akutpsychiatrie / Psychotherapie") in rows
    assert ("in_canton", "Example Klinik, Example", "F3 Affektive Störungen") in rows
    assert ("outside_canton", "Other Klinik, Other", "Kinder und Jugendliche") in rows
    assert all("beschränkt" not in row.label for row in parsed.mandates)
    assert all("Bettenzahl" not in row.label for row in parsed.mandates)
    assert all(row.code is None for row in parsed.mandates)


def test_acute_columns_ignore_the_group_heading_and_the_footnote() -> None:
    parsed = parse_acute_lines(ACUTE_LINES, "April 2026")
    assert [(row.source_name, row.code, row.label) for row in parsed.mandates] == [
        ("Example Hospital, Example", "KAR1", "Kardiologie (inkl. Schrittmacher)"),
        ("Example Hospital, Example", "VIS1", "Viszeralchirurgie, grosse Eingriffe"),
        ("Annex Klinik", "NEU1", "Neurologie"),
    ]
    assert {row.canton_scope for row in parsed.mandates} == {"in_canton"}


DEPARTMENT_LINES = [
    [(67.0, "1."), (85.0, "Example"), (140.0, "Hospital,"), (200.0, "Example")],
    [(85.0, "Leistungsauftrag"), (170.0, "für")],
    [(87.0, "Gynäkologie"), (179.0, "GYN1"), (221.0, "Gynäkologie")],
    [(87.0, "Bewegungsapparat")],
    [(87.0, "chirurgisch"), (179.0, "BEW1"), (221.0, "Schulter")],
    [(87.0, "Klinik Gut AG,")],
    [(85.0, "Leistungsauftrag"), (170.0, "für")],
    [(87.0, "Querschnitts-")],
    [(87.0, "bereiche"), (179.0, "KINM")],
    [(87.0, "Sozialversicherungssystem"), (195.0, "kranken-,")],
    [(87.0, "(Radio-)"), (120.0, "Onkologie"), (179.0, "ONK1"), (221.0, "Onkologie")],
    [(87.0, "1"), (110.0, "-"), (130.0, "beschränkt"), (180.0, "auf")],
    [(87.0, "Z04.6X.21,"), (150.0, "Z04.6X.22,")],
]


def test_first_column_is_one_department_and_a_code_line_is_not() -> None:
    names = departments_from_lines(DEPARTMENT_LINES)
    assert names == [
        ("Example Hospital, Example", "Gynäkologie"),
        ("Example Hospital, Example", "Bewegungsapparat chirurgisch"),
        ("Example Hospital, Example", "Querschnittsbereiche"),
        ("Example Hospital, Example", "(Radio-) Onkologie"),
    ]


def test_a_service_line_is_a_department_and_a_footnote_fragment_is_not() -> None:
    parsed = parse_prose_list(PROSE, "psychiatrie", "August 2025")
    assert department_names(parsed) == [
        ("Example Klinik, Example", "Akutpsychiatrie / Psychotherapie"),
        ("Example Klinik, Example", "Affektive Störungen"),
        ("Other Klinik, Other", "Kinder und Jugendliche"),
    ]
    extra = SpitallisteParse(
        list_kind="rehabilitation",
        edition="August 2024",
        mandates=[
            ParsedMandate(
                list_kind="rehabilitation",
                edition="August 2024",
                canton_scope="in_canton",
                source_name="Example Klinik, Example",
                code=None,
                label="neurologische Rehabilitation (beschränkt auf schwer Hirnverletzte und Wachkoma)",
            ),
            ParsedMandate(
                list_kind="rehabilitation",
                edition="August 2024",
                canton_scope="in_canton",
                source_name="Example Klinik, Example",
                code=None,
                label="somatischer Krankheitsbilder",
            ),
            ParsedMandate(
                list_kind="rehabilitation",
                edition="August 2024",
                canton_scope="in_canton",
                source_name="Example Klinik, Example",
                code=None,
                label="kardiovaskuläre Rehabilitation (provisorisch bis 31. Dezember 2015)",
            ),
        ],
    )
    assert department_names(extra) == [
        ("Example Klinik, Example", "neurologische Rehabilitation"),
        ("Example Klinik, Example", "kardiovaskuläre Rehabilitation"),
    ]


def test_loader_links_only_an_exact_name_and_a_second_run_keeps_the_row(tmp_path: Path) -> None:
    path = tmp_path / "psychiatrie.pdf"
    _pdf(path, PROSE)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    exact_id = uuid4()
    names = {"Example Klinik, Example": exact_id}
    with Session(engine) as session:
        first = load_spitalliste(session, path, names)
        session.commit()
        mandate_ids = set(session.scalars(select(ServiceMandate.id)))
        again = load_spitalliste(session, path, names)
        session.commit()
        assert first.mandates == 3
        assert first.exact_links == 2
        assert first.unmatched == 1
        assert again.mandates == 3
        assert session.scalar(select(func.count()).select_from(ServiceMandate)) == 3
        assert set(session.scalars(select(ServiceMandate.id))) == mandate_ids
        linked = session.scalar(
            select(ServiceMandate).where(ServiceMandate.source_name == "Example Klinik, Example")
        )
        assert linked is not None
        assert linked.organization_id == exact_id
        assert linked.match_status == "exact"
        other = session.scalar(select(ServiceMandate).where(ServiceMandate.source_name == "Other Klinik, Other"))
        assert other is not None
        assert other.organization_id is None
        assert other.match_status == "unmatched"


def test_text_before_the_comma_links_only_when_that_text_is_the_establishment_name(tmp_path: Path) -> None:
    path = tmp_path / "acute-names.pdf"
    _pdf(
        path,
        """
Spitalliste
Psychiatrie
Stand August 2025
A. Kliniken mit Standort im Kanton Graubünden
1. Example Hospital, Example
Leistungsauftrag für
Akutpsychiatrie / Psychotherapie
2. Example Hospital Annex, Example
Leistungsauftrag für
Gerontopsychiatrie
""",
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hospital_id = uuid4()
    with Session(engine) as session:
        load_spitalliste(session, path, {"Example Hospital": hospital_id})
        session.commit()
        linked = session.scalar(select(ServiceMandate).where(ServiceMandate.source_name == "Example Hospital, Example"))
        annex = session.scalar(
            select(ServiceMandate).where(ServiceMandate.source_name == "Example Hospital Annex, Example")
        )
        assert linked is not None and linked.organization_id == hospital_id
        assert annex is not None and annex.organization_id is None
        method = session.scalar(select(EntityCrosswalk.method).where(EntityCrosswalk.target_id == linked.id))
        assert method == COMMA_METHOD


def test_a_reviewed_alias_links_and_another_printed_name_stays_unmatched(tmp_path: Path) -> None:
    path = tmp_path / "reviewed.pdf"
    _pdf(
        path,
        """
Spitalliste
Psychiatrie
Stand August 2025
A. Kliniken mit Standort im Kanton Graubünden
1. Printed Clinic, Example
Leistungsauftrag für
Akutpsychiatrie / Psychotherapie
2. Zürcher RehaZentren, Davos
Leistungsauftrag für
Gerontopsychiatrie
""",
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    hospital_id = uuid4()
    alias = ReviewedAlias(
        source_name="Printed Clinic, Example",
        organization_name="Example Hospital",
        evidence="The printed heading is the reviewed establishment.",
    )
    with Session(engine) as session:
        result = load_spitalliste(
            session,
            path,
            {"Example Hospital": hospital_id},
            aliases=[alias],
        )
        session.commit()
        linked = session.scalar(select(ServiceMandate).where(ServiceMandate.source_name == "Printed Clinic, Example"))
        left = session.scalar(select(ServiceMandate).where(ServiceMandate.label == "Gerontopsychiatrie"))
        assert result.reviewed_links == 1
        assert result.unmatched == 1
        assert linked is not None and linked.organization_id == hospital_id
        assert linked.match_status == "reviewed"
        assert left is not None and left.organization_id is None


def test_real_lists_when_the_files_are_present() -> None:
    directory = Path("data/raw/spitalliste")
    acute = directory / "akutsomatik.pdf"
    psych = directory / "psychiatrie.pdf"
    rehab = directory / "rehabilitation.pdf"
    if not acute.is_file() or not psych.is_file() or not rehab.is_file():
        pytest.skip("Spitalliste PDFs are not on disk")
    acute_rows = parse_spitalliste(acute)
    ksgr = [row for row in acute_rows.mandates if row.source_name == "Kantonsspital Graubünden, Chur"]
    assert acute_rows.edition == "April 2026"
    assert any(row.code == "KAR1" and row.canton_scope == "in_canton" for row in ksgr)
    assert any(
        row.source_name.startswith("Ente Ospedaliero") and row.canton_scope == "outside_canton"
        for row in acute_rows.mandates
    )
    assert any(row.source_name.startswith("Klinik Gut") and row.canton_scope == "in_canton" for row in acute_rows.mandates)
    assert any(row.source_name.endswith("Wolfgang") for row in acute_rows.mandates)
    assert all(row.code != "Kürzel" for row in acute_rows.mandates)
    psych_rows = parse_spitalliste(psych)
    names = {row.source_name for row in psych_rows.mandates}
    assert any(row.canton_scope == "in_canton" and "Waldhaus" in row.source_name for row in psych_rows.mandates)
    assert any(row.canton_scope == "outside_canton" for row in psych_rows.mandates)
    assert any("Unterengadin" in name for name in names)
    rehab_rows = parse_spitalliste(rehab)
    assert any(row.label == "Frührehabilitation" for row in rehab_rows.mandates)
    thusis = [
        name
        for hospital, name in parse_acute_departments(acute)
        if hospital == "SPITAL THUSIS, Thusis"
    ]
    assert thusis == [
        "Basispaket",
        "Dermatologie",
        "Neurologie",
        "Endokrinologie",
        "Gastroenterologie",
        "Viszeralchirurgie",
        "Hämatologie",
        "Herz",
        "Urologie",
        "Pneumologie",
        "Bewegungsapparat chirurgisch",
        "Rheumatologie",
        "Gynäkologie",
        "Geburtshilfe",
        "Neugeborene",
        "(Radio-) Onkologie",
        "Querschnittsbereiche",
    ]
    zurich = [
        name
        for hospital, name in parse_acute_departments(acute)
        if hospital == "Universitätsspital Zürich, Zürich"
    ]
    assert "Bewegungsapparat chirurgisch" in zurich
    assert all(not name.endswith("chirurgis") for name in zurich)
    psych_rows = parse_prose_departments(psych)
    pdgr = [name for hospital, name in psych_rows if hospital.startswith("Psychiatrische Dienste")]
    assert pdgr == [
        "Akutpsychiatrie / Psychotherapie",
        "Rehabilitationspsychiatrie",
        "Gerontopsychiatrie",
        "Abhängigkeitserkrankungen",
        "Stressfolgeerkrankungen",
        "Forensische Psychiatrie",
        "Psychosomatik",
        "Kinder und Jugendliche",
        "Hometreatment",
    ]
    rehab_rows = parse_prose_departments(rehab)
    assert all("cherungssystem" not in name and "somatischer" not in name for _, name in [*psych_rows, *rehab_rows])
    assert ("Reha Andeer, Andeer", "muskuloskelettale Rehabilitation") in rehab_rows


def _pdf(path: Path, text: str) -> None:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
