"""
services/ask.py — Grounded Q&A and Clinical AI Copilot service.
Supports:
1. Instant friendly multi-turn conversational replies (English, Tamil, Hindi).
2. Live Gemini LLM answering when GEMINI_API_KEY / LLM_API_KEY / GOOGLE_API_KEY is configured.
3. Fast 3.5s timeout with instant smart clinical fallback (no long waiting).
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.medicines_repo import get_medicines_by_profile
from app.repositories.records_repo import get_records_by_profile
from app.repositories.tests_repo import get_tests_by_name
from app.schemas import AskResponse, AskSource

logger = logging.getLogger(__name__)

DISCLAIMER = "Informational only, non-diagnostic AI assistant. Please consult your physician for medical advice."
NO_ADVICE = (
    "I can explain facts and values from your verified medical records. "
    "For direct prescription changes or clinical diagnosis, please consult your doctor."
)


def _detect_lang(text: str, default_lang: str = "en") -> str:
    """Detect language from text content or fallback to default."""
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return default_lang or "en"


def _check_conversational_reply(question: str, lang: str) -> Optional[str]:
    """
    Check if the user is having natural conversational dialogue:
    - Greetings (hi, hello, vanakkam)
    - Wellbeing (how are you, epdi irukinga)
    - Identity (who are you, yar neenga)
    - Capabilities (what can you do, enna panna mudiyum)
    - User status (i am fine, nalla iruken)
    - Gratitude & polite closers (thanks, ok, super)
    """
    q = question.strip().lower()

    # 1. How are you / Epdi irukinga / Kaise ho
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

    # 2. Greetings (hi, hello, hey, vanakkam, namaste)
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

    # 3. Who are you / Neenga yar / Aap kaun ho
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

    # 4. What can you do / Help / Enna panna mudiyum
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

    # 5. User says they are fine (i am fine, nalla iruken, all good)
    if re.search(r"\b(i\s*am\s*fine|i\s*am\s*good|im\s*fine|im\s*good|all\s*good|nalla\s*iruk|theek\s*hu)\b", q) or re.search(r"(நல்லா\s*இருக்கேன்|நலமாக\s*இருக்கிறேன்)", question):
        if lang == "ta":
            return "மிக்க மகிழ்ச்சி! 😊 உடல்நலத்தை ஆரோக்கியமாக பராமரித்துக் கொள்ளுங்கள். ஏதேனும் மருத்துவ தகவல்கள் தேவைப்பட்டால் எப்போது வேண்டுமானாலும் கேளுங்கள்."
        else:
            return "That's wonderful to hear! 😊 Keep up your healthy routine. Feel free to ask whenever you need insights into your health records or medications."

    # 6. Gratitude / Thanks
    if re.search(r"\b(thanks|thank\s*you|thx|நன்றி|dhanyawad|shukriya)\b", q, re.IGNORECASE):
        if lang == "ta":
            return "மகிழ்ச்சி! உங்கள் ஆரோக்கியத்திற்கு நல்வாழ்த்துகள். மருந்து மற்றும் சிகிச்சை மாற்றங்களுக்கு எப்போதும் உங்கள் மருத்துவரை அணுகவும். நல்வாழ்வு வாழ்த்துகள்! 🌟"
        else:
            return "You are very welcome! Always follow your physician's guidance for medications and medical care. Wishing you the best of health! 🌟"

    # 7. Acknowledgment (ok, okay, super, seri, seringa, cool, nice)
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

    # Search common .env locations
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

Language Requirement: Respond naturally and fluently in {lang_instruction}.

Patient's Verified Health Records Context:
{context}

Patient's Question:
"{question}"

Instructions:
1. Provide a direct, reassuring, and clear response.
2. Ground your response in their medical records if relevant.
3. If they ask a general health or wellness question, explain it clearly in simple layman terms.
4. If they ask about medications or dosages, describe what is in their records and advise following doctor instructions.
5. Keep the response concise (2 to 4 short paragraphs or bullet points).
6. Always end with a brief sentence reminding them to consult their physician for clinical decisions.
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


def answer_question(db: Session, profile_id: str, question: str, lang: str = "en") -> AskResponse:
    """Answer a health question with conversational intelligence, Gemini LLM, and fast fallback."""
    detected_lang = _detect_lang(question, default_lang=lang)

    # 1. Instant conversational replies (greetings, how are you, who are you, help, thanks, ok)
    conv_reply = _check_conversational_reply(question, detected_lang)
    if conv_reply:
        return AskResponse(answer=conv_reply, sources=[], disclaimer=DISCLAIMER, lang=detected_lang)

    # 2. Advice seeking check
    if _is_advice_seeking(question):
        return AskResponse(answer=NO_ADVICE, sources=[], disclaimer=DISCLAIMER, lang=detected_lang)

    # 3. Patient clinical context from DB
    context_str, sources = _build_patient_context(db, profile_id)

    # 4. Live Gemini LLM with fast 3.5s timeout
    api_key = _get_api_key()
    if api_key:
        gemini_answer = _ask_gemini_with_timeout(api_key, question, context_str, detected_lang, timeout_sec=3.5)
        if gemini_answer:
            return AskResponse(
                answer=gemini_answer,
                sources=sources[:3],
                disclaimer=DISCLAIMER,
                lang=detected_lang,
            )

    # 5. Smart Local Clinical Engine (Retrieval-Grounded Biomarkers & Medicines)
    q_lower = question.lower()
    from app.catalog.test_catalog import CATALOG
    requested = next((entry for entry in CATALOG if any(
        re.search(r"\b" + re.escape(alias.lower()) + r"\b", q_lower)
        for alias in [entry.canonical, *entry.aliases]
    )), None)
    if requested:
        results = get_tests_by_name(db, profile_id, requested.canonical)
        if results:
            latest = results[-1]
            matching = next((r for r in get_records_by_profile(db, profile_id) if r.record_id == latest.record_id), None)
            source = [AskSource(record_id=matching.record_id, doc_type=matching.doc_type, doc_date=matching.doc_date)] if matching else []
            ref_text = f"Standard clinical reference range: {requested.ref_low} - {requested.ref_high} {requested.default_unit or ''}." if (requested.ref_low is not None and requested.ref_high is not None) else ""
            return AskResponse(
                answer=(
                    f"Your latest recorded **{requested.canonical}** is **{latest.value} {latest.unit or ''}** "
                    f"({latest.date or 'recent visit'}). Status flag: **{latest.flag or 'UNKNOWN'}**. "
                    f"{ref_text} Review this result with your physician."
                ),
                sources=source,
                disclaimer=DISCLAIMER,
                lang=detected_lang,
            )
        else:
            ref_text = f"**{requested.ref_low} - {requested.ref_high} {requested.default_unit or ''}**" if (requested.ref_low is not None and requested.ref_high is not None) else f"{requested.default_unit or ''}"
            loinc_text = f" (LOINC: {requested.loinc})" if requested.loinc else ""
            if detected_lang == "ta":
                ans = f"உங்கள் கணக்கில் உறுதிசெய்யப்பட்ட {requested.canonical} முடிவு எதுவும் இல்லை (No confirmed {requested.canonical} result). இதன் பொதுவான இயல்பான அளவு: {ref_text}."
            else:
                ans = f"No confirmed {requested.canonical} result was found in this profile. {requested.canonical}{loinc_text} is a clinical diagnostic biomarker with typical normal reference range of {ref_text}. You can upload a laboratory report to add this to your health timeline."
            return AskResponse(answer=ans, sources=[], disclaimer=DISCLAIMER, lang=detected_lang)

    # Rule A2: Product Catalog Retrieval for Medicines and Medical Devices
    from app.catalog.product_catalog import catalog_service
    words = re.findall(r"[A-Za-z0-9\-]+", question)
    matched_prod = None
    for length in range(min(3, len(words)), 0, -1):
        for i in range(len(words) - length + 1):
            phrase = " ".join(words[i:i + length])
            if len(phrase) >= 3 and phrase.lower() not in {"what", "is", "the", "for", "tell", "me", "about", "how", "to", "take", "can", "you", "does", "have", "medicine", "tablet", "drug"}:
                prod_match = catalog_service.match_product(name_raw=phrase)
                if prod_match.product or (prod_match.candidate_products and prod_match.match_state != "NO_RELIABLE_MATCH"):
                    matched_prod = prod_match.product or prod_match.candidate_products[0]
                    break
        if matched_prod:
            break

    if matched_prod:
        # Check if patient has a record of this medicine
        records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]
        patient_med_entry = None
        for r in records:
            try:
                rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
                for m in rj.get("medicines", []):
                    b_match = bool(matched_prod.brand_name and matched_prod.brand_name.lower() in m.get("name_raw", "").lower())
                    g_match = bool(matched_prod.active_ingredient and matched_prod.active_ingredient.lower() in (m.get("generic") or "").lower())
                    if b_match or g_match:
                        patient_med_entry = m
                        break
            except Exception:
                pass

        rx_note = "Schedule H / Prescription Drug (valid prescription required)" if matched_prod.is_prescription_only else "Available Over-The-Counter (OTC)"
        dev_note = f"Category: Medical Equipment ({matched_prod.active_ingredient})" if matched_prod.category == "medical_device" else f"Active Generic Ingredient: **{matched_prod.active_ingredient}** ({matched_prod.strength}, {matched_prod.dosage_form})"

        ans_parts = [
            f"**{matched_prod.product_name}** is a verified healthcare product manufactured by **{matched_prod.manufacturer}**.",
            dev_note + f" • {rx_note}."
        ]
        if patient_med_entry:
            ans_parts.append(
                f"In your verified health records, you were prescribed this with schedule: **{patient_med_entry.get('schedule_raw', 'As directed')}**"
                + (f" for {patient_med_entry.get('duration_days')} days." if patient_med_entry.get('duration_days') else ".")
            )
        ans_parts.append("Always follow your prescribing doctor's clinical instructions and never adjust your dosage without consulting a healthcare professional.")
        return AskResponse(answer="\n\n".join(ans_parts), sources=sources[:2], disclaimer=DISCLAIMER, lang=detected_lang)

    # Rule A: Lab tests & biomarkers (HbA1c, sugar, glucose, etc.)
    if any(k in q_lower for k in ["hba1c", "blood", "sugar", "glucose", "test", "lab", "result", "level", "பரிசோதனை", "ரிசல்ட்"]):
        records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]
        found_tests = []
        for r in records:
            try:
                rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
                for t in rj.get("tests", []):
                    found_tests.append(t)
            except Exception:
                pass

        if found_tests:
            latest_t = found_tests[0]
            val_str = f"{latest_t.get('name')}: {latest_t.get('value')} {latest_t.get('unit', '')}"
            flag = latest_t.get("flag", "NORMAL")
            status_desc = "within normal range" if flag == "NORMAL" else f"flagged as {flag}"

            if detected_lang == "ta":
                ans = f"உங்கள் சமீபத்திய இரத்தப் பரிசோதனை விவரம்: **{val_str}** ({status_desc}). உங்களின் பரிசோதனை அளவுகள் மருத்துவ கண்காணிப்பில் உள்ளன."
            else:
                ans = f"Based on your latest verified records, your **{val_str}** is {status_desc}. Regular monitoring and healthy lifestyle habits help maintain stable biomarker levels."
            return AskResponse(answer=ans, sources=sources[:2], disclaimer=DISCLAIMER, lang=detected_lang)

    # Rule B: Medications
    if any(k in q_lower for k in ["medicine", "medication", "tablet", "drug", "metformin", "dose", "மருந்து", "மாத்திரை"]):
        records = [r for r in get_records_by_profile(db, profile_id) if r.status == "confirmed"]
        found_meds = []
        for r in records:
            try:
                rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
                for m in rj.get("medicines", []):
                    found_meds.append(m)
            except Exception:
                pass

        if found_meds:
            med_list = [f"• **{m.get('name_raw')}** ({m.get('generic', '')}) - {m.get('schedule_raw', 'As advised')}" for m in found_meds[:4]]
            if detected_lang == "ta":
                ans = "உங்கள் பதிவில் உள்ள பரிந்துரைக்கப்பட்ட மருந்துகள்:\n" + "\n".join(med_list) + "\n\nமருந்துகளை மருத்துவர் கூறிய அட்டவணைப்படி தவறாமல் உட்கொள்ளவும்."
            else:
                ans = "Your verified prescribed medications:\n" + "\n".join(med_list) + "\n\nPlease take medications strictly according to your physician's instructions."
            return AskResponse(answer=ans, sources=sources[:2], disclaimer=DISCLAIMER, lang=detected_lang)

    # Rule C: Health Summary
    if any(k in q_lower for k in ["summary", "overview", "status", "health", "சுருக்கம்", "நிலவரம்"]):
        if sources:
            if detected_lang == "ta":
                ans = f"உங்கள் கணக்கில் **{len(sources)} மருத்துவ ஆவணங்கள்** பதிவு செய்யப்பட்டுள்ளன. சமீபத்திய பரிசோதனைகள் மற்றும் மருந்துகள் சீராக கண்காணிக்கப்பட்டு வருகின்றன."
            else:
                ans = f"You have **{len(sources)} verified health record(s)** on file. Your latest biomarkers and medications are monitored. Upload new lab reports or prescriptions to keep your health timeline updated."
            return AskResponse(answer=ans, sources=sources[:3], disclaimer=DISCLAIMER, lang=detected_lang)

    # Friendly conversational default
    if detected_lang == "ta":
        ans = (
            "நான் உங்கள் Clinical AI உதவியாளர். உங்கள் மருத்துவ ஆவணங்கள், இரத்த பரிசோதனைகள் (HbA1c, சுகர்), "
            "மற்றும் மருந்துகள் குறித்த எந்தவொரு தகவலையும் என்னிடம் கேட்கலாம். அல்லது புதிய மருந்து சீட்டை ஸ்கேன் செய்து பதிவேற்றலாம்!"
        )
    elif detected_lang == "hi":
        ans = (
            "मैं आपका Clinical AI हेल्थ कोपायलट हूं। आप अपने मेडिकल रिकॉर्ड्स, लैब टेस्ट (जैसे HbA1c), "
            "या दवाओं के बारे में पूछ सकते हैं। आप नए पर्चे या रिपोर्ट की फोटो भी अपलोड कर सकते हैं!"
        )
    else:
        ans = (
            "I am your Clinical AI Health Copilot. You can ask me about your verified lab tests, prescribed medications, "
            "or summarize your health history. You can also upload a prescription or report to analyze!"
        )

    return AskResponse(answer=ans, sources=sources[:2], disclaimer=DISCLAIMER, lang=detected_lang)
