"""Official websites for the 2024 Graubünden establishments.

Each URL was taken from the hospital's own page or from the Bündner Spital- und
Klinikverein member list, and the postal address was compared with the 2024
key figures. Robots rules were not checked. This register does not download pages.
"""

from __future__ import annotations

from swiss_hospital_intelligence.ingestion.documents.source_register import WebsiteRecord

BSH_MEMBERS = "https://www.bsh-gr.ch/wp-content/uploads/2026/09/Mitglieder-BSH-KSK-Neu.pdf"

# The 2024 site sheet stores U+003F in these names. The establishment sheet has the accented letter.
SITE_KSGR = "Kantonsspital Graub?nden"
SITE_MUESTAIR = "Center da Sanda Val M?stair"
SITE_FLAESCH = "Klinik Gut Fl?sch"
SITE_PRAETTIGAU = "PDGR Pr?ttigau / Davos"
SITE_SUDTAELER = "PDGR Engadin / S?dt?ler"


def _same_site(organization: str, site: str, url: str, language: str, source: str, note: str) -> list[WebsiteRecord]:
    return [
        WebsiteRecord(organization_name=organization, url=url, language=language, source=source, note=note),
        WebsiteRecord(
            organization_name=organization,
            site_name=site,
            url=url,
            language=language,
            source=source,
            note=note,
        ),
    ]


WEBSITES = [
    *_same_site(
        "Kantonsspital Graubünden",
        SITE_KSGR,
        "https://www.ksgr.ch/",
        "de",
        "https://www.ksgr.ch/",
        "Homepage contact is Loëstrasse 170, 7000 Chur. The 2024 site name contains a question mark in place of ü. "
        + BSH_MEMBERS,
    ),
    WebsiteRecord(
        organization_name="Kantonsspital Graubünden",
        site_name="Spital Walenstadt",
        url="https://www.ksgr.ch/standorte",
        language="de",
        source="https://www.ksgr.ch/standorte",
        note="The locations page names Standort Walenstadt at Spitalstrasse 5, 8880 Walenstadt.",
    ),
    *_same_site(
        "Spital Oberengadin",
        "Spital Oberengadin",
        "https://www.spital-oberengadin.ch/",
        "de",
        "https://www.spital-oberengadin.ch/",
        "Homepage contact is Via Nouva 3, 7503 Samedan.",
    ),
    *_same_site(
        "Regionalspital Surselva AG",
        "Regionalspital Surselva",
        "https://www.rss.ch/",
        "de",
        "https://www.rss.ch/",
        "Homepage contact is Spitalstrasse 6, 7130 Ilanz. The BSH member list also prints www.spitalilanz.ch. " + BSH_MEMBERS,
    ),
    *_same_site(
        "Spital Davos AG Akutabteilung",
        "Spital Davos",
        "https://www.spitaldavos.ch/de",
        "de",
        "https://www.spitaldavos.ch/de",
        "Homepage contact is Promenade 4, 7270 Davos Platz.",
    ),
    *_same_site(
        "Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
        "Ospidal d'Engiadina Bassa",
        "https://cseb.ch/",
        "de",
        "https://cseb.ch/betriebe/ospidal/",
        "The Ospidal page gives Via da l'Ospidal 280, 7550 Scuol.",
    ),
    *_same_site(
        "Spital Thusis",
        "Spital Thusis",
        "https://www.spitalthusis.ch/",
        "de",
        "https://www.spitalthusis.ch/",
        "Homepage contact is Alte Strasse 31, 7430 Thusis.",
    ),
    *_same_site(
        "Centro Sanitario Valposchiavo Ospedale San Sisto",
        "Centro Sanitario Valposchiavo Ospedale San Sisto",
        "https://www.csvp.ch/it/",
        "it",
        "https://www.csvp.ch/it/",
        "The homepage places Ospedale San Sisto at Via da li Clüsüri 1, 7742 Poschiavo. Casa Anziani is a different street.",
    ),
    *_same_site(
        "Center da Sanadad Savognin SA",
        "Center da Sanadad Savognin",
        "https://www.cds-savognin.ch/DE/home.html",
        "de",
        "https://www.cds-savognin.ch/DE/home.html",
        "The opened page gives Stradung 52, 7460 Savognin, and also prints www.spital-savognin.ch.",
    ),
    *_same_site(
        "Center da Sanda Val Müstair Akutabteilung",
        SITE_MUESTAIR,
        "http://csvm.ch/de/",
        "de",
        "http://csvm.ch/de/",
        "The opened page gives Via Val Müstair 186, 7536 Sta. Maria. The 2024 site name contains a question mark in place of ü.",
    ),
    *_same_site(
        "Centro Sanitario Bregaglia Reparto Acuto",
        "Centro Sanitario Bregaglia Reparto Acuto",
        "https://www.csbregaglia.ch/it/",
        "it",
        "https://www.csbregaglia.ch/it/",
        "The homepage places the center at Flin, 7606 Promontogno. The 2024 street cell is Flin, without the house number.",
    ),
    WebsiteRecord(
        organization_name="Psychiatrische Dienste Graubünden",
        url="https://www.pdgr.ch/",
        language="de",
        source="https://www.pdgr.ch/",
        note="Homepage contact is Loëstrasse 220, 7000 Chur.",
    ),
    WebsiteRecord(
        organization_name="Psychiatrische Dienste Graubünden",
        site_name="PDGR Klinik Waldhaus",
        url="https://www.pdgr.ch/standorte/klinik-waldhaus-chur/",
        language="de",
        source="https://www.pdgr.ch/standorte/klinik-waldhaus-chur/",
        note="The page places Klinik Waldhaus at Loëstrasse 220, 7000 Chur.",
    ),
    WebsiteRecord(
        organization_name="Psychiatrische Dienste Graubünden",
        site_name="PDGR Klinik Beverin",
        url="https://www.pdgr.ch/standorte/standort-beverin/",
        language="de",
        source="https://www.pdgr.ch/standorte/standort-beverin/",
        note="The page places Klinik Beverin at La Nicca Strasse 17, 7408 Cazis. The 2024 street cell is empty.",
    ),
    WebsiteRecord(
        organization_name="Psychiatrische Dienste Graubünden",
        site_name="PDGR Tagesklinik Glarus",
        url="https://www.pdgr.ch/start-psychiatrische-dienste-glarus-ueberfuehrung-atk-glarus/",
        language="de",
        source="https://www.pdgr.ch/start-psychiatrische-dienste-glarus-ueberfuehrung-atk-glarus/",
        note="PDGR says the Glarus day clinic moved to Psychiatrische Dienste Glarus, www.pdgl.ch, on 1 July 2025. The 2024 row remains a PDGR site.",
    ),
    *_same_site(
        "Clinica Holistica Engiadina SA",
        "Clinica Holistica Susch",
        "https://www.clinica-holistica.ch/de",
        "de",
        "https://www.clinica-holistica.ch/de",
        "The opened page gives Plaz 40, 7542 Susch.",
    ),
    *_same_site(
        "Hochgebirgsklinik Davos AG",
        "Hochgebirgsklinik Davos",
        "https://hochgebirgsklinik.ch/",
        "de",
        "https://hochgebirgsklinik.ch/",
        "The opened page gives Herman-Burchard-Strasse 1, 7265 Davos Wolfgang. The BSH list also prints www.hgk.ch. " + BSH_MEMBERS,
    ),
    *_same_site(
        "Rehabilitationszentrum Seewis Klinik für Herz- & Kreislauferkrankungen",
        "Reha Seewis",
        "https://www.rehaklinik-seewis.ch/de/",
        "de",
        "https://www.rehaklinik-seewis.ch/de/",
        "The opened page gives Schlossstrasse 1, 7212 Seewis.",
    ),
    *_same_site(
        "Rehazentrum Chur",
        "Rehazentrum Chur",
        "https://valens.ch/reha-chur/",
        "de",
        "https://valens.ch/reha-chur/kontakt/",
        "The clinic page gives Loëstrasse 99, 7000 Chur. The BSH address www.rehazentrum-chur.ch returns a hosting placeholder, not the clinic.",
    ),
    *_same_site(
        "reha andeer ag Rehabilitationsklinik",
        "reha andeer ag",
        "https://reha-andeer.ch/de/die-reha-andeer",
        "de",
        "https://reha-andeer.ch/de/die-reha-andeer",
        "The opened page gives Veia Granda 44, 7440 Andeer. The 2024 street cell is Veia Granda, without the house number.",
    ),
    WebsiteRecord(
        organization_name="Klinik Gut St. Moritz AG",
        url="https://www.klinik-gut.ch/",
        language="de",
        source="https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz",
        note="The opened locations page names Klinik Gut St. Moritz and Klinik Gut Fläsch. The 2024 St. Moritz street is Via Arona 34. The page gives Via Paracelsus 2a and Plazza Paracelsus 2a.",
    ),
    WebsiteRecord(
        organization_name="Klinik Gut St. Moritz AG",
        site_name="Klinik Gut St. Moritz",
        url="https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz",
        language="de",
        source="https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz",
        note="Page address Via Paracelsus 2a, 7500 St. Moritz. The 2024 key-figure street is Via Arona 34.",
    ),
    WebsiteRecord(
        organization_name="Klinik Gut St. Moritz AG",
        site_name=SITE_FLAESCH,
        url="https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz",
        language="de",
        source="https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz",
        note="The same page gives Steigstrasse 12, 7306 Fläsch. The 2024 site name contains a question mark in place of ä.",
    ),
    *_same_site(
        "Flury Stiftung Spital Schiers",
        "Flury Stiftung Spital Schiers",
        "https://www.flurystiftung.ch/de/spital-schiers",
        "de",
        "https://www.flurystiftung.ch/de/spital-schiers",
        "The opened page gives Tersierstrasse 7, 7220 Schiers. The 2024 street cell is empty.",
    ),
]
