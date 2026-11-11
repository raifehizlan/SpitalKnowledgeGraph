"""Names transcribed from the Graubünden hospital page.

The page was opened on 2026-11-10. This is not a live fetch. A later crawl
has to open the page again. These strings are matched only by
`exact_normalized_name_2024`.
"""

from __future__ import annotations

PAGE_URL = (
    "https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/"
    "InstitutionenGesundeitswesens/Spitaeler/Seiten/default.aspx"
)
PAGE_NOTE = (
    "Transcribed from the cantonal page opened on 2026-11-10. "
    "Not a live fetch. Subsidized acute hospitals, then Psychiatrische Dienste Graubünden."
)

# Order is the order of the opened page.
NAMES = [
    "Kantonsspital Graubünden",
    "Spital Oberengadin",
    "Gesundheitszentrum Unterengadin",
    "Spital Davos",
    "Regionalspital Surselva",
    "Spital Thusis",
    "Gesundheitszentrum Savognin",
    "Flury Stiftung - Spital Schiers",
    "Center da sandà Val Müstair",
    "Center Sanitario Valposchiavo",
    "Centro Sanitario Bregaglia",
    "Psychiatrische Dienste Graubünden",
]
