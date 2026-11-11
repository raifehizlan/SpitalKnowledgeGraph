"""The pilot graph keeps verified rows and leaves candidates out."""

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Base,
    Evidence,
    HospitalOrganization,
    HospitalSite,
    MeasureDefinition,
    OrganizationCodeSet,
    OrganizationName,
    ServiceMandate,
    SiteName,
    StatisticObservation,
)
from swiss_hospital_intelligence.knowledge_graph.network import build_network
from swiss_hospital_intelligence.knowledge_graph.project import SHI, project_pilot_graph
from swiss_hospital_intelligence.knowledge_graph.reason import inferred_has_site
from swiss_hospital_intelligence.knowledge_graph.validate import example_graph, validation_text
from swiss_hospital_intelligence.knowledge_graph.queries import (
    PRESETS,
    document_claims,
    equipment_codes,
    establishment_measure,
    establishment_statistics_about_a_site,
    home_establishments,
    require_select,
    select_rows,
    sites_in_canton,
)


def test_verified_sites_and_beds_enter_the_graph_without_candidate_clinics() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        hospital = HospitalOrganization(
            home_canton_code="GR",
            typology_code="K112",
            legal_form_code="R2",
            street="Loestrasse 170",
            postal_place="7000 Chur",
            reference_year=2024,
            verification_status="verified",
        )
        other = HospitalOrganization(home_canton_code="SG", reference_year=2024, verification_status="verified")
        session.add_all([hospital, other])
        session.flush()
        chur = HospitalSite(
            organization_id=hospital.id,
            canton_code="GR",
            street="Loestrasse 170",
            postal_place="7000 Chur",
            reference_year=2024,
        )
        walenstadt = HospitalSite(
            organization_id=hospital.id,
            canton_code="SG",
            street="Spitalstrasse 5",
            postal_place="8880 Walenstadt",
            reference_year=2024,
        )
        guest = HospitalSite(
            organization_id=other.id,
            canton_code="GR",
            postal_place="7000 Chur",
            reference_year=2024,
        )
        session.add_all([chur, walenstadt, guest])
        session.flush()
        session.add_all(
            [
                OrganizationName(
                    organization_id=hospital.id,
                    name="Kantonsspital Graubünden",
                    name_role="source_primary",
                    match_status="exact",
                ),
                OrganizationName(
                    organization_id=other.id,
                    name="Other Hospital",
                    name_role="source_primary",
                    match_status="exact",
                ),
                SiteName(site_id=chur.id, name="Kantonsspital Graubünden", name_role="source_primary"),
                SiteName(site_id=walenstadt.id, name="Spital Walenstadt", name_role="source_primary"),
                SiteName(site_id=guest.id, name="Guest Site", name_role="source_primary"),
                MeasureDefinition(
                    code="BettenStatA",
                    unit="bed_operating_average",
                    activity_type="A",
                    scope="establishment",
                    publication_status="published",
                ),
                StatisticObservation(
                    organization_id=hospital.id,
                    measure_code="BettenStatA",
                    reference_year=2024,
                    activity_type="A",
                    scope="establishment",
                    value_numeric=Decimal("343"),
                    raw_value="343",
                    value_state="value",
                    unit="bed_operating_average",
                    source_row_fingerprint="beds",
                ),
                StatisticObservation(
                    site_id=walenstadt.id,
                    measure_code="BettenStatA",
                    reference_year=2024,
                    activity_type="A",
                    scope="site",
                    value_numeric=Decimal("99"),
                    raw_value="99",
                    value_state="value",
                    unit="bed_operating_average",
                    source_row_fingerprint="site-beds",
                ),
                OrganizationCodeSet(
                    organization_id=hospital.id,
                    code_set="equipment",
                    code="MRI",
                    reference_year=2024,
                ),
                ServiceMandate(
                    organization_id=hospital.id,
                    list_kind="akutsomatik",
                    edition="April 2026",
                    canton_scope="in_canton",
                    source_name="Kantonsspital Graubünden, Chur",
                    code="KAR1",
                    label="Kardiologie",
                    match_status="exact",
                    source_row_fingerprint="kar",
                ),
            ]
        )
        evidence = Evidence(excerpt="Chirurgie", extraction_method="catalog_link")
        session.add(evidence)
        session.flush()
        session.add(
            Assertion(
                evidence_id=evidence.id,
                organization_id=hospital.id,
                predicate="hasDepartment",
                object_value="Chirurgie",
                fact_status="candidate",
                assertion_mode="extracted",
            )
        )
        session.commit()
        graph = project_pilot_graph(session)

    assert home_establishments(graph) == ["Kantonsspital Graubünden"]
    assert ("Spital Walenstadt", "Kantonsspital Graubünden", "GR") in sites_in_canton(graph, "SG")
    assert ("Guest Site", "Other Hospital", "SG") in sites_in_canton(graph)
    assert ("Kantonsspital Graubünden", "Kantonsspital Graubünden", "GR") in sites_in_canton(graph)
    assert establishment_measure(graph, "Kantonsspital Graubünden", "BettenStatA") == ["343"]
    assert establishment_measure(graph, "Other Hospital", "BettenStatA") == []
    assert establishment_statistics_about_a_site(graph) == 0
    assert equipment_codes(graph, "Kantonsspital Graubünden") == ["MRI"]
    assert ("Department", "Chirurgie", "candidate") in document_claims(graph, "Kantonsspital Graubünden")
    assert ("Department", "Chirurgie", "verified") not in document_claims(graph, "Kantonsspital Graubünden")
    nodes, edges = build_network(graph)
    org = next(node["id"] for node in nodes if node["group"] == "establishment" and node["label"] == "Kantonsspital Graubünden")
    walenstadt = next(node["id"] for node in nodes if node["group"] == "site" and node["label"] == "Spital Walenstadt")
    chirurgie = next(node["id"] for node in nodes if node["group"] == "Department" and node["label"] == "Chirurgie")
    mri = next(node["id"] for node in nodes if node["group"] == "equipment" and node["label"] == "MRI")
    site_edge = next(edge for edge in edges if edge["from"] == org and edge["to"] == walenstadt and edge["label"] == "site")
    assert site_edge["title"] == "Spital Walenstadt is a site of Kantonsspital Graubünden."
    department_edge = next(edge for edge in edges if edge["from"] == org and edge["to"] == chirurgie and edge["label"] == "department")
    assert department_edge["title"] == "Kantonsspital Graubünden has a department claim named Chirurgie. Status: candidate."
    assert any(edge["from"] == org and edge["to"] == mri and edge["label"] == "equipment" for edge in edges)
    assert all(node["label"] != "Kardiologie" for node in nodes)
    focused, _focused_edges = build_network(graph, organization="Kantonsspital Graubünden")
    assert any(node["label"] == "Guest Site" for node in nodes)
    assert all(node["label"] != "Guest Site" for node in focused)
    inferred = {node["label"] for node in nodes if node["group"] == "inferred"}
    assert inferred == {"Spital Walenstadt", "Guest Site"}
    turtle = graph.serialize(format="turtle")
    assert "Kardiologie" not in turtle
    assert '"99"' not in turtle
    equipment = _preset("Equipment codes of GR establishments")
    _header, equipment_rows = select_rows(graph, equipment)
    assert ["Kantonsspital Graubünden", "MRI"] in equipment_rows
    guests = _preset("Sites in GR run from another canton")
    _header, guest_rows = select_rows(graph, guests)
    assert ["Guest Site", "Other Hospital", "SG"] in guest_rows
    accepted = _preset("Accepted claims per establishment")
    accepted_header, accepted_rows = select_rows(graph, accepted)
    assert accepted_header == ["establishment", "accepted"]
    assert accepted_rows == []
    conforms, report = validation_text(graph)
    assert conforms, report
    assert any(graph.triples((None, SHI.derivedFrom, None)))
    assert not any(graph.triples((None, SHI.hasSite, None)))


def test_the_example_conforms_and_hermit_infers_the_inverse() -> None:
    conforms, report = validation_text(example_graph())
    assert conforms, report
    assert inferred_has_site() == [
        ("Kantonsspital Graubünden", "Kantonsspital Graubünden"),
        ("Kantonsspital Graubünden", "Spital Walenstadt"),
    ]


def test_the_query_box_runs_a_select() -> None:
    require_select("SELECT ?name WHERE { ?s ?p ?name }")
    try:
        require_select("ASK { ?s ?p ?o }")
    except ValueError as exc:
        assert "SELECT" in str(exc)
    else:
        raise AssertionError("ASK was accepted")


def _preset(title: str) -> str:
    return next(query for name, query in PRESETS if name == title)
