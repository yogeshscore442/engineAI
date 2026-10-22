"""
catalog/test_catalog.py — Canonical test names, aliases, LOINC codes, default ref ranges.
New entries = add to CATALOG dict; no other changes needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestEntry:
    __test__ = False
    canonical: str
    loinc: Optional[str]
    default_unit: Optional[str]
    ref_low: Optional[float]
    ref_high: Optional[float]
    aliases: list[str] = field(default_factory=list)



CATALOG: list[TestEntry] = [
    TestEntry(
        canonical="HbA1c",
        loinc="4548-4",
        default_unit="%",
        ref_low=4.0,
        ref_high=5.7,
        aliases=["hba1c", "glycated hemoglobin", "hemoglobin a1c", "a1c", "hb a1c"],
    ),
    TestEntry(
        canonical="Fasting Blood Glucose",
        loinc="1558-6",
        default_unit="mg/dL",
        ref_low=70.0,
        ref_high=100.0,
        aliases=["fbg", "fasting glucose", "blood sugar fasting", "fasting blood sugar", "fbs"],
    ),
    TestEntry(
        canonical="Post-Prandial Blood Glucose",
        loinc="1521-4",
        default_unit="mg/dL",
        ref_low=70.0,
        ref_high=140.0,
        aliases=["ppbg", "post meal glucose", "post prandial glucose", "postprandial blood sugar", "ppbs"],
    ),
    TestEntry(
        canonical="Serum Creatinine",
        loinc="2160-0",
        default_unit="mg/dL",
        ref_low=0.6,
        ref_high=1.2,
        aliases=["creatinine", "serum creat", "s creatinine"],
    ),
    TestEntry(
        canonical="eGFR",
        loinc="62238-1",
        default_unit="mL/min/1.73m²",
        ref_low=60.0,
        ref_high=120.0,
        aliases=["egfr", "estimated gfr", "glomerular filtration rate"],
    ),
    TestEntry(
        canonical="Total Cholesterol",
        loinc="2093-3",
        default_unit="mg/dL",
        ref_low=0.0,
        ref_high=200.0,
        aliases=["cholesterol", "total chol", "tc"],
    ),
    TestEntry(
        canonical="LDL Cholesterol",
        loinc="2089-1",
        default_unit="mg/dL",
        ref_low=0.0,
        ref_high=100.0,
        aliases=["ldl", "ldl-c", "low density lipoprotein"],
    ),
    TestEntry(
        canonical="HDL Cholesterol",
        loinc="2085-9",
        default_unit="mg/dL",
        ref_low=40.0,
        ref_high=200.0,
        aliases=["hdl", "hdl-c", "high density lipoprotein"],
    ),
    TestEntry(
        canonical="Triglycerides",
        loinc="2571-8",
        default_unit="mg/dL",
        ref_low=0.0,
        ref_high=150.0,
        aliases=["tg", "trigs", "triglyceride"],
    ),
    TestEntry(
        canonical="TSH",
        loinc="3016-3",
        default_unit="mIU/L",
        ref_low=0.4,
        ref_high=4.0,
        aliases=["tsh", "thyroid stimulating hormone", "thyrotropin"],
    ),
    TestEntry(
        canonical="Haemoglobin",
        loinc="718-7",
        default_unit="g/dL",
        ref_low=12.0,
        ref_high=17.5,
        aliases=["hb", "hemoglobin", "haemoglobin"],
    ),
    TestEntry(
        canonical="WBC Count",
        loinc="6690-2",
        default_unit="10³/μL",
        ref_low=4.5,
        ref_high=11.0,
        aliases=["wbc", "white blood cell count", "leucocyte count", "leukocyte count"],
    ),
    TestEntry(
        canonical="Platelet Count",
        loinc="777-3",
        default_unit="10³/μL",
        ref_low=150.0,
        ref_high=400.0,
        aliases=["platelets", "platelet", "plt"],
    ),
    TestEntry(
        canonical="Serum ALT",
        loinc="1742-6",
        default_unit="U/L",
        ref_low=7.0,
        ref_high=56.0,
        aliases=["alt", "sgpt", "alanine aminotransferase"],
    ),
    TestEntry(
        canonical="Serum AST",
        loinc="1920-8",
        default_unit="U/L",
        ref_low=10.0,
        ref_high=40.0,
        aliases=["ast", "sgot", "aspartate aminotransferase"],
    ),
    TestEntry(
        canonical="Serum Sodium",
        loinc="2951-2",
        default_unit="mEq/L",
        ref_low=136.0,
        ref_high=145.0,
        aliases=["sodium", "na+", "serum na"],
    ),
    TestEntry(
        canonical="Serum Potassium",
        loinc="2823-3",
        default_unit="mEq/L",
        ref_low=3.5,
        ref_high=5.0,
        aliases=["potassium", "k+", "serum k"],
    ),
    TestEntry(
        canonical="Uric Acid",
        loinc="3084-1",
        default_unit="mg/dL",
        ref_low=2.4,
        ref_high=7.0,
        aliases=["uric acid", "serum uric acid", "sua"],
    ),
    TestEntry(
        canonical="Vitamin D",
        loinc="14635-7",
        default_unit="ng/mL",
        ref_low=20.0,
        ref_high=100.0,
        aliases=["vitamin d", "25-oh vitamin d", "vit d", "25(oh)d"],
    ),
    TestEntry(
        canonical="Vitamin B12",
        loinc="2132-9",
        default_unit="pg/mL",
        ref_low=200.0,
        ref_high=900.0,
        aliases=["vitamin b12", "b12", "cobalamin", "cyanocobalamin"],
    ),
    # ── Apollo 24/7 Expanded Diagnostics Panel ────────────────────────────────
    TestEntry(
        canonical="RBC Count",
        loinc="789-8",
        default_unit="10^6/μL",
        ref_low=4.0,
        ref_high=5.5,
        aliases=["rbc", "red blood cell count", "total rbc", "erythrocyte count"],
    ),
    TestEntry(
        canonical="Hematocrit",
        loinc="4544-3",
        default_unit="%",
        ref_low=36.0,
        ref_high=50.0,
        aliases=["hematocrit", "pcv", "packed cell volume", "hct"],
    ),
    TestEntry(
        canonical="Serum Bilirubin Total",
        loinc="1975-2",
        default_unit="mg/dL",
        ref_low=0.2,
        ref_high=1.2,
        aliases=["bilirubin", "total bilirubin", "serum bilirubin", "s. bilirubin"],
    ),
    TestEntry(
        canonical="Direct Bilirubin",
        loinc="1968-7",
        default_unit="mg/dL",
        ref_low=0.0,
        ref_high=0.3,
        aliases=["direct bilirubin", "conjugated bilirubin", "d bilirubin"],
    ),
    TestEntry(
        canonical="Indirect Bilirubin",
        loinc="1971-1",
        default_unit="mg/dL",
        ref_low=0.2,
        ref_high=0.8,
        aliases=["indirect bilirubin", "unconjugated bilirubin", "id bilirubin"],
    ),
    TestEntry(
        canonical="Serum Urea",
        loinc="22703-3",
        default_unit="mg/dL",
        ref_low=15.0,
        ref_high=40.0,
        aliases=["urea", "serum urea", "blood urea", "bun"],
    ),
    TestEntry(
        canonical="Total Protein",
        loinc="2885-2",
        default_unit="g/dL",
        ref_low=6.0,
        ref_high=8.3,
        aliases=["total protein", "serum protein", "tp"],
    ),
    TestEntry(
        canonical="Serum Albumin",
        loinc="1751-7",
        default_unit="g/dL",
        ref_low=3.5,
        ref_high=5.0,
        aliases=["albumin", "serum albumin", "alb"],
    ),
    TestEntry(
        canonical="Serum Globulin",
        loinc="2336-6",
        default_unit="g/dL",
        ref_low=2.0,
        ref_high=3.5,
        aliases=["globulin", "serum globulin", "glob"],
    ),
    TestEntry(
        canonical="A/G Ratio",
        loinc="1759-0",
        default_unit="ratio",
        ref_low=1.0,
        ref_high=2.5,
        aliases=["a/g ratio", "ag ratio", "albumin globulin ratio"],
    ),
    TestEntry(
        canonical="Alkaline Phosphatase",
        loinc="6768-6",
        default_unit="U/L",
        ref_low=44.0,
        ref_high=147.0,
        aliases=["alp", "alkaline phosphatase", "alk phos"],
    ),
    TestEntry(
        canonical="Serum Calcium",
        loinc="17861-6",
        default_unit="mg/dL",
        ref_low=8.5,
        ref_high=10.5,
        aliases=["calcium", "serum calcium", "total calcium", "ca++"],
    ),
    TestEntry(
        canonical="Serum Phosphorus",
        loinc="2777-1",
        default_unit="mg/dL",
        ref_low=2.5,
        ref_high=4.5,
        aliases=["phosphorus", "serum phosphorus", "phosphate", "po4"],
    ),
    TestEntry(
        canonical="Serum Chloride",
        loinc="2075-0",
        default_unit="mEq/L",
        ref_low=96.0,
        ref_high=106.0,
        aliases=["chloride", "serum chloride", "cl-"],
    ),
    TestEntry(
        canonical="hs-CRP",
        loinc="30522-7",
        default_unit="mg/L",
        ref_low=0.0,
        ref_high=3.0,
        aliases=["crp", "hs-crp", "c-reactive protein", "high sensitivity crp"],
    ),
    TestEntry(
        canonical="D-Dimer",
        loinc="48065-7",
        default_unit="ng/mL",
        ref_low=0.0,
        ref_high=500.0,
        aliases=["d-dimer", "d dimer", "fibrin degradation fragment"],
    ),
    TestEntry(
        canonical="Troponin I",
        loinc="10839-9",
        default_unit="ng/mL",
        ref_low=0.0,
        ref_high=0.04,
        aliases=["troponin", "trop i", "troponin i", "hs-tropi"],
    ),
    TestEntry(
        canonical="Random Blood Glucose",
        loinc="2345-7",
        default_unit="mg/dL",
        ref_low=70.0,
        ref_high=140.0,
        aliases=["rbs", "random blood sugar", "random glucose", "rbg"],
    ),
    TestEntry(
        canonical="Total T3",
        loinc="3049-7",
        default_unit="ng/dL",
        ref_low=80.0,
        ref_high=200.0,
        aliases=["t3", "total t3", "triiodothyronine"],
    ),
    TestEntry(
        canonical="Total T4",
        loinc="3026-2",
        default_unit="μg/dL",
        ref_low=4.5,
        ref_high=12.0,
        aliases=["t4", "total t4", "thyroxine"],
    ),
    TestEntry(
        canonical="Free T3",
        loinc="3051-3",
        default_unit="pg/mL",
        ref_low=2.0,
        ref_high=4.4,
        aliases=["ft3", "free t3"],
    ),
    TestEntry(
        canonical="Free T4",
        loinc="3024-7",
        default_unit="ng/dL",
        ref_low=0.8,
        ref_high=1.8,
        aliases=["ft4", "free t4"],
    ),
    TestEntry(
        canonical="ESR",
        loinc="4537-7",
        default_unit="mm/hr",
        ref_low=0.0,
        ref_high=20.0,
        aliases=["esr", "erythrocyte sedimentation rate"],
    ),
]

# Build lookup index: alias -> entry
_ALIAS_INDEX: dict[str, TestEntry] = {}
for _entry in CATALOG:
    _ALIAS_INDEX[_entry.canonical.lower()] = _entry
    for _alias in _entry.aliases:
        _ALIAS_INDEX[_alias.lower()] = _entry


def lookup(name: str) -> Optional[TestEntry]:
    """Return TestEntry for a given test name (case-insensitive alias match)."""
    return _ALIAS_INDEX.get(name.strip().lower())
