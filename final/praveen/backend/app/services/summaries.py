"""Use Yogesh's deterministic summaries after normalization / user correction."""
import sys
from app.integration import AI_PROJECT_ROOT


def refresh_summaries(record: dict) -> dict:
    if str(AI_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(AI_PROJECT_ROOT))
    from ai_engine.summarize import build_summaries
    for key in ("summary", "summary_en", "summary_ta", "summary_hi"):
        record.pop(key, None)
    for test in record.get("tests", []):
        for key in ("explanation_en", "explanation_ta", "explanation_hi"):
            test.pop(key, None)
    # The frozen project scope excludes interaction/treatment recommendations.
    for key in ("safety_alerts", "drug_advisories", "cost_savings"):
        record.pop(key, None)
    return build_summaries(record, use_llm=False)
