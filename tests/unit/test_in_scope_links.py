"""In-scope links stay. News, jobs, and other sites do not."""

from swiss_hospital_intelligence.ingestion.documents.in_scope_links import in_scope_links, junk_reason


def test_scope_keeps_departments_and_annual_reports() -> None:
    html = """
    <a href="/fachgebiete/innere-medizin/">Innere Medizin</a>
    <a href="/aktuelles/news">News</a>
    <a href="/jobs">Jobs</a>
    <a href="https://other.example/fachgebiete">Elsewhere</a>
    <a href="/ueber-uns/geschaeftsberichte/">Geschäftsbericht</a>
    <a href="/files/jahresbericht-2024.pdf">Jahresbericht 2024</a>
    <a href="/files/inserat.pdf">Publikumsvortrag</a>
    <a href="/en/fachgebiete">Specialties</a>
    <a href="/de/spital/poppigalerie/mira-1">Mira</a>
    """
    assert in_scope_links("https://www.example.ch/de", html) == [
        "https://www.example.ch/fachgebiete/innere-medizin",
        "https://www.example.ch/ueber-uns/geschaeftsberichte",
        "https://www.example.ch/files/jahresbericht-2024.pdf",
    ]


def test_junk_reason_drops_galleries_images_and_other_clinics() -> None:
    assert junk_reason("https://www.flurystiftung.ch/de/spital/poppigalerie/mira") == "baby_gallery"
    assert junk_reason("https://valens.ch/reha-triemli/angebot") == "other_clinic"
    assert junk_reason("https://valens.ch/reha-chur/angebot") is None
    assert junk_reason("https://valens.ch/wp-content/uploads/2026/08/Valens_Jahresbericht_2025_web.pdf") is None
    assert junk_reason("https://www.ksgr.ch/foto.jpg") == "image"
    assert junk_reason("https://www.flurystiftung.ch/de/altersheime/angebot") == "other_operation"
    assert junk_reason("https://www.ksgr.ch/spitaltechnik") is None
