# Complete Full-Stack Integration (Praveen + Yogesh + Naveen)

All three modules are fully connected and operational:

- **Backend API & Database**: `praveen/backend` (FastAPI, SQLite, FHIR R4 Bundle, ABHA Mock, Profiles)
- **AI Extraction & Normalization**: `yogesh/healthcare_copilot_AI-Engine-main` (Vision/LLM engine, catalogs, clinical parser)
- **Frontend UI & Hospital Portal**: `naveen/hi-main/hi-main/frontend` (React 19, Vite, Tailwind CSS, Recharts, Multilingual EN/TA/HI)

## Run from this folder (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start_backend.ps1
```

The default is explicitly MOCK extraction. Swagger: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/api/health

For live extraction, create `praveen/backend/.env` with `LLM_PROVIDER`,
`LLM_API_KEY`, and `LLM_MODEL`, then run `./start_backend.ps1 -RealAI`.
Do not commit keys. The script sets `AI_ENGINE_ROOT` automatically and disables
the engine's disk cache. Google dependencies are included; OpenAI/Anthropic
providers need their respective optional SDKs installed separately.

The test environment created during integration uses Python 3.12.14. The supplied
project brief asks for Python 3.11; that interpreter has not been validated here.

## API currently exposed (before Naveen integration)

- Upload returns HTTP **201**, with extraction at `response.record.record_json`.
- GET/PUT record responses expose extraction at `response.record_json`.
- PUT accepts both `{"record": {...}}` and legacy `{"record_json": {...}}`.
- Flags inside `record_json` are `HIGH/LOW/NORMAL/UNKNOWN`; existing relational
  projections/trends retain legacy `H/L/N` for tests with both range bounds.
- Summary and explanations are regenerated deterministically from normalized
  data, including on confirmation, so edited values cannot retain old summaries.
- Returned AI errors become review-needed draft records; uploading the same file
  again retries extraction instead of returning the failed record forever.

These existing response shapes differ from the original frozen brief. Coordinate
the frontend against the actual OpenAPI schema before integrating Naveen's UI.
No claim of full frozen-contract or FHIR/ABDM certification is made.

## Run tests

Run suites in separate processes: both modules name their test package `tests`.

```powershell
Push-Location praveen/backend
..\..\.venv\Scripts\python.exe -m pytest tests -q
Pop-Location
Push-Location yogesh/healthcare_copilot_AI-Engine-main
..\..\.venv\Scripts\python.exe -m pytest tests -q
Pop-Location
```

The backend suite uses an in-memory database and temporary upload directory.
`tests/test_integration.py` uses the real adapter, engine extraction/parser,
normalization, summaries, API, and database. Only the external LLM response is
substituted with synthetic fixture data. This verifies module wiring and data
flow; it does not measure live model extraction accuracy.

## Scope and remaining checks

The work checks the backend/engine boundary, runs both existing suites, and adds
regressions for upload/confirm/timeline/trends/FHIR, corrections, failures, and
temporary-file cleanup. Live credentials/provider calls and frontend browser
flows are not validated. The AI engine currently sends only the first page image
to its vision provider; multi-page document extraction needs separate work.
The engine's standalone Streamlit app still includes interaction/advisory/cost
features outside the frozen project scope; these fields are removed from the
integrated backend response. This is an integration check, not a full clinical,
security, or external FHIR conformance audit.
