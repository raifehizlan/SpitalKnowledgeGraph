"""Measure columns in the BAG key-figure workbook.

Activity type is declared here. A trailing letter is not an activity code:
``PersA`` means physicians, not acute care.
"""

from __future__ import annotations

from dataclasses import dataclass

# Columns present in the 2024 edition and left empty because BAG did not publish them.
# A filled cell is still kept. An empty cell does not become 270 observations.
UNPUBLISHED_MEASURES: frozenset[str] = frozenset(
    {
        "PflegetageT",
        "PTageLangT",
        "AustLangT",
        "KostLangT",
        "ErlLangT",
        "KostABT",
        "KostWBT",
        "KostForT",
        "KostAmbT",
        "KostOKPAmbT",
        "ErlAmbT",
        "ErlOKPAmbT",
        "PflegetageA",
        "PflegetageP",
        "PflegetageR",
        "PflegetageB",
        "DADA",
        "DADP",
        "DADR",
        "DADB",
        "pBettenBelStatA",
        "pBettenBelStatP",
        "pBettenBelStatR",
        "pBettenBelStatB",
        "KostStatA",
        "KostKVGStatA",
        "AnlKVGStatA",
        "KostZvOKPStatA",
        "AnlZvOKPStatA",
        "ErlStatA",
        "ErlKVGStatA",
        "ErlKVGStatVA",
        "ErlZvOKPStatA",
        "ErlZvOKPStatVA",
        "KostStatP",
        "KostKVGStatP",
        "AnlKVGStatP",
        "KostZvOKPStatP",
        "AnlZvOKPStatP",
        "ErlStatP",
        "ErlKVGStatP",
        "ErlKVGStatVP",
        "ErlZvOKPStatP",
        "ErlZvOKPStatVP",
        "KostStatR",
        "KostKVGStatR",
        "AnlKVGStatR",
        "KostZvOKPStatR",
        "AnlZvOKPStatR",
        "ErlStatR",
        "ErlKVGStatR",
        "ErlKVGStatVR",
        "ErlZvOKPStatR",
        "ErlZvOKPStatVR",
        "KostStatB",
        "KostKVGStatB",
        "AnlKVGStatB",
        "KostZvOKPStatB",
        "AnlZvOKPStatB",
        "ErlStatB",
        "ErlKVGStatB",
        "ErlKVGStatVB",
        "ErlZvOKPStatB",
        "ErlZvOKPStatVB",
    }
)

IDENTITY_COLUMNS: frozenset[str] = frozenset(
    {
        "JAHR",
        "KT",
        "Inst",
        "Adr",
        "Ort",
        "Typ",
        "RForm",
        "Akt",
        "SL",
        "WB",
        "AnzStand",
        "SA",
        "LA",
    }
)


@dataclass(frozen=True)
class MeasureSpec:
    code: str
    unit: str
    activity_type: str | None
    scope: str = "establishment"


def _activity_measures(base: str, unit: str, activities: tuple[str, ...]) -> dict[str, MeasureSpec]:
    return {f"{base}{activity}": MeasureSpec(f"{base}{activity}", unit, activity) for activity in activities}


PUBLISHED_MEASURES: dict[str, MeasureSpec] = {
    "AmbPatKont": MeasureSpec("AmbPatKont", "contact", None),
    "AustritteT": MeasureSpec("AustritteT", "case", None),
    "NeugT": MeasureSpec("NeugT", "count", None),
    "Ops": MeasureSpec("Ops", "count", None),
    "Gebs": MeasureSpec("Gebs", "count", None),
    "pPatWAU": MeasureSpec("pPatWAU", "percent", None),
    "pPatWAK": MeasureSpec("pPatWAK", "percent", None),
    "pPatLKP": MeasureSpec("pPatLKP", "percent", None),
    "pPatHOK": MeasureSpec("pPatHOK", "percent", None),
    "pMRI_AMB": MeasureSpec("pMRI_AMB", "per_device", None),
    "pMRI_STAT": MeasureSpec("pMRI_STAT", "per_device", None),
    "pCT_AMB": MeasureSpec("pCT_AMB", "per_device", None),
    "pCT_STAT": MeasureSpec("pCT_STAT", "per_device", None),
    "pANGIO_AMB": MeasureSpec("pANGIO_AMB", "per_device", None),
    "pANGIO_STAT": MeasureSpec("pANGIO_STAT", "per_device", None),
    "pDIA_AMB": MeasureSpec("pDIA_AMB", "per_device", None),
    "pDIA_STAT": MeasureSpec("pDIA_STAT", "per_device", None),
    "PersA": MeasureSpec("PersA", "fte", None),
    "PersAWB": MeasureSpec("PersAWB", "fte", None),
    "PersP": MeasureSpec("PersP", "fte", None),
    "PersMT": MeasureSpec("PersMT", "fte", None),
    "PersT": MeasureSpec("PersT", "fte", None),
    "StdBelA": MeasureSpec("StdBelA", "hour", None),
    "StdBelP": MeasureSpec("StdBelP", "hour", None),
    "AwBesold": MeasureSpec("AwBesold", "undeclared", None),
    "AwInvest": MeasureSpec("AwInvest", "undeclared", None),
    "AwSonst": MeasureSpec("AwSonst", "undeclared", None),
    "AwT": MeasureSpec("AwT", "undeclared", None),
    "EtMedL": MeasureSpec("EtMedL", "undeclared", None),
    "EtSonst": MeasureSpec("EtSonst", "undeclared", None),
    "EtSubv": MeasureSpec("EtSubv", "undeclared", None),
    "EtDef": MeasureSpec("EtDef", "undeclared", None),
    "EtT": MeasureSpec("EtT", "undeclared", None),
    "FiErg": MeasureSpec("FiErg", "undeclared", None),
    "CMIbA": MeasureSpec("CMIbA", "index", "A"),
    "CMInA": MeasureSpec("CMInA", "index", "A"),
    "CMIbB": MeasureSpec("CMIbB", "index", "B"),
    "CMInB": MeasureSpec("CMInB", "index", "B"),
    "DMI_P": MeasureSpec("DMI_P", "index", "P"),
    "DMI_R": MeasureSpec("DMI_R", "index", "R"),
}
PUBLISHED_MEASURES.update(_activity_measures("Austritte", "case", ("A", "P", "R", "B")))
PUBLISHED_MEASURES.update(
    _activity_measures("BettenStat", "bed_operating_average", ("A", "P", "R", "B"))
)
