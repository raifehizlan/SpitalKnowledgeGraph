"""Run the SHACL shapes over a graph.

The example keeps the equipment-concept types in the ontology file, so the
vocabulary is added before validation. The pilot graph already types the
concepts it uses. Adding the vocabulary again does not create new facts.
"""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[3]


def shapes_graph() -> Graph:
    return Graph().parse(ROOT / "ontology" / "shapes" / "core.shacl.ttl", format="turtle")


def ontology_graph() -> Graph:
    return Graph().parse(ROOT / "ontology" / "swiss_hospital_ontology.ttl", format="turtle")


def example_graph() -> Graph:
    graph = ontology_graph()
    graph.parse(ROOT / "ontology" / "examples" / "ksgr-2024.ttl", format="turtle")
    return graph


def validation_text(data: Graph) -> tuple[bool, str]:
    graph = ontology_graph()
    graph += data
    conforms, _results, text = validate(
        graph,
        shacl_graph=shapes_graph(),
        advanced=True,
        inference="none",
    )
    return bool(conforms), text
