"""Link a quality-file institution name to a 2024 key-figure establishment.

Normalization only removes differences that are not part of the name: Unicode
form, surrounding space, and repeated internal space. Case is folded. Legal
suffixes, hyphens, and missing words are not removed. A near miss stays
unmatched. This method is for the 2024 files only.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel

MATCH_METHOD = "exact_normalized_name_2024"


class NameLink(BaseModel):
    source_name: str
    organization_name: str | None
    match_status: Literal["exact", "unmatched"]
    method: str | None


def normalize_name(name: str) -> str:
    characters = []
    previous_space = False
    for character in unicodedata.normalize("NFC", name).casefold():
        if character.isspace() or character == "\u00a0":
            if characters and not previous_space:
                characters.append(" ")
            previous_space = True
            continue
        previous_space = False
        characters.append(character)
    return "".join(characters).strip()


def link_institution_names(source_names: list[str], establishment_names: list[str]) -> list[NameLink]:
    establishments_by_key: dict[str, list[str]] = {}
    for name in establishment_names:
        establishments_by_key.setdefault(normalize_name(name), []).append(name)
    links: list[NameLink] = []
    for source_name in source_names:
        matches = establishments_by_key.get(normalize_name(source_name), [])
        if len(matches) == 1:
            links.append(
                NameLink(
                    source_name=source_name,
                    organization_name=matches[0],
                    match_status="exact",
                    method=MATCH_METHOD,
                )
            )
            continue
        links.append(
            NameLink(
                source_name=source_name,
                organization_name=None,
                match_status="unmatched",
                method=None,
            )
        )
    return links
