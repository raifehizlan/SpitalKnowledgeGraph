"""Explicit phrases become candidates. A vague partner sentence does not."""

from swiss_hospital_intelligence.ingestion.documents.extract_mentions import extract_mentions


def test_clinical_heading_is_a_department_without_a_site() -> None:
    mentions = extract_mentions("Station A", "Innere Medizin")
    assert [(item.predicate, item.object_value) for item in mentions] == [
        ("hasDepartment", "Innere Medizin")
    ]


def test_contact_heading_and_vague_partners_are_not_extracted() -> None:
    mentions = extract_mentions(
        "Unsere Partner sind wichtig. Zusammenarbeit mit verschiedenen Partnern.",
        "Kontakt",
    )
    assert mentions == []


def test_named_cooperation_and_device_keep_the_source_words() -> None:
    text = (
        "Die Klinik betreibt einen Magnetresonanztomographen. "
        "Zusammenarbeit mit dem Kantonsspital Graubünden."
    )
    mentions = extract_mentions(text, None)
    assert ("mentionsEquipment", "Magnetresonanztomographen") in [
        (item.predicate, item.object_value) for item in mentions
    ]
    assert ("cooperatesWith", "Kantonsspital Graubünden") in [
        (item.predicate, item.object_value) for item in mentions
    ]
