"""A near-miss cantonal name stays in manual review."""

from __future__ import annotations

from decimal import Decimal

from swiss_hospital_intelligence.ingestion.structured.qip import QualityParse, QualityRow
from swiss_hospital_intelligence.ingestion.structured.records import (
    KeyFigureParse,
    MeasureObservation,
    ParsedEstablishment,
    ParsedSite,
)
from swiss_hospital_intelligence.reports.reviewed_aliases import ReviewedAlias
from swiss_hospital_intelligence.reports.structured_quality import (
    ReportSource,
    SiteLine,
    build_structured_quality_report,
    render_structured_quality_report,
)


def _report():
    key_figures = KeyFigureParse(
        establishments=[
            ParsedEstablishment(
                reference_year=2024,
                home_canton="GR",
                name="Example Hospital AG",
                street="Example Street 1",
                postal_place="7000 Example",
                typology_code="K122",
                legal_form_code="R1",
                equipment=["MRI"],
                reported_site_count=1,
                measures=[
                    MeasureObservation(
                        code="BettenStatA",
                        unit="bed_operating_average",
                        activity_type="A",
                        value_numeric=Decimal("32.95"),
                        raw_value="32.95",
                        value_state="value",
                    )
                ],
            ),
            ParsedEstablishment(
                reference_year=2024,
                home_canton="ZH",
                name="Other Hospital",
                street=None,
                postal_place="8000 Example",
                typology_code=None,
                legal_form_code=None,
                reported_site_count=None,
            ),
        ],
        sites=[
            ParsedSite(
                reference_year=2024,
                parent_name="Example Hospital AG",
                parent_home_canton="GR",
                name="Example Walenstadt",
                street=None,
                postal_place="8880 Example",
                canton_code="SG",
                reported_site_count=None,
            )
        ],
        excluded_national_rows=1,
    )
    quality = QualityParse(
        rows=[
            QualityRow(
                line_number=2,
                institution="Example Hospital AG",
                indicator="A.1.1.M Example",
                indicator_code="A.1.1.M",
                row_kind="measure",
            )
        ],
        failures=[],
        header_count=1,
    )
    return build_structured_quality_report(
        key_figures,
        ["Example Hospital AG", "Example Hospital", "Example Hospital Annex"],
        quality=quality,
        sources=[ReportSource(role="synthetic", filename="synthetic.xlsx", note="Fictional names.")],
        reviewed_aliases=[
            ReviewedAlias(
                source_name="Example Hospital",
                organization_name="Example Hospital AG",
                evidence="Fictional review for the unit test.",
            )
        ],
    )


def test_near_miss_stays_in_manual_review_and_beds_stay_on_the_establishment() -> None:
    report = _report()
    assert report.organization_count == 2
    assert report.excluded_national_rows == 1
    assert report.graubuenden_home_canton_count == 1
    assert report.manual_review_names == ["Example Hospital Annex"]
    exact = [item for item in report.cantonal_names if item.match_status == "exact"]
    reviewed = [item for item in report.cantonal_names if item.match_status == "reviewed"]
    assert len(exact) == 1
    assert exact[0].organization_name == "Example Hospital AG"
    assert exact[0].method == "exact_normalized_name_2024"
    assert len(reviewed) == 1
    assert reviewed[0].source_name == "Example Hospital"
    assert reviewed[0].organization_name == "Example Hospital AG"
    assert reviewed[0].method == "reviewed_same_establishment"
    row = report.establishments[0]
    assert row.acute_beds == Decimal("32.95")
    assert row.acute_beds_unit == "bed_operating_average"
    assert row.equipment == ["MRI"]
    assert row.quality_file == "present"
    assert row.sites[0].canton_code == "SG"
    assert "acute_beds" not in SiteLine.model_fields
    text = render_structured_quality_report(report)
    assert "manual_review: Example Hospital Annex" in text
    assert "Example Walenstadt [SG]" in text
    assert "32.95 bed_operating_average" in text


def test_a_missing_quality_file_is_not_absence() -> None:
    key_figures = KeyFigureParse(
        establishments=[
            ParsedEstablishment(
                reference_year=2024,
                home_canton="GR",
                name="Example Hospital AG",
                street=None,
                postal_place=None,
                typology_code=None,
                legal_form_code=None,
                reported_site_count=None,
            )
        ],
        sites=[],
        excluded_national_rows=0,
    )
    closed = build_structured_quality_report(key_figures, [], quality=None, sources=[])
    assert closed.quality_institution_count is None
    assert closed.quality_failures == []
    assert closed.establishments[0].quality_file == "source_not_opened"
