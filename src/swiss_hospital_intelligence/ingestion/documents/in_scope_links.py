"""Choose in-scope links from a saved hospital page.

Same site only. Departments, services, locations, people, quality, and annual
or quality reports stay. News, jobs, and English translations do not.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse, urlunparse

OUT_OF_SCOPE = {
    "aktuell",
    "aktuelles",
    "attualita",
    "attualita-centro-sanitario",
    "blog",
    "cookie",
    "datenschutz",
    "event",
    "events",
    "impressum",
    "jobs",
    "karriere",
    "login",
    "media",
    "medien",
    "mitteilungen",
    "news",
    "news-mitteilungen",
    "newsletter",
    "offerte-di-lavoro",
    "poppigalerie",
    "babygalerie",
    "babyportal",
    "altersheim",
    "altersheime",
    "spitex",
    "wohnen-mit-service",
    "search",
    "spenden",
    "stellen",
    "suche",
    "veranstaltungen",
}
IN_SCOPE = (
    "abteilung",
    "aerzte",
    "ambul",
    "angebot",
    "arzt",
    "behandlung",
    "diagnos",
    "direktion",
    "dokument",
    "download",
    "fachbereich",
    "fachgebiet",
    "geschaeftsbericht",
    "gremien",
    "jahresbericht",
    "klinik",
    "leistung",
    "medici",
    "mitarbeit",
    "offerta",
    "organigram",
    "organisation",
    "qualit",
    "radiolog",
    "reparto",
    "serviz",
    "spital",
    "standort",
    "team",
    "therap",
    "traegerschaft",
    "ueber-uns",
    "unternehmen",
)
REPORT_PDF = (
    "annual",
    "bericht",
    "bilancio",
    "geschaeft",
    "jahres",
    "qualit",
    "rapporto",
    "report",
)


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.found.append((self._href, "".join(self._text).strip()))
            self._href = None


def in_scope_links(page_url: str, html: str) -> list[str]:
    parser = _Anchors()
    parser.feed(html)
    chosen: list[str] = []
    seen: set[str] = set()
    for href, text in parser.found:
        absolute = _clean(urljoin(page_url, href))
        if absolute is None or absolute in seen or not _same_site(page_url, absolute):
            continue
        if not _in_scope(absolute, text):
            continue
        seen.add(absolute)
        chosen.append(absolute)
    return chosen


def _clean(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


def _same_site(page_url: str, link: str) -> bool:
    return _host(urlparse(page_url).netloc) == _host(urlparse(link).netloc)


def _host(netloc: str) -> str:
    host = netloc.lower()
    if host.startswith("www."):
        return host[4:]
    return host


_IMAGE_SUFFIXES = (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".css", ".js")
_OTHER_VALENS = {
    "reha-valens",
    "reha-gais",
    "reha-wald",
    "reha-walenstadtberg",
    "reha-davos-clavadel",
    "reha-stgallen",
    "reha-walzenhausen",
    "reha-triemli",
    "ambi-psy-stgallen",
}
_VALENS_NOISE = {
    "team",
    "fachbereich",
    "angebot",
    "menschen",
    "rehakliniken",
    "downloads-fuer-lieferanten",
    "baustart-fuer-neue-rehaklinik-triemli-zuerich",
    "valenser-kuechenteam-belegt-4-platz-an-der-swiss-svg-trophy",
    "stabwechsel-in-der-aerztlichen-direktion",
    "stationaere-behandlung-von-traumafolgestoerungen",
}
_JOB_OR_NEWS = {
    "jobs",
    "stellen",
    "offene-stellen",
    "bewerben",
    "zukunftstag",
    "news-eventi",
    "news-events",
    "jobs-und-karriere",
    "jobsbildung",
}
_BROKEN_TAIL = {
    "berufsbildungplus.ch",
    "www.oda-gs.gr.ch",
    "www.pdgr.ch",
}
_UNRELATED_HOSTS = {
    "restaurant-zanai.ch",
    "thermalbad-valens.ch",
    "www.rehazentrum-chur.ch",
}


def junk_reason(url: str) -> str | None:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    segments = [unquote(segment).casefold().strip() for segment in parsed.path.split("/") if segment.strip()]
    path = unquote(parsed.path).casefold()
    if host in _UNRELATED_HOSTS:
        return "unrelated_site"
    if any(segment in {"poppigalerie", "babygalerie", "babyportal"} for segment in segments):
        return "baby_gallery"
    if path.endswith(_IMAGE_SUFFIXES):
        return "image"
    if host == "valens.ch" and segments:
        if segments[0] in _OTHER_VALENS or "restaurant-zanai" in path or "thermalbad" in path:
            return "other_clinic"
        if segments[0] in _VALENS_NOISE:
            return "other_clinic"
        if segments[0] == "wp-content" and not path.endswith(".pdf"):
            return "image"
    if any(segment in {"altersheim", "altersheime", "spitex", "wohnen-mit-service"} for segment in segments):
        return "other_operation"
    if "bogn-engiadina" in path or "bogn_engiadina" in path:
        return "other_operation"
    if any(segment in _JOB_OR_NEWS for segment in segments):
        return "job_or_news"
    if segments and segments[-1] in _BROKEN_TAIL:
        return "broken_link"
    if path.endswith(".zip") or path.endswith(".docx"):
        return "form"
    if "goennerverein" in path or "gönnerverein" in path:
        return "donor_club"
    return None


def _in_scope(url: str, text: str) -> bool:
    if junk_reason(url):
        return False
    parsed = urlparse(url)
    segments = [segment.casefold() for segment in parsed.path.split("/") if segment]
    if "en" in segments or any(segment in OUT_OF_SCOPE for segment in segments):
        return False
    blob = " ".join(segments) + " " + text.casefold()
    if parsed.path.casefold().endswith(".pdf"):
        return any(token in blob for token in REPORT_PDF)
    return any(token in blob for token in IN_SCOPE)
