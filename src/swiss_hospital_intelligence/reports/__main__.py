"""Print the structured quality report for the local BAG files."""

from __future__ import annotations

import sys
from pathlib import Path

from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures
from swiss_hospital_intelligence.ingestion.structured.qip import parse_quality_indicators
from swiss_hospital_intelligence.reports.gr_cantonal_page import NAMES, PAGE_NOTE, PAGE_URL
from swiss_hospital_intelligence.reports.reviewed_aliases import ALIASES
from swiss_hospital_intelligence.reports.structured_quality import (
    ReportSource,
    build_structured_quality_report,
    key_figure_sources,
    render_structured_quality_report,
)


def main() -> int:
    key_figures = _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx")
    if key_figures is None:
        print("Key-figure workbook is not on disk.", file=sys.stderr)
        return 2
    quality_path = _existing(
        "data/raw/qip24_tabdaten.csv",
        "_discovery/raw/qip24_tabdaten.csv",
        "_discovery/raw/qip24_tabdaten_head.csv",
    )
    quality = parse_quality_indicators(quality_path) if quality_path is not None else None
    sources = key_figure_sources(key_figures.name)
    if quality_path is None:
        sources.append(
            ReportSource(
                role="quality indicators",
                filename=None,
                note="Establishment quality CSV was not on disk.",
            )
        )
    else:
        sources.append(
            ReportSource(
                role="quality indicators",
                filename=quality_path.name,
                note="Acute-hospital quality file. A missing name is absent, not zero.",
            )
        )
    sources.append(
        ReportSource(
            role="Graubünden cantonal page",
            filename=None,
            url=PAGE_URL,
            note=PAGE_NOTE,
        )
    )
    report = build_structured_quality_report(
        parse_key_figures(key_figures),
        NAMES,
        quality=quality,
        sources=sources,
        reviewed_aliases=ALIASES,
    )
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_structured_quality_report(report), end="")
    return 0


def _existing(*relative_paths: str) -> Path | None:
    for relative in relative_paths:
        path = Path(relative)
        if path.is_file():
            return path
    return None


if __name__ == "__main__":
    raise SystemExit(main())
