"""
medicine_catalog.py — Indian Medicine Catalog, Abbreviation Normalizer & Safety Adapter.

Official Data Sources:
1. National List of Essential Medicines (NLEM 2022) — Ministry of Health & Family Welfare, Govt. of India.
2. Pradhan Mantri Bharatiya Janaushadhi Pariyojana (PMBJP) — Department of Pharmaceuticals, Govt. of India.
3. Curated Indian Brand & Generic Formulations (brands.csv & jan_aushadhi.csv).

Key Safety Principles (Zero Hallucination / Responsible AI):
- Distinguishes: (1) name as written, (2) normalized generic, (3) verified catalog match, (4) review candidates.
- Fuzzy matching is strictly used to SUGGEST CANDIDATES for human confirmation, never for silent substitution.
- Does not automatically substitute medicines or recommend prescription-only alternatives.
- Unverified medicines are explicitly labeled "Medicine not verified in catalog", preserving raw extracted text.
- Pharmacy search URLs link only to official/configured portals (PMBJP) with explicit price/availability disclaimers.
"""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Common Indian Doctor Handwriting & Shorthand Abbreviations
INDIAN_MED_ABBREVIATIONS: dict[str, str] = {
    "pcm": "Paracetamol",
    "pcm 650": "Paracetamol 650 mg",
    "pcm 500": "Paracetamol 500 mg",
    "amox": "Amoxicillin",
    "amox 500": "Amoxicillin 500 mg",
    "amox-cv": "Amoxicillin + Clavulanate",
    "amoxyclav": "Amoxicillin + Clavulanate",
    "aug": "Augmentin",
    "azith": "Azithromycin",
    "azithro": "Azithromycin",
    "azith 500": "Azithromycin 500 mg",
    "cipro": "Ciprofloxacin",
    "levo": "Levofloxacin",
    "oflox": "Ofloxacin",
    "met": "Metformin",
    "met 500": "Metformin 500 mg",
    "glyco": "Glycomet",
    "pantop": "Pantoprazole",
    "pan": "Pantoprazole",
    "pan 40": "Pantoprazole 40 mg",
    "pan-d": "Pantoprazole + Domperidone",
    "rab": "Rabeprazole",
    "rab-d": "Rabeprazole + Domperidone",
    "omz": "Omeprazole",
    "telma": "Telmisartan",
    "telmi": "Telmisartan",
    "telma 40": "Telmisartan 40 mg",
    "ator": "Atorvastatin",
    "atorva": "Atorvastatin",
    "atorlip": "Atorvastatin",
    "rosuv": "Rosuvastatin",
    "rosuvas": "Rosuvastatin",
    "cet": "Cetirizine",
    "ceti": "Cetirizine",
    "cetiriz": "Cetirizine",
    "cetirizine 10": "Cetirizine 10 mg",
    "mont": "Montelukast",
    "mont-lc": "Montelukast + Levocetirizine",
    "levocet": "Levocetirizine",
    "para": "Paracetamol",
    "dolo": "Paracetamol 650 mg",
    "crocin": "Paracetamol 500 mg",
    "meftal": "Mefenamic Acid",
    "meftal spas": "Mefenamic Acid + Dicyclomine",
    "ondem": "Ondansetron",
    "emeset": "Ondansetron",
    "dom": "Domperidone",
    "vomistop": "Domperidone",
    "ranit": "Ranitidine",
    "zantac": "Ranitidine",
    "ascoril": "Terbutaline + Bromhexine + Guaifenesin",
    "grilinctus": "Dextromethorphan + Chlorpheniramine",
    "glycomet": "Metformin",
    "januvia": "Sitagliptin",
    "galvus": "Vildagliptin",
    "cilacar": "Cilnidipine",
    "amlong": "Amlodipine",
    "ecosprin": "Aspirin",
    "clopilet": "Clopidogrel",
    "opox": "Cefpodoxime Proxetil",
    "opox-cv": "Cefpodoxime Proxetil + Clavulanic Acid",
    "opox-cv 200": "Cefpodoxime Proxetil + Clavulanic Acid 200 mg",
    "allose": "Aceclofenac + Paracetamol + Serratiopeptidase",
    "allose-sp": "Aceclofenac + Paracetamol + Serratiopeptidase",
    "breezy": "Levosalbutamol + Ambroxol + Guaiphenesin",
    "shipan": "Pantoprazole",
    "shipan-d": "Pantoprazole + Domperidone",
    "shipan-d 40": "Pantoprazole + Domperidone 40 mg",
}

# Formulation keywords
FORMULATIONS: dict[str, str] = {
    "tab": "tablet",
    "tablet": "tablet",
    "cap": "capsule",
    "capsule": "capsule",
    "syp": "syrup",
    "syr": "syrup",
    "syrup": "syrup",
    "susp": "suspension",
    "suspension": "suspension",
    "inj": "injection",
    "injection": "injection",
    "oint": "ointment",
    "ointment": "ointment",
    "cream": "cream",
    "gel": "gel",
    "drops": "drops",
    "drop": "drops",
    "inhaler": "inhaler",
    "respules": "respules",
    "powder": "powder",
    "sachet": "sachet",
}

# Routes of administration
ROUTE_MAP: dict[str, str] = {
    "tablet": "oral",
    "capsule": "oral",
    "syrup": "oral",
    "suspension": "oral",
    "injection": "parenteral",
    "ointment": "topical",
    "cream": "topical",
    "gel": "topical",
    "drops": "ophthalmic/otic",
    "inhaler": "inhalation",
    "respules": "inhalation",
}

JAN_AUSHADHI_PORTAL_URL = "https://janaushadhi.gov.in/ProductList.aspx"


@dataclass
class CatalogEntry:
    brand: str
    generic: str
    strength: Optional[str]
    formulation: str = "tablet"
    route: str = "oral"
    is_pmbjp: bool = False
    pmbjp_price_inr: Optional[float] = None
    market_price_inr: Optional[float] = None


@dataclass
class MedicineVerificationResult:
    name_raw: str
    normalized_name: str
    generic: Optional[str]
    brand_name: Optional[str]
    strength: Optional[str]
    formulation: Optional[str]
    route: str
    verification_state: str  # "present_verified" | "requires_human_review" | "unverified"
    catalog_status: str       # "VERIFIED_EXACT" | "CANDIDATE_MATCH" | "UNVERIFIED"
    match_confidence: float
    review_candidates: list[str] = field(default_factory=list)
    pharmacy_info: Optional[dict[str, Any]] = None

    @property
    def jan_aushadhi_url(self) -> Optional[str]:
        if self.pharmacy_info:
            return self.pharmacy_info.get("search_portal")
        return None

    @property
    def pmbjp_price_inr(self) -> Optional[float]:
        if self.pharmacy_info:
            return self.pharmacy_info.get("pmbjp_price_inr")
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name_raw": self.name_raw,
            "normalized_name": self.normalized_name,
            "generic": self.generic,
            "brand_name": self.brand_name,
            "strength": self.strength,
            "formulation": self.formulation,
            "route": self.route,
            "verification_state": self.verification_state,
            "catalog_status": self.catalog_status,
            "match_confidence": round(self.match_confidence, 3),
            "review_candidates": self.review_candidates,
            "pharmacy_info": self.pharmacy_info,
            "jan_aushadhi_url": self.jan_aushadhi_url,
            "pmbjp_price_inr": self.pmbjp_price_inr,
        }


class MedicineCatalog:
    """Thread-safe Indian Medicine Terminology & Verification Engine."""
    _instance: Optional["MedicineCatalog"] = None

    def __init__(self):
        self._entries_by_brand: dict[str, CatalogEntry] = {}
        self._entries_by_generic: dict[str, list[CatalogEntry]] = {}
        self._search_keys: list[str] = []
        self._load_catalogs()

    @classmethod
    def get_instance(cls) -> "MedicineCatalog":
        if cls._instance is None:
            cls._instance = MedicineCatalog()
        return cls._instance

    def _clean_key(self, text: str) -> str:
        s = re.sub(r"(\d+)\s*(mg|mcg|g|ml|iu)\b", r"\1 \2", text.lower())
        return re.sub(r"[\s\-\.,/]+", " ", s).strip()

    def _extract_strength(self, text: str) -> Optional[str]:
        m = re.search(r"\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu)(?:\s*\+\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu))?)\b", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_formulation(self, text: str) -> str:
        words = re.findall(r"[a-z]+", text.lower())
        for w in words:
            if w in FORMULATIONS:
                return FORMULATIONS[w]
        return "tablet"

    def _load_catalogs(self) -> None:
        base_dir = Path(__file__).parent

        # 1. Load brands.csv
        brands_path = base_dir / "brands.csv"
        if brands_path.exists():
            try:
                with open(brands_path, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        brand = row.get("brand_name", "").strip()
                        generic = row.get("generic_name", "").strip()
                        strength = row.get("strength", "").strip() or None
                        if brand and generic:
                            form = self._extract_formulation(brand)
                            entry = CatalogEntry(
                                brand=brand,
                                generic=generic,
                                strength=strength or self._extract_strength(brand),
                                formulation=form,
                                route=ROUTE_MAP.get(form, "oral"),
                            )
                            k = self._clean_key(brand)
                            self._entries_by_brand[k] = entry
                            self._entries_by_generic.setdefault(self._clean_key(generic), []).append(entry)
            except Exception as e:
                logger.warning("Error loading brands.csv: %s", e)

        # 2. Load jan_aushadhi.csv
        ja_path = base_dir / "jan_aushadhi.csv"
        if ja_path.exists():
            try:
                with open(ja_path, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        brand = row.get("brand", "").strip()
                        generic = row.get("generic", "").strip()
                        strength = row.get("strength", "").strip() or None
                        mrp = float(row.get("market_price_inr", 0)) if row.get("market_price_inr") else None
                        jap = float(row.get("jan_aushadhi_price_inr", 0)) if row.get("jan_aushadhi_price_inr") else None
                        if brand and generic:
                            form = self._extract_formulation(brand)
                            entry = CatalogEntry(
                                brand=brand,
                                generic=generic,
                                strength=strength or self._extract_strength(brand),
                                formulation=form,
                                route=ROUTE_MAP.get(form, "oral"),
                                is_pmbjp=True,
                                pmbjp_price_inr=jap,
                                market_price_inr=mrp,
                            )
                            k = self._clean_key(brand)
                            self._entries_by_brand[k] = entry
                            self._entries_by_generic.setdefault(self._clean_key(generic), []).append(entry)
            except Exception as e:
                logger.warning("Error loading jan_aushadhi.csv: %s", e)

        self._search_keys = list(self._entries_by_brand.keys())
        logger.info("Loaded MedicineCatalog with %d brand entries", len(self._entries_by_brand))

    def get_generic_names(self) -> set[str]:
        return set(self._entries_by_generic.keys())

    def verify_medicine(self, raw_input: str) -> MedicineVerificationResult:
        """
        Takes raw written medicine text and resolves it against the verified catalog.
        Never fabricates an unverified drug. Fuzzy matches are returned as candidates for confirmation.
        """
        if not raw_input or not raw_input.strip():
            return MedicineVerificationResult(
                name_raw="",
                normalized_name="",
                generic=None,
                brand_name=None,
                strength=None,
                formulation=None,
                route="oral",
                verification_state="missing",
                catalog_status="UNVERIFIED",
                match_confidence=0.0,
                review_candidates=[],
            )

        clean_raw = raw_input.strip()
        key_raw = self._clean_key(clean_raw)
        formulation = self._extract_formulation(clean_raw)
        route = ROUTE_MAP.get(formulation, "oral")
        detected_strength = self._extract_strength(clean_raw)

        # 1. Exact Match against Brand Catalog
        key_without_unit = re.sub(r"\b(?:mg|mcg|g|ml|iu)\b", "", key_raw).strip()
        matched_brand_key = key_raw if key_raw in self._entries_by_brand else (key_without_unit if key_without_unit in self._entries_by_brand else None)
        if matched_brand_key:
            entry = self._entries_by_brand[matched_brand_key]
            strength = entry.strength or detected_strength
            return self._build_verified_result(clean_raw, entry, strength, 1.0)

        # 1b. Exact Match against Generic / Active Ingredient Catalog
        matched_gen_key = key_raw if key_raw in self._entries_by_generic else (key_without_unit if key_without_unit in self._entries_by_generic else None)
        if matched_gen_key:
            entry = self._entries_by_generic[matched_gen_key][0]
            strength = detected_strength or entry.strength
            return self._build_verified_result(clean_raw, entry, strength, 1.0)

        # 2. Check Indian Doctor Handwriting Shorthand Dictionary
        # (e.g. "PCM 650", "Dolo 650", "Ceti 10")
        for abbr, expanded in INDIAN_MED_ABBREVIATIONS.items():
            if key_raw == abbr or key_raw.startswith(abbr + " "):
                exp_key = self._clean_key(expanded)
                if exp_key in self._entries_by_brand:
                    entry = self._entries_by_brand[exp_key]
                    return self._build_candidate_result(
                        clean_raw,
                        entry.generic,
                        entry.brand,
                        entry.strength or detected_strength,
                        formulation,
                        route,
                        0.92,
                        review_candidates=[f"{entry.brand} ({entry.generic} {entry.strength or ''})".strip()],
                    )
                # Standalone expanded generic
                return self._build_candidate_result(
                    clean_raw,
                    expanded,
                    clean_raw,
                    detected_strength,
                    formulation,
                    route,
                    0.88,
                    review_candidates=[expanded],
                )

        # 3. Strip formulation prefixes ("Tab.", "Cap.", "Inj.", "Syp.")
        stripped = re.sub(r"^(?:tab(?:let)?|cap(?:sule)?|inj(?:ection)?|sy[rp](?:up)?|oint(?:ment)?|susp(?:ension)?)\s+", "", key_raw)
        if stripped in self._entries_by_brand:
            entry = self._entries_by_brand[stripped]
            return self._build_verified_result(clean_raw, entry, entry.strength or detected_strength, 0.98)

        # Strip unit suffix ("mg", "g", "ml")
        stripped_no_unit = re.sub(r"\s*(?:mg|mcg|g|ml|iu)\b", "", stripped).strip()
        if stripped_no_unit in self._entries_by_brand:
            entry = self._entries_by_brand[stripped_no_unit]
            return self._build_verified_result(clean_raw, entry, entry.strength or detected_strength, 0.95)

        # Strip trailing numbers (e.g. "dolo 650" -> "dolo")
        base_match = stripped_no_unit.rsplit(" ", 1)
        if len(base_match) == 2 and re.match(r"^\d", base_match[1]):
            base = base_match[0]
            if base in self._entries_by_brand:
                entry = self._entries_by_brand[base]
                return self._build_verified_result(clean_raw, entry, detected_strength or entry.strength, 0.90)

        # 4. Fuzzy Match (Candidate Discovery for Uncertain Handwriting)
        # Require minimum length >= 4 to prevent spurious matches
        review_candidates = []
        if len(stripped_no_unit) >= 4 and self._search_keys:
            matches = process.extract(
                stripped_no_unit,
                self._search_keys,
                scorer=fuzz.token_set_ratio,
                limit=3,
            )
            for match_key, score, _ in matches:
                if score >= 75:
                    entry = self._entries_by_brand[match_key]
                    cand_str = f"{entry.brand} ({entry.generic})"
                    if cand_str not in review_candidates:
                        review_candidates.append(cand_str)

            if review_candidates and matches[0][1] >= 80:
                top_entry = self._entries_by_brand[matches[0][0]]
                return self._build_candidate_result(
                    clean_raw,
                    top_entry.generic,
                    top_entry.brand,
                    detected_strength or top_entry.strength,
                    formulation,
                    route,
                    round(matches[0][1] / 100.0, 2),
                    review_candidates=review_candidates,
                )

        # 5. Unverified / Unknown Medicine
        return MedicineVerificationResult(
            name_raw=clean_raw,
            normalized_name=clean_raw,
            generic=None,
            brand_name=None,
            strength=detected_strength,
            formulation=formulation,
            route=route,
            verification_state="requires_human_review",
            catalog_status="UNVERIFIED",
            match_confidence=0.50,
            review_candidates=review_candidates,
            pharmacy_info={
                "search_portal": JAN_AUSHADHI_PORTAL_URL,
                "note": "Medicine not verified in catalog. Verify with your pharmacist.",
            },
        )

    def _build_verified_result(
        self,
        name_raw: str,
        entry: CatalogEntry,
        strength: Optional[str],
        confidence: float,
    ) -> MedicineVerificationResult:
        pharmacy_info = {
            "search_portal": JAN_AUSHADHI_PORTAL_URL,
            "disclaimer": "Prices & availability may vary by location. PMBJP generic pricing shown when available.",
        }
        if entry.is_pmbjp:
            pharmacy_info["is_jan_aushadhi_available"] = True
            pharmacy_info["pmbjp_price_inr"] = entry.pmbjp_price_inr
            pharmacy_info["market_price_inr"] = entry.market_price_inr

        return MedicineVerificationResult(
            name_raw=name_raw,
            normalized_name=entry.brand,
            generic=entry.generic,
            brand_name=entry.brand,
            strength=strength,
            formulation=entry.formulation,
            route=entry.route,
            verification_state="present_verified",
            catalog_status="VERIFIED_EXACT",
            match_confidence=confidence,
            review_candidates=[f"{entry.brand} ({entry.generic})"],
            pharmacy_info=pharmacy_info,
        )

    def _build_candidate_result(
        self,
        name_raw: str,
        generic: Optional[str],
        brand: Optional[str],
        strength: Optional[str],
        formulation: str,
        route: str,
        confidence: float,
        review_candidates: list[str],
    ) -> MedicineVerificationResult:
        return MedicineVerificationResult(
            name_raw=name_raw,
            normalized_name=brand or name_raw,
            generic=generic,
            brand_name=brand,
            strength=strength,
            formulation=formulation,
            route=route,
            verification_state="requires_human_review",
            catalog_status="CANDIDATE_MATCH",
            match_confidence=confidence,
            review_candidates=review_candidates,
            pharmacy_info={
                "search_portal": JAN_AUSHADHI_PORTAL_URL,
                "note": "Possible match requiring clinical confirmation. Do not substitute without clinician approval.",
            },
        )


def verify_medicine(name_raw: str) -> MedicineVerificationResult:
    """Helper function to verify a medicine against the official catalog."""
    return MedicineCatalog.get_instance().verify_medicine(name_raw)


def get_generic_names() -> set[str]:
    """Helper function to get all known generic medicine names."""
    return MedicineCatalog.get_instance().get_generic_names()
