"""Run HermiT on the KSGR example.

The loader writes siteOf. hasSite is declared as its inverse and is not
stored. HermiT materializes that inverse on the example. The pilot is not
classified, and the reasoner is not asked to add a site or a department.
HermiT does not accept xsd:gYear, so unsupported datatypes are ignored.
The stored graph keeps the year as xsd:gYear.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from owlready2 import World, sync_reasoner_hermit
from rdflib import Graph, URIRef

from swiss_hospital_intelligence.knowledge_graph.project import SHI
from swiss_hospital_intelligence.knowledge_graph.validate import example_graph

HAS_SITE = URIRef(str(SHI.hasSite))


def inferred_has_site(graph: Graph | None = None) -> list[tuple[str, str]]:
    data = example_graph() if graph is None else graph
    before = set(data.triples((None, HAS_SITE, None)))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "example.owl"
        data.serialize(path, format="xml")
        world = World()
        with path.open("rb") as handle:
            onto = world.get_ontology("https://example.org/shi/ontology/").load(fileobj=handle)
        sync_reasoner_hermit([onto], infer_property_values=True, ignore_unsupported_datatypes=True)
        reasoned = world.as_rdflib_graph()
    added = set(reasoned.triples((None, HAS_SITE, None))) - before
    return sorted((_label(data, org), _label(data, site)) for org, site in ((s, o) for s, _p, o in added))


def _label(graph: Graph, node: URIRef) -> str:
    name = graph.value(node, SHI.officialName)
    if name is not None:
        return str(name)
    return str(node)


def example_still_has_site_of(graph: Graph | None = None) -> int:
    data = example_graph() if graph is None else graph
    return sum(1 for _ in data.triples((None, SHI.siteOf, None)))
