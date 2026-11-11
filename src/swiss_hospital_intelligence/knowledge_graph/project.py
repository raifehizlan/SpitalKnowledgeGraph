"""Project the Graubünden pilot.

Verified BAG rows become establishments, sites, statistics, and equipment
presence. A document extraction becomes an assertion with its fact status.
A Leistungsauftrag is not written here. Inverse properties are not materialized.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD
from sqlalchemy import false, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import (
    Assertion,
    Evidence,
    HospitalOrganization,
    HospitalSite,
    MeasureDefinition,
    OrganizationCodeSet,
    OrganizationName,
    SiteName,
    SourceFile,
    StatisticObservation,
)

SHI = Namespace("https://example.org/shi/ontology/")
SHIC = Namespace("https://example.org/shi/concept/")
SHID = Namespace("https://example.org/shi/data/")
METHOD = "official_structured_parse"
HOME_CANTON = "GR"
CLAIM_TYPE = {
    "hasDepartment": SHI.Department,
    "hasClinic": SHI.Clinic,
    "hasService": SHI.MedicalService,
    "offersTreatment": SHI.Treatment,
    "mentionsEquipment": SHI.MedicalDevice,
    "hasEvent": SHI.Event,
    "cooperatesWith": SHI.Cooperation,
}
CLAIM_LINK = {
    "hasDepartment": SHI.hasDepartment,
    "hasClinic": SHI.hasClinic,
    "hasService": SHI.providesService,
    "offersTreatment": SHI.offersTreatment,
    "mentionsEquipment": SHI.usesDevice,
}


def project_pilot_graph(session: Session) -> Graph:
    graph = Graph()
    graph.bind("shi", SHI)
    graph.bind("shic", SHIC)
    graph.bind("shid", SHID)
    graph.bind("skos", SKOS)

    organizations = list(
        session.scalars(
            select(HospitalOrganization).where(HospitalOrganization.home_canton_code == HOME_CANTON)
        )
    )
    home_ids = {item.id for item in organizations}
    canton_sites = list(
        session.scalars(select(HospitalSite).where(HospitalSite.canton_code == HOME_CANTON))
    )
    extra_ids = {site.organization_id for site in canton_sites} - home_ids
    if extra_ids:
        organizations.extend(
            session.scalars(select(HospitalOrganization).where(HospitalOrganization.id.in_(extra_ids)))
        )
    included_ids = {item.id for item in organizations}
    sites = list(
        session.scalars(select(HospitalSite).where(_in(HospitalSite.organization_id, home_ids)))
    )
    sites.extend(site for site in canton_sites if site.id not in {item.id for item in sites})
    statistics = list(
        session.scalars(
            select(StatisticObservation).where(
                _in(StatisticObservation.organization_id, home_ids),
                StatisticObservation.scope == "establishment",
            )
        )
    )
    equipment = list(
        session.scalars(
            select(OrganizationCodeSet).where(
                _in(OrganizationCodeSet.organization_id, home_ids),
                OrganizationCodeSet.code_set == "equipment",
            )
        )
    )
    org_names = _one_name(
        session.execute(
            select(OrganizationName.organization_id, OrganizationName.name, OrganizationName.match_status).where(
                _in(OrganizationName.organization_id, included_ids),
                OrganizationName.name_role == "source_primary",
            )
        ).all()
    )
    site_names = _one_name(
        session.execute(
            select(SiteName.site_id, SiteName.name, SiteName.name_role).where(
                _in(SiteName.site_id, {site.id for site in sites}),
                SiteName.name_role == "source_primary",
            )
        ).all()
    )
    measures = {
        item.code: item
        for item in session.scalars(
            select(MeasureDefinition).where(_in(MeasureDefinition.code, {row.measure_code for row in statistics}))
        )
    }
    filenames = {
        item.id: item.filename
        for item in session.scalars(
            select(SourceFile).where(
                SourceFile.id.in_(
                    {
                        row.source_file_id
                        for row in (*statistics, *equipment, *organizations)
                        if getattr(row, "source_file_id", None)
                    }
                )
            )
        )
    } if any(getattr(row, "source_file_id", None) for row in (*statistics, *equipment)) else {}

    for code in {item.home_canton_code for item in organizations} | {site.canton_code for site in sites}:
        _canton(graph, code)
    for organization in organizations:
        _organization(graph, organization, org_names.get(organization.id))
    for site in sites:
        _site(graph, site, site_names.get(site.id))
    for row in statistics:
        _statistic(graph, row, measures.get(row.measure_code), filenames.get(row.source_file_id))
    for row in equipment:
        _equipment(graph, row, filenames.get(row.source_file_id))
    _project_claims(session, graph, home_ids, {site.id for site in sites})
    _project_outside_sites(graph, organizations, sites, site_names)
    return graph


def _in(column, values: set) -> object:
    if not values:
        return false()
    return column.in_(values)


def _one_name(rows: list[tuple]) -> dict[UUID, tuple[str, str]]:
    grouped: dict[UUID, list[tuple[str, str]]] = {}
    for entity_id, name, status in rows:
        grouped.setdefault(entity_id, []).append((name, status))
    return {entity_id: sorted(values)[0] for entity_id, values in grouped.items()}


def _canton(graph: Graph, code: str) -> None:
    node = SHID[f"canton-{code}"]
    graph.add((node, RDF.type, SHI.Canton))
    graph.add((node, SHI.cantonCode, _string(code)))


def _organization(graph: Graph, organization: HospitalOrganization, name: tuple[str, str] | None) -> None:
    node = SHID[f"org-{organization.id}"]
    graph.add((node, RDF.type, SHI.HospitalOrganization))
    if name is not None:
        graph.add((node, SHI.officialName, _string(name[0])))
        graph.add((node, SHI.matchStatus, _string(name[1])))
    graph.add((node, SHI.homeCanton, SHID[f"canton-{organization.home_canton_code}"]))
    graph.add((node, SHI.referenceYear, _year(organization.reference_year)))
    graph.add((node, SHI.factStatus, _string(organization.verification_status)))
    graph.add((node, SHI.extractionMethod, _string(METHOD)))
    _optional(graph, node, SHI.postalStreet, organization.street)
    _optional(graph, node, SHI.postalPlace, organization.postal_place)
    if organization.typology_code:
        graph.add((node, SHI.typology, SHIC[f"typology-{organization.typology_code}"]))
    if organization.legal_form_code:
        graph.add((node, SHI.legalForm, SHIC[f"legalform-{organization.legal_form_code}"]))


def _site(graph: Graph, site: HospitalSite, name: tuple[str, str] | None) -> None:
    node = SHID[f"site-{site.id}"]
    graph.add((node, RDF.type, SHI.HospitalSite))
    graph.add((node, SHI.siteOf, SHID[f"org-{site.organization_id}"]))
    graph.add((node, SHI.siteCanton, SHID[f"canton-{site.canton_code}"]))
    graph.add((node, SHI.referenceYear, _year(site.reference_year)))
    graph.add((node, SHI.factStatus, _string("verified")))
    graph.add((node, SHI.extractionMethod, _string(METHOD)))
    if name is not None:
        graph.add((node, SHI.officialName, _string(name[0])))
    _optional(graph, node, SHI.postalStreet, site.street)
    _optional(graph, node, SHI.postalPlace, site.postal_place)
    evidence = _evidence(
        graph,
        f"site-{site.id}",
        f"KT_Standort={site.canton_code}; name={name[0] if name else ''}",
        None,
    )
    graph.add((node, SHI.supportedBy, evidence))


def _statistic(
    graph: Graph,
    row: StatisticObservation,
    measure: MeasureDefinition | None,
    filename: str | None,
) -> None:
    node = SHID[f"stat-{row.id}"]
    measure_node = SHID[f"measure-{row.measure_code}"]
    graph.add((measure_node, RDF.type, SHI.MeasureDefinition))
    graph.add((measure_node, SHI.measureCode, _string(row.measure_code)))
    if measure is not None:
        graph.add((measure_node, SHI.unit, _string(measure.unit)))
        graph.add((measure_node, SHI.statisticalScope, _string(measure.scope)))
        graph.add((measure_node, SHI.publicationStatus, _string(measure.publication_status)))
    graph.add((node, RDF.type, SHI.StatisticObservation))
    graph.add((node, SHI.aboutOrganization, SHID[f"org-{row.organization_id}"]))
    graph.add((node, SHI.measure, measure_node))
    graph.add((node, SHI.statisticalScope, _string(row.scope)))
    graph.add((node, SHI.referenceYear, _year(row.reference_year)))
    graph.add((node, SHI.valueState, _string(row.value_state)))
    graph.add((node, SHI.unit, _string(row.unit)))
    graph.add((node, SHI.factStatus, _string("verified")))
    graph.add((node, SHI.extractionMethod, _string(METHOD)))
    if row.value_numeric is not None:
        graph.add((node, SHI.valueNumeric, _decimal(row.value_numeric)))
    if row.raw_value is not None:
        graph.add((node, SHI.rawValue, _string(row.raw_value)))
    if row.activity_type:
        graph.add((node, SHI.activityType, SHIC[f"activity-{row.activity_type}"]))
    evidence = _evidence(
        graph,
        f"stat-{row.id}",
        f"{row.measure_code}={row.raw_value or ''}; scope={row.scope}",
        filename,
    )
    graph.add((node, SHI.supportedBy, evidence))


def _equipment(graph: Graph, row: OrganizationCodeSet, filename: str | None) -> None:
    node = SHID[f"equip-{row.id}"]
    concept = SHIC[f"equipment-{row.code}"]
    graph.add((concept, RDF.type, SHI.EquipmentConcept))
    graph.add((concept, SKOS.notation, _string(row.code)))
    graph.add((node, RDF.type, SHI.EquipmentPresence))
    graph.add((node, SHI.recordedFor, SHID[f"org-{row.organization_id}"]))
    graph.add((node, SHI.presenceOf, concept))
    graph.add((node, SHI.codeSet, _string(row.code_set)))
    graph.add((node, SHI.referenceYear, _year(row.reference_year)))
    graph.add((node, SHI.factStatus, _string("verified")))
    graph.add((node, SHI.extractionMethod, _string(METHOD)))
    evidence = _evidence(graph, f"equip-{row.id}", f"SA={row.code}", filename)
    graph.add((node, SHI.supportedBy, evidence))


def _project_claims(session: Session, graph: Graph, organization_ids: set[UUID], site_ids: set[UUID]) -> None:
    rows = session.execute(
        select(Assertion, Evidence)
        .join(Evidence, Evidence.id == Assertion.evidence_id)
        .where(_in(Assertion.organization_id, organization_ids))
    ).all()
    for assertion, evidence in rows:
        if not assertion.object_value or not assertion.object_value.strip():
            continue
        if assertion.organization_id is None:
            continue
        node = SHID[f"assertion-{assertion.id}"]
        graph.add((node, RDF.type, SHI.Assertion))
        kind = CLAIM_TYPE.get(assertion.predicate)
        if kind is not None and kind != SHI.Assertion:
            graph.add((node, RDF.type, kind))
        graph.add((node, SHI.officialName, _string(assertion.object_value.strip())))
        graph.add((node, SHI.factStatus, _string(assertion.fact_status)))
        graph.add((node, SHI.assertionMode, _string(assertion.assertion_mode)))
        graph.add((node, SHI.extractionMethod, _string(evidence.extraction_method)))
        proof = _passage(graph, assertion.id, evidence)
        graph.add((node, SHI.supportedBy, proof))
        organization = SHID[f"org-{assertion.organization_id}"]
        graph.add((organization, SHI.asserts, node))
        link = CLAIM_LINK.get(assertion.predicate)
        if link is not None:
            graph.add((organization, link, node))
        elif assertion.predicate == "cooperatesWith":
            graph.add((node, SHI.cooperatesWith, organization))
        if assertion.predicate == "hasDepartment" and assertion.site_id in site_ids:
            graph.add((node, SHI.departmentAtSite, SHID[f"site-{assertion.site_id}"]))


def _project_outside_sites(
    graph: Graph,
    organizations: list[HospitalOrganization],
    sites: list[HospitalSite],
    site_names: dict[UUID, tuple[str, str]],
) -> None:
    home = {item.id: item.home_canton_code for item in organizations}
    for site in sites:
        if site.canton_code == home.get(site.organization_id):
            continue
        name = site_names[site.id][0] if site.id in site_names else site.canton_code
        node = SHID[f"inference-outside-{site.id}"]
        graph.add((node, RDF.type, SHI.Assertion))
        graph.add((node, SHI.officialName, _string(name)))
        graph.add((node, SHI.factStatus, _string("verified")))
        graph.add((node, SHI.assertionMode, _string("inferred")))
        graph.add((node, SHI.extractionMethod, _string("site_canton_differs_from_home")))
        evidence = SHID[f"evidence-site-{site.id}"]
        premise = SHID[f"premise-site-canton-{site.id}"]
        graph.add((premise, RDF.type, SHI.Assertion))
        graph.add((premise, SHI.officialName, _string(f"site canton {site.canton_code}")))
        graph.add((premise, SHI.factStatus, _string("verified")))
        graph.add((premise, SHI.assertionMode, _string("documented")))
        graph.add((premise, SHI.extractionMethod, _string(METHOD)))
        graph.add((premise, SHI.supportedBy, evidence))
        graph.add((node, SHI.supportedBy, evidence))
        graph.add((node, SHI.derivedFrom, premise))
        graph.add((SHID[f"org-{site.organization_id}"], SHI.asserts, node))


def _passage(graph: Graph, assertion_id: UUID, evidence: Evidence) -> URIRef:
    node = SHID[f"evidence-assertion-{assertion_id}"]
    graph.add((node, RDF.type, SHI.Evidence))
    graph.add((node, SHI.excerpt, _string(evidence.excerpt)))
    graph.add((node, SHI.extractionMethod, _string(evidence.extraction_method)))
    if evidence.source_url:
        graph.add((node, SHI.documentedIn, _string(evidence.source_url)))
    return node


def _evidence(graph: Graph, local: str, excerpt: str, filename: str | None) -> URIRef:
    node = SHID[f"evidence-{local}"]
    graph.add((node, RDF.type, SHI.Evidence))
    graph.add((node, SHI.excerpt, _string(excerpt)))
    graph.add((node, SHI.extractionMethod, _string(METHOD)))
    if filename:
        source = SHID["source-bag-kzp-2024"]
        graph.add((source, RDF.type, SHI.Source))
        graph.add((source, SHI.sourceFileName, _string(filename)))
        graph.add((node, SHI.evidenceIn, source))
        graph.add((node, SHI.sourceFileName, _string(filename)))
    return node


def _optional(graph: Graph, node: URIRef, predicate: URIRef, value: str | None) -> None:
    if value:
        graph.add((node, predicate, _string(value)))


def _string(value: str) -> Literal:
    return Literal(value, datatype=XSD.string)


def _year(value: int) -> Literal:
    return Literal(str(value), datatype=XSD.gYear)


def _decimal(value: Decimal) -> Literal:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return Literal(text, datatype=XSD.decimal)
