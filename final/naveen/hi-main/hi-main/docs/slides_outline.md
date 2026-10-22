# 📊 AI Health Copilot: 10-Slide Pitch Outline

**Event:** Altrix Labs Hackathon  
**Track:** AI-Powered Personal Health Copilot  

---

### Slide 1: Title & Vision
* **Title:** AI Health Copilot
* **Subtitle:** Empowering Patients and Caregivers with Grounded, Safe Health Intelligence
* **Tagline:** Upload • Verify • Understand • Prevent
* **Team:** Person 1 (AI Engine), Person 2 (Backend & ABDM), Person 3 (Frontend & UX)

---

### Slide 2: The Core Problem
* **Fragmentation:** Patients manage loose papers, handwritten prescriptions, and diagnostic lab reports across multiple clinics.
* **Medical Jargon & Illiteracy:** Elderly and non-technical patients cannot interpret biomarker levels or abnormal test flags.
* **Medication Confusion:** 30%+ of chronic patients risk duplicate dosing when different doctors prescribe distinct brand names for the same active molecule (e.g. Glucophage vs Obimet SR).

---

### Slide 3: The Solution & Core User Journey
* **Single Unified Workflow:**
  1. **Upload:** Camera capture or PDF drag-and-drop.
  2. **Verify (Human-in-the-Loop):** Side-by-side original document comparison with bounding box overlays.
  3. **Plain-Language Synthesis:** Clear explanations in English and Tamil with Web Speech read-aloud.
  4. **Longitudinal Timeline:** Automated biomarker tracking (HbA1c, Glucose) + Daily dosing schedule.

---

### Slide 4: Human-in-the-Loop & Medical Safety Guardrails
* **Strict Ethical AI Rules:**
  - Never diagnose, never prescribe treatments.
  - Normal/abnormal ranges evaluated strictly by deterministic code, never LLM hallucination.
  - Low confidence fields (< 70%) flagged in amber with "Please check" badges.
  - Unconfirmed AI extractions clearly labeled as **Draft** until patient or caregiver confirms.
  - Permanent, non-dismissible clinical disclaimer on every screen.

---

### Slide 5: Technical Architecture
* **Frontend:** React 19 + Vite 8 + Tailwind CSS + Recharts + Web Speech API.
* **Backend:** Python FastAPI + SQLAlchemy + SQLite (WAL Mode) + Indexed relational schema.
* **Interoperability:** Standard HL7 FHIR R4 Bundle JSON export.
* **ABDM Readiness:** MOCK 14-digit ABHA linking and consent-based record retrieval.

---

### Slide 6: Product Design System & Accessibility
* **Calm Healthcare Aesthetics:** WCAG AAA contrast, medical teal & slate surfaces, large readable typography (Inter + Noto Sans Tamil).
* **Dual-Cue Visual Communication:** Never relying on color alone; every status combines distinct shapes, directional arrows (▲ / ▼ / ✓), and explicit text labels.
* **Responsive Multi-Form Factor:** Desktop collapsible navigation sidebar + Mobile bottom drawer.

---

### Slide 7: Live Demonstration Highlights
* **Walkthrough:**
  - Demo Patient `demo-patient-001`.
  - Side-by-side interactive document verification with bounding box highlights.
  - Tamil voice read-aloud playback.
  - Duplicate generic detection banner (Metformin safety alert).
  - Emergency card with paramedic-ready QR code.

---

### Slide 8: Healthcare Impact & Patient Safety
* **Prevention:** Catches drug brand duplications before adverse events occur.
* **Health Literacy:** Translates complex LOINC observation ranges into everyday language.
* **Empowerment:** Allows patients to walk into doctor appointments with structured printable summaries.

---

### Slide 9: Evaluation Rubric Alignment
* **AI Utilization (35%):** High-confidence extraction, bounding box mapping, bilingual RAG summaries.
* **Technical Architecture (25%):** Clean layered REST API, FHIR R4 standard bundles, ABDM readiness.
* **User Experience (20%):** 4-state screens, elderly-accessible touch targets, smooth micro-interactions.
* **Healthcare Impact (10%):** Safe guardrails, disclaimer enforcement, medication alert.
* **Presentation & Demo (10%):** Production build, 100% test pass rate, offline mock resilience.

---

### Slide 10: Future Roadmap & Next Steps
* **Phase 2 (Future Scope):**
  - Official ABDM M2/M3 Sandbox certification with National Health Authority (NHA).
  - Real-time WhatsApp bot integration for rural document uploads.
  - Multi-regional Indian languages (Hindi, Telugu, Kannada).
* **Call to Action:** Experience the prototype live at `http://localhost:5173/`!
