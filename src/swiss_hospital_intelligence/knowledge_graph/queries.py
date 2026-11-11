"""Questions the pilot graph is required to answer.

Each query reads the stored property direction. A site statistic is a
different question from an establishment statistic.
"""

from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import XSD

_PREFIXES = """
PREFIX shi: <https://example.org/shi/ontology/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


def home_establishments(graph: Graph, canton: str = "GR") -> list[str]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?name WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?name ;
               shi:homeCanton ?canton .
          ?canton shi:cantonCode ?code .
          FILTER (?code = ?wanted)
        }
        ORDER BY ?name
        """,
        initBindings={"wanted": _string(canton)},
    )
    return [str(row.name) for row in rows]


def sites_in_canton(graph: Graph, canton: str = "GR") -> list[tuple[str, str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?site_name ?org_name ?home WHERE {
          ?site a shi:HospitalSite ;
                shi:officialName ?site_name ;
                shi:siteOf ?org ;
                shi:siteCanton ?site_canton .
          ?site_canton shi:cantonCode ?site_code .
          ?org shi:officialName ?org_name ;
               shi:homeCanton ?home_canton .
          ?home_canton shi:cantonCode ?home .
          FILTER (?site_code = ?wanted)
        }
        ORDER BY ?site_name
        """,
        initBindings={"wanted": _string(canton)},
    )
    return [(str(row.site_name), str(row.org_name), str(row.home)) for row in rows]


def establishment_measure(graph: Graph, organization: str, measure: str) -> list[str]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?value WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?name .
          ?stat shi:aboutOrganization ?org ;
                shi:measure ?measure ;
                shi:statisticalScope ?scope ;
                shi:valueNumeric ?value .
          ?measure shi:measureCode ?code .
          FILTER (?name = ?wanted_name && ?code = ?wanted_code && ?scope = "establishment")
          FILTER NOT EXISTS { ?stat shi:aboutSite ?site }
        }
        """,
        initBindings={"wanted_name": _string(organization), "wanted_code": _string(measure)},
    )
    return [str(row.value) for row in rows]


def equipment_codes(graph: Graph, organization: str) -> list[str]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?code WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?name .
          ?presence a shi:EquipmentPresence ;
                     shi:recordedFor ?org ;
                     shi:presenceOf ?concept .
          ?concept skos:notation ?code .
          FILTER (?name = ?wanted)
          FILTER NOT EXISTS { ?presence a shi:MedicalDevice }
        }
        ORDER BY ?code
        """,
        initBindings={"wanted": _string(organization)},
    )
    return [str(row.code) for row in rows]


def document_claims(graph: Graph, organization: str) -> list[tuple[str, str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?kind ?name ?status WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?org_name ;
               shi:asserts ?claim .
          ?claim shi:officialName ?name ;
                 shi:factStatus ?status ;
                 a ?kind .
          FILTER (?org_name = ?wanted && ?kind != shi:Assertion)
        }
        ORDER BY ?kind ?name
        """,
        initBindings={"wanted": _string(organization)},
    )
    found = [( _local(row.kind), str(row.name), str(row.status)) for row in rows]
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?name ?status WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?org_name ;
               shi:asserts ?claim .
          ?claim shi:officialName ?name ;
                 shi:factStatus ?status ;
                 a shi:Assertion .
          FILTER (?org_name = ?wanted)
          FILTER NOT EXISTS { ?claim a ?other . FILTER(?other != shi:Assertion) }
        }
        ORDER BY ?name
        """,
        initBindings={"wanted": _string(organization)},
    )
    found.extend(("Assertion", str(row.name), str(row.status)) for row in rows)
    return found


def claim_count(graph: Graph, status: str) -> int:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT (COUNT(?claim) AS ?n) WHERE {
          ?claim a shi:Assertion ; shi:factStatus ?status .
          FILTER (?status = ?wanted)
        }
        """,
        initBindings={"wanted": _string(status)},
    )
    return int(next(iter(rows)).n)


PRESETS: list[tuple[str, str]] = [
    (
        "Departments named Gynäkologie",
        """
        SELECT ?establishment WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?establishment ;
               shi:hasDepartment ?department .
          ?department shi:officialName ?label ; shi:factStatus ?status .
          FILTER (?label = "Gynäkologie" && (?status = "verified" || ?status = "accepted"))
        }
        ORDER BY ?establishment
        """,
    ),
    (
        "Canton of Spital Walenstadt",
        """
        SELECT ?canton WHERE {
          ?site a shi:HospitalSite ; shi:officialName ?name ; shi:siteCanton ?place .
          ?place shi:cantonCode ?canton .
          FILTER (?name = "Spital Walenstadt")
        }
        """,
    ),
    (
        "KSGR acute beds, with no site",
        """
        SELECT ?value WHERE {
          ?org a shi:HospitalOrganization ; shi:officialName ?name .
          ?stat shi:aboutOrganization ?org ;
                shi:measure ?measure ;
                shi:statisticalScope ?scope ;
                shi:valueNumeric ?value .
          ?measure shi:measureCode ?code .
          FILTER (?name = "Kantonsspital Graubünden" && ?code = "BettenStatA" && ?scope = "establishment")
          FILTER NOT EXISTS { ?stat shi:aboutSite ?site }
        }
        """,
    ),
    (
        "Sites outside the home canton",
        """
        SELECT ?establishment ?site WHERE {
          ?org shi:officialName ?establishment ; shi:asserts ?claim .
          ?claim shi:officialName ?site ;
                 shi:assertionMode ?mode ;
                 shi:extractionMethod ?method .
          FILTER (?mode = "inferred" && ?method = "site_canton_differs_from_home")
        }
        ORDER BY ?establishment ?site
        """,
    ),
    (
        "Accepted claims per establishment",
        """
        SELECT ?establishment (COUNT(?claim) AS ?accepted) WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?establishment ;
               shi:asserts ?claim .
          ?claim shi:factStatus ?status .
          FILTER (?status = "accepted")
        }
        GROUP BY ?establishment
        ORDER BY DESC(?accepted) ?establishment
        """,
    ),
    (
        "Equipment codes of GR establishments",
        """
        SELECT ?establishment ?code WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?establishment ;
               shi:homeCanton ?canton .
          ?canton shi:cantonCode ?home .
          ?presence a shi:EquipmentPresence ;
                    shi:recordedFor ?org ;
                    shi:presenceOf ?concept .
          ?concept skos:notation ?code .
          FILTER (?home = "GR")
          FILTER NOT EXISTS { ?presence a shi:MedicalDevice }
        }
        ORDER BY ?establishment ?code
        """,
    ),
    (
        "Sites in GR run from another canton",
        """
        SELECT ?site ?establishment ?home WHERE {
          ?node a shi:HospitalSite ;
                shi:officialName ?site ;
                shi:siteOf ?org ;
                shi:siteCanton ?site_canton .
          ?site_canton shi:cantonCode ?site_code .
          ?org shi:officialName ?establishment ;
               shi:homeCanton ?home_canton .
          ?home_canton shi:cantonCode ?home .
          FILTER (?site_code = "GR" && ?home != "GR")
        }
        ORDER BY ?site
        """,
    ),
]


def select_rows(graph: Graph, query: str) -> tuple[list[str], list[list[str]]]:
    result = graph.query(_PREFIXES + _without_declarations(query))
    header = [str(variable) for variable in (result.vars or [])]
    body = [["" if cell is None else str(cell) for cell in row] for row in result]
    return header, body


def establishment_statistics_about_a_site(graph: Graph) -> int:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT (COUNT(?stat) AS ?n) WHERE {
          ?stat shi:statisticalScope ?scope ;
                shi:aboutSite ?site .
          FILTER (?scope = "establishment")
        }
        """
    )
    return int(next(iter(rows)).n)


def require_select(query: str) -> str:
    """The screen runs a read query. Updates and other query forms stay out."""
    lines = _without_declarations(query).splitlines()
    body = "\n".join(line for line in lines if line.strip() and not line.strip().startswith("#")).strip()
    head = body.split(None, 1)[0].upper() if body else ""
    if head != "SELECT":
        raise ValueError("This box runs a SELECT query.")
    return query


def _without_declarations(query: str) -> str:
    lines = query.splitlines()
    while lines and lines[0].strip().upper().startswith(("PREFIX ", "BASE ")):
        lines.pop(0)
    return "\n".join(lines)


def _local(value: object) -> str:
    text = str(value)
    return text.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _string(value: str) -> Literal:
    return Literal(value, datatype=XSD.string)
