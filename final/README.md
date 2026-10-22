# 🏥 Multilingual AI Health Records Copilot

[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-84%2F84%20Pass-brightgreen)](#)
[![AI Engine Tests](https://img.shields.io/badge/AI%20Engine%20Tests-167%2F167%20Pass-brightgreen)](#)
[![Frontend Tests](https://img.shields.io/badge/Frontend%20Tests-12%2F12%20Pass-brightgreen)](#)
[![TypeScript / Vite](https://img.shields.io/badge/TypeScript%20Build-0%20Errors-brightgreen)](#)

An enterprise-ready, multilingual (English / Tamil / Hindi) Clinical Health Records Copilot with OCR document extraction, ABDM FHIR R4 compatibility, interactive timelines, medication interaction alerts, biomarker trend tracking, and doctor prep summaries.

---

## 👥 Engineering Team & Component Architecture

| Member | Subsystem / Layer | Tech Stack | Location |
| :--- | :--- | :--- | :--- |
| **Praveen** | **Backend Core & Database** | FastAPI, SQLAlchemy, SQLite, FHIR R4, REST APIs | [`praveen/backend`](file:///c:/Users/Praveen/Desktop/final/praveen/backend) |
| **Yogesh** | **AI Extraction Engine** | Gemini Vision, Clinical Parser, Drug Catalogs, OCR | [`yogesh/healthcare_copilot_AI-Engine-main`](file:///c:/Users/Praveen/Desktop/final/yogesh/healthcare_copilot_AI-Engine-main) |
| **Naveen** | **Frontend UI & Hospital Portal** | React 19, TypeScript, Vite, Tailwind CSS, Recharts | [`naveen/hi-main/hi-main/frontend`](file:///c:/Users/Praveen/Desktop/final/naveen/hi-main/hi-main/frontend) |

---

## 📁 Repository Directory Structure

```text
final/
├── praveen/
│   └── backend/                     # FastAPI core, DB models, routers, services, SQLite
│       ├── app/                     # Routers (records, profiles, fhir, ask, abha)
│       ├── scripts/                 # Demo database seeding script
│       ├── tests/                   # Pytest suite (84 automated tests)
│       └── uploads/                 # Secure document storage
├── yogesh/
│   └── healthcare_copilot_AI-Engine-main/  # OCR, LLM extraction & clinical catalog
│       ├── ai_engine/               # Gemini Vision extractor, normalizer, catalogs
│       ├── samples/                 # Sample prescriptions and ground truths
│       └── tests/                   # Pytest suite (167 automated tests)
├── naveen/
│   └── hi-main/hi-main/
│       ├── frontend/                # React 19 + TypeScript SPA
│       │   ├── src/                 # Screens, components, API client, i18n
│       │   ├── tests/               # Frontend client tests (12 tests)
│       │   ├── Dockerfile           # Multi-stage production container
│       │   └── nginx.conf           # Production Nginx reverse-proxy
│       └── docs/                    # UI specifications & presentation notes
├── qa/                              # Quality assurance & audit runner scripts
├── docker-compose.yml               # Production multi-container orchestrator
├── Dockerfile.backend               # Container definition for FastAPI backend
├── render.yaml                      # Cloud deployment blueprint (Render)
├── start_all.bat                    # One-click Windows runner (Backend + Frontend)
├── requirements.txt                 # Unified Python dependencies
└── README.md                        # Project documentation
```

---

## 🚀 Quick Start (Local Run)

### Option 1: One-Click Windows Launcher (Recommended)
Simply double-click:
```bat
start_all.bat
```
This automatically launches:
- **Backend API:** `http://127.0.0.1:8000` (FastAPI + Swagger Docs at `/docs`)
- **Frontend UI:** `http://127.0.0.1:5173` (React 19 + Vite with `/api` proxy)

### Option 2: Manual Terminal Run
**1. Backend:**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# (from praveen/backend)
```

**2. Frontend:**
```powershell
cd naveen/hi-main/hi-main/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## 🐳 Production Deployment

### 1. Docker Compose (Single Command)
```bash
docker compose up --build -d
```
- Frontend available at: `http://localhost:5173`
- Backend API available at: `http://localhost:8000`

### 2. Cloud Deployment (Render / Railway / Vercel)
- **Backend (Web Service):**
  - Build command: `pip install -r requirements.txt`
  - Start command: `uvicorn praveen.backend.app.main:app --host 0.0.0.0 --port $PORT`
  - Environment: `USE_MOCK_AI=true` (or provide `GEMINI_API_KEY`)
- **Frontend (Static Site):**
  - Root directory: `naveen/hi-main/hi-main/frontend`
  - Build command: `npm install && npm run build`
  - Publish directory: `dist`

---

## 🧪 Automated Testing & Quality Audit

All test suites pass 100% with zero regressions:

```bash
# 1. Backend Core Test Suite (84 tests)
pytest praveen/backend/tests -q

# 2. AI Extraction Engine Test Suite (167 tests)
pytest yogesh/healthcare_copilot_AI-Engine-main/tests -q

# 3. Frontend Client & Normalizer Test Suite (12 tests)
cd naveen/hi-main/hi-main/frontend && npm test

# 4. Production TypeScript Compilation
cd naveen/hi-main/hi-main/frontend && npm run build
```
