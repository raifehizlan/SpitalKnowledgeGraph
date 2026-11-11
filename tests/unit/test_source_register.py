"""A recorded website attaches only to the named establishment or site."""

from __future__ import annotations

from swiss_hospital_intelligence.ingestion.documents.source_register import (
    WebsiteRecord,
    build_source_register,
)
from swiss_hospital_intelligence.ingestion.structured.records import (
    KeyFigureParse,
    ParsedEstablishment,
    ParsedSite,
)


def test_a_missing_website_stays_not_found_and_is_not_copied_from_the_parent() -> None:
    parsed = KeyFigureParse(
        establishments=[
            ParsedEstablishment(
                reference_year=2024,
                home_canton="GR",
                name="Example Hospital",
                street=None,
                postal_place=None,
                typology_code=None,
                legal_form_code=None,
                reported_site_count=2,
            )
        ],
        sites=[
            ParsedSite(
                reference_year=2024,
                parent_name="Example Hospital",
                parent_home_canton="GR",
                name="Example Main",
                street=None,
                postal_place=None,
                canton_code="GR",
                reported_site_count=None,
            ),
            ParsedSite(
                reference_year=2024,
                parent_name="Example Hospital",
                parent_home_canton="GR",
                name="Example Other",
                street=None,
                postal_place=None,
                canton_code="SG",
                reported_site_count=None,
            ),
        ],
        excluded_national_rows=0,
    )
    register = build_source_register(
        parsed,
        [
            WebsiteRecord(
                organization_name="Example Hospital",
                url="https://example.test/",
                language="de",
                source="https://example.test/",
                note="Fictional.",
            )
        ],
    )
    by_site = {row.site_name: row for row in register.rows}
    assert by_site[None].url_status == "found"
    assert by_site[None].url == "https://example.test/"
    assert by_site["Example Main"].url_status == "not_found"
    assert by_site["Example Main"].url is None
    assert by_site["Example Other"].site_canton == "SG"
    assert register.annual_reports == "not_reviewed"
