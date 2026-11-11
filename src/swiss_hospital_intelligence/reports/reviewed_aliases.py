"""Reviewed identities for the Graubünden cantonal page.

These are not string matches. Each row was accepted on 2026-11-10 because the
cantonal acute-hospital list, the cantonal Spitalliste, and the hospital's own
address name one 2024 key-figure establishment. `exact_normalized_name_2024`
stays unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel

METHOD = "reviewed_same_establishment"
SPITALLISTE_URL = (
    "https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/"
    "InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste_Akutsomatik.pdf"
)


class ReviewedAlias(BaseModel):
    source_name: str
    organization_name: str
    method: str = METHOD
    evidence: str


ALIASES = [
    ReviewedAlias(
        source_name="Gesundheitszentrum Unterengadin",
        organization_name="Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
        evidence=(
            "The Ospidal site uses both names at Via da l'Ospidal 280, 7550 Scuol, "
            "the 2024 key-figure address. The cantonal Spitalliste names "
            "CSEB / CENTER DA SANDÀ ENGIADINA BASSA, Scuol. "
            "Spitex, the nursing homes, and Bogn Engiadina are other operations of the Stiftung "
            "and are not this row. https://cseb.ch/betriebe/ospidal/ "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Spital Davos",
        organization_name="Spital Davos AG Akutabteilung",
        evidence=(
            "Spital Davos AG gives Promenade 4, 7270 Davos Platz, the 2024 address of the "
            "Akutabteilung row. The Spitalliste Leistungsauftrag is Spital Davos AG, Davos Platz. "
            "Pflegeheim Alberti is another operation at the house and is not a second key-figure row. "
            "https://www.spitaldavos.ch/de " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Regionalspital Surselva",
        organization_name="Regionalspital Surselva AG",
        evidence=(
            "The page omits the legal suffix. The Spitalliste and the 2026 acute tariff both name "
            "Regionalspital Surselva AG, Ilanz. The 2024 address is Spitalstrasse 6, 7130 Ilanz. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Gesundheitszentrum Savognin",
        organization_name="Center da Sanadad Savognin SA",
        evidence=(
            "The SA calls itself the regional Gesundheitszentrum at Stradung 52, 7460 Savognin, "
            "the 2024 address. The Spitalliste and the 2026 tariff use the SA name. "
            "The nursing home belongs to the same SA and is not a second key-figure hospital. "
            "https://www.cds-savognin.ch/DE/home.html " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Flury Stiftung - Spital Schiers",
        organization_name="Flury Stiftung Spital Schiers",
        evidence=(
            "The page adds a hyphen. The Spitalliste says Flury Stiftung – Spital, Schiers, "
            "and the 2026 tariff says Flury Stiftung (Spital Schiers). "
            "The 2024 place is 7220 Schiers. The key-figure street cell is empty. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Center da sandà Val Müstair",
        organization_name="Center da Sanda Val Müstair Akutabteilung",
        evidence=(
            "The hospital site uses Center da sandà Val Müstair at Via Val Müstair 186, "
            "7536 Sta. Maria, the 2024 address. The Spitalliste uses that name at Sta. Maria. "
            "The key-figure name adds Akutabteilung and spells Sanda without the accent. "
            "The nursing home and Spitex are not a second key-figure hospital. "
            "http://csvm.ch/de/ " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Center Sanitario Valposchiavo",
        organization_name="Centro Sanitario Valposchiavo Ospedale San Sisto",
        evidence=(
            "The page spells Center. Ospedale San Sisto of Centro sanitario Valposchiavo is at "
            "Via da li Clüsüri 1, 7742 Poschiavo, the 2024 address. "
            "Casa Anziani is at Via da Sottsassa 2 and is not this row. "
            "The Spitalliste names Fondazione Centro sanitario Valposchiavo, Poschiavo. "
            "https://www.csvp.ch/it/ " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Centro Sanitario Bregaglia",
        organization_name="Centro Sanitario Bregaglia Reparto Acuto",
        evidence=(
            "The center places its acute ward at Flin, 7606 Promontogno. "
            "The 2024 street is Flin and the place is 7606 Promontogno; the row name adds Reparto Acuto. "
            "The Spitalliste says Centro sanitario Bregaglia, Promontogno. "
            "Long-term care at the same site is not a second key-figure hospital. "
            "https://www.csbregaglia.ch/it/ " + SPITALLISTE_URL
        ),
    ),
]

SPITALLISTE_ALIASES = [
    ReviewedAlias(
        source_name="CSEB / CENTER DA SANDÀ ENGIADINA BASSA, Scuol",
        organization_name="Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
        evidence=(
            "The acute Spitalliste prints this heading for the Ospidal at Scuol. "
            "The 2024 key-figure name is the same establishment. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Center da sandà Engiadina Bassa / Gesundheitszentrum Unterengadin, Scuol",
        organization_name="Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
        evidence=(
            "The psychiatry Spitalliste prints both names in one heading. "
            "They are the Ospidal at Via da l'Ospidal 280, 7550 Scuol, not Spitex or the nursing homes. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Gesundheitszentrum Unterengadin, Scuol",
        organization_name="Center da Sanda Engiadina Bassa Ospidal d'Engiadina Bassa",
        evidence=(
            "The rehabilitation Spitalliste adds the town to the cantonal name already reviewed. "
            "The place is Scuol, the 2024 address of the Ospidal. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Spital Davos AG, Davos Platz",
        organization_name="Spital Davos AG Akutabteilung",
        evidence=(
            "The acute Spitalliste heading is the Akutabteilung at Promenade 4, 7270 Davos Platz. "
            "Pflegeheim Alberti is not this row. https://www.spitaldavos.ch/de " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Flury Stiftung – Spital, Schiers",
        organization_name="Flury Stiftung Spital Schiers",
        evidence=(
            "The acute Spitalliste inserts an en dash and a comma before Schiers. "
            "The 2024 place is 7220 Schiers. " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Center da sandà Val Müstair, Sta. Maria",
        organization_name="Center da Sanda Val Müstair Akutabteilung",
        evidence=(
            "The acute Spitalliste adds Sta. Maria to the name already reviewed. "
            "The 2024 address is Via Val Müstair 186, 7536 Sta. Maria. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Fondazione Centro sanitario Valposchiavo, Poschiavo",
        organization_name="Centro Sanitario Valposchiavo Ospedale San Sisto",
        evidence=(
            "The acute Spitalliste names the Fondazione. Ospedale San Sisto is the 2024 row "
            "at Via da li Clüsüri 1, 7742 Poschiavo. Casa Anziani is not this row. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Centro sanitario Bregaglia, Promotogno",
        organization_name="Centro Sanitario Bregaglia Reparto Acuto",
        evidence=(
            "The acute Spitalliste names the center at Promontogno. "
            "The 2024 row is the acute ward at Flin, 7606 Promontogno. "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Spital Oberengadin AG, Samedan",
        organization_name="Spital Oberengadin",
        evidence=(
            "The acute Spitalliste adds AG. The 2024 name omits it. "
            "The address is Via Nouva 3, 7503 Samedan. https://www.spital-oberengadin.ch/ "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Klinik Gut, St. Moritz und Fläsch",
        organization_name="Klinik Gut St. Moritz AG",
        evidence=(
            "The acute Spitalliste names both sites of one establishment. "
            "The 2024 row is Klinik Gut St. Moritz AG, with sites in St. Moritz and Fläsch. "
            "https://www.klinik-gut.ch/de/standorte/klinik-gut-st-moritz " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Clinica Holistica Engiadina, Susch",
        organization_name="Clinica Holistica Engiadina SA",
        evidence=(
            "The psychiatry Spitalliste omits SA and adds Susch. "
            "The 2024 address is Plaz 40, 7542 Susch. https://www.clinica-holistica.ch/de "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Hochgebirgsklinik Davos, Davos Wolfgang",
        organization_name="Hochgebirgsklinik Davos AG",
        evidence=(
            "The psychiatry and rehabilitation lists omit AG. "
            "The 2024 address is Herman-Burchard-Strasse 1, 7265 Davos Wolfgang. "
            "https://hochgebirgsklinik.ch/ " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Psychiatrische Dienste Graubünden Klinik Beverin, Cazis, und Klinik Waldhaus, Chur",
        organization_name="Psychiatrische Dienste Graubünden",
        evidence=(
            "The psychiatry Spitalliste names Klinik Beverin and Klinik Waldhaus in one heading. "
            "Both are sites of Psychiatrische Dienste Graubünden. The mandate is not given a site. "
            "https://www.pdgr.ch/ " + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Reha Seewis, Seewis",
        organization_name="Rehabilitationszentrum Seewis Klinik für Herz- & Kreislauferkrankungen",
        evidence=(
            "The psychiatry and rehabilitation lists shorten the name and repeat Seewis. "
            "The 2024 address is Schlossstrasse 1, 7212 Seewis. https://www.rehaklinik-seewis.ch/de/ "
            + SPITALLISTE_URL
        ),
    ),
    ReviewedAlias(
        source_name="Reha Andeer, Andeer",
        organization_name="reha andeer ag Rehabilitationsklinik",
        evidence=(
            "The rehabilitation Spitalliste shortens the name and repeats Andeer. "
            "The 2024 address is Veia Granda 44, 7440 Andeer. https://reha-andeer.ch/de/die-reha-andeer "
            + SPITALLISTE_URL
        ),
    ),
]
