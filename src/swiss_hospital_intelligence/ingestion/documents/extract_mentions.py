"""Extract explicit mentions from a saved passage.

A heading or a sentence must name the thing. The passage does not receive a
site. A sentence that only says "partners" does not become a cooperation.
Every result is a candidate.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

METHOD = "explicit_phrase"
GENERIC_HEADINGS = {
    "fachgebiete",
    "angebot",
    "leistungen",
    "leistungsangebot",
    "medizinische leistungen",
    "medizinisches angebot",
    "offerta",
    "servizi",
    "team",
    "kontakt",
    "zuweisung",
    "unternehmen",
    "veranstaltungen",
    "fachpersonen",
    "unsere kompetenz",
}
REJECT_HEADING = re.compile(
    r"kontakt|search|suchen|instagram|facebook|podcast|flyer|brosch|karriere|anmeldung|"
    r"nummern|telefon|impression|situationsplan|dokumente|details|wissenswert|"
    r"öffentlichkeit|oeffentlichkeit|partner|veranstaltung",
    re.IGNORECASE,
)
SPECIALTY = re.compile(
    r"medizin|chirurgie|chirurgia|radiolog|psychiatr|psichiatr|rehabilit|riabilit|"
    r"kardiolog|cardiolog|onkolog|oncolog|neurolog|orthop|ortoped|gyn[aä]k|ginecolog|"
    r"urolog|p[aä]diatr|paediatr|pediatr|gastro|intensiv|an[aä]sth|anestes|"
    r"dialyse|geburt|ostetric|dermatolog|pneumo|nephro|endokrin|rheuma|geriatr|"
    r"palliativ|neonat|augenheil|oftalm|ophtalm|unfall|notfall|urgenza|urgences|"
    r"physiotherap|ergotherap|logop",
    re.IGNORECASE,
)
CLINIC_WORD = re.compile(r"\b(klinik|clinica|clinique|reparto|clinic)\b", re.IGNORECASE)
SERVICE_WORD = re.compile(r"\b(therapie|terapia|thérapie|service|servizio|dienst)\b", re.IGNORECASE)
DEVICES = re.compile(
    r"magnetresonanztomograph\w*|risonanza magnetica|imagerie par résonance|mrt\b|mri\b|"
    r"computertomograph\w*|tomodensitom\w*|\bct\b|\btac\b|"
    r"positronen-emissions\w*|pet-ct|pet/ct|\bpet\b|"
    r"linearbeschleuniger|accélérateur linéaire|acceleratore lineare|"
    r"gammakamera|gamma-kamera|lithotrip\w*|angiograph\w*",
    re.IGNORECASE,
)
COOPERATION = re.compile(
    r"(?:Zusammenarbeit mit|Kooperation mit|in Kooperation mit|partenariat avec|"
    r"en collaboration avec|in collaborazione con|cooperazione con)\s+([^,.;]{4,80})"
)
AFFILIATION = re.compile(
    r"(?:Mitglied (?:des|der|von)|Trägerschaft(?: der| des)?|affilié à|"
    r"affiliata (?:a|alla|al))\s+([^,.;]{4,80})"
)
TREATMENT = re.compile(
    r"(?:Behandlung von|Therapie bei|trattamento (?:di|della|del)|traitement d[eu'])\s+([^,.;]{4,80})"
)
EVENT_DATE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
EVENT_WORD = re.compile(r"veranstaltung|tagung|kongress|symposium|giornata|colloque", re.IGNORECASE)
VAGUE_NAME = re.compile(
    r"^(uns|ihnen|partner|partnern|anderen|verschiedenen|institutionen|unsere partner)$",
    re.IGNORECASE,
)


class Mention(BaseModel):
    predicate: str
    object_value: str
    excerpt: str


def extract_mentions(text: str, section: str | None) -> list[Mention]:
    found: list[Mention] = []
    heading = _heading_mention(section)
    if heading is not None:
        found.append(heading)
    for sentence in _sentences(text):
        found.extend(_sentence_mentions(sentence))
    unique: list[Mention] = []
    seen: set[tuple[str, str]] = set()
    for mention in found:
        key = (mention.predicate, _key(mention.object_value))
        if key in seen or not mention.object_value.strip():
            continue
        seen.add(key)
        unique.append(mention)
    return unique


def _heading_mention(section: str | None) -> Mention | None:
    if not section or not section.strip():
        return None
    folded = " ".join(section.casefold().split())
    if folded in GENERIC_HEADINGS or REJECT_HEADING.search(section):
        return None
    if not SPECIALTY.search(section):
        return None
    if CLINIC_WORD.search(section):
        predicate = "hasClinic"
    elif SERVICE_WORD.search(section):
        predicate = "hasService"
    else:
        predicate = "hasDepartment"
    return Mention(predicate=predicate, object_value=section.strip(), excerpt=section.strip())


def _named(value: str) -> str | None:
    name = " ".join(value.split())
    name = re.sub(r"^(dem|der|des|die|den|la|le|les|il|lo)\s+", "", name, flags=re.IGNORECASE)
    if not name or VAGUE_NAME.match(name) or re.search(
        r"\b(partner|partnern|verschiedenen|anderen|uns)\b", name, re.IGNORECASE
    ):
        return None
    return name


def _sentence_mentions(sentence: str) -> list[Mention]:
    found: list[Mention] = []
    for match in DEVICES.finditer(sentence):
        found.append(Mention(predicate="mentionsEquipment", object_value=match.group(0), excerpt=sentence))
    for pattern, predicate in (
        (COOPERATION, "cooperatesWith"),
        (AFFILIATION, "affiliatedWith"),
        (TREATMENT, "offersTreatment"),
    ):
        match = pattern.search(sentence)
        if match is None:
            continue
        name = _named(match.group(1))
        if name is None:
            continue
        found.append(Mention(predicate=predicate, object_value=name, excerpt=sentence))
    if EVENT_DATE.search(sentence) and EVENT_WORD.search(sentence):
        found.append(Mention(predicate="hasEvent", object_value=sentence.strip(), excerpt=sentence.strip()))
    return found


def _sentences(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _key(value: str) -> str:
    return " ".join(value.casefold().split())
