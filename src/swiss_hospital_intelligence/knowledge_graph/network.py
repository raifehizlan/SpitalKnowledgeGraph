"""One picture of the pilot graph.

A shared canton, equipment code, or claim name is one node, so establishments
meet where the source uses the same thing. A Leistungsauftrag is not a node.
"""

from __future__ import annotations

import json
from rdflib import Graph

_PREFIXES = """
PREFIX shi: <https://example.org/shi/ontology/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

CLAIM_EDGE = {
    "Department": "department",
    "Clinic": "clinic",
    "MedicalService": "service",
    "MedicalDevice": "device mention",
    "Cooperation": "cooperation",
    "Treatment": "treatment",
    "Event": "event",
    "Assertion": "affiliation",
    "inferred": "outside home canton",
}
COLORS = {
    "establishment": "#8fb8d6",
    "site": "#f0d78c",
    "canton": "#e7b3a1",
    "equipment": "#9dccb2",
    "beds": "#d7c4f0",
    "Department": "#f0b7a1",
    "Clinic": "#e3b3e0",
    "MedicalService": "#b7d4c8",
    "MedicalDevice": "#b9c7e8",
    "Cooperation": "#efd3a3",
    "Treatment": "#f3c1cf",
    "Event": "#cfcfcf",
    "Assertion": "#d5d0c8",
    "inferred": "#f3e27a",
}
SIZES = {"establishment": 28, "canton": 22, "site": 16, "equipment": 14, "beds": 14, "inferred": 16}


def build_network(
    graph: Graph,
    *,
    organization: str | None = None,
    kinds: set[str] | None = None,
    statuses: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    allowed = set(CLAIM_EDGE) - {"inferred"} if kinds is None else set(kinds) - {"inferred"}
    organizations = _organizations(graph)
    if organization is not None:
        organizations = [row for row in organizations if row[1] == organization]
    org_ids = {row[0] for row in organizations}
    sites = [row for row in _sites(graph) if row[2] in org_ids]
    equipment = [row for row in _equipment(graph) if row[0] in org_ids]
    beds = [row for row in _beds(graph) if row[0] in org_ids]
    claims = [
        row
        for row in _claims(graph)
        if row[0] in org_ids and row[1] in allowed and (statuses is None or row[3] in statuses)
    ]
    inferences = [row for row in _inferences(graph) if row[0] in org_ids]

    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()
    cantons: set[str] = set()

    def add(node_id: str, label: str, group: str, title: str) -> None:
        nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "label": _short(label),
                "title": title,
                "group": group,
                "color": COLORS.get(group, "#d0d0d0"),
                "size": SIZES.get(group, 10),
                "font": {"size": 14 if group in SIZES else 0},
            },
        )

    for org_id, name, canton in organizations:
        add(org_id, name, "establishment", f"{name}\nestablishment, home {canton}")
        canton_id = f"canton:{canton}"
        cantons.add(canton)
        add(canton_id, canton, "canton", f"Canton {canton}")
        edges.add((org_id, canton_id, "home canton"))
    for site_id, name, org_id, canton in sites:
        add(site_id, name, "site", f"{name}\nsite, {canton}")
        canton_id = f"canton:{canton}"
        cantons.add(canton)
        add(canton_id, canton, "canton", f"Canton {canton}")
        edges.add((org_id, site_id, "site"))
        edges.add((site_id, canton_id, "site canton"))
    for org_id, code in equipment:
        node_id = f"equipment:{code}"
        add(node_id, code, "equipment", f"{code}\nequipment presence")
        edges.add((org_id, node_id, "equipment"))
    for org_id, value in beds:
        node_id = f"beds:{org_id}"
        add(node_id, f"{value} beds", "beds", f"BettenStatA {value}\nestablishment")
        edges.add((org_id, node_id, "beds"))
    for org_id, kind, name, status in claims:
        node_id = f"claim:{kind}:{_key(name)}"
        add(node_id, name, kind, f"{name}\n{CLAIM_EDGE[kind]}, {status}")
        edges.add((org_id, node_id, CLAIM_EDGE[kind]))
    for org_id, name in inferences:
        node_id = f"inferred:{org_id}:{_key(name)}"
        add(node_id, name, "inferred", f"{name}\ninferred: site canton differs from the home canton")
        edges.add((org_id, node_id, CLAIM_EDGE["inferred"]))
    claim_nodes = [node for node in nodes.values() if node["group"] in CLAIM_EDGE and node["group"] != "inferred"]
    if len(claim_nodes) <= 40:
        for node in claim_nodes:
            node["font"] = {"size": 13}
    listed = []
    for index, (source, target, label) in enumerate(sorted(edges)):
        listed.append(
            {
                "id": f"e{index}",
                "from": source,
                "to": target,
                "label": label,
                "title": _edge_sentence(label, nodes[source], nodes[target]),
                "width": 2,
            }
        )
    return list(nodes.values()), listed


def network_html(nodes: list[dict], edges: list[dict]) -> str:
    payload = json.dumps({"nodes": nodes, "edges": edges}).replace("<", "\\u003c")
    return f"""
    <div id="shi-detail" style="max-height:220px;overflow:auto;min-height:52px;margin-bottom:8px;padding:10px 12px;background:#161b22;border:1px solid #30363d;border-radius:8px;color:#f5f5f5;font:14px/1.4 sans-serif;white-space:pre-wrap;">Click a line or a node.</div>
    <div id="shi-net" style="height:690px;background:#0e1117;border:1px solid #30363d;border-radius:8px;"></div>
    <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
    <script>
    const data = {payload};
    const order = ["canton", "establishment", "site", "equipment", "beds", "inferred", "Department", "Clinic", "MedicalService", "MedicalDevice", "Cooperation", "Treatment", "Event", "Assertion"];
    const groups = {{}};
    data.nodes.forEach(node => {{
      if (!groups[node.group]) groups[node.group] = [];
      groups[node.group].push(node);
    }});
    order.filter(group => groups[group]).forEach((group, index) => {{
      const radius = 140 + index * 120;
      groups[group].forEach((node, item) => {{
        const angle = (2 * Math.PI * item) / groups[group].length;
        node.x = Math.cos(angle) * radius;
        node.y = Math.sin(angle) * radius;
      }});
    }});
    const network = new vis.Network(
      document.getElementById("shi-net"),
      {{
        nodes: new vis.DataSet(data.nodes),
        edges: new vis.DataSet(data.edges)
      }},
      {{
        nodes: {{ shape: "dot", font: {{ color: "#f5f5f5" }} }},
        edges: {{
          arrows: "to",
          width: 2,
          selectionWidth: 5,
          hoverWidth: 4,
          color: {{ color: "#8aa0b4", highlight: "#f5f5f5", hover: "#f5f5f5" }},
          font: {{ color: "#d0d0d0", size: 11, strokeWidth: 0 }},
          smooth: false
        }},
        physics: false,
        interaction: {{ hover: true, tooltipDelay: 60, navigationButtons: true, hideEdgesOnDrag: true }}
      }}
    );
    function show(text) {{
      document.getElementById("shi-detail").textContent = text;
    }}
    network.on("click", function (params) {{
      if (params.nodes.length) {{
        const nodeId = params.nodes[0];
        const node = data.nodes.find(item => item.id === nodeId);
        const linked = data.edges.filter(item => item.from === nodeId || item.to === nodeId);
        show(linked.length ? linked.map(item => item.title).join("\\n") : node.title);
        return;
      }}
      if (params.edges.length) {{
        const edge = data.edges.find(item => item.id === params.edges[0]);
        show(edge.title);
        return;
      }}
      show("Click a line or a node.");
    }});
    network.fit();
    </script>
    """


def _organizations(graph: Graph) -> list[tuple[str, str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?name ?canton WHERE {
          ?org a shi:HospitalOrganization ;
               shi:officialName ?name ;
               shi:homeCanton ?home .
          ?home shi:cantonCode ?canton .
        }
        """
    )
    return [(str(row.org), str(row.name), str(row.canton)) for row in rows]


def _sites(graph: Graph) -> list[tuple[str, str, str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?site ?name ?org ?canton WHERE {
          ?site a shi:HospitalSite ;
                shi:officialName ?name ;
                shi:siteOf ?org ;
                shi:siteCanton ?place .
          ?place shi:cantonCode ?canton .
        }
        """
    )
    return [(str(row.site), str(row.name), str(row.org), str(row.canton)) for row in rows]


def _equipment(graph: Graph) -> list[tuple[str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?code WHERE {
          ?presence a shi:EquipmentPresence ;
                    shi:recordedFor ?org ;
                    shi:presenceOf ?concept .
          ?concept skos:notation ?code .
          FILTER NOT EXISTS { ?presence a shi:MedicalDevice }
        }
        """
    )
    return [(str(row.org), str(row.code)) for row in rows]


def _beds(graph: Graph) -> list[tuple[str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?value WHERE {
          ?stat shi:aboutOrganization ?org ;
                shi:measure ?measure ;
                shi:statisticalScope ?scope ;
                shi:valueNumeric ?value .
          ?measure shi:measureCode ?code .
          FILTER (?code = "BettenStatA" && ?scope = "establishment")
          FILTER NOT EXISTS { ?stat shi:aboutSite ?site }
        }
        """
    )
    return [(str(row.org), str(row.value)) for row in rows]


def _claims(graph: Graph) -> list[tuple[str, str, str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?kind ?name ?status WHERE {
          ?org shi:asserts ?claim .
          ?claim shi:officialName ?name ;
                 shi:factStatus ?status ;
                 a ?kind .
          FILTER (?kind != shi:Assertion)
        }
        """
    )
    found = [(_id(row.org), _local(row.kind), str(row.name), str(row.status)) for row in rows]
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?name ?status WHERE {
          ?org shi:asserts ?claim .
          ?claim shi:officialName ?name ;
                 shi:factStatus ?status ;
                 a shi:Assertion .
          FILTER NOT EXISTS { ?claim a ?other . FILTER(?other != shi:Assertion) }
          FILTER NOT EXISTS {
            ?claim shi:extractionMethod ?method .
            FILTER (?method = "site_canton_differs_from_home")
          }
        }
        """
    )
    found.extend((_id(row.org), "Assertion", str(row.name), str(row.status)) for row in rows)
    return found


def _inferences(graph: Graph) -> list[tuple[str, str]]:
    rows = graph.query(
        _PREFIXES
        + """
        SELECT ?org ?name WHERE {
          ?org shi:asserts ?claim .
          ?claim shi:officialName ?name ;
                 shi:extractionMethod ?method .
          FILTER (?method = "site_canton_differs_from_home")
        }
        """
    )
    return [(str(row.org), str(row.name)) for row in rows]


def _id(value: object) -> str:
    return str(value)


def _local(value: object) -> str:
    text = str(value)
    return text.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


_EDGE_TEXT = {
    "home canton": "{left} has home canton {right}.",
    "site": "{right} is a site of {left}.",
    "site canton": "{left} is in canton {right}.",
    "equipment": "{left} has equipment presence {right}. This code comes from the BAG sheet.",
    "beds": "{left} has {right}. The number is recorded for the establishment.",
    "department": "{left} has a department claim named {right}.",
    "clinic": "{left} has a clinic claim named {right}.",
    "service": "{left} has a service claim named {right}.",
    "device mention": "{left} mentions the device {right}. This comes from a saved page.",
    "cooperation": "{left} has a cooperation claim with {right}.",
    "treatment": "{left} has a treatment claim named {right}.",
    "event": "{left} has an event claim named {right}.",
    "affiliation": "{left} has an affiliation claim named {right}.",
    "outside home canton": "{right} is marked because its canton differs from the home canton of {left}.",
}


def _edge_sentence(label: str, source: dict, target: dict) -> str:
    left = source["title"].split("\n", 1)[0]
    right = target["title"].split("\n", 1)[0]
    sentence = _EDGE_TEXT[label].format(left=left, right=right)
    if label in set(CLAIM_EDGE.values()) - {"outside home canton"}:
        status = target["title"].rsplit(",", 1)[-1].strip()
        sentence = f"{sentence} Status: {status}."
    return sentence


def _short(value: str, limit: int = 42) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
