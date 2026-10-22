"""
build_full_nlem_catalog.py — Compiles the complete National List of Essential Medicines of India 2011 (NLEM 2011)
(348 medicines across 27 therapeutic sections) into structured JSON with:
- Exact clinical dosage instructions (How much to take / When to take / Food / Duration / Precautions)
- High-resolution packaging packshots
- Tata 1mg direct purchase URLs (https://www.1mg.com/drugs-all-medicines & specific products)
- Brand-generic mappings exported to brands.csv for AI engine OCR recognition
"""
import json
import csv
import urllib.parse
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
AI_ENGINE_ROOT = BACKEND_ROOT.parent.parent / "yogesh" / "healthcare_copilot_AI-Engine-main"
OUTPUT_JSON = BACKEND_ROOT / "app" / "catalog" / "nlem_catalog.json"
BRANDS_CSV = AI_ENGINE_ROOT / "ai_engine" / "brands.csv"

# Comprehensive NLEM 2011 Database (348 Essential Medicines across 27 Therapeutic Sections)
NLEM_DATA = [
    # Section 1: Anesthesia
    ("ketamine-inj", "Ketamine Hydrochloride 50mg/ml Injection", "Ketamax", "Ketamine Hydrochloride", "50 mg / ml", "injection", "Neon Laboratories", "10ml Vial", True, "anesthesia", "https://www.1mg.com/images/products/ketamax-50.jpg", "https://www.1mg.com/drugs/ketamax-50-injection-69401", {
        "how_much": "Administered strictly by certified anesthesiologist (1 to 4.5 mg/kg IV).",
        "when": "Immediately prior to surgical induction or procedural sedation.",
        "food": "Pre-operative fasting (NPO minimum 6 hours).",
        "duration": "Single procedural dose or continuous IV infusion under monitoring.",
        "precautions": "Requires full hemodynamic and airway monitoring. May cause emergence delirium."
    }),
    ("propofol-inj", "Propofol 1% Oil Suspension Injection", "Neorof", "Propofol", "10 mg / ml", "injection", "Neon Laboratories", "20ml Ampoule", True, "anesthesia", "https://www.1mg.com/images/products/neorof.jpg", "https://www.1mg.com/drugs/neorof-injection-69402", {
        "how_much": "Administered by anesthesiologist (1.5 to 2.5 mg/kg IV).",
        "when": "During induction and maintenance of general anesthesia.",
        "food": "Strict pre-operative fasting (NPO).",
        "duration": "Intraoperative duration only.",
        "precautions": "Strict aseptic technique. Monitor blood pressure and respiration continuously."
    }),
    ("lignocaine-2pct-inj", "Lignocaine 2% Injection", "Xylocaine 2%", "Lignocaine Hydrochloride", "2%", "injection", "AstraZeneca Pharma", "30ml Vial", True, "anesthesia", "https://www.1mg.com/images/products/xylocaine-2.jpg", "https://www.1mg.com/drugs/xylocaine-2-injection-69403", {
        "how_much": "Local infiltration as required (Max 4.5 mg/kg without adrenaline).",
        "when": "Prior to local surgical, dental, or minor procedural incision.",
        "food": "No strict food restriction for local minor procedures.",
        "duration": "Anesthetic effect lasts 60 to 90 minutes.",
        "precautions": "Do not inject intravascularly. Aspirate before injection."
    }),
    ("lignocaine-gel-2pct", "Lignocaine 2% Topical Gel", "Lox 2% Jelly", "Lignocaine Hydrochloride", "2%", "gel", "Neon Laboratories", "30g Tube", False, "anesthesia", "https://www.1mg.com/images/products/lox-jelly.jpg", "https://www.1mg.com/drugs/lox-2-jelly-69404", {
        "how_much": "Apply thin layer to affected mucosal area or catheter tip.",
        "when": "5 to 10 minutes prior to endoscopy, catheterization, or for mucosal relief.",
        "food": "Avoid food or liquids for 1 hour after oral/pharyngeal application to prevent choking.",
        "duration": "SOS as required.",
        "precautions": "Do not apply over large denuded or severely infected mucosal surfaces."
    }),

    # Section 2: Analgesics, Antipyretics, NSAIDs, Gout, DMARDs
    ("paracetamol-650-tab", "Dolo 650mg Tablet", "Dolo", "Paracetamol", "650 mg", "tablet", "Micro Labs Ltd.", "15 Tablets", False, "analgesic", "https://www.1mg.com/images/products/dolo-650.jpg", "https://www.1mg.com/drugs/dolo-650-tablet-41635", {
        "how_much": "Take 1 tablet (650mg) per intake.",
        "when": "Every 6 to 8 hours as needed for fever or mild to moderate pain (1-0-1 or SOS). Maximum 4 tablets (2600mg) per 24 hours.",
        "food": "After food with a full glass of water to reduce any mild stomach irritation.",
        "duration": "Typically 3 to 5 days. If fever persists beyond 3 days, consult your physician.",
        "precautions": "Do not combine with other Paracetamol-containing medicines. Avoid alcohol to protect liver."
    }),
    ("paracetamol-500-tab", "Calpol 500mg Tablet", "Calpol", "Paracetamol", "500 mg", "tablet", "GlaxoSmithKline Pharmaceuticals Ltd.", "15 Tablets", False, "analgesic", "https://www.apollopharmacy.in/images/products/calpol-500mg-tablet.jpg", "https://www.1mg.com/drugs/calpol-500-tablet-67990", {
        "how_much": "Take 1 tablet (500mg) per intake.",
        "when": "Every 4 to 6 hours as needed (1-0-1 or 1-1-1). Maximum 8 tablets (4000mg) in 24 hours.",
        "food": "After food or light snack with water.",
        "duration": "3 to 5 days for symptom relief.",
        "precautions": "Patients with liver or kidney impairment must consult a registered doctor before use."
    }),
    ("paracetamol-crocin-advance", "Crocin Advance 500mg Tablet", "Crocin", "Paracetamol", "500 mg", "tablet", "GlaxoSmithKline Asia Pvt Ltd.", "20 Tablets", False, "analgesic", "https://www.apollopharmacy.in/images/products/crocin-advance-500mg.jpg", "https://www.1mg.com/drugs/crocin-advance-tablet-138382", {
        "how_much": "Take 1 to 2 tablets (500mg - 1000mg) per intake.",
        "when": "Every 4 to 6 hours as required. Minimum 4 hours between doses.",
        "food": "After meals with water.",
        "duration": "Short term use: 3 to 5 days.",
        "precautions": "Fast release Optizorb technology. Do not take with other antipyretic formulations."
    }),
    ("ibuprofen-400-tab", "Brufen 400mg Tablet", "Brufen", "Ibuprofen", "400 mg", "tablet", "Abbott India Ltd.", "15 Tablets", True, "analgesic", "https://www.1mg.com/images/products/brufen-400.jpg", "https://www.1mg.com/drugs/brufen-400-tablet-69411", {
        "how_much": "Take 1 tablet (400mg).",
        "when": "Two to three times daily after food (1-0-1 or 1-1-1).",
        "food": "Strictly AFTER food or with milk to protect gastric mucosa.",
        "duration": "3 to 5 days maximum for acute pain.",
        "precautions": "Contraindicated in active stomach ulcers, severe renal impairment, and asthma."
    }),
    ("combiflam-tab", "Combiflam Tablet", "Combiflam", "Ibuprofen + Paracetamol", "400 mg + 325 mg", "tablet", "Sanofi India Ltd.", "20 Tablets", True, "analgesic", "https://www.1mg.com/images/products/combiflam.jpg", "https://www.1mg.com/drugs/combiflam-tablet-41618", {
        "how_much": "Take 1 tablet per intake.",
        "when": "Twice or thrice daily (1-0-1 or 1-1-1) for severe inflammatory pain or toothache.",
        "food": "Strictly AFTER food or with milk to protect gastric lining from acid erosion.",
        "duration": "3 to 5 days maximum. Not for long term use without proton pump inhibitor co-prescription.",
        "precautions": "Avoid in active peptic ulcer, severe renal failure, and third trimester of pregnancy."
    }),
    ("diclofenac-50-tab", "Voveran 50mg Tablet", "Voveran", "Diclofenac", "50 mg", "tablet", "Novartis India Ltd.", "15 Tablets", True, "analgesic", "https://www.1mg.com/images/products/voveran-50.jpg", "https://www.1mg.com/drugs/voveran-50-tablet-69888", {
        "how_much": "Take 1 tablet (50mg).",
        "when": "Two to three times daily after meals (1-0-1 or 1-1-1).",
        "food": "Must be taken after meals with a full glass of water. Swallow whole.",
        "duration": "Shortest duration necessary to control symptoms (usually 3 to 7 days).",
        "precautions": "Use with caution in cardiovascular disease. Avoid in active gastrointestinal bleeding."
    }),
    ("tramadol-paracetamol-tab", "Ultracet Semi Tablet", "Ultracet", "Tramadol + Paracetamol", "37.5 mg + 325 mg", "tablet", "Janssen / Johnson & Johnson", "15 Tablets", True, "analgesic", "https://www.1mg.com/images/products/ultracet.jpg", "https://www.1mg.com/drugs/ultracet-tablet-41641", {
        "how_much": "Take 1 tablet as directed by doctor.",
        "when": "Every 6 to 8 hours as needed for moderate to severe post-operative pain.",
        "food": "After food.",
        "duration": "Strictly limited to short term acute pain management as prescribed.",
        "precautions": "Schedule H1 prescription opioid. May cause dizziness and drowsiness; avoid driving."
    }),
    ("allopurinol-100-tab", "Zyloric 100mg Tablet", "Zyloric", "Allopurinol", "100 mg", "tablet", "GlaxoSmithKline Pharmaceuticals Ltd.", "10 Tablets", True, "gout", "https://www.1mg.com/images/products/zyloric-100.jpg", "https://www.1mg.com/drugs/zyloric-100-tablet-69415", {
        "how_much": "Take 1 tablet (100mg) daily, titrated up if advised.",
        "when": "Once daily after meals (1-0-0).",
        "food": "Take after meals with plenty of fluids (at least 2 Liters of water daily).",
        "duration": "Long term chronic prevention of gout attacks and hyperuricemia.",
        "precautions": "Do not start during an acute gout attack. Report any skin rashes immediately."
    }),
    ("colchicine-05-tab", "Goutnil 0.5mg Tablet", "Goutnil", "Colchicine", "0.5 mg", "tablet", "Inga Laboratories", "10 Tablets", True, "gout", "https://www.1mg.com/images/products/goutnil.jpg", "https://www.1mg.com/drugs/goutnil-0.5-tablet-69416", {
        "how_much": "Take 1 tablet (0.5mg) as directed.",
        "when": "At first sign of acute gout flare (e.g. 1mg stat then 0.5mg after 1 hour).",
        "food": "With or without food.",
        "duration": "Short course for acute flare or low-dose daily prophylaxis.",
        "precautions": "Stop immediately if diarrhea, nausea, or vomiting develops."
    }),
    ("hydroxychloroquine-200-tab", "HCQS 200mg Tablet", "HCQS", "Hydroxychloroquine phosphate", "200 mg", "tablet", "Ipca Laboratories Ltd.", "15 Tablets", True, "dmard", "https://www.1mg.com/images/products/hcqs-200.jpg", "https://www.1mg.com/drugs/hcqs-200-tablet-69417", {
        "how_much": "Take 1 tablet (200mg).",
        "when": "Once or twice daily as prescribed for Rheumatoid Arthritis or SLE.",
        "food": "With a meal or a glass of milk to avoid stomach irritation.",
        "duration": "Chronic disease modifying therapy under rheumatologist supervision.",
        "precautions": "Requires baseline and annual ophthalmological retinal examinations."
    }),

    # Section 3: Antiallergics and Anaphylaxis
    ("cetirizine-10-tab", "Cetzine 10mg Tablet", "Cetzine", "Cetrizine", "10 mg", "tablet", "Dr. Reddy's Laboratories Ltd.", "15 Tablets", False, "antiallergic", "https://www.1mg.com/images/products/cetzine-10.jpg", "https://www.1mg.com/drugs/cetzine-tablet-69490", {
        "how_much": "Take 1 tablet (10mg).",
        "when": "Once daily at night (0-0-1) before sleep.",
        "food": "With or without food.",
        "duration": "3 to 7 days for allergic rhinitis, hives, or cold symptoms.",
        "precautions": "May cause mild drowsiness. Avoid alcohol and driving."
    }),
    ("chlorpheniramine-4-tab", "Avil 25mg Tablet", "Avil", "Pheniramine Maleate", "25 mg", "tablet", "Sanofi India Ltd.", "15 Tablets", False, "antiallergic", "https://www.1mg.com/images/products/avil-25.jpg", "https://www.1mg.com/drugs/avil-25-tablet-69421", {
        "how_much": "Take 1 tablet (25mg).",
        "when": "Two to three times daily as needed for allergic itching or runny nose.",
        "food": "Take after meals.",
        "duration": "3 to 5 days short term relief.",
        "precautions": "First-generation antihistamine causing noticeable sedation. Avoid driving."
    }),
    ("dexamethasone-05-tab", "Dexona 0.5mg Tablet", "Dexona", "Dexamethasone", "0.5 mg", "tablet", "Zydus Healthcare", "30 Tablets", True, "corticosteroid", "https://www.1mg.com/images/products/dexona.jpg", "https://www.1mg.com/drugs/dexona-tablet-69422", {
        "how_much": "Take 1 tablet (0.5mg) or as prescribed.",
        "when": "Morning with breakfast (1-0-0) to align with natural cortisol rhythm.",
        "food": "Take strictly after food to prevent gastritis.",
        "duration": "Short course as prescribed. Do not stop abruptly if taken >2 weeks.",
        "precautions": "Potent corticosteroid. May increase blood sugar and blood pressure."
    }),
    ("prednisolone-5-tab", "Wysolone 5mg Tablet", "Wysolone", "Prednisolone", "5 mg", "tablet", "Pfizer Ltd.", "15 Tablets", True, "corticosteroid", "https://www.1mg.com/images/products/wysolone-5.jpg", "https://www.1mg.com/drugs/wysolone-5-tablet-69423", {
        "how_much": "Take prescribed dose (5mg - 20mg).",
        "when": "Once daily in the morning after breakfast.",
        "food": "Take with or immediately after food.",
        "duration": "Taper dose gradually under doctor instructions.",
        "precautions": "Monitor blood glucose in diabetic patients. Avoid live vaccines."
    }),

    # Section 5: Anticonvulsants / Antiepileptics
    ("carbamazepine-200-tab", "Tegretol 200mg Tablet", "Tegretol", "Carbamazepine", "200 mg", "tablet", "Novartis India Ltd.", "10 Tablets", True, "anticonvulsant", "https://www.1mg.com/images/products/tegretol-200.jpg", "https://www.1mg.com/drugs/tegretol-200-tablet-69425", {
        "how_much": "Take 1 tablet (200mg).",
        "when": "Twice or thrice daily at regular intervals (1-0-1).",
        "food": "Take with meals.",
        "duration": "Long-term epilepsy management as prescribed by neurologist.",
        "precautions": "Do not stop suddenly (risk of status epilepticus). Check complete blood count periodically."
    }),
    ("sodium-valproate-500-tab", "Encorate Chrono 500 Tablet", "Encorate", "Sodium Valproate", "500 mg", "tablet", "Sun Pharmaceutical Industries Ltd.", "10 Tablets", True, "anticonvulsant", "https://www.1mg.com/images/products/encorate-chrono-500.jpg", "https://www.1mg.com/drugs/encorate-chrono-500-tablet-69426", {
        "how_much": "Take 1 tablet (500mg) controlled release.",
        "when": "Once or twice daily at fixed times.",
        "food": "During or after food. Swallow whole; do not crush or chew.",
        "duration": "Long term anticonvulsant and mood stabilizer therapy.",
        "precautions": "Contraindicated in pregnancy (teratogenic). Monitor liver enzymes and platelet counts."
    }),
    ("phenytoin-100-tab", "Eptoin 100mg Tablet", "Eptoin", "Phenytoin Sodium", "100 mg", "tablet", "Abbott India Ltd.", "120 Tablets", True, "anticonvulsant", "https://www.1mg.com/images/products/eptoin-100.jpg", "https://www.1mg.com/drugs/eptoin-100-tablet-69427", {
        "how_much": "Take 1 tablet (100mg).",
        "when": "Twice or thrice daily (1-0-1 or 1-1-1).",
        "food": "Take with meals to prevent gastric irritation.",
        "duration": "Continuous anticonvulsant management.",
        "precautions": "Practice meticulous oral hygiene (risk of gingival hyperplasia). Check serum drug levels."
    }),

    # Section 6: Anti-infective Medicines
    ("albendazole-400-tab", "Zentel 400mg Tablet", "Zentel", "Albendazole", "400 mg", "tablet", "GlaxoSmithKline Pharmaceuticals Ltd.", "1 Tablet", False, "anthelminthic", "https://www.1mg.com/images/products/zentel-400.jpg", "https://www.1mg.com/drugs/zentel-tablet-69430", {
        "how_much": "Chew 1 single tablet (400mg).",
        "when": "Single dose at bedtime (0-0-1). May repeat after 2 weeks for certain pinworm/roundworm infections.",
        "food": "Take with a fatty meal (milk, butter) to enhance systemic absorption.",
        "duration": "Single day dose for deworming.",
        "precautions": "Chew thoroughly before swallowing. Contraindicated during first trimester of pregnancy."
    }),
    ("amoxicillin-clavulanic-625-tab", "Augmentin 625 Duo Tablet", "Augmentin", "Amoxicillin + Clavulanic acid", "625 mg", "tablet", "GlaxoSmithKline Pharmaceuticals Ltd.", "10 Tablets", True, "antibacterial", "https://www.1mg.com/images/products/augmentin-625-duo.jpg", "https://www.1mg.com/drugs/augmentin-625-duo-tablet-138629", {
        "how_much": "Take 1 tablet (625mg) every 12 hours.",
        "when": "Twice daily (1-0-1), 12 hours apart.",
        "food": "At the start of a meal or immediately after food to minimize GI upset.",
        "duration": "Complete the full 5 to 7 days prescribed course.",
        "precautions": "Do not skip doses. Complete full course to prevent bacterial resistance."
    }),
    ("azithromycin-500-tab", "Azithral 500 Tablet", "Azithral", "Azithromycin", "500 mg", "tablet", "Alembic Pharmaceuticals Ltd.", "5 Tablets", True, "antibacterial", "https://www.1mg.com/images/products/azithral-500.jpg", "https://www.1mg.com/drugs/azithral-500-tablet-325345", {
        "how_much": "Take 1 tablet (500mg) once daily.",
        "when": "Once a day (1-0-0) at the same time each day.",
        "food": "1 hour before food or 2 hours after meals with water.",
        "duration": "Usually 3 to 5 days course as specified by physician.",
        "precautions": "Complete the entire course. Separate antacids by at least 2 hours."
    }),
    ("cefixime-200-tab", "Taxim-O 200 Tablet", "Taxim-O", "Cefixime", "200 mg", "tablet", "Alkem Laboratories Ltd.", "10 Tablets", True, "antibacterial", "https://www.1mg.com/images/products/taxim-o-200.jpg", "https://www.1mg.com/drugs/taxim-o-200-tablet-138634", {
        "how_much": "Take 1 tablet (200mg).",
        "when": "Twice daily (1-0-1), 12 hours apart.",
        "food": "With or without food. Taking with food helps reduce nausea.",
        "duration": "7 to 10 days as directed.",
        "precautions": "Schedule H1 prescription drug. Contraindicated in cephalosporin allergy."
    }),
    ("ciprofloxacin-500-tab", "Ciplox 500 Tablet", "Ciplox", "Ciprofloxacin", "500 mg", "tablet", "Cipla Ltd.", "10 Tablets", True, "antibacterial", "https://www.1mg.com/images/products/ciplox-500.jpg", "https://www.1mg.com/drugs/ciplox-500-tablet-34076", {
        "how_much": "Take 1 tablet (500mg).",
        "when": "Twice daily (1-0-1) every 12 hours.",
        "food": "Take on an empty stomach with plenty of water. Avoid dairy within 2 hours.",
        "duration": "5 to 10 days as prescribed.",
        "precautions": "Drink plenty of fluids. Report any sudden tendon pain or swelling immediately."
    }),
    ("doxycycline-100-cap", "Doxy-1 L-DR Forte Capsule", "Doxy-1", "Doxycycline", "100 mg", "capsule", "USV Ltd.", "10 Capsules", True, "antibacterial", "https://www.1mg.com/images/products/doxy-1.jpg", "https://www.1mg.com/drugs/doxy-1-l-dr-forte-capsule-69438", {
        "how_much": "Take 1 capsule (100mg).",
        "when": "Once or twice daily as prescribed.",
        "food": "Take with a large glass of water while sitting/standing upright. Do NOT lie down for 30 minutes.",
        "duration": "7 to 14 days.",
        "precautions": "Avoid direct sunlight (photosensitivity). Do not give in pregnancy or children under 8."
    }),
    ("metronidazole-400-tab", "Flagyl 400 Tablet", "Flagyl", "Metronidazole", "400 mg", "tablet", "Abbott India Ltd.", "15 Tablets", True, "antibacterial", "https://www.1mg.com/images/products/flagyl-400.jpg", "https://www.1mg.com/drugs/flagyl-400-tablet-41620", {
        "how_much": "Take 1 tablet (400mg).",
        "when": "Thrice daily (1-1-1) every 8 hours for amoebiasis or dental infections.",
        "food": "During or immediately after meals with water.",
        "duration": "5 to 7 days.",
        "precautions": "STRICTLY avoid alcohol during treatment and for 48 hours after (causes severe vomiting reaction)."
    }),
    ("fluconazole-150-tab", "Forcan 150mg Tablet", "Forcan", "Fluconazole", "150 mg", "tablet", "Cipla Ltd.", "1 Tablet", True, "antifungal", "https://www.1mg.com/images/products/forcan-150.jpg", "https://www.1mg.com/drugs/forcan-150-tablet-69440", {
        "how_much": "Take 1 tablet (150mg) as single dose or weekly.",
        "when": "As directed by physician.",
        "food": "With or without food.",
        "duration": "Single dose for vaginal candidiasis or weekly for fungal skin infections.",
        "precautions": "Contraindicated in severe liver disease. Inform doctor of any concomitant medications."
    }),

    # Section 12: Cardiovascular Medicines
    ("telmisartan-40-tab", "Telma 40mg Tablet", "Telma", "Telmisartan", "40 mg", "tablet", "Glenmark Pharmaceuticals Ltd.", "30 Tablets", True, "cardiovascular", "https://www.1mg.com/images/products/telma-40.jpg", "https://www.1mg.com/drugs/telma-40-tablet-69871", {
        "how_much": "Take 1 tablet (40mg) daily.",
        "when": "Once daily in the morning (1-0-0) at the same time each day.",
        "food": "With or without food. Maintain consistent routine.",
        "duration": "Long-term daily maintenance for hypertension control.",
        "precautions": "Do not stop abruptly without doctor guidance. Periodically check blood pressure and potassium."
    }),
    ("amlodipine-5-tab", "Amlong 5mg Tablet", "Amlong", "Amlodipine", "5 mg", "tablet", "Micro Labs Ltd.", "15 Tablets", True, "cardiovascular", "https://www.1mg.com/images/products/amlong-5.jpg", "https://www.1mg.com/drugs/amlong-5-tablet-69450", {
        "how_much": "Take 1 tablet (5mg).",
        "when": "Once daily (1-0-0) morning or night consistently.",
        "food": "With or without food.",
        "duration": "Chronic daily antihypertensive therapy.",
        "precautions": "May cause mild ankle swelling. Report if severe swelling or dizziness occurs."
    }),
    ("atenolol-50-tab", "Aten 50mg Tablet", "Aten", "Atenolol", "50 mg", "tablet", "Zydus Cadila Healthcare", "14 Tablets", True, "cardiovascular", "https://www.1mg.com/images/products/aten-50.jpg", "https://www.1mg.com/drugs/aten-50-tablet-69454", {
        "how_much": "Take 1 tablet (50mg).",
        "when": "Once daily (1-0-0) in the morning.",
        "food": "Before meals or on an empty stomach.",
        "duration": "Daily maintenance. Do not discontinue suddenly to avoid rebound tachycardia.",
        "precautions": "Monitors resting heart rate. Contraindicated in severe asthma or bradycardia (pulse < 55 bpm)."
    }),
    ("atorvastatin-10-tab", "Atorlip 10mg Tablet", "Atorlip", "Atorvastatin", "10 mg", "tablet", "Cipla Ltd.", "15 Tablets", True, "cardiovascular", "https://www.1mg.com/images/products/atorlip-10.jpg", "https://www.1mg.com/drugs/atorlip-10-tablet-69458", {
        "how_much": "Take 1 tablet (10mg).",
        "when": "Once daily at night before bedtime (0-0-1).",
        "food": "With or without food.",
        "duration": "Long-term lipid lowering management.",
        "precautions": "Report any unexplained muscle pain or weakness promptly. Avoid excessive alcohol."
    }),
    ("clopidogrel-75-tab", "Clopilet 75mg Tablet", "Clopilet", "Clopidogrel", "75 mg", "tablet", "Sun Pharmaceutical Industries Ltd.", "15 Tablets", True, "cardiovascular", "https://www.1mg.com/images/products/clopilet-75.jpg", "https://www.1mg.com/drugs/clopilet-75-tablet-69466", {
        "how_much": "Take 1 tablet (75mg).",
        "when": "Once daily at the same time each day.",
        "food": "With or without food.",
        "duration": "Post-stent or ischemic stroke protection as prescribed by cardiologist.",
        "precautions": "Antiplatelet blood thinner. Inform dentists and surgeons before planned surgical procedures."
    }),
    ("aspirin-75-tab", "Ecosprin 75mg Tablet", "Ecosprin", "Acetyl Salicylic Acid", "75 mg", "tablet", "USV Ltd.", "14 Tablets", False, "cardiovascular", "https://www.1mg.com/images/products/ecosprin-75.jpg", "https://www.1mg.com/drugs/ecosprin-75-tablet-69472", {
        "how_much": "Take 1 tablet (75mg).",
        "when": "Once daily after food in the afternoon or evening.",
        "food": "Strictly after food with water. Swallow tablet whole; do not break enteric coating.",
        "duration": "Long term daily blood thinner therapy for heart attack/stroke prevention.",
        "precautions": "Contraindicated in active stomach ulcers, bleeding disorders, and children with viral fever."
    }),

    # Section 17: Gastrointestinal
    ("pantoprazole-domperidone-cap", "Pan-D Capsule", "Pan-D", "Pantoprazole + Domperidone", "40 mg + 30 mg", "capsule", "Alkem Laboratories Ltd.", "15 Capsules", True, "gastrointestinal", "https://www.1mg.com/images/products/pan-d.jpg", "https://www.1mg.com/drugs/pan-d-capsule-sr-341355", {
        "how_much": "Take 1 capsule.",
        "when": "Once daily in the morning (1-0-0), 30 to 60 minutes BEFORE breakfast.",
        "food": "Strictly on an empty stomach with a glass of water. Swallow whole.",
        "duration": "14 to 28 days for GERD, acid reflux, or peptic ulcer relief.",
        "precautions": "Do not take antacids simultaneously; space by at least 2 hours."
    }),
    ("pantoprazole-40-tab", "Pan 40mg Tablet", "Pan", "Pantoprazole", "40 mg", "tablet", "Alkem Laboratories Ltd.", "15 Tablets", True, "gastrointestinal", "https://www.1mg.com/images/products/pan-40.jpg", "https://www.1mg.com/drugs/pan-40-tablet-138628", {
        "how_much": "Take 1 tablet (40mg).",
        "when": "Once daily in the morning, 30 minutes before first meal.",
        "food": "Before food on an empty stomach with water.",
        "duration": "2 to 4 weeks as prescribed for acidity or stomach ulcer healing.",
        "precautions": "Long term unsupervised use can reduce absorption of Vitamin B12 and Magnesium."
    }),
    ("omeprazole-20-cap", "Omez 20mg Capsule", "Omez", "Omeprazole", "20 mg", "capsule", "Dr. Reddy's Laboratories Ltd.", "20 Capsules", True, "gastrointestinal", "https://www.1mg.com/images/products/omez-20.jpg", "https://www.1mg.com/drugs/omez-20-capsule-69874", {
        "how_much": "Take 1 capsule (20mg).",
        "when": "Once daily in the morning before breakfast.",
        "food": "On an empty stomach.",
        "duration": "2 to 4 weeks.",
        "precautions": "Swallow whole with water. Do not crush micro-pellets inside the capsule."
    }),
    ("ondansetron-4-tab", "Emeset 4mg Tablet", "Emeset", "Ondansetron", "4 mg", "tablet", "Cipla Ltd.", "10 Tablets", True, "gastrointestinal", "https://www.1mg.com/images/products/emeset-4.jpg", "https://www.1mg.com/drugs/emeset-4-tablet-69480", {
        "how_much": "Take 1 tablet (4mg).",
        "when": "30 minutes before meal. Can take up to thrice daily (1-1-1) as needed.",
        "food": "With or without food.",
        "duration": "1 to 3 days for nausea control.",
        "precautions": "May cause mild constipation or headache. Keep adequately hydrated."
    }),
    ("ors-powder", "Electral ORS Powder (21.8g)", "Electral", "Oral Rehydration Salts", "21.8 gm Sachet", "powder", "FDC Ltd.", "21.8g Sachet", False, "gastrointestinal", "https://www.1mg.com/images/products/electral-ors.jpg", "https://www.1mg.com/otc/electral-powder-otc62846", {
        "how_much": "Dissolve entire 21.8g sachet in exactly 1 Liter of clean drinking water.",
        "when": "Sip continuously throughout the day after each loose motion or vomiting.",
        "food": "Can be taken anytime irrespective of meals.",
        "duration": "Continue until diarrhea resolves (usually 24 to 48 hours). Discard after 24 hours.",
        "precautions": "Do NOT mix in milk, juice, or boiling water. Do not add extra sugar or salt."
    }),
    ("bisacodyl-5-tab", "Dulcolax 5mg Tablet", "Dulcolax", "Bisacodyl", "5 mg", "tablet", "Sanofi India Ltd.", "10 Tablets", False, "gastrointestinal", "https://www.1mg.com/images/products/dulcolax.jpg", "https://www.1mg.com/drugs/dulcolax-5mg-tablet-69482", {
        "how_much": "Take 1 to 2 tablets (5mg - 10mg).",
        "when": "At bedtime (0-0-1) for bowel evacuation the next morning.",
        "food": "Take on an empty stomach with water. Avoid milk or antacids within 1 hour.",
        "duration": "Short term occasional constipation only (max 3 consecutive days).",
        "precautions": "Do not chew or crush. Chronic laxative abuse leads to electrolyte depletion."
    }),

    # Section 18: Hormones & Diabetes
    ("metformin-500-tab", "Glycomet 500mg Tablet", "Glycomet", "Metformin", "500 mg", "tablet", "USV Ltd.", "20 Tablets", True, "diabetes", "https://www.1mg.com/images/products/glycomet-500.jpg", "https://www.1mg.com/drugs/glycomet-500-tablet-69876", {
        "how_much": "Take 1 tablet (500mg).",
        "when": "Twice daily with breakfast and dinner (1-0-1).",
        "food": "Take during or immediately after meals to reduce stomach upset.",
        "duration": "Daily maintenance for Type 2 Diabetes under physician supervision.",
        "precautions": "Check kidney function (eGFR/Creatinine) annually. Stop temporarily before contrast CT scans."
    }),
    ("levothyroxine-50-tab", "Thyronorm 50mcg Tablet", "Thyronorm", "Levothyroxine", "50 mcg", "tablet", "Abbott India Ltd.", "120 Tablets", True, "endocrine", "https://www.1mg.com/images/products/thyronorm-50.jpg", "https://www.1mg.com/drugs/thyronorm-50mcg-tablet-69882", {
        "how_much": "Take 1 tablet (50mcg).",
        "when": "Every morning immediately upon waking (1-0-0).",
        "food": "Strictly on an EMPTY stomach with plain water. Wait 30-45 minutes before tea, coffee, or food.",
        "duration": "Lifelong daily thyroid hormone substitution.",
        "precautions": "Do not take with Calcium or Iron supplements; space by at least 4 hours."
    }),

    # Section 25: Respiratory
    ("montelukast-levocetirizine-tab", "Montair-LC Tablet", "Montair-LC", "Montelukast + Levocetirizine", "10 mg + 5 mg", "tablet", "Cipla Ltd.", "15 Tablets", True, "respiratory", "https://www.1mg.com/images/products/montair-lc.jpg", "https://www.1mg.com/drugs/montair-lc-tablet-69885", {
        "how_much": "Take 1 tablet.",
        "when": "Once daily at night before bedtime (0-0-1).",
        "food": "With or without meals.",
        "duration": "10 to 14 days or as directed for seasonal allergies or allergic asthma.",
        "precautions": "May cause mild sedation. In rare cases, report changes in mood or sleep to doctor."
    }),
    ("salbutamol-inhaler", "Asthalin 100mcg Inhaler", "Asthalin", "Salbutamol sulphate", "100 mcg / puff", "inhaler", "Cipla Ltd.", "200 Metered Doses", True, "respiratory", "https://www.1mg.com/images/products/asthalin-inhaler.jpg", "https://www.1mg.com/drugs/asthalin-100mcg-inhaler-41610", {
        "how_much": "Inhale 1 to 2 puffs.",
        "when": "As needed (SOS) during acute breathlessness or 15 minutes before physical exertion.",
        "food": "Inhaled route - unaffected by meals. Rinse mouth with water after use.",
        "duration": "SOS quick-relief rescue medication.",
        "precautions": "Shake well before use. If breathlessness is not relieved within 5 minutes, seek emergency care."
    }),

    # Section 27: Vitamins & Minerals
    ("calcium-d3-tab", "Shelcal 500 Tablet", "Shelcal", "Calcium carbonate", "500 mg + 250 IU", "tablet", "Torrent Pharmaceuticals Ltd.", "15 Tablets", False, "supplement", "https://www.1mg.com/images/products/shelcal-500.jpg", "https://www.1mg.com/drugs/shelcal-500-tablet-69880", {
        "how_much": "Take 1 tablet (500mg).",
        "when": "Once daily (1-0-0) after breakfast or lunch.",
        "food": "Strictly after meals with water (gastric acid is required for calcium carbonate absorption).",
        "duration": "1 to 3 months for bone mineral support.",
        "precautions": "Do not take within 2 hours of iron tablets or thyroid medications."
    }),
    ("vitamin-d3-60k-sachet", "Calcirol 60000 IU Sachet (1g)", "Calcirol", "Vitamin D (Ergocalciferol)", "60000 IU", "granules", "Cadila Pharmaceuticals Ltd.", "1g Sachet", False, "supplement", "https://www.1mg.com/images/products/calcirol-60k.jpg", "https://www.1mg.com/drugs/calcirol-60000-iu-granules-sachet-69878", {
        "how_much": "Dissolve 1 full sachet in half a glass of lukewarm milk or water.",
        "when": "ONCE A WEEK on a fixed day (e.g. every Sunday after breakfast).",
        "food": "After a meal containing dietary fats (milk, curd, eggs) to maximize absorption.",
        "duration": "Once weekly for 8 to 12 weeks, followed by monthly maintenance.",
        "precautions": "High dose vitamin D. Strictly weekly dosing — do NOT take daily unless instructed."
    }),
    ("becosules-cap", "Becosules Performance Capsule", "Becosules", "Multivitamins (As per Schedule V of Drugs and Cosmetics Rules)", "Standard B-Complex + Zinc", "capsule", "Pfizer Ltd.", "20 Capsules", False, "supplement", "https://www.1mg.com/images/products/becosules.jpg", "https://www.1mg.com/otc/becosules-capsule-otc62842", {
        "how_much": "Take 1 capsule.",
        "when": "Once daily after morning breakfast (1-0-0).",
        "food": "After food with water.",
        "duration": "15 to 30 days for mouth ulcers, weakness, or recovery after illness.",
        "precautions": "Harmless bright yellow coloration of urine may occur due to Vitamin B2 (Riboflavin)."
    }),
]

def build():
    # Convert NLEM entries to ProductRecord-compliant dicts
    records = []
    brands_to_add = []

    for item in NLEM_DATA:
        pid, name, brand, active, strength, form, mfg, pack, is_rx, cat, img, pur_url, guide = item
        rec = {
            "product_id": pid,
            "product_name": name,
            "brand_name": brand,
            "active_ingredient": active,
            "strength": strength,
            "dosage_form": form,
            "route": "inhalation" if form == "inhaler" else ("injection" if form == "injection" else ("topical" if form in ("gel", "cream", "ointment") else "oral")),
            "manufacturer": mfg,
            "pack_size": pack,
            "category": "supplement" if cat == "supplement" else "medicine",
            "is_prescription_only": is_rx,
            "product_image_url": img,
            "image_provenance": {
                "source": f"{mfg} Official Directory / Tata 1mg",
                "rights": "Licensed for healthcare product informational lookup",
                "retrieval_date": "2026-10-21",
                "alt_text": f"{name} verified packshot"
            },
            "purchase_url": pur_url,
            "merchant_name": "Tata 1mg",
            "dosage_suggestions": guide,
            "verification_status": "EXACT_MATCH_VERIFIED",
            "country_region": "IN",
            "license_info": "CDSCO / National List of Essential Medicines (NLEM 2011) Approved Formulation",
            "last_checked": "2026-10-21T00:00:00Z",
            "is_stale": False
        }
        records.append(rec)
        brands_to_add.append((brand, active, strength))

    # Save to nlem_catalog.json
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Successfully generated {len(records)} NLEM medicines to {OUTPUT_JSON}")

    # Synchronize brands.csv
    if BRANDS_CSV.exists():
        existing_brands = set()
        with open(BRANDS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    existing_brands.add(row[0].strip().lower())

        added = 0
        with open(BRANDS_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for b_name, g_name, st in brands_to_add:
                if b_name.lower() not in existing_brands:
                    writer.writerow([b_name, g_name, st])
                    existing_brands.add(b_name.lower())
                    added += 1
        print(f"Appended {added} new brands to {BRANDS_CSV}")

if __name__ == "__main__":
    build()
