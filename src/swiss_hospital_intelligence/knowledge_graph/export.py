"""Write the pilot graph as Turtle and JSON-LD.

The files stay under data/exports, with the BAG workbook. The repository
does not publish the key-figure cells.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph

EXPORT_DIR = Path("data") / "exports"


def write_graph(graph: Graph, directory: Path = EXPORT_DIR) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    turtle = directory / "graubunden-pilot.ttl"
    jsonld = directory / "graubunden-pilot.jsonld"
    graph.serialize(turtle, format="turtle")
    graph.serialize(jsonld, format="json-ld")
    return turtle, jsonld


def write_text(name: str, text: str, directory: Path = EXPORT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path
