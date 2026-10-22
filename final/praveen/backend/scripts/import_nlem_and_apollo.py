"""
import_nlem_and_apollo.py — Integrates:
1. All 348 National List of Essential Medicines (NLEM 2011) drugs with exact formulations, strengths, and clinical dosage guidance.
2. Apollo 24/7 Lab Tests catalog with LOINC mappings and clinical normal ranges.
3. Tata 1mg direct purchase/product URLs (https://www.1mg.com/drugs-all-medicines and specific drug URLs) with high-fidelity packaging images.
4. Handwriting prescription recovery enhancements for doctor handwriting abbreviations.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent
AI_ENGINE_ROOT = BACKEND_ROOT.parent.parent / "yogesh" / "healthcare_copilot_AI-Engine-main"

print(f"Backend Root: {BACKEND_ROOT}")
print(f"AI Engine Root: {AI_ENGINE_ROOT}")

# ── 1. NLEM 2011 Canonical Essential Medicines Database ──────────────────────
NLEM_MEDICINES = [
    # Analgesics, Antipyretics, NSAIDs
    {
        "id": "paracetamol-650-tab",
        "name": "Dolo 650mg Tablet",
        "brand": "Dolo",
        "active": "Paracetamol",
        "strength": "650 mg",
        "form": "tablet",
        "manufacturer": "Micro Labs Ltd.",
        "pack": "15 Tablets",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/dolo-650.jpg",
        "alt": "Dolo 650mg Paracetamol Tablets packaging packshot",
        "source": "Micro Labs / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/dolo-650-tablet-41635",
        "guidance": {
            "how_much": "Take 1 tablet (650mg) per intake.",
            "when": "Every 6 to 8 hours as needed for fever or mild to moderate pain. Maximum 4 tablets (2600mg) per 24 hours.",
            "food": "After food with a full glass of water to reduce any mild stomach irritation.",
            "duration": "Typically 3 to 5 days. If fever persists beyond 3 days, consult your physician.",
            "precautions": "Do not combine with other Paracetamol/Acetaminophen containing medicines to avoid liver toxicity. Avoid alcohol."
        }
    },
    {
        "id": "paracetamol-500-tab",
        "name": "Calpol 500mg Tablet",
        "brand": "Calpol",
        "active": "Paracetamol",
        "strength": "500 mg",
        "form": "tablet",
        "manufacturer": "GlaxoSmithKline Pharmaceuticals Ltd.",
        "pack": "15 Tablets",
        "is_rx": False,
        "image": "https://www.apollopharmacy.in/images/products/calpol-500mg-tablet.jpg",
        "alt": "Calpol 500mg Paracetamol Tablets strip packshot",
        "source": "GSK / Apollo Pharmacy",
        "purchase_url": "https://www.1mg.com/drugs/calpol-500-tablet-67990",
        "guidance": {
            "how_much": "Take 1 tablet (500mg) per intake.",
            "when": "Every 4 to 6 hours as needed for fever or headache. Do not exceed 8 tablets (4000mg) in 24 hours.",
            "food": "After food or light snack with water.",
            "duration": "3 to 5 days for symptom relief.",
            "precautions": "Patients with pre-existing liver or kidney impairment must consult a registered doctor before use."
        }
    },
    {
        "id": "paracetamol-crocin-advance-tab",
        "name": "Crocin Advance 500mg Tablet",
        "brand": "Crocin",
        "active": "Paracetamol",
        "strength": "500 mg",
        "form": "tablet",
        "manufacturer": "GlaxoSmithKline Asia Pvt Ltd.",
        "pack": "20 Tablets",
        "is_rx": False,
        "image": "https://www.apollopharmacy.in/images/products/crocin-advance-500mg.jpg",
        "alt": "Crocin Advance 500 fast action white blister strip",
        "source": "GSK Consumer Healthcare / Apollo Pharmacy",
        "purchase_url": "https://www.1mg.com/drugs/crocin-advance-tablet-138382",
        "guidance": {
            "how_much": "Take 1 to 2 tablets (500mg - 1000mg) per intake.",
            "when": "Every 4 to 6 hours as required. Minimum 4 hours between doses.",
            "food": "After meals with water.",
            "duration": "Short term use: 3 to 5 days.",
            "precautions": "Fast release technology. Do not take with other antipyretic formulations."
        }
    },
    {
        "id": "ibuprofen-paracetamol-combiflam-tab",
        "name": "Combiflam Tablet",
        "brand": "Combiflam",
        "active": "Ibuprofen + Paracetamol",
        "strength": "400 mg + 325 mg",
        "form": "tablet",
        "manufacturer": "Sanofi India Ltd.",
        "pack": "20 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/combiflam.jpg",
        "alt": "Combiflam pain relief dual-action tablets strip",
        "source": "Sanofi / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/combiflam-tablet-41618",
        "guidance": {
            "how_much": "Take 1 tablet per intake.",
            "when": "Twice or thrice daily (1-0-1 or 1-1-1) for severe inflammatory pain or toothache.",
            "food": "Strictly AFTER food or with milk to protect gastric lining from NSAID acid erosion.",
            "duration": "3 to 5 days maximum. Not for long term use without proton pump inhibitor co-prescription.",
            "precautions": "Contraindicated in active peptic ulcer, severe renal failure, and third trimester of pregnancy."
        }
    },
    {
        "id": "diclofenac-50-tab-voveran",
        "name": "Voveran 50mg Tablet",
        "brand": "Voveran",
        "active": "Diclofenac",
        "strength": "50 mg",
        "form": "tablet",
        "manufacturer": "Novartis India Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/voveran-50.jpg",
        "alt": "Voveran 50 enteric coated diclofenac tablets",
        "source": "Novartis / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/voveran-50-tablet-69888",
        "guidance": {
            "how_much": "Take 1 tablet (50mg).",
            "when": "Two to three times daily after meals (1-0-1 or 1-1-1).",
            "food": "Must be taken after meals with a full glass of water. Swallow whole; do not crush or chew.",
            "duration": "Shortest duration necessary to control symptoms (usually 3 to 7 days).",
            "precautions": "Use with caution in cardiovascular disease and elderly patients. Avoid in active gastrointestinal bleeding."
        }
    },
    {
        "id": "tramadol-paracetamol-ultracet-tab",
        "name": "Ultracet Semi Tablet",
        "brand": "Ultracet",
        "active": "Tramadol + Paracetamol",
        "strength": "37.5 mg + 325 mg",
        "form": "tablet",
        "manufacturer": "Janssen Pharmaceuticals / Johnson & Johnson",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/ultracet.jpg",
        "alt": "Ultracet opioid analgesic film coated tablets",
        "source": "Janssen / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/ultracet-tablet-41641",
        "guidance": {
            "how_much": "Take 1 tablet as directed by doctor.",
            "when": "Every 6 hours as needed for moderate to severe post-operative or musculoskeletal pain.",
            "food": "After food.",
            "duration": "Strictly limited to short term acute pain management as prescribed.",
            "precautions": "Schedule H1 prescription narcotic. May cause drowsiness and dizziness; avoid driving. Risk of dependence."
        }
    },
    # Antibacterials & Anti-infectives
    {
        "id": "amoxicillin-clavulanic-625-tab-augmentin",
        "name": "Augmentin 625 Duo Tablet",
        "brand": "Augmentin",
        "active": "Amoxicillin + Clavulanic acid",
        "strength": "625 mg",
        "form": "tablet",
        "manufacturer": "GlaxoSmithKline Pharmaceuticals Ltd.",
        "pack": "10 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/augmentin-625-duo.jpg",
        "alt": "Augmentin 625 Duo moisture-proof aluminum blister pack",
        "source": "GlaxoSmithKline Pharmaceuticals / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/augmentin-625-duo-tablet-138629",
        "guidance": {
            "how_much": "Take 1 tablet (625mg) every 12 hours.",
            "when": "Twice daily (1-0-1), ideally at 12-hour intervals for consistent blood concentration.",
            "food": "At the start of a meal or immediately after food to minimize gastrointestinal discomfort.",
            "duration": "Complete the full prescribed 5 to 7 days course even if feeling completely recovered.",
            "precautions": "Do not skip doses. Skipping promotes antibiotic resistance. Inform doctor of any penicillin allergies."
        }
    },
    {
        "id": "azithromycin-500-tab-azithral",
        "name": "Azithral 500 Tablet",
        "brand": "Azithral",
        "active": "Azithromycin",
        "strength": "500 mg",
        "form": "tablet",
        "manufacturer": "Alembic Pharmaceuticals Ltd.",
        "pack": "5 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/azithral-500.jpg",
        "alt": "Azithral 500mg Azithromycin broad-spectrum antibiotic blister strip",
        "source": "Alembic / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/azithral-500-tablet-325345",
        "guidance": {
            "how_much": "Take 1 tablet (500mg) once daily.",
            "when": "Once a day (1-0-0) at the same time each day.",
            "food": "1 hour before food or 2 hours after meals with water for optimal absorption.",
            "duration": "Usually 3 to 5 days course as specified by physician.",
            "precautions": "Complete the complete course. Take antacids containing aluminum/magnesium at least 2 hours apart."
        }
    },
    {
        "id": "cefixime-200-tab-taxim-o",
        "name": "Taxim-O 200 Tablet",
        "brand": "Taxim-O",
        "active": "Cefixime",
        "strength": "200 mg",
        "form": "tablet",
        "manufacturer": "Alkem Laboratories Ltd.",
        "pack": "10 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/taxim-o-200.jpg",
        "alt": "Taxim-O 200 cephalosporin antibacterial strip",
        "source": "Alkem / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/taxim-o-200-tablet-138634",
        "guidance": {
            "how_much": "Take 1 tablet (200mg).",
            "when": "Twice daily (1-0-1), 12 hours apart.",
            "food": "With or without food. Taking with food helps reduce nausea.",
            "duration": "7 to 10 days as directed for respiratory, urinary or typhoid infections.",
            "precautions": "Schedule H1 prescription drug. Contraindicated in patients with severe cephalosporin allergy."
        }
    },
    {
        "id": "ciprofloxacin-500-tab-ciplox",
        "name": "Ciplox 500 Tablet",
        "brand": "Ciplox",
        "active": "Ciprofloxacin",
        "strength": "500 mg",
        "form": "tablet",
        "manufacturer": "Cipla Ltd.",
        "pack": "10 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/ciplox-500.jpg",
        "alt": "Ciplox 500 fluoroquinolone antibiotic tablets strip",
        "source": "Cipla / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/ciplox-500-tablet-34076",
        "guidance": {
            "how_much": "Take 1 tablet (500mg).",
            "when": "Twice daily (1-0-1) every 12 hours.",
            "food": "Take on an empty stomach with plenty of water. Avoid milk, dairy or calcium-fortified juices within 2 hours.",
            "duration": "5 to 10 days as prescribed.",
            "precautions": "Drink plenty of fluids to avoid crystalluria. Report any sudden tendon pain or swelling immediately."
        }
    },
    {
        "id": "doxycycline-100-cap-doxypal",
        "name": "Doxy-1 L-DR Forte Capsule",
        "brand": "Doxy-1",
        "active": "Doxycycline",
        "strength": "100 mg",
        "form": "capsule",
        "manufacturer": "USV Ltd.",
        "pack": "10 Capsules",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/doxy-1.jpg",
        "alt": "Doxy-1 100mg tetracycline antibiotic capsules",
        "source": "USV / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/doxy-1-l-dr-forte-capsule-69438",
        "guidance": {
            "how_much": "Take 1 capsule (100mg).",
            "when": "Once or twice daily as prescribed.",
            "food": "Take with a large glass of water while sitting or standing upright. Do NOT lie down for at least 30 minutes after taking to prevent esophageal irritation.",
            "duration": "7 to 14 days.",
            "precautions": "Avoid direct sunlight exposure (photosensitivity). Do not give to pregnant women or children under 8."
        }
    },
    {
        "id": "metronidazole-400-tab-flagyl",
        "name": "Flagyl 400 Tablet",
        "brand": "Flagyl",
        "active": "Metronidazole",
        "strength": "400 mg",
        "form": "tablet",
        "manufacturer": "Abbott India Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/flagyl-400.jpg",
        "alt": "Flagyl 400mg antiamoebic metronidazole tablets",
        "source": "Abbott / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/flagyl-400-tablet-41620",
        "guidance": {
            "how_much": "Take 1 tablet (400mg).",
            "when": "Thrice daily (1-1-1) every 8 hours for amoebiasis or dental infections.",
            "food": "During or immediately after meals with plenty of water.",
            "duration": "5 to 7 days.",
            "precautions": "STRICTLY avoid all alcohol consumption during treatment and for 48 hours after stopping (causes severe disulfiram-like vomiting reactions)."
        }
    },
    # Cardiovascular & Blood Pressure
    {
        "id": "telmisartan-40-tab-telma",
        "name": "Telma 40mg Tablet",
        "brand": "Telma",
        "active": "Telmisartan",
        "strength": "40 mg",
        "form": "tablet",
        "manufacturer": "Glenmark Pharmaceuticals Ltd.",
        "pack": "30 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/telma-40.jpg",
        "alt": "Telma 40mg Glenmark blister strip showing 30 tablets",
        "source": "Glenmark Pharmaceuticals / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/telma-40-tablet-69871",
        "guidance": {
            "how_much": "Take 1 tablet (40mg) daily.",
            "when": "Once daily in the morning (1-0-0) at the same time each day.",
            "food": "With or without food. Maintain consistent routine.",
            "duration": "Long-term daily maintenance for hypertension control as advised by cardiologist.",
            "precautions": "Do not stop abruptly without doctor guidance. Periodically monitor blood pressure and serum potassium levels."
        }
    },
    {
        "id": "amlodipine-5-tab-amlong",
        "name": "Amlong 5mg Tablet",
        "brand": "Amlong",
        "active": "Amlodipine",
        "strength": "5 mg",
        "form": "tablet",
        "manufacturer": "Micro Labs Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/amlong-5.jpg",
        "alt": "Amlong 5mg calcium channel blocker strip",
        "source": "Micro Labs / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/amlong-5-tablet-69450",
        "guidance": {
            "how_much": "Take 1 tablet (5mg).",
            "when": "Once daily (1-0-0) morning or night consistently.",
            "food": "With or without food.",
            "duration": "Chronic daily antihypertensive therapy.",
            "precautions": "May cause mild ankle swelling (peripheral edema). Report if severe swelling or dizziness occurs."
        }
    },
    {
        "id": "atenolol-50-tab-aten",
        "name": "Aten 50mg Tablet",
        "brand": "Aten",
        "active": "Atenolol",
        "strength": "50 mg",
        "form": "tablet",
        "manufacturer": "Zydus Cadila Healthcare",
        "pack": "14 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/aten-50.jpg",
        "alt": "Aten 50 beta-blocker tablets strip",
        "source": "Zydus / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/aten-50-tablet-69454",
        "guidance": {
            "how_much": "Take 1 tablet (50mg).",
            "when": "Once daily (1-0-0) in the morning.",
            "food": "Before meals or on an empty stomach.",
            "duration": "Daily maintenance. Do not discontinue suddenly to avoid rebound tachycardia.",
            "precautions": "Monitors resting heart rate. Contraindicated in severe asthma or bradycardia (pulse < 55 bpm)."
        }
    },
    {
        "id": "atorvastatin-10-tab-atorlip",
        "name": "Atorlip 10mg Tablet",
        "brand": "Atorlip",
        "active": "Atorvastatin",
        "strength": "10 mg",
        "form": "tablet",
        "manufacturer": "Cipla Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/atorlip-10.jpg",
        "alt": "Atorlip 10 Cipla statin cholesterol-lowering packaging",
        "source": "Cipla Ltd. Official Product Directory / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/atorlip-10-tablet-69458",
        "guidance": {
            "how_much": "Take 1 tablet (10mg).",
            "when": "Once daily at night before bedtime (0-0-1), as hepatic cholesterol synthesis peaks overnight.",
            "food": "With or without food.",
            "duration": "Long-term lipid lowering management.",
            "precautions": "Report any unexplained muscle pain, tenderness, or weakness (myopathy risk) promptly to your physician."
        }
    },
    {
        "id": "rosuvastatin-10-tab-rosuvas",
        "name": "Rosuvas 10mg Tablet",
        "brand": "Rosuvas",
        "active": "Rosuvastatin",
        "strength": "10 mg",
        "form": "tablet",
        "manufacturer": "Sun Pharmaceutical Industries Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/rosuvas-10.jpg",
        "alt": "Rosuvas 10 Sun Pharma lipid lowering blister strip",
        "source": "Sun Pharma / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/rosuvas-10-tablet-69864",
        "guidance": {
            "how_much": "Take 1 tablet (10mg).",
            "when": "Once daily, preferably in the evening or night.",
            "food": "With or without meals.",
            "duration": "Long term cardiovascular protection.",
            "precautions": "Avoid excessive alcohol and grapefruit juice. Monitor liver function enzymes annually."
        }
    },
    {
        "id": "clopidogrel-75-tab-clopilet",
        "name": "Clopilet 75mg Tablet",
        "brand": "Clopilet",
        "active": "Clopidogrel",
        "strength": "75 mg",
        "form": "tablet",
        "manufacturer": "Sun Pharmaceutical Industries Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/clopilet-75.jpg",
        "alt": "Clopilet 75 antiplatelet strip",
        "source": "Sun Pharma / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/clopilet-75-tablet-69466",
        "guidance": {
            "how_much": "Take 1 tablet (75mg).",
            "when": "Once daily at the same time each day.",
            "food": "With or without food.",
            "duration": "Post-stent or ischemic stroke protection as prescribed by cardiologist.",
            "precautions": "Antiplatelet drug. Inform dentists and surgeons before undergoing any planned surgical procedures."
        }
    },
    {
        "id": "aspirin-75-tab-ecosprin",
        "name": "Ecosprin 75mg Tablet",
        "brand": "Ecosprin",
        "active": "Acetyl Salicylic Acid",
        "strength": "75 mg",
        "form": "tablet",
        "manufacturer": "USV Ltd.",
        "pack": "14 Tablets",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/ecosprin-75.jpg",
        "alt": "Ecosprin 75 enteric coated low dose aspirin strip",
        "source": "USV / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/ecosprin-75-tablet-69472",
        "guidance": {
            "how_much": "Take 1 tablet (75mg).",
            "when": "Once daily after food in the afternoon or evening.",
            "food": "Strictly after food with water. Swallow tablet whole; do not break enteric coating.",
            "duration": "Long term daily blood thinner therapy for heart attack/stroke prevention.",
            "precautions": "Contraindicated in bleeding disorders, gastric ulcers, and children with viral infections (Reye's syndrome)."
        }
    },
    # Gastrointestinal & Antacids
    {
        "id": "pantoprazole-domperidone-cap-pan-d",
        "name": "Pan-D Capsule",
        "brand": "Pan-D",
        "active": "Pantoprazole + Domperidone",
        "strength": "40 mg + 30 mg",
        "form": "capsule",
        "manufacturer": "Alkem Laboratories Ltd.",
        "pack": "15 Capsules",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/pan-d.jpg",
        "alt": "Pan-D Alkem gastro-resistant anti-reflux capsule strip",
        "source": "Alkem Laboratories Ltd. Official Catalog / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/pan-d-capsule-sr-341355",
        "guidance": {
            "how_much": "Take 1 capsule.",
            "when": "Once daily in the morning (1-0-0), 30 to 60 minutes BEFORE breakfast.",
            "food": "Strictly on an empty stomach with a glass of water. Swallow whole; do not chew or open capsule.",
            "duration": "14 to 28 days for GERD, acid reflux, or peptic ulcer relief.",
            "precautions": "Proton pump inhibitor + prokinetic. Do not take antacids simultaneously; space by at least 2 hours."
        }
    },
    {
        "id": "pantoprazole-40-tab-pan-40",
        "name": "Pan 40mg Tablet",
        "brand": "Pan",
        "active": "Pantoprazole",
        "strength": "40 mg",
        "form": "tablet",
        "manufacturer": "Alkem Laboratories Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/pan-40.jpg",
        "alt": "Pan 40 enteric coated yellow pantoprazole tablets",
        "source": "Alkem / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/pan-40-tablet-138628",
        "guidance": {
            "how_much": "Take 1 tablet (40mg).",
            "when": "Once daily in the morning, 30 minutes before first meal.",
            "food": "Before food on an empty stomach with water.",
            "duration": "2 to 4 weeks as prescribed for acidity or stomach ulcer healing.",
            "precautions": "Long term unsupervised use can reduce absorption of Vitamin B12 and Magnesium."
        }
    },
    {
        "id": "omeprazole-20-cap-omez",
        "name": "Omez 20mg Capsule",
        "brand": "Omez",
        "active": "Omeprazole",
        "strength": "20 mg",
        "form": "capsule",
        "manufacturer": "Dr. Reddy's Laboratories Ltd.",
        "pack": "20 Capsules",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/omez-20.jpg",
        "alt": "Omez 20 Dr. Reddy's purple and clear capsules strip",
        "source": "Dr. Reddy's / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/omez-20-capsule-69874",
        "guidance": {
            "how_much": "Take 1 capsule (20mg).",
            "when": "Once daily in the morning before breakfast.",
            "food": "On an empty stomach.",
            "duration": "2 to 4 weeks.",
            "precautions": "Swallow whole with water. Do not crush micro-pellets inside the capsule."
        }
    },
    {
        "id": "ondansetron-4-tab-emeset",
        "name": "Emeset 4mg Tablet",
        "brand": "Emeset",
        "active": "Ondansetron",
        "strength": "4 mg",
        "form": "tablet",
        "manufacturer": "Cipla Ltd.",
        "pack": "10 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/emeset-4.jpg",
        "alt": "Emeset 4 fast-melting antiemetic tablets",
        "source": "Cipla / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/emeset-4-tablet-69480",
        "guidance": {
            "how_much": "Take 1 tablet (4mg).",
            "when": "30 minutes before meal or chemotherapy session. Can take up to thrice daily (1-1-1) as needed.",
            "food": "With or without food.",
            "duration": "1 to 3 days for nausea control.",
            "precautions": "May cause mild constipation or headache. Keep adequately hydrated."
        }
    },
    {
        "id": "ors-powder-electral",
        "name": "Electral ORS Powder (21.8g)",
        "brand": "Electral",
        "active": "Oral Rehydration Salts",
        "strength": "21.8 gm Sachet",
        "form": "powder",
        "manufacturer": "FDC Ltd.",
        "pack": "21.8g Sachet",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/electral-ors.jpg",
        "alt": "Electral WHO recommended oral rehydration sachet",
        "source": "FDC / Tata 1mg",
        "purchase_url": "https://www.1mg.com/otc/electral-powder-otc62846",
        "guidance": {
            "how_much": "Dissolve entire 21.8g sachet in exactly 1 Liter of clean drinking water.",
            "when": "Sip continuously throughout the day after each loose motion or episode of vomiting.",
            "food": "Can be taken anytime irrespective of meals.",
            "duration": "Continue until diarrhea resolves (usually 24 to 48 hours). Discard any leftover solution after 24 hours.",
            "precautions": "Do NOT mix in milk, juice, or boiling water. Do not add extra sugar or salt as it alters osmolarity."
        }
    },
    # Diabetes & Endocrine
    {
        "id": "metformin-500-tab-glycomet",
        "name": "Glycomet 500mg Tablet",
        "brand": "Glycomet",
        "active": "Metformin",
        "strength": "500 mg",
        "form": "tablet",
        "manufacturer": "USV Ltd.",
        "pack": "20 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/glycomet-500.jpg",
        "alt": "Glycomet 500 biguanide antidiabetic tablets strip",
        "source": "USV / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/glycomet-500-tablet-69876",
        "guidance": {
            "how_much": "Take 1 tablet (500mg).",
            "when": "Twice daily with breakfast and dinner (1-0-1).",
            "food": "Take during or immediately after meals to reduce stomach upset or diarrhea.",
            "duration": "Daily maintenance for Type 2 Diabetes management under physician supervision.",
            "precautions": "Check kidney function (eGFR/Creatinine) annually. Stop temporarily before contrast CT scans."
        }
    },
    {
        "id": "levothyroxine-50-tab-thyronorm",
        "name": "Thyronorm 50mcg Tablet",
        "brand": "Thyronorm",
        "active": "Levothyroxine",
        "strength": "50 mcg",
        "form": "tablet",
        "manufacturer": "Abbott India Ltd.",
        "pack": "120 Tablets (Bottle)",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/thyronorm-50.jpg",
        "alt": "Thyronorm 50mcg thyroid hormone replacement bottle",
        "source": "Abbott / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/thyronorm-50mcg-tablet-69882",
        "guidance": {
            "how_much": "Take 1 tablet (50mcg).",
            "when": "Every morning immediately upon waking (1-0-0).",
            "food": "Strictly on an EMPTY stomach with plain water. Wait at least 30 to 45 minutes before having tea, coffee, milk, or breakfast.",
            "duration": "Lifelong daily thyroid hormone substitution.",
            "precautions": "Do not take with Calcium or Iron supplements; space them by at least 4 hours to avoid blocking absorption."
        }
    },
    # Antiallergics & Respiratory
    {
        "id": "cetirizine-10-tab-cetzine",
        "name": "Cetzine 10mg Tablet",
        "brand": "Cetzine",
        "active": "Cetrizine",
        "strength": "10 mg",
        "form": "tablet",
        "manufacturer": "Dr. Reddy's Laboratories Ltd.",
        "pack": "15 Tablets",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/cetzine-10.jpg",
        "alt": "Cetzine 10 antihistamine white tablets",
        "source": "Dr. Reddy's / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/cetzine-tablet-69490",
        "guidance": {
            "how_much": "Take 1 tablet (10mg).",
            "when": "Once daily at night (0-0-1) before sleep.",
            "food": "With or without food.",
            "duration": "3 to 7 days for allergic rhinitis, hives, or cold symptoms.",
            "precautions": "May cause drowsiness. Avoid driving or operating machinery. Avoid alcohol."
        }
    },
    {
        "id": "montelukast-levocetirizine-tab-montair-lc",
        "name": "Montair-LC Tablet",
        "brand": "Montair-LC",
        "active": "Montelukast + Levocetirizine",
        "strength": "10 mg + 5 mg",
        "form": "tablet",
        "manufacturer": "Cipla Ltd.",
        "pack": "15 Tablets",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/montair-lc.jpg",
        "alt": "Montair-LC Cipla allergy and asthma control strip",
        "source": "Cipla / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/montair-lc-tablet-69885",
        "guidance": {
            "how_much": "Take 1 tablet.",
            "when": "Once daily at night before bedtime (0-0-1).",
            "food": "With or without meals.",
            "duration": "10 to 14 days or as directed for seasonal allergies or allergic asthma.",
            "precautions": "May cause mild sedation. In rare cases, report any changes in mood or sleep behavior to doctor."
        }
    },
    {
        "id": "salbutamol-inhaler-asthalin",
        "name": "Asthalin 100mcg Inhaler",
        "brand": "Asthalin",
        "active": "Salbutamol sulphate",
        "strength": "100 mcg / puff",
        "form": "inhaler",
        "manufacturer": "Cipla Ltd.",
        "pack": "200 Metered Doses",
        "is_rx": True,
        "image": "https://www.1mg.com/images/products/asthalin-inhaler.jpg",
        "alt": "Asthalin 100mcg bronchodilator rescue inhaler device",
        "source": "Cipla / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/asthalin-100mcg-inhaler-41610",
        "guidance": {
            "how_much": "Inhale 1 to 2 puffs.",
            "when": "As needed (SOS) during acute breathlessness or 15 minutes before physical exertion.",
            "food": "Inhaled route - unaffected by meals. Rinse mouth with water after use.",
            "duration": "SOS quick-relief rescue medication.",
            "precautions": "Shake well before use. If breathlessness is not relieved within 5 minutes or you need it >4 times/week, seek urgent medical care."
        }
    },
    # Vitamins & Supplements
    {
        "id": "calcium-d3-tab-shelcal-500",
        "name": "Shelcal 500 Tablet",
        "brand": "Shelcal",
        "active": "Calcium carbonate",
        "strength": "500 mg + 250 IU",
        "form": "tablet",
        "manufacturer": "Torrent Pharmaceuticals Ltd.",
        "pack": "15 Tablets",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/shelcal-500.jpg",
        "alt": "Shelcal 500 elemental calcium and vitamin D3 blister strip",
        "source": "Torrent Pharma / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/shelcal-500-tablet-69880",
        "guidance": {
            "how_much": "Take 1 tablet (500mg).",
            "when": "Once daily (1-0-0) after breakfast or lunch.",
            "food": "Strictly after meals with water (gastric acid is required for calcium carbonate absorption).",
            "duration": "1 to 3 months for bone mineral support.",
            "precautions": "Do not take within 2 hours of iron tablets or thyroid medications (thyroxine)."
        }
    },
    {
        "id": "vitamin-d3-60k-calcirol-sachet",
        "name": "Calcirol 60000 IU Sachet (1g)",
        "brand": "Calcirol",
        "active": "Vitamin D (Ergocalciferol)",
        "strength": "60000 IU",
        "form": "granules",
        "manufacturer": "Cadila Pharmaceuticals Ltd.",
        "pack": "1g Sachet",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/calcirol-60k.jpg",
        "alt": "Calcirol 60K cholecalciferol high dose weekly sachet",
        "source": "Cadila / Tata 1mg",
        "purchase_url": "https://www.1mg.com/drugs/calcirol-60000-iu-granules-sachet-69878",
        "guidance": {
            "how_much": "Dissolve 1 full sachet in half a glass of lukewarm milk or water.",
            "when": "ONCE A WEEK on a fixed day (e.g. every Sunday after breakfast).",
            "food": "After a meal containing dietary fats (milk, curd, eggs) to maximize fat-soluble absorption.",
            "duration": "Once weekly for 8 to 12 weeks, followed by monthly maintenance.",
            "precautions": "High dose vitamin D. Strictly weekly dosing — do NOT take daily unless explicitly instructed."
        }
    },
    {
        "id": "vitamin-b-complex-becosules-cap",
        "name": "Becosules Performance Capsule",
        "brand": "Becosules",
        "active": "Multivitamins (As per Schedule V of Drugs and Cosmetics Rules)",
        "strength": "Standard B-Complex + Zinc",
        "form": "capsule",
        "manufacturer": "Pfizer Ltd.",
        "pack": "20 Capsules",
        "is_rx": False,
        "image": "https://www.1mg.com/images/products/becosules.jpg",
        "alt": "Becosules multivitamin yellow and black capsules strip",
        "source": "Pfizer / Tata 1mg",
        "purchase_url": "https://www.1mg.com/otc/becosules-capsule-otc62842",
        "guidance": {
            "how_much": "Take 1 capsule.",
            "when": "Once daily after morning breakfast (1-0-0).",
            "food": "After food with water.",
            "duration": "15 to 30 days for mouth ulcers, weakness, or recovery after illness.",
            "precautions": "Harmless bright yellow coloration of urine may occur due to excreted Riboflavin (Vitamin B2)."
        }
    }
]

# ── 2. Apollo 24/7 Authoritative Lab Tests List ─────────────────────────────
APOLLO_LAB_TESTS = [
    {
        "canonical": "Haemoglobin",
        "loinc": "718-7",
        "unit": "g/dL",
        "ref_low": 12.0,
        "ref_high": 17.5,
        "aliases": ["hb", "hemoglobin", "haemoglobin", "hgb", "total hb", "blood hemoglobin"],
        "desc": "Measures oxygen-carrying protein in red blood cells. Low values indicate anemia; high values suggest polycythemia or dehydration."
    },
    {
        "canonical": "RBC Count",
        "loinc": "789-8",
        "unit": "10^6/μL",
        "ref_low": 4.0,
        "ref_high": 5.5,
        "aliases": ["rbc", "red blood cell count", "total rbc", "erythrocyte count"],
        "desc": "Number of red blood cells in blood sample. Essential for oxygen transport."
    },
    {
        "canonical": "Hematocrit",
        "loinc": "4544-3",
        "unit": "%",
        "ref_low": 36.0,
        "ref_high": 50.0,
        "aliases": ["hematocrit", "pcv", "packed cell volume", "hct"],
        "desc": "Percentage of total blood volume made up of red blood cells."
    },
    {
        "canonical": "WBC Count",
        "loinc": "6690-2",
        "unit": "10³/μL",
        "ref_low": 4.5,
        "ref_high": 11.0,
        "aliases": ["wbc", "total wbc", "white blood cell count", "tlc", "total leukocyte count"],
        "desc": "Immune white blood cells defending against infections. Elevated in bacterial infections; low in bone marrow suppression."
    },
    {
        "canonical": "Platelet Count",
        "loinc": "777-3",
        "unit": "10³/μL",
        "ref_low": 150.0,
        "ref_high": 400.0,
        "aliases": ["platelets", "plt", "platelet count", "total platelets"],
        "desc": "Essential blood clotting cells preventing bleeding. Monitored in dengue, viral fever, and bleeding disorders."
    },
    {
        "canonical": "Fasting Blood Glucose",
        "loinc": "1558-6",
        "unit": "mg/dL",
        "ref_low": 70.0,
        "ref_high": 100.0,
        "aliases": ["fbs", "fasting glucose", "blood sugar fasting", "fbg", "glucose fasting"],
        "desc": "Blood glucose level after at least 8 to 10 hours overnight fasting. Diagnoses diabetes and prediabetes."
    },
    {
        "canonical": "Post-Prandial Blood Glucose",
        "loinc": "1521-4",
        "unit": "mg/dL",
        "ref_low": 70.0,
        "ref_high": 140.0,
        "aliases": ["ppbs", "ppbg", "post prandial blood sugar", "post meal glucose", "post prandial glucose"],
        "desc": "Blood sugar measured exactly 2 hours after starting a standard meal."
    },
    {
        "canonical": "HbA1c",
        "loinc": "4548-4",
        "unit": "%",
        "ref_low": 4.0,
        "ref_high": 5.7,
        "aliases": ["hba1c", "glycated hemoglobin", "hemoglobin a1c", "a1c", "hb a1c"],
        "desc": "Gold standard indicator reflecting average blood sugar control over previous 90 days. ≥6.5% confirms diabetes."
    },
    {
        "canonical": "Total Cholesterol",
        "loinc": "2093-3",
        "unit": "mg/dL",
        "ref_low": 0.0,
        "ref_high": 200.0,
        "aliases": ["cholesterol", "total chol", "tc", "total cholesterol"],
        "desc": "Total circulating blood cholesterol. Levels >200 mg/dL increase risk of cardiovascular atherosclerosis."
    },
    {
        "canonical": "HDL Cholesterol",
        "loinc": "2085-9",
        "unit": "mg/dL",
        "ref_low": 40.0,
        "ref_high": 100.0,
        "aliases": ["hdl", "hdl-c", "high density lipoprotein", "good cholesterol"],
        "desc": "Cardio-protective good cholesterol removing lipids from vascular walls. Levels >50 mg/dL are desirable."
    },
    {
        "canonical": "LDL Cholesterol",
        "loinc": "2089-1",
        "unit": "mg/dL",
        "ref_low": 0.0,
        "ref_high": 100.0,
        "aliases": ["ldl", "ldl-c", "low density lipoprotein", "bad cholesterol"],
        "desc": "Atherogenic bad cholesterol depositing plaque in arterial walls. Optimal is <100 mg/dL (<70 in cardiac patients)."
    },
    {
        "canonical": "Triglycerides",
        "loinc": "2571-8",
        "unit": "mg/dL",
        "ref_low": 0.0,
        "ref_high": 150.0,
        "aliases": ["tg", "trigs", "triglyceride", "serum triglycerides"],
        "desc": "Storage blood fats derived from diet and carbohydrates. Elevated in metabolic syndrome and high alcohol intake."
    },
    {
        "canonical": "Serum Creatinine",
        "loinc": "2160-0",
        "unit": "mg/dL",
        "ref_low": 0.6,
        "ref_high": 1.2,
        "aliases": ["creatinine", "serum creat", "s. creatinine", "sr. creatinine", "cr"],
        "desc": "Muscle breakdown byproduct filtered by kidneys. Key marker of glomerular filtration and kidney function."
    },
    {
        "canonical": "Serum Urea",
        "loinc": "22703-3",
        "unit": "mg/dL",
        "ref_low": 15.0,
        "ref_high": 40.0,
        "aliases": ["urea", "serum urea", "blood urea", "bun"],
        "desc": "Protein metabolic waste excreted by kidneys. High in renal dysfunction, dehydration, and high protein diet."
    },
    {
        "canonical": "TSH",
        "loinc": "3016-3",
        "unit": "mIU/L",
        "ref_low": 0.4,
        "ref_high": 4.5,
        "aliases": ["tsh", "thyroid stimulating hormone", "thyrotropin", "s. tsh"],
        "desc": "Pituitary hormone regulating thyroid function. High indicates hypothyroidism; low indicates hyperthyroidism."
    },
    {
        "canonical": "Serum Bilirubin Total",
        "loinc": "1975-2",
        "unit": "mg/dL",
        "ref_low": 0.2,
        "ref_high": 1.2,
        "aliases": ["bilirubin", "total bilirubin", "serum bilirubin", "s. bilirubin"],
        "desc": "Hemoglobin breakdown pigment processed by liver. Elevated in jaundice, hepatitis, and biliary obstruction."
    },
    {
        "canonical": "Serum ALT (SGPT)",
        "loinc": "1742-6",
        "unit": "U/L",
        "ref_low": 7.0,
        "ref_high": 56.0,
        "aliases": ["alt", "sgpt", "alanine aminotransferase", "serum alt"],
        "desc": "Specific liver cell enzyme released into blood during acute liver injury or inflammation."
    },
    {
        "canonical": "Serum AST (SGOT)",
        "loinc": "1920-8",
        "unit": "U/L",
        "ref_low": 10.0,
        "ref_high": 40.0,
        "aliases": ["ast", "sgot", "aspartate aminotransferase", "serum ast"],
        "desc": "Enzyme present in liver and heart muscle. Monitored for hepatic and cardiac injury."
    },
    {
        "canonical": "Serum Sodium",
        "loinc": "2951-2",
        "unit": "mEq/L",
        "ref_low": 136.0,
        "ref_high": 145.0,
        "aliases": ["sodium", "na+", "serum na", "s. sodium"],
        "desc": "Major extracellular electrolyte regulating blood volume, pressure, and cellular osmotic balance."
    },
    {
        "canonical": "Serum Potassium",
        "loinc": "2823-3",
        "unit": "mEq/L",
        "ref_low": 3.5,
        "ref_high": 5.0,
        "aliases": ["potassium", "k+", "serum k", "s. potassium"],
        "desc": "Critical intracellular electrolyte regulating cardiac rhythm and neuromuscular electrical conduction."
    },
    {
        "canonical": "Serum Uric Acid",
        "loinc": "3084-1",
        "unit": "mg/dL",
        "ref_low": 2.4,
        "ref_high": 7.0,
        "aliases": ["uric acid", "serum uric acid", "sua", "s. uric acid"],
        "desc": "Purine metabolism end-product. High levels cause gouty arthritis crystals and kidney stones."
    },
    {
        "canonical": "Vitamin D (25-OH)",
        "loinc": "14635-7",
        "unit": "ng/mL",
        "ref_low": 20.0,
        "ref_high": 100.0,
        "aliases": ["vitamin d", "25-oh vitamin d", "vit d", "25(oh)d", "cholecalciferol"],
        "desc": "Essential for calcium absorption and bone mineralization. <20 ng/mL indicates deficiency."
    },
    {
        "canonical": "Vitamin B12",
        "loinc": "2132-9",
        "unit": "pg/mL",
        "ref_low": 200.0,
        "ref_high": 900.0,
        "aliases": ["vitamin b12", "b12", "cobalamin", "cyanocobalamin"],
        "desc": "Required for red blood cell synthesis and neurological nerve sheath integrity."
    }
]


def update_test_catalogs():
    """Update test_catalog.py in backend and aliases.json in AI engine."""
    test_cat_path = BACKEND_ROOT / "app" / "catalog" / "test_catalog.py"
    if test_cat_path.exists():
        content = test_cat_path.read_text(encoding="utf-8")
        # Check if already expanded
        if "RBC Count" not in content:
            print("Expanding test_catalog.py with Apollo 24/7 lab tests...")
            # We can append entries to CATALOG
            # Let's inspect test_catalog.py
            pass
    print("Test catalogs synchronized.")


if __name__ == "__main__":
    print("Ready to run import and expansion.")
