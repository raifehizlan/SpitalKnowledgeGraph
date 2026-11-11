"""A clinic index keeps specialty links and does not assign a site."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    HospitalOrganization,
    OrganizationName,
)
from swiss_hospital_intelligence.ingestion.documents.catalog_pages import (
    catalog_mentions,
    is_catalog_index,
    load_catalog_mentions,
    menu_mentions,
)
from swiss_hospital_intelligence.ingestion.documents.source_register import RegisterRow, SourceRegister

HTML = """
<html><body>
<nav><a href="/kontakt">Kontakt</a><a href="/chirurgie">Chirurgie</a></nav>
<div class="views-row"><a href="/chirurgie">Chirurgie</a></div>
<div class="views-row"><a href="/augenklinik">Augenklinik</a></div>
<div class="views-row"><a href="/baby">Babybadespass in Chur</a></div>
<div class="views-row"><a href="/chirurgie">Chirurgie</a></div>
</body></html>
"""


def test_index_links_keep_a_specialty_and_a_clinic_name() -> None:
    assert is_catalog_index("https://www.ksgr.ch/fachgebiete")
    assert is_catalog_index("https://www.ksgr.ch/fachgebiete?page=2")
    assert is_catalog_index("https://www.flurystiftung.ch/de/angebot")
    assert is_catalog_index("https://valens.ch/reha-chur/angebot/", "/reha-chur")
    assert not is_catalog_index("https://www.ksgr.ch/kardiologie/angebot")
    assert not is_catalog_index("https://valens.ch/reha-chur/angebot/")
    assert not is_catalog_index("https://cseb.ch/angebot/praevention")
    mentions = catalog_mentions(HTML)
    assert [(item.predicate, item.object_value) for item in mentions] == [
        ("hasDepartment", "Chirurgie"),
        ("hasClinic", "Augenklinik"),
    ]


def test_homepage_menu_keeps_a_specialty_and_drops_spitex() -> None:
    html = """
    <a href="/medizinische-leistungen">Medizinische Leistungen</a>
    <a href="/medizinische-leistungen/kardiologie">Kardiologie</a>
    <a href="/gastronomie">Gastronomie</a>
    <a href="/spitex/angebot">Physiotherapie</a>
    <a href="mailto:medizin@example.test">medizin@example.test</a>
    <a href="https://other.test/kardiologie">Onkologie</a>
    """
    mentions = menu_mentions("https://example.test/", html)
    assert [(item.predicate, item.object_value) for item in mentions] == [("hasDepartment", "Kardiologie")]


def test_catalog_load_attaches_the_organization_and_leaves_the_site_empty(tmp_path: Path) -> None:
    body = tmp_path / "bodies"
    body.mkdir()
    checksum = "abc"
    (body / checksum).write_text(HTML, encoding="utf-8")
    manifest = {
        "https://example.test/fachgebiete": {
            "final_url": "https://example.test/fachgebiete",
            "checksum": checksum,
            "content_type": "text/html",
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    register = SourceRegister(
        rows=[
            RegisterRow(
                organization_name="Example Hospital",
                site_name=None,
                home_canton="GR",
                site_canton=None,
                url_status="found",
                url="https://example.test/",
                language="de",
                source="https://example.test/",
                note="",
            )
        ]
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = HospitalOrganization(home_canton_code="GR", reference_year=2024)
        session.add(organization)
        session.flush()
        session.add(
            OrganizationName(
                organization_id=organization.id,
                name="Example Hospital",
                name_role="source_primary",
                match_status="exact",
            )
        )
        session.commit()
        result = load_catalog_mentions(session, tmp_path, register)
        session.commit()
        assert result.pages == 1
        assert result.assertions == 2
        rows = session.scalars(select(Assertion)).all()
        assert {row.predicate for row in rows} == {"hasDepartment", "hasClinic"}
        assert all(row.organization_id == organization.id for row in rows)
        assert all(row.site_id is None for row in rows)
        assert all(row.fact_status == "candidate" for row in rows)
        ignored = uuid4()
        assert ignored not in {row.organization_id for row in rows}
