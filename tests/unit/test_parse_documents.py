"""HTML stays in sections. A PDF stays in pages. An empty page is kept as a failure."""

import pymupdf

from swiss_hospital_intelligence.ingestion.documents.parse_documents import parse_html, parse_pdf, parse_saved_page


def test_html_sections_stay_separate_and_keep_language() -> None:
    html = """
    <html lang="de-CH">
      <head><title>Spital</title><style>.x{color:red}</style></head>
      <body>
        <nav>Navigation</nav>
        <h2>Innere Medizin</h2>
        <p>Station A</p>
        <h2>Chirurgie</h2>
        <p>Station B</p>
        <footer>Impressum</footer>
      </body>
    </html>
    """
    parsed = parse_html(html, "https://example.ch/de/angebot")
    assert parsed.language == "de"
    assert parsed.title == "Spital"
    assert [(chunk.section, chunk.text) for chunk in parsed.chunks] == [
        ("Innere Medizin", "Station A"),
        ("Chirurgie", "Station B"),
    ]
    assert parsed.processing_status == "parsed"


def test_html_without_text_is_a_failed_chunk() -> None:
    parsed = parse_html("<html><body><nav>Only</nav></body></html>", "https://example.ch/")
    assert len(parsed.chunks) == 1
    assert parsed.chunks[0].status == "failed"
    assert parsed.chunks[0].failure_reason == "no_text"


def test_pdf_pages_stay_separate_and_blank_page_is_kept() -> None:
    document = pymupdf.open()
    first = document.new_page()
    first.insert_text((72, 72), "Innere Medizin")
    document.new_page()
    data = document.tobytes()
    document.close()
    parsed = parse_pdf(data, "https://example.ch/files/bericht.pdf")
    assert [chunk.page_number for chunk in parsed.chunks] == [1, 2]
    assert parsed.chunks[0].status == "parsed"
    assert "Innere Medizin" in parsed.chunks[0].text
    assert parsed.chunks[1].status == "failed"
    assert parsed.chunks[1].failure_reason == "no_extractable_text"
    assert parsed.processing_status == "parsed_with_failures"
    assert "\n" not in "".join(chunk.text for chunk in parsed.chunks) or parsed.chunks[0].text != parsed.chunks[1].text


def test_a_long_page_becomes_several_passages_on_the_same_page() -> None:
    from swiss_hospital_intelligence.ingestion.documents.parse_documents import split_passage

    pieces = split_passage(("Station A behandelt Patienten. " * 80).strip())
    assert len(pieces) > 1
    assert all(len(piece) <= 1200 for piece in pieces)
    assert pieces[0].endswith(".")


def test_http_error_is_not_parsed_as_a_page() -> None:
    parsed = parse_saved_page(
        "https://example.ch/missing",
        b"<html><h1>Not found</h1><p>Theme text</p></html>",
        content_type=None,
        http_status=404,
        error=None,
        checksum="abc",
    )
    assert parsed.processing_status == "failed"
    assert parsed.chunks[0].text == ""
    assert parsed.chunks[0].failure_reason == "http_404"
