"""A robots disallow does not stop the save, and the same body is stored once."""

from __future__ import annotations

from swiss_hospital_intelligence.ingestion.documents.save_pages import save_registered_pages
from swiss_hospital_intelligence.ingestion.documents.source_register import RegisterRow, SourceRegister


def _register(url: str) -> SourceRegister:
    return SourceRegister(
        rows=[
            RegisterRow(
                organization_name="Example Hospital",
                site_name=None,
                home_canton="GR",
                site_canton=None,
                url_status="found",
                url=url,
                language="de",
                source=url,
                note="",
            )
        ]
    )


def test_a_disallowed_page_is_saved_once(tmp_path) -> None:
    body = b"<html>example</html>"
    calls = {"page": 0}

    def fetch(url: str):
        if url.endswith("/robots.txt"):
            return 200, b"User-agent: *\nDisallow: /page\n", "text/plain", url, None
        calls["page"] += 1
        return 200, body, "text/html", url, None

    directory = tmp_path / "documents"
    url = "https://example.test/page"
    first = save_registered_pages(_register(url), directory, fetch=fetch, robots_allowed_for=None)
    second = save_registered_pages(_register(url), directory, fetch=fetch, robots_allowed_for=None)

    saved = first.pages[0]
    assert saved.robots_allowed is False
    assert saved.saved_despite_robots is True
    assert saved.checksum is not None
    assert (directory / "bodies" / saved.checksum).read_bytes() == body
    assert list((directory / "bodies").iterdir()) == [directory / "bodies" / saved.checksum]
    assert second.pages[0].checksum == saved.checksum
    assert calls["page"] == 2
