"""Graubünden screen: verified graph, Spitalliste departments, candidate page claims."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.knowledge_graph.accept import accept_corroborated_claims
from swiss_hospital_intelligence.knowledge_graph.network import CLAIM_EDGE, build_network, network_html
from swiss_hospital_intelligence.knowledge_graph.project import project_pilot_graph
from swiss_hospital_intelligence.knowledge_graph.queries import (
    PRESETS,
    claim_count,
    document_claims,
    equipment_codes,
    establishment_measure,
    home_establishments,
    require_select,
    select_rows,
    sites_in_canton,
)
from swiss_hospital_intelligence.reports.gr_offer import load_gr_offer

PILOT_DB = ROOT / "data" / "pilot.sqlite"
DATABASE_URL = f"sqlite:///{PILOT_DB.resolve().as_posix()}"


@st.cache_resource
def _load():
    if not PILOT_DB.is_file():
        raise FileNotFoundError("data/pilot.sqlite is missing.")
    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        changed = accept_corroborated_claims(session)
        if changed:
            session.commit()
        else:
            session.rollback()
        graph = project_pilot_graph(session)
        offers = {item.organization_name: item for item in load_gr_offer(session)}
    return graph, offers


def main() -> None:
    st.set_page_config(page_title="Swiss Hospital Intelligence", layout="wide")
    try:
        graph, offers = _load()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return
    names = home_establishments(graph)
    st.title("Swiss Hospital Intelligence")
    st.caption(
        "Graubünden pilot. Verified BAG rows and document claims are both in the graph. "
        "Department names come from the three Spitalliste PDFs: the first column of the acute list, "
        "and the service line under Leistungsauftrag in the psychiatry and rehabilitation lists. "
        "A billing code stays beside the graph. "
        "The same graph is written as Turtle and JSON-LD by "
        "`python -m swiss_hospital_intelligence.knowledge_graph`."
    )
    left, middle = st.columns(2)
    left.metric("Establishments in the graph", len(names))
    middle.metric(
        "Candidate and verified claims",
        claim_count(graph, "candidate") + claim_count(graph, "verified"),
    )

    scope = st.radio("Graph", ["Whole pilot", "Selected establishment"], horizontal=True, index=0)
    selected = st.selectbox("Establishment", names)
    picture = st.radio(
        "Claims in the picture",
        ["Official departments", "All extracted claims"],
        horizontal=True,
        index=1,
    )
    hidden_kinds = {"inferred", "Event", "Assertion"}
    document_kinds = [kind for kind in CLAIM_EDGE if kind not in hidden_kinds]
    kinds = st.multiselect("Document relationships", document_kinds, default=["Department", "Clinic"])
    nodes, edges = build_network(
        graph,
        organization=None if scope == "Whole pilot" else selected,
        kinds=set(kinds),
        statuses={"verified", "accepted"} if picture == "Official departments" else None,
    )
    st.caption(
        f"{len(nodes)} nodes, {len(edges)} links. "
        "An official department is a name from one of the three Spitalliste PDFs. "
        "Whole pilot joins the hospitals that share that name. "
        "A gold node is a site whose canton differs from the home canton. "
        "Click a node to list every link that touches it. Click a line to read that one link."
    )
    components.html(network_html(nodes, edges), height=780)
    st.subheader("SPARQL")
    st.caption("shi: and skos: are already declared. A name comparison belongs in FILTER.")
    query_mode = st.radio("Query", ["Prepared", "Your query"], horizontal=True)
    if query_mode == "Prepared":
        choice = st.selectbox("Prepared question", [title for title, _query in PRESETS])
        _title, query = next(item for item in PRESETS if item[0] == choice)
        st.code(query.strip(), language="sparql")
        _show_rows(graph, query)
    else:
        with st.form("sparql_query"):
            custom = st.text_area(
                "SELECT",
                height=180,
                placeholder='SELECT ?establishment WHERE {\n  ?org shi:officialName ?establishment .\n}',
            )
            submitted = st.form_submit_button("Run")
        if submitted:
            try:
                require_select(custom)
            except ValueError as exc:
                st.error(str(exc))
            else:
                _show_rows(graph, custom)
    offer = offers.get(selected)
    sites = [
        (site, home)
        for site, organization, home in sites_in_canton(graph)
        if organization == selected
    ]
    foreign_sites = _foreign_sites(graph, selected)
    beds = establishment_measure(graph, selected, "BettenStatA")
    equipment = equipment_codes(graph, selected)

    st.subheader(selected)
    fact, mandate, clinic = st.columns(3)
    with fact:
        st.markdown("**Verified graph**")
        st.write(f"Acute operating beds: {beds[0] if beds else 'not published'}")
        st.write("Sites in GR: " + (", ".join(site for site, _home in sites) or "none"))
        if foreign_sites:
            st.write(
                "Sites outside the home canton: "
                + ", ".join(f"{name} ({canton})" for name, canton in foreign_sites)
            )
        st.write("Equipment presence: " + (", ".join(equipment) or "none published"))
    with mandate:
        st.markdown("**Spitalliste mandate**")
        st.caption("Official billing mandate. This is not a department triple.")
        parents = offer.parents() if offer else []
        if parents:
            st.dataframe(
                [{"list": item.list_kind, "code": item.code or "", "label": item.label} for item in parents],
                hide_index=True,
            )
        else:
            st.write("No linked parent mandate.")
    with clinic:
        st.markdown("**Document claims**")
        st.caption(
            "Official departments from the three Spitalliste PDFs, and claims from saved pages. "
            "Each row keeps its fact status."
        )
        claims = document_claims(graph, selected)
        st.write(f"{len(claims)} claims")
        if claims:
            st.dataframe(
                [{"kind": kind, "name": name, "status": status} for kind, name, status in claims],
                hide_index=True,
            )


def _show_rows(graph, query: str) -> None:
    try:
        header, body = select_rows(graph, query)
    except Exception as exc:
        st.error(str(exc))
        return
    if len(body) > 200:
        st.caption(f"Showing the first 200 of {len(body)} rows.")
        body = body[:200]
    if body:
        st.dataframe([{column: value for column, value in zip(header, row)} for row in body], hide_index=True)
    else:
        st.write("The query returned no rows.")


def _foreign_sites(graph, organization: str) -> list[tuple[str, str]]:
    from rdflib import Literal
    from rdflib.namespace import XSD

    rows = graph.query(
        """
        PREFIX shi: <https://example.org/shi/ontology/>
        SELECT ?site_name ?canton WHERE {
          ?org shi:officialName ?org_name ;
               shi:homeCanton ?home .
          ?home shi:cantonCode ?home_code .
          ?site shi:siteOf ?org ;
                shi:officialName ?site_name ;
                shi:siteCanton ?site_canton .
          ?site_canton shi:cantonCode ?canton .
          FILTER (?org_name = ?wanted && ?canton != ?home_code)
        }
        ORDER BY ?site_name
        """,
        initBindings={"wanted": Literal(organization, datatype=XSD.string)},
    )
    return [(str(item.site_name), str(item.canton)) for item in rows]


if __name__ == "__main__":
    main()
else:
    main()
