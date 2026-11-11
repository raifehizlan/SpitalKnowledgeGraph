"""Parse the draft ontology and check the Kantonsspital Graubünden example.

The checks mirror ontology/shapes/core.shacl.ttl. pySHACL runs the shapes themselves.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import Namespace

ROOT = Path(__file__).resolve().parents[1]
SHI = Namespace("https://example.org/shi/ontology/")


def load() -> Graph:
    graph = Graph()
    for relative in (
        "ontology/swiss_hospital_ontology.ttl",
        "ontology/shapes/core.shacl.ttl",
        "ontology/examples/ksgr-2024.ttl",
    ):
        graph.parse(ROOT / relative, format="turtle")
    return graph


def ask(graph: Graph, query: str) -> bool:
    return bool(graph.query(query).askAnswer)


def main() -> None:
    graph = load()
    checks: list[tuple[str, str, bool]] = [
        (
            "KSGR has two sites",
            """
            ASK {
              ?org a shi:HospitalOrganization ;
                   shi:officialName "Kantonsspital Graubünden" .
              { SELECT ?org (COUNT(?site) AS ?n) WHERE {
                  ?site a shi:HospitalSite ; shi:siteOf ?org .
                } GROUP BY ?org }
              FILTER (?n = 2)
            }
            """,
            True,
        ),
        (
            "Walenstadt is in SG and the organization home canton is GR",
            """
            ASK {
              ?org shi:officialName "Kantonsspital Graubünden" ;
                   shi:homeCanton ?home .
              ?home shi:cantonCode "GR" .
              ?site shi:officialName "Spital Walenstadt" ;
                    shi:siteOf ?org ;
                    shi:siteCanton ?site_canton .
              ?site_canton shi:cantonCode "SG" .
            }
            """,
            True,
        ),
        (
            "Acute beds are about the organization and about no site",
            """
            ASK {
              ?stat shi:measure ?measure ;
                    shi:aboutOrganization ?org ;
                    shi:statisticalScope "establishment" ;
                    shi:valueNumeric 343 .
              ?measure shi:measureCode "BettenStatA" .
              FILTER NOT EXISTS { ?stat shi:aboutSite ?site }
            }
            """,
            True,
        ),
        (
            "MRI presence is not a medical device",
            """
            ASK {
              ?presence a shi:EquipmentPresence ;
                        shi:presenceOf ?code .
              ?code skos:notation "MRI" .
              FILTER NOT EXISTS { ?presence a shi:MedicalDevice }
            }
            """,
            True,
        ),
        (
            "Every site has exactly one parent",
            """
            ASK {
              FILTER NOT EXISTS {
                ?site a shi:HospitalSite .
                { SELECT ?site (COUNT(?org) AS ?n) WHERE {
                    ?site shi:siteOf ?org .
                  } GROUP BY ?site }
                FILTER (?n != 1)
              }
            }
            """,
            True,
        ),
        (
            "No establishment statistic points at a site",
            """
            ASK {
              FILTER NOT EXISTS {
                ?stat shi:statisticalScope "establishment" ;
                      shi:aboutSite ?site .
              }
            }
            """,
            True,
        ),
    ]
    failed = 0
    for name, query, expected in checks:
        query = "PREFIX shi: <https://example.org/shi/ontology/>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n" + query
        actual = ask(graph, query)
        status = "ok" if actual is expected else "FAILED"
        if actual is not expected:
            failed += 1
        print(f"{status}: {name}")
    print(f"triples: {len(graph)}")
    if failed:
        raise SystemExit(f"{failed} check(s) failed")


if __name__ == "__main__":
    main()
