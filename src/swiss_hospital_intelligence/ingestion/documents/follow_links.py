"""Save in-scope links found in pages that are already stored.

Robots.txt does not stop the save. News, jobs, and English copies are not
followed. The save repeats until those filters leave no new address.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from swiss_hospital_intelligence.ingestion.documents.in_scope_links import in_scope_links
from swiss_hospital_intelligence.ingestion.documents.save_pages import save_urls

DIRECTORY = Path("data/documents/gr")


def linked_urls(directory: Path, *, per_host_limit: int | None = None) -> tuple[list[str], list[str]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    already = set(manifest)
    counts: dict[str, int] = {}
    chosen: list[str] = []
    leftover: list[str] = []
    for url, page in manifest.items():
        checksum = page.get("checksum")
        content_type = page.get("content_type") or ""
        if not checksum or "html" not in content_type:
            continue
        html = (directory / "bodies" / checksum).read_text(encoding="utf-8", errors="replace")
        for link in in_scope_links(page.get("final_url") or url, html):
            if link in already or link in chosen or link in leftover:
                continue
            if per_host_limit is not None and counts.get(link.split("/")[2], 0) >= per_host_limit:
                leftover.append(link)
                continue
            if per_host_limit is not None:
                host = link.split("/")[2]
                counts[host] = counts.get(host, 0) + 1
            chosen.append(link)
    return chosen, leftover


def main() -> int:
    if not (DIRECTORY / "manifest.json").is_file():
        print("No saved pages yet.", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    saved_count = 0
    despite = 0
    failed: list = []
    wave = 0
    while True:
        chosen, _ = linked_urls(DIRECTORY)
        (DIRECTORY / "not_fetched.txt").write_text("\n".join(chosen), encoding="utf-8")
        if not chosen:
            break
        wave += 1
        print(f"wave {wave}: {len(chosen)}", flush=True)
        result = save_urls(chosen, DIRECTORY, delay_seconds=0.5)
        saved_count += sum(page.checksum is not None for page in result.pages)
        despite += sum(page.saved_despite_robots for page in result.pages)
        failed.extend(page for page in result.pages if page.checksum is None)
    print(f"waves: {wave}")
    print(f"saved: {saved_count}")
    print(f"saved_despite_robots: {despite}")
    print(f"not_saved: {len(failed)}")
    print("left_for_a_later_pass: 0")
    for page in failed:
        print(f"- {page.http_status} {page.url} {page.error or ''}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
