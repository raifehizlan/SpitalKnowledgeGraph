"""Export the pilot graph, validate it, and run HermiT on the example."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.knowledge_graph.export import write_graph, write_text
from swiss_hospital_intelligence.knowledge_graph.project import project_pilot_graph
from swiss_hospital_intelligence.knowledge_graph.queries import PRESETS, select_rows
from swiss_hospital_intelligence.knowledge_graph.reason import example_still_has_site_of, inferred_has_site
from swiss_hospital_intelligence.knowledge_graph.validate import example_graph, validation_text

DATABASE_URL = "postgresql+psycopg://shi:shi@localhost:5432/shi"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        graph = project_pilot_graph(session)
    turtle, jsonld = write_graph(graph)
    print(f"triples {len(graph)}")
    print(f"turtle {turtle}")
    print(f"jsonld {jsonld}")

    example_ok, example_text = validation_text(example_graph())
    pilot_ok, pilot_text = validation_text(graph)
    report = "\n".join(
        [
            f"KSGR example conforms: {example_ok}",
            example_text.strip(),
            "",
            f"Graubünden pilot conforms: {pilot_ok}",
            pilot_text.strip(),
            "",
        ]
    )
    print(report)
    write_text("shacl-report.txt", report)

    stored = example_still_has_site_of()
    inferred = inferred_has_site()
    reasoner = "\n".join(
        [
            f"Example siteOf triples before HermiT: {stored}",
            "hasSite inferred by HermiT:",
            *(f"- {org} -> {site}" for org, site in inferred),
            "",
        ]
    )
    print(reasoner)
    write_text("reasoner-example.txt", reasoner)

    for title, query in PRESETS:
        header, rows = select_rows(graph, query)
        print(title)
        print("\t".join(header))
        for row in rows:
            print("\t".join(row))
        print()
    return 0 if example_ok and pilot_ok and inferred else 1


if __name__ == "__main__":
    raise SystemExit(main())
