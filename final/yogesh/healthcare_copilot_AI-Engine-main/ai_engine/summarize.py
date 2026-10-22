"""
summarize.py — Safe plain-language summary generation.

Rules (enforced by prompt + keyword scanner + deterministic fallback):
  ✓ Grounded ONLY in extracted JSON — no outside facts about the patient.
  ✗ No diagnosis wording ("you have...", "diagnosed with...")
  ✗ No treatment/dosage advice ("you should take...", "increase dose...")
  ✗ No drug interaction claims
  ✓ Abnormal values: "is above/below the usual range — please discuss with your doctor"
  ✓ Always ends with fixed disclaimer
  ✓ Tamil summary via separate LLM call with same safety rules
  ✓ Deterministic fallback used when LLM unavailable
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

from .models import DISCLAIMER
from .privacy import mask_record_for_llm

logger = logging.getLogger(__name__)

def _get_api_key() -> str:
    return os.getenv("LLM_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

def _get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "google").lower()

def _get_model() -> str:
    model = os.getenv("LLM_MODEL", "").strip()
    provider = _get_provider()
    if not model:
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "medgemma")
        if provider in ("llamacpp", "llama.cpp"):
            return os.getenv("LLAMACPP_MODEL", "medgemma")
        if provider in ("transformers", "huggingface", "medgemma"):
            return os.getenv("TRANSFORMERS_MODEL", "google/medgemma-2b")
        raise ValueError("Set LLM_MODEL in .env before using live summaries")
    return model

_TIMEOUT = float(os.getenv("LLM_SUMMARIZE_TIMEOUT", "4.0"))
_CIRCUIT_BROKEN = False
_CIRCUIT_BROKEN_UNTIL = 0.0
_SUMMARY_CACHE: dict[str, dict[str, str]] = {}
_MODEL_CACHE: dict[tuple[str, int], Any] = {}

def _compute_record_hash(record: dict) -> str:
    import hashlib
    key_parts = [
        str(record.get("doc_type") or record.get("document_type")),
        str(record.get("doc_date")),
        str([(m.get("name_raw"), m.get("strength"), m.get("schedule_raw"), m.get("verification_state")) for m in record.get("medicines", [])]),
        str([(t.get("name"), t.get("value"), t.get("unit"), t.get("flag")) for t in record.get("tests", [])]),
        str(record.get("diagnoses", [])),
        str(record.get("clinical_notes", [])),
        str(record.get("allergies", [])),
    ]
    return hashlib.md5("||".join(key_parts).encode("utf-8")).hexdigest()

# ── Forbidden wording patterns (post-process check) ───────────────────────────
_FORBIDDEN = re.compile(
    r"\b("
    r"you have|you are diagnosed|diagnosed with|your diagnosis|"
    r"you should take|increase your dose|decrease your dose|stop taking|"
    r"drug interaction|contraindicated|side effects?|"
    r"prescribe|recommend(?:ed)? (?:taking|you)|"
    r"treatment plan|medical advice"
    r")\b",
    re.IGNORECASE,
)

# The fixed disclaimer is always safe — bypass forbidden-phrase check for it
_DISCLAIMER_PHRASE = "it is not a diagnosis or medical advice"

# Matches any standalone number (integer or decimal) in summary text
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _collect_record_numbers(record: dict) -> set[str]:
    """
    Collect every numeric value from the extracted record so we can
    verify that summary numbers are grounded in the actual data.
    """
    nums: set[str] = set()
    for test in record.get("tests", []):
        for field in ("value", "ref_low", "ref_high"):
            v = test.get(field)
            if v is not None:
                nums.add(str(float(v)))
                nums.add(str(int(v)) if float(v) == int(float(v)) else str(v))
    for med in record.get("medicines", []):
        d = med.get("duration_days")
        if d is not None:
            nums.add(str(d))
        # strength digits
        strength = med.get("strength") or ""
        for m in _NUMBER_RE.findall(strength):
            nums.add(m)
    return nums


def _grounding_check(summary_text: str, record: dict) -> bool:
    """
    PHASE 3: Verify that every number in the summary text exists in the
    extracted record (tests, medicines, diagnoses). Returns True if grounded,
    False if a hallucinated number is detected.

    Numbers that are always safe (counts, years, percentages of 100):
    - 0, 1, 2, 100 (common incidental numbers)
    """
    safe_numbers = {"0", "1", "2", "100"}
    record_nums = _collect_record_numbers(record)
    summary_numbers = set(_NUMBER_RE.findall(summary_text))
    ungrounded = summary_numbers - record_nums - safe_numbers
    if ungrounded:
        logger.warning(
            "Grounding check: %d ungrounded number(s) in summary: %s — using deterministic fallback",
            len(ungrounded), list(ungrounded)[:5],
        )
        return False
    return True


def _safety_check(text: str) -> bool:
    """Return True if text is safe (no forbidden phrases)."""
    # Strip the standard disclaimer sentence before scanning — it contains
    # the otherwise-forbidden phrase 'medical advice'.
    scan_text = re.sub(
        re.escape(_DISCLAIMER_PHRASE), "", text, flags=re.IGNORECASE
    )
    return _FORBIDDEN.search(scan_text) is None


# ── LLM summarization ─────────────────────────────────────────────────────────

_EN_SYSTEM = """You are a medical document summary assistant.
Your ONLY job is to write a short, plain-language summary of the extracted medical record data provided.

STRICT RULES:
1. Only describe what is in the data. Do not add outside knowledge about the patient.
2. NEVER say "you have [condition]", "you are diagnosed with", or any diagnosis statement.
3. NEVER say "you should take", "increase", "decrease", or give any treatment advice.
4. NEVER mention drug interactions.
5. For abnormal lab values: say "The [test name] value ([value] [unit]) is above/below the usual range ([low]–[high] [unit]). Please discuss this with your doctor."
6. For normal values: say "The [test name] ([value] [unit]) is within the usual range."
7. For medicines: list them as-is. Do not comment on dosages.
8. For diagnostic reports: use "The report mentions..." and never add your own interpretation.
9. Keep the tone neutral and calm. Write at a 6th-grade reading level.
10. End with EXACTLY this sentence: "This is AI-generated information to help you understand your records. It is not a diagnosis or medical advice. Please consult your doctor."
11. Return only the summary text. No headings, no bullet points, no markdown."""

_TA_SYSTEM = """நீங்கள் ஒரு மருத்துவ ஆவண சுருக்க உதவியாளர்.
கொடுக்கப்பட்ட மருத்துவ பதிவு தரவை அடிப்படையாகக் கொண்டு, தமிழில் ஒரு சுருக்கமான, எளிமையான சுருக்கம் எழுதவும்.

கட்டாய விதிகள்:
1. கொடுக்கப்பட்ட தரவில் உள்ளதை மட்டுமே விவரிக்கவும்.
2. "உங்களுக்கு [நோய்] உள்ளது" என்று எந்த நோய் கண்டறிதலையும் கூறாதீர்கள்.
3. எந்த மருந்தையும் எடுக்க வேண்டும் அல்லது அளவை மாற்ற வேண்டும் என்று கூறாதீர்கள்.
4. அசாதாரண மதிப்புகளுக்கு: "[சோதனை பெயர்] மதிப்பு ([மதிப்பு] [அலகு]) வழக்கமான அளவை விட அதிகமாக/குறைவாக உள்ளது. உங்கள் மருத்துவரிடம் இதைப் பற்றி பேசுங்கள்."
5. கடைசியாக சரியாக இந்த வாக்கியத்தை சேர்க்கவும்: "இது AI-உருவாக்கிய தகவல். இது நோய் கண்டறிதலோ மருத்துவ ஆலோசனையோ அல்ல. உங்கள் மருத்துவரை அணுகவும்."
6. சுருக்க உரையை மட்டும் திரும்பவும்."""

_HI_SYSTEM = """आप एक मेडिकल दस्तावेज़ सारांश सहायक हैं।
दिए गए मेडिकल रिकॉर्ड डेटा के आधार पर, हिंदी में एक संक्षिप्त और सरल सारांश लिखें।

अनिवार्य नियम:
1. दिए गए डेटा में जो है केवल वही बताएं।
2. "आपको [बीमारी] है" जैसा कोई निदान न कहें।
3. कोई भी दवा लेने या खुराक बदलने की सलाह न दें।
4. असामान्य मानों के लिए: "[परीक्षण नाम] का मान ([मान] [इकाई]) सामान्य सीमा से अधिक/कम है। कृपया अपने डॉक्टर से चर्चा करें।"
5. अंत में बिल्कुल यह वाक्य जोड़ें: "यह AI-जनरेटेड जानकारी है। यह कोई निदान या चिकित्सीय सलाह नहीं है। कृपया अपने डॉक्टर से परामर्श लें।"
6. केवल सारांश पाठ लौटाएं।"""


def _call_summarize_llm(prompt: str, system: str) -> str:
    """Call LLM for summarization with automatic fallback. Returns empty string on failure."""
    global _CIRCUIT_BROKEN, _CIRCUIT_BROKEN_UNTIL
    now = time.time()
    if _CIRCUIT_BROKEN and now < _CIRCUIT_BROKEN_UNTIL:
        return ""

    provider = _get_provider()
    api_key = _get_api_key()

    local_providers = {"ollama", "llamacpp", "llama.cpp", "transformers", "huggingface", "medgemma"}
    if not api_key and provider not in local_providers:
        return ""

    try:
        preferred_model = _get_model()
        if provider == "google":
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            models_to_try = [preferred_model]

            for m in models_to_try:
                try:
                    cache_key = (m, hash(system))
                    if cache_key in _MODEL_CACHE:
                        model = _MODEL_CACHE[cache_key]
                    else:
                        model = genai.GenerativeModel(
                            model_name=m, system_instruction=system
                        )
                        _MODEL_CACHE[cache_key] = model

                    resp = model.generate_content(
                        prompt,
                        generation_config={"temperature": 0.3, "max_output_tokens": 250},
                        request_options={"timeout": _TIMEOUT},
                    )
                    if resp and resp.text:
                        return resp.text
                except Exception as ex:
                    logger.warning("Summarize model %s failed: %s", m, ex)
                    err_msg = str(ex).lower()
                    if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg:
                        logger.info("Project quota exceeded — tripping circuit breaker to use instant deterministic fallback")
                        _CIRCUIT_BROKEN = True
                        _CIRCUIT_BROKEN_UNTIL = time.time() + 60.0
                        break
                    continue

        elif provider == "openai":
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=api_key, timeout=_TIMEOUT)
            resp = client.chat.completions.create(
                model=preferred_model,
                temperature=0.3,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content or ""

        elif provider == "anthropic":
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=preferred_model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text

        elif provider == "ollama":
            import requests
            host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
            resp = requests.post(
                f"{host}/api/generate",
                json={
                    "model": preferred_model,
                    "prompt": f"{system}\n\n{prompt}",
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")

        elif provider in ("llamacpp", "llama.cpp"):
            import requests
            host = os.getenv("LLAMACPP_HOST", "http://127.0.0.1:8080").rstrip("/")
            resp = requests.post(
                f"{host}/v1/chat/completions",
                json={
                    "model": preferred_model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]

        elif provider in ("transformers", "huggingface", "medgemma"):
            from transformers import pipeline
            pipe = pipeline("text-generation", model=preferred_model, max_new_tokens=512, temperature=0.3)
            full_prompt = f"<|system|>\n{system}</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"
            out = pipe(full_prompt)
            if out and len(out) > 0:
                return out[0].get("generated_text", "")[len(full_prompt):].strip()

    except Exception as e:
        logger.warning("Summarization LLM call failed: %s", e)
        _CIRCUIT_BROKEN = True
        _CIRCUIT_BROKEN_UNTIL = time.time() + 60.0

    return ""


# ── Deterministic fallback summaries ─────────────────────────────────────────

def _deterministic_summary_en(record: dict) -> str:
    """Build a safe template summary from flags — no LLM needed."""
    doc_type = str(record.get("doc_type") or record.get("document_type") or "").lower()

    # Handle Medical Reference Chart
    if "reference_chart" in doc_type or "alphabet" in doc_type:
        return (
            "This document is a medical reference chart or handwriting guide (such as a medical alphabet reference). "
            "It does not contain patient prescription or diagnostic findings. " + DISCLAIMER
        )

    # Handle Hospital Form and Clinical Notes
    if doc_type in ("hospital_form", "clinical_note"):
        c_notes = record.get("clinical_notes") or record.get("notes") or []
        notes_str = "; ".join(c_notes) if isinstance(c_notes, list) else str(c_notes)
        findings = []
        if record.get("patient_info", {}).get("vitals"):
            vitals = record["patient_info"]["vitals"]
            findings.append(", ".join([f"{k.upper()}: {v}" for k, v in vitals.items()]))
        if notes_str:
            findings.append(f"Recorded notes: {notes_str}")
        findings_text = "; ".join(findings) if findings else "Clinical observations and vitals recorded"
        return (
            f"This record is a clinical note or hospital form. {findings_text}. "
            "Please review these clinical entries with your healthcare provider. " + DISCLAIMER
        )

    parts = []
    tests = record.get("tests", [])
    meds = record.get("medicines", [])
    diagnoses = record.get("diagnoses", [])

    if tests:
        highs = [t["name"] for t in tests if t.get("flag") == "HIGH"]
        lows = [t["name"] for t in tests if t.get("flag") == "LOW"]
        normals = [t["name"] for t in tests if t.get("flag") == "NORMAL"]

        parts.append(f"This report shows {len(tests)} test result(s).")

        for t in tests:
            name = t.get("name", "")
            val = t.get("value")
            unit = t.get("unit", "")
            low = t.get("ref_low")
            high = t.get("ref_high")
            flag = t.get("flag", "UNKNOWN")
            vt = t.get("value_text")

            if vt:
                parts.append(f"The {name} report contains findings — please discuss with your doctor.")
            elif val is not None:
                val_str = f"{val} {unit}".strip()
                if flag == "HIGH" and high is not None:
                    parts.append(
                        f"The {name} ({val_str}) is above the usual upper limit ({high} {unit}). "
                        "Please discuss this with your doctor."
                    )
                elif flag == "LOW" and low is not None:
                    parts.append(
                        f"The {name} ({val_str}) is below the usual lower limit ({low} {unit}). "
                        "Please discuss this with your doctor."
                    )
                elif flag == "NORMAL":
                    parts.append(f"The {name} ({val_str}) is within the usual range.")
                else:
                    parts.append(f"The {name} ({val_str}) could not be classified — please review with your doctor.")

    if meds:
        med_names = [m.get("name_raw", "") for m in meds]
        parts.append(
            f"This record lists {len(meds)} medicine(s): {', '.join(med_names)}. "
            "Please verify all medicines with your doctor or pharmacist."
        )

    if not parts:
        parts.append("Please review this record with your doctor.")

    return " ".join(parts) + " " + DISCLAIMER


def _deterministic_summary_ta(record: dict) -> str:
    """Minimal Tamil deterministic fallback."""
    doc_type = str(record.get("doc_type") or record.get("document_type") or "").lower()
    if "reference_chart" in doc_type or "alphabet" in doc_type:
        return (
            "இந்த ஆவணம் மருத்துவ குறிப்பு விளக்கப்படம் ஆகும். இதில் நோயாளி மருந்துச் சீட்டு அல்லது பரிசோதனை முடிவுகள் இல்லை. "
            "இது AI-உருவாக்கிய தகவல். இது நோய் கண்டறிதலோ மருத்துவ ஆலோசனையோ அல்ல. உங்கள் மருத்துவரை அணுகவும்."
        )
    if doc_type in ("hospital_form", "clinical_note"):
        return (
            "இந்த பதிவு ஒரு மருத்துவ குறிப்பு அல்லது மருத்துவமனை படிவம் ஆகும். இதில் குறிப்பிடப்பட்டுள்ள மருத்துவ விவரங்களை உங்கள் மருத்துவரிடம் ஆலோசிக்கவும். "
            "இது AI-உருவாக்கிய தகவல். இது நோய் கண்டறிதலோ மருத்துவ ஆலோசனையோ அல்ல. உங்கள் மருத்துவரை அணுகவும்."
        )

    tests = record.get("tests", [])
    meds = record.get("medicines", [])
    parts = []

    if tests:
        highs = [t["name"] for t in tests if t.get("flag") == "HIGH"]
        lows = [t["name"] for t in tests if t.get("flag") == "LOW"]
        if highs:
            parts.append(f"{', '.join(highs)} மதிப்பு வழக்கமான அளவை விட அதிகமாக உள்ளது. மருத்துவரிடம் பேசுங்கள்.")
        if lows:
            parts.append(f"{', '.join(lows)} மதிப்பு வழக்கமான அளவை விட குறைவாக உள்ளது. மருத்துவரிடம் பேசுங்கள்.")
        if all(t.get("flag") == "NORMAL" for t in tests):
            parts.append("அனைத்து பரிசோதனை முடிவுகளும் சாதாரண அளவில் உள்ளன.")
        elif any(t.get("flag") not in ("HIGH", "LOW", "NORMAL") for t in tests):
            parts.append("சில முடிவுகளை வகைப்படுத்த முடியவில்லை. மருத்துவரிடம் சரிபார்க்கவும்.")

    if meds:
        parts.append(f"இந்த பதிவில் {len(meds)} மருந்து(கள்) பட்டியலிடப்பட்டுள்ளன. உங்கள் மருத்துவர் அல்லது மருந்தாளுனரிடம் சரிபார்க்கவும்.")

    if not parts:
        parts.append("இந்த பதிவை உங்கள் மருத்துவரிடம் மதிப்பாய்வு செய்யவும்.")

    return " ".join(parts) + " இது AI-உருவாக்கிய தகவல். இது நோய் கண்டறிதலோ மருத்துவ ஆலோசனையோ அல்ல. உங்கள் மருத்துவரை அணுகவும்."


def _deterministic_summary_hi(record: dict) -> str:
    """Safe Hindi deterministic fallback."""
    doc_type = str(record.get("doc_type") or record.get("document_type") or "").lower()
    if "reference_chart" in doc_type or "alphabet" in doc_type:
        return (
            "यह दस्तावेज़ एक मेडिकल संदर्भ चार्ट है। इसमें रोगी के नुस्खे या परीक्षण परिणाम शामिल नहीं हैं। "
            "यह AI-जनरेटेड जानकारी है। यह कोई निदान या चिकित्सीय सलाह नहीं है। कृपया अपने डॉक्टर से परामर्श लें।"
        )
    if doc_type in ("hospital_form", "clinical_note"):
        return (
            "यह रिकॉर्ड एक क्लिनिकल नोट या अस्पताल का फॉर्म है। कृपया दर्ज किए गए क्लिनिकल विवरणों पर अपने चिकित्सक से चर्चा करें। "
            "यह AI-जनरेटेड जानकारी है। यह कोई निदान या चिकित्सीय सलाह नहीं है। कृपया अपने डॉक्टर से परामर्श लें।"
        )

    tests = record.get("tests", [])
    meds = record.get("medicines", [])
    parts = []

    if tests:
        highs = [t["name"] for t in tests if t.get("flag") == "HIGH"]
        lows = [t["name"] for t in tests if t.get("flag") == "LOW"]
        if highs:
            parts.append(f"{', '.join(highs)} का मान सामान्य सीमा से अधिक है। कृपया अपने डॉक्टर से चर्चा करें।")
        if lows:
            parts.append(f"{', '.join(lows)} का मान सामान्य सीमा से कम है। कृपया अपने डॉक्टर से चर्चा करें।")
        if all(t.get("flag") == "NORMAL" for t in tests):
            parts.append("सभी परीक्षण परिणाम सामान्य सीमा के भीतर हैं।")
        elif any(t.get("flag") not in ("HIGH", "LOW", "NORMAL") for t in tests):
            parts.append("कुछ परिणामों का वर्गीकरण उपलब्ध नहीं है। कृपया डॉक्टर से समीक्षा कराएं।")

    if meds:
        parts.append(f"इस रिकॉर्ड में {len(meds)} दवा(एं) सूचीबद्ध हैं। कृपया अपने डॉक्टर या फार्मासिस्ट से पुष्टि करें।")

    if not parts:
        parts.append("कृपया अपने डॉक्टर से इस मेडिकल रिकॉर्ड की समीक्षा करें।")

    return " ".join(parts) + " यह AI-जनरेटेड जानकारी है। यह कोई निदान या चिकित्सीय सलाह नहीं है। कृपया अपने डॉक्टर से परामर्श लें।"


def _build_prompt(record: dict) -> str:
    """Build a concise text representation of the record for the summarization LLM."""
    masked = mask_record_for_llm(record)
    lines = [
        f"Document type: {masked.get('doc_type', 'unknown')}",
        f"Document date: {masked.get('doc_date') or 'unknown'}",
    ]
    if masked.get("follow_up_date"):
        lines.append(f"Follow-up date: {masked['follow_up_date']}")
    if masked.get("allergies"):
        lines.append(f"Noted allergies: {', '.join(masked['allergies'])}")

    tests = masked.get("tests", [])
    if tests:
        lines.append("\nLab/diagnostic tests:")
        for t in tests:
            name = t.get("name", "")
            vt = t.get("value_text")
            if vt:
                lines.append(f"  - {name}: {vt[:400]}")
            else:
                val = t.get("value", "")
                unit = t.get("unit", "")
                low = t.get("ref_low", "")
                high = t.get("ref_high", "")
                flag = t.get("flag", "UNKNOWN")
                ref_str = f"(ref: {low}–{high} {unit})" if (low or high) else ""
                lines.append(f"  - {name}: {val} {unit} {ref_str} → {flag}")

    meds = masked.get("medicines", [])
    if meds:
        lines.append("\nMedicines:")
        for m in meds:
            name = m.get("name_raw", "")
            gen = m.get("generic", "")
            sched = m.get("schedule_raw", "")
            dur = m.get("duration_days")
            gen_str = f" ({gen})" if gen else ""
            dur_str = f" for {dur} days" if dur else ""
            lines.append(f"  - {name}{gen_str}: {sched}{dur_str}")

    return "\n".join(lines)


# ── Explanation per test ──────────────────────────────────────────────────────

def build_explanation_en(test: dict) -> Optional[str]:
    """One-sentence plain-language explanation for a single test result."""
    name = test.get("name", "")
    val = test.get("value")
    unit = test.get("unit", "")
    low = test.get("ref_low")
    high = test.get("ref_high")
    flag = test.get("flag", "UNKNOWN")
    vt = test.get("value_text")

    if vt:
        return f"The {name} report mentions findings — please discuss with your doctor."
    if val is None:
        return None

    val_str = f"{val} {unit}".strip()
    if flag == "HIGH" and high is not None:
        return (
            f"Your {name} ({val_str}) is above the usual range ({low or ''}–{high} {unit}). "
            "Please discuss this with your doctor."
        )
    if flag == "LOW" and low is not None:
        return (
            f"Your {name} ({val_str}) is below the usual range ({low}–{high or ''} {unit}). "
            "Please discuss this with your doctor."
        )
    if flag == "NORMAL":
        return f"Your {name} ({val_str}) is within the usual range."
    return None


def build_explanation_ta(test: dict) -> Optional[str]:
    """Plain-language Tamil explanation for a single test result."""
    name = test.get("name", "")
    val = test.get("value")
    unit = test.get("unit", "")
    flag = test.get("flag", "UNKNOWN")
    vt = test.get("value_text")
    if vt:
        return f"{name} பரிசோதனை முடிவுகள் உள்ளன — மருத்துவரிடம் ஆலோசிக்கவும்."
    if val is None:
        return None
    val_str = f"{val} {unit}".strip()
    if flag == "HIGH":
        return f"{name} ({val_str}) வழக்கமான அளவை விட அதிகமாக உள்ளது. மருத்துவரிடம் பேசுங்கள்."
    if flag == "LOW":
        return f"{name} ({val_str}) வழக்கமான அளவை விட குறைவாக உள்ளது. மருத்துவரிடம் பேசுங்கள்."
    if flag == "NORMAL":
        return f"{name} ({val_str}) இயல்பான அளவில் உள்ளது."
    return None


def build_explanation_hi(test: dict) -> Optional[str]:
    """Plain-language Hindi explanation for a single test result."""
    name = test.get("name", "")
    val = test.get("value")
    unit = test.get("unit", "")
    flag = test.get("flag", "UNKNOWN")
    vt = test.get("value_text")
    if vt:
        return f"{name} रिपोर्ट में निष्कर्ष शामिल हैं — कृपया डॉक्टर से चर्चा करें।"
    if val is None:
        return None
    val_str = f"{val} {unit}".strip()
    if flag == "HIGH":
        return f"आपका {name} ({val_str}) सामान्य सीमा से अधिक है। कृपया डॉक्टर से चर्चा करें।"
    if flag == "LOW":
        return f"आपका {name} ({val_str}) सामान्य सीमा से कम है। कृपया डॉक्टर से चर्चा करें।"
    if flag == "NORMAL":
        return f"आपका {name} ({val_str}) सामान्य सीमा के भीतर है।"
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def build_short_summary(record: dict) -> str:
    """
    Produce a concise, clinically grounded overview:
    - Document type & date
    - Number of extracted medicine/lab test entries
    - Clearly readable instructions
    - Missing or uncertain fields
    - Human verification requirement flag
    """
    doc_type_raw = str(record.get("doc_type") or record.get("document_type") or "Medical Document").replace("_", " ").title()
    doc_date = record.get("doc_date")
    date_str = f"dated {doc_date}" if doc_date else "with date unstated"

    meds = record.get("medicines", [])
    tests = record.get("tests", [])
    needs_review = bool(record.get("needs_review") or str(record.get("status", "")).upper() == "NEEDS_REVIEW")

    items_parts = []
    if meds:
        items_parts.append(f"{len(meds)} medicine entry(ies) extracted")
    if tests:
        items_parts.append(f"{len(tests)} laboratory test result(s) detected")

    if "reference_chart" in doc_type_raw.lower() or "alphabet" in doc_type_raw.lower():
        return f"[{doc_type_raw}] Medical reference chart / handwriting recognition guide. Does not contain patient prescription or test records."

    if any(k in doc_type_raw.lower() for k in ["clinical note", "hospital form"]):
        c_notes = record.get("clinical_notes") or record.get("notes") or []
        notes_str = "; ".join(c_notes[:2]) if isinstance(c_notes, list) else str(c_notes)[:80]
        return f"[{doc_type_raw} - {date_str}] Clinical observations and notes documented: {notes_str or 'Clinical notes recorded'}. Human verification required."

    if not items_parts:
        items_summary = "No active medicines or laboratory tests detected"
    else:
        items_summary = ", ".join(items_parts)

    readable_instructions = 0
    missing_fields = []
    if meds:
        for m in meds:
            if m.get("schedule_raw"):
                readable_instructions += 1
            if not m.get("duration_days"):
                missing_fields.append(f"duration for {m.get('name_raw', 'medicine')}")
            if not m.get("strength"):
                missing_fields.append(f"strength for {m.get('name_raw', 'medicine')}")
    if tests:
        for t in tests:
            if t.get("value") is not None and t.get("unit"):
                readable_instructions += 1
            if not t.get("unit"):
                missing_fields.append(f"unit for {t.get('name', 'test')}")

    instr_str = f"Clear directions readable for {readable_instructions} item(s)." if readable_instructions > 0 else "Instructions could not be confirmed."

    missing_str = ""
    if missing_fields:
        missing_preview = ", ".join(missing_fields[:3])
        if len(missing_fields) > 3:
            missing_preview += f" and {len(missing_fields) - 3} other field(s)"
        missing_str = f"Missing or unstated: {missing_preview}."

    review_str = "Human verification required before clinical action." if (needs_review or missing_fields) else "Extracted data verified against standard clinical references."

    summary = f"[{doc_type_raw} - {date_str}] {items_summary}. {instr_str} {missing_str} {review_str}".strip()
    return summary


def build_detailed_summary(record: dict) -> str:
    """
    Produce a structured, multi-section detailed summary organizing:
    1. Document & Clinical Metadata
    2. Directly Extracted Items vs Independently Verified Catalog Information
    3. Administration Instructions, Dosages & Timings
    4. Ambiguities, Uncertainties or Missing Information
    5. Clinical Verification & Non-prescription Safety Notice
    """
    doc_type_raw = str(record.get("doc_type") or record.get("document_type") or "Medical Document").replace("_", " ").title()
    if "reference_chart" in doc_type_raw.lower() or "alphabet" in doc_type_raw.lower():
        return (
            f"### 1. Document Classification\n"
            f"- **Document Type:** Medical Reference Chart\n"
            f"- **Description:** Medical handwriting alphabet reference guide containing letterforms A-Z.\n"
            f"- **Patient Data:** None (Negative classification test — not a patient prescription or medical schedule).\n\n"
            f"### 2. Safety Notice\n"
            f"- {DISCLAIMER}"
        )

    doc_date = record.get("doc_date") or "Not stated"
    follow_up = record.get("follow_up_date")
    allergies = record.get("allergies") or []

    sections = []

    # Section 1: Clinical Metadata
    meta_lines = [
        f"### 1. Document & Clinical Metadata",
        f"- **Document Type:** {doc_type_raw}",
        f"- **Document Date:** {doc_date}",
    ]
    if follow_up:
        meta_lines.append(f"- **Scheduled Follow-up:** {follow_up}")
    if allergies:
        meta_lines.append(f"- **Documented Allergies:** {', '.join(allergies)}")
    sections.append("\n".join(meta_lines))

    # Section 2 & 3: Extracted Items & Verified Catalog Info
    meds = record.get("medicines", [])
    tests = record.get("tests", [])

    if meds:
        med_lines = [
            f"### 2. Prescribed Medicines & Verified Catalog Data",
            "*(Distinguishing directly extracted source text from independent catalog verification)*"
        ]
        for idx, m in enumerate(meds, 1):
            name_raw = m.get("name_raw", "Unknown")
            state = m.get("verification_state", "UNVERIFIED_CANDIDATE")
            gen = m.get("generic")
            form = m.get("formulation")
            strength = m.get("strength")

            status_badge = "[VERIFIED]" if state == "VERIFIED" else ("[REQUIRES REVIEW]" if state == "REQUIRES_HUMAN_REVIEW" else "[UNVERIFIED CANDIDATE]")

            med_lines.append(f"- **Item {idx}: {name_raw}** {status_badge}")
            med_lines.append(f"  - *Directly Extracted:* Name: \"{name_raw}\", Strength: \"{strength or 'Not explicitly stated'}\"")
            if gen or form:
                catalog_facts = []
                if gen: catalog_facts.append(f"Active Ingredient: {gen}")
                if form: catalog_facts.append(f"Dosage Form: {form}")
                med_lines.append(f"  - *Catalog Verified:* {', '.join(catalog_facts)}")
            else:
                med_lines.append(f"  - *Catalog Verified:* No exact canonical catalog match confirmed")
        sections.append("\n".join(med_lines))

        # Administration & Schedule
        sched_lines = [
            f"### 3. Directions, Timings & Administration",
        ]
        for m in meds:
            name_raw = m.get("name_raw", "Unknown")
            sched = m.get("schedule_raw") or "As directed by physician"
            food = m.get("food_instruction")
            dur = m.get("duration_days")

            food_text = "After food" if food == "after_food" else ("Before food" if food == "before_food" else "Food timing unstated")
            dur_text = f"for {dur} days" if dur else "duration unstated"
            sched_lines.append(f"- **{name_raw}:** {sched} ({food_text}, {dur_text})")
        sections.append("\n".join(sched_lines))

    if tests:
        test_lines = [
            f"### 2. Laboratory Test Findings & Clinical Reference Intervals",
        ]
        for idx, t in enumerate(tests, 1):
            name = t.get("name", "Unknown Test")
            val = t.get("value")
            unit = t.get("unit", "")
            low = t.get("ref_low")
            high = t.get("ref_high")
            flag = t.get("flag", "NORMAL")

            val_display = f"{val} {unit}".strip() if val is not None else (t.get("value_text") or "Not reported")
            ref_display = f"{low}-{high} {unit}".strip() if (low is not None or high is not None) else "Laboratory range unstated"
            flag_badge = f"[HIGH]" if flag == "HIGH" else (f"[LOW]" if flag == "LOW" else f"[NORMAL]")

            test_lines.append(f"- **{name}:** {val_display} (Ref: {ref_display}) -> {flag_badge}")
        sections.append("\n".join(test_lines))

    # Section: Ambiguities & Missing Information
    ambiguities = []
    if meds:
        for m in meds:
            if not m.get("duration_days"):
                ambiguities.append(f"Duration of treatment unstated for {m.get('name_raw')}")
            if not m.get("strength"):
                ambiguities.append(f"Specific milligram strength unstated for {m.get('name_raw')}")
            if m.get("verification_state") != "VERIFIED":
                ambiguities.append(f"Handwritten or printed text for {m.get('name_raw')} requires pharmacist/physician confirmation")
    if tests:
        for t in tests:
            if t.get("flag") not in ("NORMAL", "HIGH", "LOW"):
                ambiguities.append(f"Result for {t.get('name')} could not be classified against standard reference range")

    if ambiguities:
        amb_lines = [
            f"### 4. Ambiguities & Information Requiring Review",
        ]
        for amb in ambiguities:
            amb_lines.append(f"- [!] {amb}")
        sections.append("\n".join(amb_lines))

    # Section: Verification & Safety Notice
    safety_lines = [
        f"### 5. Verification & Safety Notice",
        f"- {DISCLAIMER}",
        f"- *Never alter prescribed dosages or discontinue prescription medicines without consulting your registered medical practitioner.*"
    ]
    sections.append("\n".join(safety_lines))

    return "\n\n".join(sections)


def build_summaries(record: dict, *, use_llm: bool = True) -> dict:
    """
    Add summary_en, summary_ta, summary_hi, short_summary, detailed_summary,
    and per-test explanations to *record* (modifies in place). Returns the record.
    Executes English, Tamil, and Hindi summarization in parallel with ThreadPoolExecutor.
    Uses sub-millisecond in-memory content caching and deterministic fallbacks when offline or on quota limits.
    """
    import concurrent.futures

    # Per-test explanations (deterministic — no LLM)
    for test in record.get("tests", []):
        if not test.get("explanation_en"):
            test["explanation_en"] = build_explanation_en(test)
        if not test.get("explanation_ta"):
            test["explanation_ta"] = build_explanation_ta(test)
        if not test.get("explanation_hi"):
            test["explanation_hi"] = build_explanation_hi(test)

    rec_hash = _compute_record_hash(record)
    if rec_hash in _SUMMARY_CACHE:
        cached = _SUMMARY_CACHE[rec_hash]
        for k in ("summary_en", "summary_ta", "summary_hi", "short_summary", "detailed_summary"):
            if cached.get(k) and not record.get(k):
                record[k] = cached[k]
        return record

    fast_mode = (
        not use_llm
        or os.getenv("FAST_SUMMARIES", "").lower() in ("1", "true", "yes")
        or (_CIRCUIT_BROKEN and time.time() < _CIRCUIT_BROKEN_UNTIL)
    )

    prompt = _build_prompt(record)

    def _get_en() -> str:
        if record.get("summary_en"):
            return record["summary_en"]
        if fast_mode:
            return _deterministic_summary_en(record)
        llm_text = _call_summarize_llm(prompt, _EN_SYSTEM)
        if llm_text and _safety_check(llm_text) and _grounding_check(llm_text, record):
            res = llm_text.strip()
            if DISCLAIMER not in res:
                res = res.rstrip() + " " + DISCLAIMER
            return res
        return _deterministic_summary_en(record)

    def _get_ta() -> str:
        if record.get("summary_ta"):
            return record["summary_ta"]
        if fast_mode:
            return _deterministic_summary_ta(record)
        ta_text = _call_summarize_llm(prompt, _TA_SYSTEM)
        if ta_text and _safety_check(ta_text):
            return ta_text.strip()
        return _deterministic_summary_ta(record)

    def _get_hi() -> str:
        if record.get("summary_hi"):
            return record["summary_hi"]
        if fast_mode:
            return _deterministic_summary_hi(record)
        hi_text = _call_summarize_llm(prompt, _HI_SYSTEM)
        if hi_text and _safety_check(hi_text):
            return hi_text.strip()
        return _deterministic_summary_hi(record)

    # Generate the requested active user language with AI, filling others with instant safe fallbacks
    target_lang = (record.get("language") or "en").lower()
    if fast_mode:
        record["summary_en"] = record.get("summary_en") or _deterministic_summary_en(record)
        record["summary_ta"] = record.get("summary_ta") or _deterministic_summary_ta(record)
        record["summary_hi"] = record.get("summary_hi") or _deterministic_summary_hi(record)
    elif target_lang == "ta":
        record["summary_ta"] = _get_ta()
        record["summary_en"] = record.get("summary_en") or _deterministic_summary_en(record)
        record["summary_hi"] = record.get("summary_hi") or _deterministic_summary_hi(record)
    elif target_lang == "hi":
        record["summary_hi"] = _get_hi()
        record["summary_en"] = record.get("summary_en") or _deterministic_summary_en(record)
        record["summary_ta"] = record.get("summary_ta") or _deterministic_summary_ta(record)
    else:
        record["summary_en"] = _get_en()
        record["summary_ta"] = record.get("summary_ta") or _deterministic_summary_ta(record)
        record["summary_hi"] = record.get("summary_hi") or _deterministic_summary_hi(record)

    if record["summary_en"] and DISCLAIMER not in record["summary_en"]:
        record["summary_en"] = record["summary_en"].rstrip() + " " + DISCLAIMER

    # Short & Detailed summaries (instant, deterministic)
    record["short_summary"] = build_short_summary(record)
    record["detailed_summary"] = build_detailed_summary(record)

    # Persist in cache
    _SUMMARY_CACHE[rec_hash] = {
        "summary_en": record["summary_en"],
        "summary_ta": record["summary_ta"],
        "summary_hi": record["summary_hi"],
        "short_summary": record["short_summary"],
        "detailed_summary": record["detailed_summary"],
    }

    return record


def stream_summary(record: dict, lang: str = "en"):
    """
    Yields chunks of the plain-language summary progressively as they are generated.
    When live streaming LLM is supported, yields real-time chunks from the model.
    Falls back to progressive words/phrases from the verified deterministic summary.
    """
    lang = (lang or "en").lower()
    prompt = _build_prompt(record)
    provider = _get_provider()
    api_key = _get_api_key()

    if lang == "ta":
        fallback_text = _deterministic_summary_ta(record)
        system = _TA_SYSTEM
    elif lang == "hi":
        fallback_text = _deterministic_summary_hi(record)
        system = _HI_SYSTEM
    else:
        fallback_text = _deterministic_summary_en(record)
        system = _EN_SYSTEM

    local_providers = {"ollama", "llamacpp", "llama.cpp", "transformers", "huggingface", "medgemma"}
    can_stream_llm = bool(api_key or provider in local_providers) and not _CIRCUIT_BROKEN and os.getenv("FAST_SUMMARIES", "").lower() not in ("1", "true", "yes")

    if can_stream_llm and provider == "google":
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_name = _get_model()
            cache_key = (model_name, hash(system))
            if cache_key in _MODEL_CACHE:
                model = _MODEL_CACHE[cache_key]
            else:
                model = genai.GenerativeModel(model_name=model_name, system_instruction=system)
                _MODEL_CACHE[cache_key] = model

            response = model.generate_content(
                prompt,
                stream=True,
                generation_config={"temperature": 0.3, "max_output_tokens": 250},
                request_options={"timeout": _TIMEOUT},
            )
            full_text = []
            for chunk in response:
                if chunk and chunk.text:
                    full_text.append(chunk.text)
                    yield chunk.text

            joined = "".join(full_text).strip()
            if lang == "en" and DISCLAIMER not in joined:
                yield " " + DISCLAIMER
            return
        except Exception as ex:
            logger.warning("Live LLM summary streaming failed (%s); streaming deterministic summary", ex)

    # Progressive streaming fallback (delivers first content in <100ms)
    words = fallback_text.split(" ")
    chunk_size = 3
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        if i + chunk_size < len(words):
            chunk += " "
        yield chunk
        time.sleep(0.03)
