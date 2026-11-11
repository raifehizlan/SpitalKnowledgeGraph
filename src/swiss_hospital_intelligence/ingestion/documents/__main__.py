"""Print the Graubünden source register. This command does not download pages."""

from __future__ import annotations

import sys
from pathlib import Path

from swiss_hospital_intelligence.ingestion.documents.gr_websites import WEBSITES
from swiss_hospital_intelligence.ingestion.documents.source_register import (
    build_source_register,
    render_source_register,
)
from swiss_hospital_intelligence.ingestion.structured.kzp import parse_key_figures


def main() -> int:
    path = _existing("data/raw/kzp24_data.xlsx", "_discovery/raw/kzp24_data.xlsx")
    if path is None:
        print("Key-figure workbook is not on disk.", file=sys.stderr)
        return 2
    register = build_source_register(parse_key_figures(path), WEBSITES)
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_source_register(register), end="")
    return 0


def _existing(*relative_paths: str) -> Path | None:
    for relative in relative_paths:
        path = Path(relative)
        if path.is_file():
            return path
    return None


if __name__ == "__main__":
    raise SystemExit(main())
