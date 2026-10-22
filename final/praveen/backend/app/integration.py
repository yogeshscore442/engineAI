"""Resolve the two team modules without copying or renaming their folders."""
from pathlib import Path
import os

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[1]
AI_PROJECT_ROOT = Path(os.environ.get(
    "AI_ENGINE_ROOT",
    str(WORKSPACE_ROOT / "yogesh" / "healthcare_copilot_AI-Engine-main"),
)).resolve()
DISCLAIMER = (
    "This is AI-generated information to help you understand your records. "
    "It is not a diagnosis or medical advice. Please consult your doctor."
)
