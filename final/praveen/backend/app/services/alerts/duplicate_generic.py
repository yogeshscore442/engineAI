"""
services/alerts/duplicate_generic.py — Alert for same generic under different brand names.
No interaction claims made. Just flags "same ingredient under different brands."
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.repositories.medicines_repo import get_medicines_by_profile
from app.schemas import AlertItem


class DuplicateGenericRule:
    def check(self, db: Session, profile_id: str) -> list[AlertItem]:
        """
        Detect medicines with the same generic but different brand names
        across any records for this profile.
        """
        medicines = get_medicines_by_profile(db, profile_id)

        # Group by generic → {generic: {brand_raw: [record_ids]}}
        generic_to_brands: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for med in medicines:
            generic = (med.generic or "").strip().lower()
            if not generic:
                continue
            brand = (med.name_raw or "").strip().lower()
            generic_to_brands[generic][brand].append(med.record_id)

        alerts = []
        for generic, brand_dict in generic_to_brands.items():
            if len(brand_dict) > 1:
                all_record_ids = []
                brands_list = list(brand_dict.keys())
                for rids in brand_dict.values():
                    all_record_ids.extend(rids)

                alerts.append(AlertItem(
                    alert_type="duplicate_generic",
                    type="duplicate_generic",
                    generic=generic,
                    severity="warning",
                    message=(
                        f"The same active ingredient '{generic}' appears under different "
                        f"brand names ({', '.join(brands_list)}). "
                        "This may indicate duplicate medication. Please confirm with your doctor."
                    ),
                    record_ids=list(set(all_record_ids)),
                    disclaimer="Informational only. Please confirm with your doctor.",
                ))

        return alerts
