# 🎬 AI Health Copilot: 3-Minute Hackathon Demo Script

**Project:** AI-Powered Personal Health Copilot (Altrix Labs Challenge)  
**Target:** Judges & Clinical Evaluators  
**Duration:** 3 Minutes  
**Demo Persona:** An adult daughter managing her diabetic elderly mother's prescriptions and lab reports.

---

## ⏱️ Minute 0:00 - 0:45: The Problem & The Core Flow
* **Hook:** *"Medical reports in India are notoriously fragmented. Prescriptions are handwritten, lab values use complex clinical terminology, and elderly patients often end up taking duplicate medications under different brand names."*
* **Action:**
  1. Open app at `http://localhost:5173/`.
  2. Show patient profile `demo-patient-001`.
  3. Click **Upload** -> Drag & Drop an investigation report or prescription.
  4. Point out the friendly 4-stage analysis state:
     - 📖 Reading document…
     - 🧠 Extracting structured medical data…
     - 🩺 Validating clinical reference ranges…
     - ✓ Analysis complete!

---

## ⏱️ Minute 0:45 - 1:30: The Key Differentiator — Interactive Verify Screen
* **The "Wow" Factor (AI Utilization 35% & UX 20%):**
  1. Show the **Side-by-Side Verification Screen**:
     - **Left Side:** Real document view with highlighted bounding boxes (`bbox`).
     - **Right Side:** Extracted structured fields.
  2. Hover on a low-confidence or abnormal test (e.g. *HbA1c 7.2%* or *Metformin*):
     - The corresponding bounding box on the original document instantly highlights!
  3. Point out the amber **"⚠️ Please check"** badge on any field with confidence < 70%.
  4. Explain: *"We never diagnose, and we never present unconfirmed AI guesses as ground truth. The patient or caregiver verifies and confirms before it enters the health record."*
  5. Click **"Confirm & Save"**.

---

## ⏱️ Minute 1:30 - 2:15: Plain-Language Summary, Tamil TTS & FHIR R4 Export
* **Action:**
  1. Opens the **Summary Screen**:
     - Show the Plain-Language Clinical Synthesis (bilingual English + Tamil).
  2. Click **🔊 Read Aloud (குரல் வாசிப்பு)**:
     - Plays clear Tamil audio read-aloud via Web Speech API so elderly non-technical patients can listen without straining to read.
  3. Point out the **Dual-Cue Abnormal Flags**:
     - Not just color, but directional indicators: **▲ HIGH (Red)**, **▼ LOW (Blue)**, **✓ NORMAL (Green)**.
  4. Click **📥 FHIR R4 Export**:
     - Demonstrates instant download of HL7 FHIR R4 Bundle JSON for ABDM nationwide interoperability.

---

## ⏱️ Minute 2:15 - 2:45: Safety Alerts & Medication Schedule
* **Action:**
  1. Navigate to **Medicines**:
     - Point out the **Medication Safety Alert Banner**: Automatically caught that `Glucophage 500mg` and `Obimet SR 500` are the exact same generic active ingredient (`Metformin`), preventing accidental double-dosing!
     - Show the **Daily Dosage Grid**: Morning / Afternoon / Night organized by before-food and after-food instructions.
  2. Navigate to **Trends**:
     - Show the longitudinal HbA1c graph with normal reference band (4.0% - 5.6%) tracking patient improvement from 9.2% -> 7.8% -> 6.8%.

---

## ⏱️ Minute 2:45 - 3:00: Emergency Card & Wrap Up
* **Action:**
  1. Click **🆘 Emergency Card**:
     - Show instant wallet card with patient vitals, diagnosed conditions, and paramedic-ready QR code.
  2. Mention offline resilience: *"Notice the API Mode toggle in Settings — our frontend is fully wired to our live FastAPI backend, with an instant offline mock mode fallback ensuring 100% demo uptime."*
* **Closing:** *"AI Health Copilot empowers families with clear understanding, prevents medication errors, and prepares India for the ABDM digital health era."*
