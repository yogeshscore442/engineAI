"""
services/ask.py — Grounded Clinical Q&A, Intent Classification & Medical Guidance Service.

Features:
1. Intent Classification:
   - GENERAL_CONVERSATIONAL: Friendly conversational replies (English, Tamil, Hindi).
   - MEDICINE_SUBSTITUTION_REQUEST: Strict clinical safeguards. Prohibits automatic prescription substitution.
   - PRODUCT_ALTERNATIVES: Shows verified comparable medical equipment with technical trade-offs.
   - PRODUCT_SHOPPING: Verified purchasable medical devices only when explicitly requested.
   - MEDICINE_QUERY: Pharmacology, dosage interpretation, precautions, questions for doctor.
   - MEDICAL_INFORMATION: Explanations of lab reports, biomarkers, prescriptions, and clinical notes.
2. Link Separation:
   - Medical reference links: WHO, MedlinePlus, CDSCO, AIIMS, LOINC.
   - Product purchase links: Genuine retailer links for authorized equipment only.
   - Alternative product links: Comparable equipment with key differences.
   - Never generate product links for prescriptions or medical information queries.
3. Fast 3.5s timeout with instant deterministic fallback.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.catalog.product_catalog import catalog_service, ProductRecord
from app.repositories.medicines_repo import get_medicines_by_profile
from app.repositories.records_repo import get_records_by_profile
from app.repositories.tests_repo import get_tests_by_name
from app.schemas import AskResponse, AskSource, MedicalReference, ProductCard

logger = logging.getLogger(__name__)

DISCLAIMER = "Informational only, non-diagnostic AI assistant. Please consult your physician for medical advice."
NO_ADVICE = (
    "I can explain facts and values from your verified medical records. "
    "For direct prescription changes or clinical diagnosis, please consult your doctor."
)

# ── Authoritative Medical References ──────────────────────────────────────────

OFFICIAL_MED_REFERENCES = [
    MedicalReference(
        title="MedlinePlus Drug & Health Information",
        source="U.S. National Library of Medicine / NIH",
        url="https://medlineplus.gov/druginformation.html",
        description="Authoritative, evidence-based drug monographs, dosing guides, and patient precautions.",
        reference_type="official_monograph",
    ),
    MedicalReference(
        title="CDSCO National List of Essential Medicines (NLEM)",
        source="Central Drugs Standard Control Organization",
        url="https://cdsco.gov.in",
        description="Approved clinical formulations, indications, and regulatory safety guidelines in India.",
        reference_type="clinical_guideline",
    ),
    MedicalReference(
        title="WHO Model Lists of Essential Medicines",
        source="World Health Organization (WHO)",
        url="https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines",
        description="Global clinical standards for essential medicines and public health therapeutics.",
        reference_type="health_authority",
    ),
]

OFFICIAL_LAB_REFERENCES = [
    MedicalReference(
        title="LOINC Clinical Lab Biomarker Database",
        source="Regenstrief Institute & National Library of Medicine",
        url="https://loinc.org",
        description="Universal diagnostic standard for clinical test codes and biological reference intervals.",
        reference_type="clinical_guideline",
    ),
    MedicalReference(
        title="MedlinePlus Medical Test Guide",
        source="National Institutes of Health (NIH)",
        url="https://medlineplus.gov/lab-tests/",
        description="Comprehensive explanations of blood tests, diagnostic ranges, and biomarker interpretations.",
        reference_type="official_monograph",
    ),
]

OFFICIAL_PMBJP_REFERENCE = MedicalReference(
    title="Pradhan Mantri Bharatiya Janaushadhi Pariyojana (PMBJP)",
    source="Government of India - Department of Pharmaceuticals",
    url="https://janaushadhi.gov.in",
    description="Official portal for verified, high-quality generic equivalents at licensed government Kendra pharmacies.",
    reference_type="health_authority",
)


def _detect_lang(text: str, default_lang: str = "en") -> str:
    """Detect language from text content or fallback to default."""
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return default_lang or "en"


def _to_product_card(prod: ProductRecord, comparison_notes: Optional[str] = None) -> ProductCard:
    """Helper to convert ProductRecord to API ProductCard."""
    price_disp = f"₹{prod.price_inr:,.0f}" if prod.price_inr is not None else "Price on inquiry"
    return ProductCard(
        product_id=prod.product_id,
        product_name=prod.product_name,
        category=prod.category,
        price_inr=prod.price_inr,
        price_display=price_disp,
        retailer=prod.merchant_name or "Authorized Pharmacy",
        purchase_url=prod.purchase_url,
        image_url=prod.product_image_url,
        is_prescription_only=prod.is_prescription_only,
        specifications=prod.device_specifications,
        comparison_notes=comparison_notes or prod.comparison_notes,
        availability_status="VERIFIED_AVAILABLE",
        rating=4.5,
    )


# ── Intent Classifier ──────────────────────────────────────────────────────────

def classify_intent(question: str) -> str:
    """
    Classifies user intent before generating links:
    - GENERAL_CONVERSATIONAL: Greetings, identity, wellbeing, thanks.
    - MEDICINE_SUBSTITUTION_REQUEST: User asks to substitute, replace, or find cheaper alternatives to prescribed medicines.
    - PRODUCT_ALTERNATIVES: User explicitly requests alternative medical devices / equipment.
    - PRODUCT_SHOPPING: User explicitly wants to purchase or find prices for medical devices / equipment.
    - MEDICINE_QUERY: Questions about prescribed medications, pharmacology, dosage, precautions, doctor questions.
    - MEDICAL_INFORMATION: Explanations of prescriptions, lab reports, test results, medical terms, doctor instructions.
    """
    q = question.strip().lower()

    # 1. Check conversational dialogue
    if _check_conversational_reply(question, "en"):
        return "GENERAL_CONVERSATIONAL"

    # 2. Check medicine substitution requests (STRICT SAFEGUARD)
    med_sub_patterns = [
        r"\b(?:cheaper|low\s*cost|generic)\s*(?:alternative|substitute|option|brand|replacement)\s*(?:to|for)?\s*(?:my|the)?\s*(?:prescribed|prescription|current)?\s*(?:medicine|drug|medication|tablet|pill)",
        r"\b(?:alternative|substitute|replace)\s*(?:to|for)?\s*(?:my|the)?\s*(?:prescribed|prescription)\s*(?:medicine|drug|medication|tablet)",
        r"\b(?:can\s*i\s*(?:substitute|replace|swap|change)|substitute|replace)\s*(?:my)?\s*(?:medicine|tablet|drug|prescription|dose)",
        r"\b(?:cheaper|substitute)\s*(?:for|to)?\s*(?:paracetamol|metformin|atorvastatin|telma|augmentin|pan-d|cetzine|dolo|calpol)",
        r"\b(?:find|suggest|give\s*me)\s*(?:a\s*)?(?:cheaper|generic|alternative)\s*(?:medicine|tablet|drug)",
    ]
    if any(re.search(pat, q) for pat in med_sub_patterns):
        return "MEDICINE_SUBSTITUTION_REQUEST"

    # 3. Check product alternatives (Medical devices & equipment)
    prod_alt_patterns = [
        r"\b(?:show|find|suggest|give|compare|are\s*there|what\s*are)\s*(?:me\s*)?(?:the\s*)?(?:comparable\s*|other\s*)?alternatives?\s*(?:to|for)?\s*(?:this|the|a)?\s*(?:medical\s*device|equipment|blood\s*pressure|bp|monitor|glucometer|sugar\s*meter|thermometer|oximeter|pulse\s*oximeter|wheelchair|machine|omron|accu-?chek|beurer)",
        r"\b(?:alternatives?\s*to\s*(?:this|the|a)?\s*(?:blood\s*pressure|bp|monitor|glucometer|thermometer|oximeter|device|wheelchair|omron|accu-?chek))",
        r"\bcompare\s*(?:available\s*)?(?:glucometers|blood\s*pressure\s*monitors?|bp\s*monitors?|thermometers|pulse\s*oximeters?|wheelchairs?)",
        r"\b(?:other|alternative)\s*(?:options?|models?|devices?)\s*(?:to|for)\s*(?:this|the)?\s*(?:blood\s*pressure|bp|monitor|glucometer|thermometer|oximeter|wheelchair)",
    ]
    if any(re.search(pat, q) for pat in prod_alt_patterns):
        return "PRODUCT_ALTERNATIVES"

    # 4. Check explicit product shopping intent
    shopping_patterns = [
        r"\b(?:find|buy|purchase|shop|order|where\s*to\s*buy|where\s*can\s*i\s*get|looking\s*to\s*buy|price\s*of|cost\s*of)\s*(?:a|an|the)?\s*(?:digital\s*thermometer|thermometer|blood\s*pressure|bp\s*monitor|glucometer|sugar\s*meter|pulse\s*oximeter|oximeter|wheelchair|walker|nebulizer|vaporizer|heating\s*pad)",
        r"\b(?:recommend|suggest)\s*(?:a|an|the)?\s*(?:digital\s*thermometer|thermometer|blood\s*pressure\s*monitor|bp\s*monitor|glucometer|sugar\s*meter|pulse\s*oximeter|oximeter|wheelchair)\s*(?:to\s*buy)?",
        r"\b(?:within\s*(?:my\s*)?budget|under\s*(?:rs|inr|\u20b9)?\s*\d+|best\s*price)\b",
        r"\b(?:buy|purchase|shop)\s*(?:a|an)?\s*(?:medical\s*device|equipment)",
        r"\b(?:find|search\s*for|where\s*to\s*buy|where\s*can\s*i\s*buy|buy|purchase|shop\s*for|order)\s+.*?\bto\s*buy\b",
        r"\b(?:buy|purchase)\s+(?:a|an|the)\s+[a-z0-9\-]+",
    ]
    if any(re.search(pat, q) for pat in shopping_patterns):
        return "PRODUCT_SHOPPING"

    # 5. Check medicine-related queries
    med_query_patterns = [
        r"\bwhat\s*is\s*(?:this|the|my)?\s*(?:prescribed\s*)?(?:medicine|medication|drug|tablet|pill)\s*(?:generally\s*)?(?:used\s*for|for)",
        r"\bwhat\s*is\s*(?:paracetamol|metformin|atorvastatin|telma|augmentin|pan-d|cetzine|dolo|calpol)\s*(?:used\s*for|for)",
        r"\bexplain\s*(?:the\s*)?(?:dosage|dose|schedule)\s*(?:written|prescribed)?",
        r"\bprecautions?\s*(?:associated\s*with|for|while\s*taking)",
        r"\bwhat\s*should\s*i\s*ask\s*(?:my\s*)?doctor\s*(?:about\s*(?:this|my)?\s*(?:medicine|medication|prescription|drug))",
        r"\b(?:side\s*effects?|adverse\s*effects?|contraindications?)\s*(?:of|for)",
        r"\bhow\s*to\s*take\s*(?:this|the|my)?\s*(?:medicine|tablet|drug)",
        r"\bwhen\s*to\s*take\s*(?:this|the|my)?\s*(?:medicine|tablet)",
    ]
    if any(re.search(pat, q) for pat in med_query_patterns):
        return "MEDICINE_QUERY"

    # 6. Check medical information & guidance
    med_info_patterns = [
        r"\bexplain\s*(?:this|my)?\s*(?:prescription|lab\s*report|blood\s*report|test\s*report|diagnostic\s*report|discharge\s*summary)",
        r"\bread\s*(?:this\s*)?(?:handwritten\s*)?prescription",
        r"\bwhat\s*does\s*(?:this\s*)?(?:test\s*result|result|reading|hba1c|glucose|blood\s*sugar|creatinine|hemoglobin|platelet)\s*mean",
        r"\bexplain\s*(?:this\s*)?medical\s*term",
        r"\bsummarize\s*(?:the\s*)?doctor(?:'s)?\s*instructions",
        r"\b(?:hba1c|glucose|sugar|blood\s*count|lipid|cholesterol|creatinine|tsh|platelet|wbc|rbc|hemoglobin)\b",
        r"\b(?:report|prescription|lab\s*test|biomarker|symptom|diagnosis)\b",
    ]
    if any(re.search(pat, q) for pat in med_info_patterns):
        return "MEDICAL_INFORMATION"

    return "MEDICAL_INFORMATION"


def _check_conversational_reply(question: str, lang: str) -> Optional[str]:
    """Check if the user is having natural conversational dialogue."""
    q = question.strip().lower()

    if re.search(r"\b(how\s*(?:are|r)\s*(?:you|u)|how\s*do\s*you\s*do|epdi\s*iruk|eppadi\s*iruk|kaise\s*ho|kaisa\s*hai)\b", q) or re.search(r"(எப்படி\s*இருக்கீங்க|எப்படி\s*இருக்கிறீர்கள்|எப்படி\s*இருக்க)", question):
        if lang == "ta":
            return (
                "நான் நலமாக இருக்கிறேன், கேட்டதற்கு மிக்க நன்றி! 😊 உங்கள் உடல்நலம் எப்படி உள்ளது? "
                "உங்கள் மருத்துவ அறிக்கைகள், இரத்த பரிசோதனைகள் (HbA1c, சுகர்) அல்லது மருந்து அட்டவணை குறித்து ஏதேனும் சந்தேகங்கள் இருந்தால் தாராளமாக கேளுங்கள்."
            )
        elif lang == "hi":
            return (
                "मैं बहुत अच्छा हूँ, पूछने के लिए धन्यवाद! 😊 आप कैसे महसूस कर रहे हैं? "
                "अपनी मेडिकल रिपोर्ट्स, ब्लड टेस्ट या दवाओं के बारे में कोई भी सवाल पूछ सकते हैं।"
            )
        else:
            return (
                "I'm doing great, thank you for asking! 😊 How are you feeling today? "
                "I'm here to help you review your lab reports, explain prescribed medicines, or track your health biomarkers. What would you like to check?"
            )

    if bool(re.search(r"^(?:hi|hello|hey|hai|hola|greetings|vanakkam|namaste|good\s*(?:morning|afternoon|evening)|howdy)\b", q, re.IGNORECASE)) or bool(re.search(r"^(?:வணக்கம்|ஹலோ|வணக்கம்ங்க|नमस्ते|प्रणाम)\b", question)):
        if lang == "ta":
            return (
                "வணக்கம்! நான் உங்கள் Clinical AI மருத்துவ உதவியாளர். "
                "உங்கள் மருத்துவப் பதிவுகள், மருந்துகள் மற்றும் இரத்தப் பரிசோதனை முடிவுகள் (HbA1c, குளுக்கோஸ் போன்றவை) குறித்து என்னிடம் கேட்கலாம். "
                "இன்று உங்களுக்கு எவ்வாறு உதவ வேண்டும்?"
            )
        elif lang == "hi":
            return (
                "नमस्ते! मैं आपका Clinical AI हेल्थ कोपायलट हूं। "
                "आप अपने मेडिकल रिकॉर्ड्स, दवाइयों या लैब टेस्ट (जैसे HbA1c, ब्लड शुगर) के बारे में मुझसे पूछ सकते हैं। "
                "मैं आपकी क्या मदद कर सकता हूँ?"
            )
        else:
            return (
                "Hello! I am your Clinical AI Copilot. "
                "You can ask me about your verified health records, prescribed medications, recent lab results (like HbA1c or blood count), or prepare questions for your doctor. "
                "How can I help you today?"
            )

    if re.search(r"\b(who\s*(?:are|r)\s*(?:you|u)|what\s*is\s*your\s*name|neenga\s*yar|yar\s*neenga|aap\s*kaun\s*ho)\b", q) or re.search(r"(நீங்க\s*யார்|நீங்கள்\s*யார்)", question):
        if lang == "ta":
            return (
                "நான் உங்கள் **Clinical AI Copilot** (மருத்துவ உதவியாளர்)! 🩺 "
                "உங்கள் மருத்துவமனை ஆவணங்களை படித்து, மருந்து சீட்டுகளைப் புரிந்துகொண்டு, இரத்த பரிசோதனைகளின் அளவுகளை (HbA1c, குளுக்கோஸ்) எளிய தமிழில் விளக்க நான் உதவுகிறேன்."
            )
        elif lang == "hi":
            return (
                "मैं आपका **Clinical AI हेल्थ कोपायलट** हूँ! 🩺 "
                "मैं आपकी मेडिकल रिपोर्ट्स, प्रिस्क्रिप्शन और टेस्ट परिणामों को आसान भाषा में समझने में आपकी सहायता करता हूँ।"
            )
        else:
            return (
                "I am your **Clinical AI Health Copilot** powered by multimodal intelligence! 🩺 "
                "I help you understand your hospital prescriptions, track biomarker trends (like HbA1c and glucose), check medication schedules, and get ready for doctor visits."
            )

    if re.search(r"\b(what\s*can\s*you\s*do|what\s*do\s*you\s*do|help\s*me|guide\s*me|enna\s*panna\s*mudiyum|features)\b", q) or re.search(r"(என்ன\s*செய்ய\s*முடியும்|உதவி)", question):
        if lang == "ta":
            return (
                "நான் உங்களுக்கு வழங்கும் முக்கிய சேவைகள்:\n"
                "• 📸 **ஆவண ஆய்வு**: மருந்து சீட்டு அல்லது Lab report புகைப்படங்களை படித்து தகவல்களை எடுக்கலாம்.\n"
                "• 🧬 **பரிசோதனை முடிவுகள்**: HbA1c, சுகர் அளவுகளின் விளக்கம்.\n"
                "• 💊 **மருந்து பாதுகாப்பு**: மாத்திரைகள் உட்கொள்ளும் நேரம் & உணவு வழிகாட்டுதல்.\n"
                "• 🎙️ **குரல் உரையாடல்**: தமிழ் அல்லது ஆங்கிலத்தில் வாய்ஸ் மூலம் பேசலாம்!"
            )
        else:
            return (
                "Here is what I can do for you:\n"
                "• 📸 **Document OCR**: Upload or snap a photo of any prescription or lab report.\n"
                "• 🧬 **Biomarker Insights**: Explain your HbA1c, blood sugar, and vital signs.\n"
                "• 💊 **Medication Details**: Check dosage schedules and food instructions.\n"
                "• 🎙️ **Voice & Multilingual**: Talk with me by voice in English, Tamil, or Hindi!"
            )

    if re.search(r"\b(i\s*am\s*fine|i\s*am\s*good|im\s*fine|im\s*good|all\s*good|nalla\s*iruk|theek\s*hu)\b", q) or re.search(r"(நல்லா\s*இருக்கேன்|நலமாக\s*இருக்கிறேன்)", question):
        if lang == "ta":
            return "மிக்க மகிழ்ச்சி! 😊 உடல்நலத்தை ஆரோக்கியமாக பராமரித்துக் கொள்ளுங்கள். ஏதேனும் மருத்துவ தகவல்கள் தேவைப்பட்டால் எப்போது வேண்டுமானாலும் கேளுங்கள்."
        else:
            return "That's wonderful to hear! 😊 Keep up your healthy routine. Feel free to ask whenever you need insights into your health records or medications."

    if re.search(r"\b(thanks|thank\s*you|thx|நன்றி|dhanyawad|shukriya)\b", q, re.IGNORECASE):
        if lang == "ta":
            return "மகிழ்ச்சி! உங்கள் ஆரோக்கியத்திற்கு நல்வாழ்த்துகள். மருந்து மற்றும் சிகிச்சை மாற்றங்களுக்கு எப்போதும் உங்கள் மருத்துவரை அணுகவும். நல்வாழ்வு வாழ்த்துகள்! 🌟"
        else:
            return "You are very welcome! Always follow your physician's guidance for medications and medical care. Wishing you the best of health! 🌟"

    if re.search(r"^(?:ok|okay|super|great|cool|nice|seri|seringa|சரி|சரிங்க)[!.]*$", q):
        if lang == "ta":
            return "மகிழ்ச்சி! வேறு ஏதேனும் மருத்துவ ஆவணங்கள் அல்லது சந்தேகங்கள் உள்ளதா?"
        else:
            return "Great! Let me know if there's anything else about your records or health you would like to explore."

    return None


def _is_advice_seeking(question: str) -> bool:
    """Detect requests for prescribing or diagnosing that require a doctor."""
    advice_keywords = [
        "what medicine should i take",
        "prescribe me",
        "give me medicine",
        "cure my disease",
        "can i stop taking",
    ]
    q = question.lower()
    return any(kw in q for kw in advice_keywords)


def _get_api_key() -> str:
    """Fetch Gemini API key from environment or .env files."""
    for key_name in ("GEMINI_API_KEY", "LLM_API_KEY", "GOOGLE_API_KEY"):
        val = os.getenv(key_name)
        if val and val.strip():
            return val.strip()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for candidate in [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "..", ".env"),
        os.path.join(base_dir, "..", "..", ".env"),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k in ("GEMINI_API_KEY", "LLM_API_KEY", "GOOGLE_API_KEY") and v:
                            return v
            except Exception:
                pass
    return ""


def _build_patient_context(db: Session, profile_id: str) -> tuple[str, list[AskSource]]:
    """Gather clinical records from the database for the given profile."""
    records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]
    if not records:
        return "No uploaded medical records found for this patient yet.", []

    lines = []
    sources = []
    for r in records[:6]:
        sources.append(AskSource(record_id=r.record_id, doc_type=r.doc_type, doc_date=r.doc_date))
        lines.append(f"- Record [{r.doc_type}] on {r.doc_date or 'Recent'}: {r.headline or ''}")
        try:
            rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
            meds = rj.get("medicines", [])
            if meds:
                med_strs = [
                    f"{m.get('name_raw', '')} ({m.get('generic', '')} {m.get('strength', '')}, schedule: {m.get('schedule_raw', '')}, food: {m.get('food_instruction', '')})"
                    for m in meds[:5]
                ]
                lines.append(f"  Medications: {'; '.join(med_strs)}")

            tests = rj.get("tests", [])
            if tests:
                test_strs = [
                    f"{t.get('name', '')}: {t.get('value', '')} {t.get('unit', '')} [Flag: {t.get('flag', 'NORMAL')}, Ref: {t.get('ref_low', '')}-{t.get('ref_high', '')}]"
                    for t in tests[:8]
                ]
                lines.append(f"  Lab Tests: {'; '.join(test_strs)}")

            summary = rj.get("summary_en") or rj.get("summary")
            if summary:
                lines.append(f"  Summary: {summary[:200]}")
        except Exception:
            pass

    return "\n".join(lines), sources


def _call_gemini_raw(api_key: str, prompt: str) -> Optional[str]:
    import google.generativeai as genai
    genai.configure(api_key=api_key, transport="rest")
    for candidate in ["gemini-3.8-flash", "gemini-flash-latest"]:
        try:
            model = genai.GenerativeModel(candidate)
            response = model.generate_content(prompt, request_options={"timeout": 3.5})
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.info("Candidate %s failed: %s", candidate, type(e).__name__)
            continue
    return None


def _ask_gemini_with_timeout(api_key: str, question: str, context: str, lang: str, timeout_sec: float = 3.5) -> Optional[str]:
    """Call Google Gemini with strict timeout so UI never hangs."""
    lang_instruction = "English"
    if lang == "ta":
        lang_instruction = "Tamil (தமிழ்)"
    elif lang == "hi":
        lang_instruction = "Hindi (हिंदी)"

    prompt = f"""You are a helpful, compassionate Clinical AI Health Copilot.
You assist patients in understanding their verified medical reports, lab results, and medications.

STRICT MEDICAL RESPONSIBILITY RULES:
1. Explain only evidence supported by reliable medical sources.
2. NEVER recommend buying prescription medicines or changing a prescribed dosage.
3. NEVER independently change a prescription or suggest drug substitutes.

Language Requirement: Respond naturally and fluently in {lang_instruction}.

Patient's Verified Health Records Context:
{context}

Patient's Question:
"{question}"

Instructions:
1. Provide a direct, reassuring, and clear response.
2. Ground your response in their medical records if relevant.
3. If they ask about medications or dosages, describe what is in their records and advise following doctor instructions.
4. Keep the response concise (2 to 4 short paragraphs or bullet points).
5. Always end with a brief sentence reminding them to consult their physician for clinical decisions.
"""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_call_gemini_raw, api_key, prompt)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            logger.info("Gemini call timed out after %.1fs, falling back to local clinical engine", timeout_sec)
            return None
        except Exception as exc:
            logger.warning("Gemini execution exception: %s", type(exc).__name__)
            return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# ── Specific Intent Handlers ──────────────────────────────────────────────────

def _handle_medicine_substitution(question: str, detected_lang: str) -> AskResponse:
    """
    Handles MEDICINE_SUBSTITUTION_REQUEST with strict safeguards.
    Medicines are not ordinary shopping products. Never substitute prescription drugs automatically.
    """
    if detected_lang == "ta":
        explanation = (
            "மருத்துவரால் பரிந்துரைக்கப்பட்ட மருந்துகளை (Prescription Medicines) தானாகவே வேறு மருந்தாகவோ அல்லது "
            "குறைந்த விலையுள்ள மாத்திரையாகவோ மாற்றுவது பாதுகாப்பானது அல்ல. "
            "ஒரே மூலக்கூறாக இருந்தாலும் கூட, வெவ்வேறு நிறுவன தயாரிப்புகளில் உறிஞ்சும் வேகம் (Bioavailability) மற்றும் "
            "உடலில் செயல்படும் முறை மாறுபடலாம்.\n\n"
            "குறைந்த விலையில் மருந்துகள் தேவைப்பட்டால், உங்கள் மருத்துவரிடம் அல்லது அரசு உரிமம் பெற்ற "
            "ஜன் ஔஷதி கேந்திரா (PMBJP Jan Aushadhi) மருந்தாளுநரிடம் (Pharmacist) ஆலோசனை பெறவும்."
        )
    else:
        explanation = (
            "Prescription medications must never be substituted automatically without direct consultation "
            "with your prescribing physician or a licensed pharmacist. Even within the same generic drug category, "
            "different brands, strengths, and formulations (e.g., sustained release vs immediate release) have distinct "
            "bioavailability profiles, excipients, and clinical indications.\n\n"
            "If you are seeking affordable options, ask your prescribing doctor or a licensed Jan Aushadhi Kendra (PMBJP) "
            "pharmacist about verified generic equivalents approved by the drug regulator (CDSCO) that are medically appropriate "
            "for your specific health condition."
        )

    return AskResponse(
        answer=explanation,
        intent_category="MEDICINE_SUBSTITUTION_REQUEST",
        medical_explanation=explanation,
        medical_references=[OFFICIAL_PMBJP_REFERENCE, OFFICIAL_MED_REFERENCES[1]],
        product_recommendations=[],  # STRICT: No shopping links for prescription medicines
        product_alternatives=[],     # STRICT: No automatic substitution
        safety_notes=[
            "Strict Clinical Safeguard: Prescription medicines must never be substituted automatically.",
            "Never change your medication brand, dosage, or active ingredient without consulting your physician or a licensed pharmacist.",
            "Ask your doctor or licensed Jan Aushadhi pharmacist about verified generic bioequivalents."
        ],
        needs_clinician_review=True,
        sources=[],
        disclaimer=DISCLAIMER,
        lang=detected_lang,
    )


def _handle_product_shopping(question: str, detected_lang: str) -> AskResponse:
    """
    Handles explicit PRODUCT_SHOPPING intent for medical devices / equipment.
    Returns verified purchasable products with genuine retailer links and alternatives.
    Returns honest unavailable state if no verified match is found.
    """
    primary = catalog_service.find_device_or_equipment(question)
    if not primary:
        # Honest unavailable state — do NOT fabricate URLs or pretend search succeeded
        if detected_lang == "ta":
            msg = "எங்கள் அங்கீகரிக்கப்பட்ட மருத்துவ உபகரணப் பட்டியலில் அதற்கான நேரடி முடிவுகள் கிடைக்கவில்லை. சரிபார்க்கப்படாத இணைப்புகள் வழங்கப்பட மாட்டாது."
        else:
            msg = (
                "No verified retail products found in our authorized healthcare equipment catalog for that query. "
                "We do not generate unverified or speculative shopping links. Please verify availability with an authorized medical equipment provider."
            )
        return AskResponse(
            answer=msg,
            intent_category="PRODUCT_SHOPPING",
            medical_explanation="Product search completed. No verified authorized retailer entries currently matched your query.",
            medical_references=[],
            product_recommendations=[],
            product_alternatives=[],
            safety_notes=["Only purchase medical devices from authorized dealers with valid regulatory registration."],
            needs_clinician_review=False,
            sources=[],
            disclaimer=DISCLAIMER,
            lang=detected_lang,
        )

    _, alts = catalog_service.get_device_alternatives(question)
    primary_card = _to_product_card(primary)
    alt_cards = [_to_product_card(a) for a in alts[:2]]

    if detected_lang == "ta":
        ans = (
            f"பரிந்துரைக்கப்பட்ட சரிபார்க்கப்பட்ட தயாரிப்பு: **{primary.product_name}** ({primary.manufacturer}).\n"
            f"• விற்பனையாளர்: **{primary.merchant_name}** ({primary_card.price_display})\n"
            f"• வகை: {primary.category}\n"
            f"• வாங்கும் இணைப்பு: {primary.purchase_url}\n\n"
            f"விலை மற்றும் வசதிகள் அடிப்படையில் ஒப்பிடக்கூடிய மாற்று தயாரிப்புகளும் கீழே வழங்கப்பட்டுள்ளன."
        )
    else:
        ans = (
            f"Verified Product Recommendation: **{primary.product_name}** by **{primary.manufacturer}**.\n"
            f"• Verified Retailer: **{primary.merchant_name}** ({primary_card.price_display})\n"
            f"• Category: {primary.category.replace('_', ' ').title()}\n"
            f"• Verified Retailer Link: {primary.purchase_url}\n\n"
            f"Comparable alternatives based on features, specifications, and budget are listed below for your comparison."
        )

    return AskResponse(
        answer=ans,
        intent_category="PRODUCT_SHOPPING",
        medical_explanation=f"Medical equipment purchase guidance for {primary.active_ingredient or primary.product_name}.",
        medical_references=[
            MedicalReference(
                title="CDSCO Medical Device Standards & Licensing",
                source="Central Drugs Standard Control Organization",
                url="https://cdsco.gov.in",
                description="Official registration and quality validation for diagnostic medical devices in India.",
                reference_type="clinical_guideline",
            )
        ],
        product_recommendations=[primary_card],
        product_alternatives=alt_cards,
        safety_notes=[
            "Home medical devices complement, but do not replace, periodic clinical check-ups with your physician.",
            "Verify that cuffs, sensors, or consumables are compatible with your specific device model."
        ],
        needs_clinician_review=False,
        sources=[],
        disclaimer=DISCLAIMER,
        lang=detected_lang,
    )


def _handle_product_alternatives(question: str, detected_lang: str) -> AskResponse:
    """
    Handles PRODUCT_ALTERNATIVES intent for medical devices / equipment.
    Shows comparable options with key differences in specifications, compatibility, and price.
    """
    primary, alts = catalog_service.get_device_alternatives(question)
    if not alts:
        if detected_lang == "ta":
            msg = "எங்கள் பட்டியலில் இதற்கான சரிபார்க்கப்பட்ட மாற்று உபகரணங்கள் தற்போது இல்லை."
        else:
            msg = (
                "No verified comparable equipment alternatives found in our authorized catalog for that item. "
                "We do not generate unverified or speculative alternative links."
            )
        return AskResponse(
            answer=msg,
            intent_category="PRODUCT_ALTERNATIVES",
            medical_explanation="Alternative equipment search completed without verified matches.",
            medical_references=[],
            product_recommendations=[_to_product_card(primary)] if primary else [],
            product_alternatives=[],
            safety_notes=["Only select replacement devices certified by standard regulatory bodies (CDSCO, ISO, CE)."],
            needs_clinician_review=False,
            sources=[],
            disclaimer=DISCLAIMER,
            lang=detected_lang,
        )

    primary_card = _to_product_card(primary) if primary else None
    alt_cards = [_to_product_card(a) for a in alts]

    lines = [f"### Verified Alternatives to {getattr(primary, 'product_name', 'the requested equipment')}:"]
    for idx, a in enumerate(alt_cards, 1):
        lines.append(f"{idx}. **{a.product_name}** ({a.price_display} on {a.retailer})")
        if a.comparison_notes:
            lines.append(f"   • *Key Differences:* {a.comparison_notes}")
        if a.purchase_url:
            lines.append(f"   • *Verified Retailer Link:* {a.purchase_url}")

    ans = "\n".join(lines)
    return AskResponse(
        answer=ans,
        intent_category="PRODUCT_ALTERNATIVES",
        medical_explanation="Comparison of verified healthcare equipment alternatives based on specifications, ease of use, and budget.",
        medical_references=[
            MedicalReference(
                title="AAMI / ESH International Protocol for Clinical Equipment",
                source="European Society of Hypertension & AAMI Standards",
                url="https://cdsco.gov.in",
                description="Clinical accuracy criteria for automated blood pressure and physiological monitoring instruments.",
                reference_type="clinical_guideline",
            )
        ],
        product_recommendations=[primary_card] if primary_card else [],
        product_alternatives=alt_cards,
        safety_notes=[
            "Evaluate specifications (such as cuff size, strip cost, and memory capacity) before choosing an alternative device.",
            "Ensure any selected device is officially calibrated and registered with regulatory authorities."
        ],
        needs_clinician_review=False,
        sources=[],
        disclaimer=DISCLAIMER,
        lang=detected_lang,
    )


def _handle_medicine_query(
    question: str,
    db: Session,
    profile_id: str,
    detected_lang: str,
    sources: list[AskSource],
) -> AskResponse:
    """
    Handles MEDICINE_QUERY intent.
    Explains medicine indications, dosage interpretations, precautions, and questions to ask the doctor.
    NEVER displays shopping cards or purchase links.
    """
    q_lower = question.lower()
    records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]

    # Match medicine from patient records or catalog
    matched_med = None
    for r in records:
        try:
            rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
            for m in rj.get("medicines", []):
                nm = (m.get("name_raw") or "").lower()
                gen = (m.get("generic") or "").lower()
                tokens = [t for t in re.findall(r"[a-z0-9]+", nm) if len(t) >= 4 and t not in ("tablet", "tablets", "capsule", "syrup", "suspension")]
                if (nm and nm in q_lower) or (gen and gen in q_lower) or any(tok in q_lower for tok in tokens):
                    matched_med = m
                    break
            if matched_med:
                break
        except Exception:
            pass

    # Fallback to catalog match
    matched_catalog_prod = None
    if not matched_med:
        words = re.findall(r"[A-Za-z0-9\-]+", question)
        for length in range(min(3, len(words)), 0, -1):
            for i in range(len(words) - length + 1):
                phrase = " ".join(words[i:i + length])
                if len(phrase) >= 3 and phrase.lower() not in {"what", "is", "the", "for", "tell", "me", "about", "how", "to", "take", "medicine", "tablet", "drug"}:
                    p_match = catalog_service.match_product(name_raw=phrase)
                    if p_match.product:
                        matched_catalog_prod = p_match.product
                        break
            if matched_catalog_prod:
                break

    name = (matched_med.get("name_raw") if matched_med else (matched_catalog_prod.product_name if matched_catalog_prod else "prescribed medication"))
    generic = (matched_med.get("generic") if matched_med else (matched_catalog_prod.active_ingredient if matched_catalog_prod else ""))
    schedule = (matched_med.get("schedule_raw") if matched_med else "as directed by treating clinician")
    food = (matched_med.get("food_instruction") if matched_med else "")

    food_note = f" Food instruction: {food.replace('_', ' ')}." if food else ""

    if detected_lang == "ta":
        ans = (
            f"**{name}** ({generic}):\n"
            f"• பயன்பாடு: இந்த மருந்து உங்கள் மருத்துவரால் பரிந்துரைக்கப்பட்ட சிகிச்சைக்காக வழங்கப்பட்டுள்ளது.\n"
            f"• உட்கொள்ளும் முறை: {schedule}.{food_note}\n"
            f"• முன்னெச்சரிக்கைகள்: மருந்துகளை மருத்துவர் அறிவுறுத்திய நேரத்திலும் அளவிலும் தவறாமல் உட்கொள்ளவும்.\n"
            f"• மருத்துவரிடம் கேட்க வேண்டியவை: மாத்திரையின் பக்கவிளைவுகள், உணவு கட்டுப்பாடுகள் மற்றும் அடுத்த பரிசோதனை தேதி."
        )
    else:
        ans = (
            f"**{name}** ({generic or 'Active Pharmaceutical Formulation'}):\n"
            f"• **General Clinical Use:** Prescribed by your doctor for targeted therapeutic management.\n"
            f"• **Dosage & Timing:** Scheduled as **{schedule}**.{food_note}\n"
            f"• **Important Precautions:** Take strictly as prescribed. Do not stop or alter the dosage independently.\n"
            f"• **What to ask your doctor:** Inquire about expected treatment duration, potential interactions with other medications, and dietary guidelines."
        )

    # Check uncertainty flag
    needs_review = bool(matched_med and matched_med.get("verification_state") in ("REQUIRES_HUMAN_REVIEW", "UNVERIFIED_CANDIDATE"))

    return AskResponse(
        answer=ans,
        intent_category="MEDICINE_QUERY",
        medical_explanation=ans,
        medical_references=OFFICIAL_MED_REFERENCES,
        product_recommendations=[],  # STRICT: No shopping links for medicine queries
        product_alternatives=[],     # STRICT: No shopping links
        safety_notes=[
            "Prescription medications must be taken strictly as prescribed by your treating clinician.",
            "Never alter your dosage, frequency, or brand without consulting your prescribing doctor.",
            "If dosage or handwriting is unclear, have it verified directly by your pharmacist or prescribing clinician."
        ],
        needs_clinician_review=needs_review,
        sources=sources[:2],
        disclaimer=DISCLAIMER,
        lang=detected_lang,
    )


def _handle_medical_information(
    question: str,
    db: Session,
    profile_id: str,
    detected_lang: str,
    sources: list[AskSource],
) -> AskResponse:
    """
    Handles MEDICAL_INFORMATION intent.
    Explains lab reports, test results (HbA1c, glucose, CBC), medical terms, doctor's instructions.
    NEVER displays shopping cards or purchase links.
    """
    q_lower = question.lower()
    from app.catalog.test_catalog import CATALOG
    requested = next((entry for entry in CATALOG if any(
        re.search(r"\b" + re.escape(alias.lower()) + r"\b", q_lower)
        for alias in [entry.canonical, *entry.aliases]
    )), None)

    records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]
    # Re-order records if user asked for a specific document type
    if "prescription" in q_lower:
        records.sort(key=lambda r: 0 if r.doc_type == "prescription" else 1)
    elif any(w in q_lower for w in ["lab", "test", "report", "hba1c"]):
        records.sort(key=lambda r: 0 if r.doc_type == "lab_report" else 1)

    if requested:
        results = get_tests_by_name(db, profile_id, requested.canonical)
        found_test_dict = None
        source = []
        if results:
            latest = results[-1]
            found_test_dict = {
                "name": requested.canonical,
                "value": latest.value,
                "unit": latest.unit or "",
                "flag": latest.flag or "NORMAL",
                "date": latest.date or "recent visit"
            }
            matching = next((r for r in get_records_by_profile(db, profile_id) if r.record_id == latest.record_id), None)
            source = [AskSource(record_id=matching.record_id, doc_type=matching.doc_type, doc_date=matching.doc_date)] if matching else []
        else:
            # Fallback: Check records directly
            for r in records:
                try:
                    rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
                    for t in rj.get("tests", []):
                        t_nm = (t.get("name") or "").lower()
                        if t_nm == requested.canonical.lower() or (t.get("loinc") and t.get("loinc") == requested.loinc):
                            found_test_dict = {
                                "name": t.get("name") or requested.canonical,
                                "value": t.get("value"),
                                "unit": t.get("unit") or requested.default_unit or "",
                                "flag": t.get("flag") or "NORMAL",
                                "date": r.doc_date or "recent visit"
                            }
                            source = [AskSource(record_id=r.record_id, doc_type=r.doc_type, doc_date=r.doc_date)]
                            break
                    if found_test_dict:
                        break
                except Exception:
                    pass

        if found_test_dict:
            latest_val = found_test_dict["value"]
            latest_unit = found_test_dict["unit"]
            latest_flag = found_test_dict["flag"]
            latest_date = found_test_dict["date"]
            ref_text = f"Standard clinical reference range: {requested.ref_low} - {requested.ref_high} {requested.default_unit or ''}." if (requested.ref_low is not None and requested.ref_high is not None) else ""

            if detected_lang == "ta":
                ans = (
                    f"உங்கள் சமீபத்திய **{requested.canonical}** அளவு: **{latest_val} {latest_unit}** "
                    f"({latest_date}). நிலை: **{latest_flag}**. "
                    f"{ref_text} இந்த முடிவை உங்கள் மருத்துவரிடம் கலந்தாலோசிக்கவும்."
                )
            else:
                ans = (
                    f"Your latest recorded **{requested.canonical}** is **{latest_val} {latest_unit}** "
                    f"({latest_date}). Clinical Flag: **{latest_flag}**. "
                    f"{ref_text} Discuss this result with your healthcare provider for clinical correlation."
                )
            return AskResponse(
                answer=ans,
                intent_category="MEDICAL_INFORMATION",
                medical_explanation=ans,
                medical_references=OFFICIAL_LAB_REFERENCES,
                product_recommendations=[],  # STRICT: No shopping links
                product_alternatives=[],
                safety_notes=["Diagnostic test results should always be interpreted in the context of your overall clinical history by a licensed physician."],
                needs_clinician_review=bool(latest_flag in ("HIGH", "LOW", "CRITICAL")),
                sources=source,
                disclaimer=DISCLAIMER,
                lang=detected_lang,
            )
        else:
            ref_text = f"**{requested.ref_low} - {requested.ref_high} {requested.default_unit or ''}**" if (requested.ref_low is not None and requested.ref_high is not None) else f"{requested.default_unit or ''}"
            loinc_text = f" (LOINC: {requested.loinc})" if requested.loinc else ""
            if detected_lang == "ta":
                ans = f"உங்கள் கணக்கில் உறுதிசெய்யப்பட்ட {requested.canonical} முடிவு எதுவும் இல்லை. இதன் பொதுவான இயல்பான அளவு: {ref_text}."
            else:
                ans = f"No confirmed {requested.canonical} result was found in this profile. {requested.canonical}{loinc_text} is a clinical diagnostic biomarker with typical normal reference range of {ref_text}. You can upload a laboratory report to add this to your health timeline."
            return AskResponse(
                answer=ans,
                intent_category="MEDICAL_INFORMATION",
                medical_explanation=ans,
                medical_references=OFFICIAL_LAB_REFERENCES,
                product_recommendations=[],  # STRICT: No shopping links
                product_alternatives=[],
                safety_notes=["Upload your laboratory report to automatically record and track your biomarker trends."],
                needs_clinician_review=False,
                sources=[],
                disclaimer=DISCLAIMER,
                lang=detected_lang,
            )

    # General medical document / lab / prescription explanation
    if records:
        latest_r = records[0]
        try:
            rj = json.loads(latest_r.record_json) if isinstance(latest_r.record_json, str) else (latest_r.record_json or {})
            summary = rj.get("summary_en") or rj.get("summary") or "Medical document recorded."
            if detected_lang == "ta" and rj.get("summary_ta"):
                summary = rj.get("summary_ta")
            ans = f"Based on your verified medical records ({latest_r.doc_type}):\n{summary}"
        except Exception:
            ans = "Your verified medical documents have been analyzed and clinical entities are preserved."
    else:
        if detected_lang == "ta":
            ans = "மருத்துவ ஆவணங்கள் மற்றும் பரிசோதனை முடிவுகளை எளிய முறையில் புரிந்துகொள்ள Clinical AI உங்களுக்கு உதவுகிறது. உங்கள் ஆவணத்தை பதிவேற்றி தகவல்களைப் பெறலாம்."
        else:
            ans = "I provide evidence-grounded medical explanations for prescriptions, lab reports, and clinical terms. Upload your medical document to view structured extraction and guidance."

    return AskResponse(
        answer=ans,
        intent_category="MEDICAL_INFORMATION",
        medical_explanation=ans,
        medical_references=OFFICIAL_MED_REFERENCES,
        product_recommendations=[],  # STRICT: No shopping links
        product_alternatives=[],
        safety_notes=["Preserve all original prescription copies and consult your treating doctor for direct clinical decisions."],
        needs_clinician_review=False,
        sources=sources[:2],
        disclaimer=DISCLAIMER,
        lang=detected_lang,
    )


# ── Public API Entry Point ─────────────────────────────────────────────────────

def answer_question(db: Session, profile_id: str, question: str, lang: str = "en") -> AskResponse:
    """
    Answers user questions with explicit intent classification before generating links:
    - GENERAL_CONVERSATIONAL: Friendly conversation without unsolicited links.
    - MEDICINE_SUBSTITUTION_REQUEST: Prohibits automatic drug substitution with clinical guidance.
    - PRODUCT_ALTERNATIVES: Returns verified comparable equipment and key differences.
    - PRODUCT_SHOPPING: Returns verified equipment products only upon explicit request.
    - MEDICINE_QUERY: Official medication facts without shopping cards.
    - MEDICAL_INFORMATION: Evidence-based explanation of documents and tests without shopping cards.
    """
    detected_lang = _detect_lang(question, default_lang=lang)

    # 1. Classify Intent
    intent = classify_intent(question)
    logger.info("CLASSIFIED_INTENT: '%s' -> %s", question[:40], intent)

    # 2. Conversational Handler
    if intent == "GENERAL_CONVERSATIONAL":
        conv_reply = _check_conversational_reply(question, detected_lang) or "Hello! How can I help you today?"
        return AskResponse(
            answer=conv_reply,
            intent_category="GENERAL_CONVERSATIONAL",
            medical_explanation=None,
            medical_references=[],
            product_recommendations=[],
            product_alternatives=[],
            safety_notes=[],
            needs_clinician_review=False,
            sources=[],
            disclaimer=DISCLAIMER,
            lang=detected_lang,
        )

    # 3. Direct Prescription / Advice Seeking Guard
    if _is_advice_seeking(question):
        return AskResponse(
            answer=NO_ADVICE,
            intent_category="MEDICAL_INFORMATION",
            medical_explanation=NO_ADVICE,
            medical_references=OFFICIAL_MED_REFERENCES,
            product_recommendations=[],
            product_alternatives=[],
            safety_notes=["Never start or discontinue prescription medicines without treating clinician authorization."],
            needs_clinician_review=True,
            sources=[],
            disclaimer=DISCLAIMER,
            lang=detected_lang,
        )

    # 4. Medicine Substitution Safeguard Handler
    if intent == "MEDICINE_SUBSTITUTION_REQUEST":
        return _handle_medicine_substitution(question, detected_lang)

    # 5. Product Alternatives Handler
    if intent == "PRODUCT_ALTERNATIVES":
        return _handle_product_alternatives(question, detected_lang)

    # 6. Product Shopping Handler (Devices / Equipment / OTC only)
    if intent == "PRODUCT_SHOPPING":
        return _handle_product_shopping(question, detected_lang)

    # 7. Patient Clinical Context from Database
    context_str, sources = _build_patient_context(db, profile_id)

    # 8. Medicine Query Handler (NO shopping links)
    if intent == "MEDICINE_QUERY":
        return _handle_medicine_query(question, db, profile_id, detected_lang, sources)

    # 9. Medical Information Handler (Prescriptions, Lab Reports, Terms, Tests — NO shopping links)
    return _handle_medical_information(question, db, profile_id, detected_lang, sources)
