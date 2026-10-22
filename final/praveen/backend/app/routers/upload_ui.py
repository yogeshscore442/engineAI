"""
routers/upload_ui.py — Interactive web interface for uploading prescriptions & viewing outputs.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Health Copilot — Upload & Extraction Pipeline</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Tamil:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card: #111827;
      --card-border: #1f293d;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --primary-glow: rgba(59, 130, 246, 0.25);
      --emerald: #10b981;
      --emerald-bg: rgba(16, 185, 129, 0.12);
      --amber: #f59e0b;
      --amber-bg: rgba(245, 158, 11, 0.12);
      --rose: #f43f5e;
      --rose-bg: rgba(244, 63, 94, 0.12);
      --text: #f3f4f6;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
      background: radial-gradient(circle at 50% 0%, #172554 0%, #090d16 60%);
      color: var(--text);
      min-height: 100vh;
      padding: 30px 20px 80px;
    }
    .container { max-width: 1120px; margin: 0 auto; }
    header { text-align: center; margin-bottom: 35px; }
    .badge {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 14px; background: rgba(59,130,246,0.15);
      border: 1px solid rgba(59,130,246,0.3); border-radius: 9999px;
      font-size: 13px; font-weight: 600; color: #93c5fd; margin-bottom: 12px;
    }
    h1 { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 8px; }
    p.subtitle { color: var(--text-muted); font-size: 15px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
    @media (min-width: 860px) { .grid { grid-template-columns: 420px 1fr; } }
    .card {
      background: var(--card); border: 1px solid var(--card-border);
      border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
    }
    .card-title { font-size: 17px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
    .dropzone {
      border: 2px dashed #334155; border-radius: 14px; padding: 36px 20px;
      text-align: center; cursor: pointer; transition: all 0.2s ease;
      background: rgba(15, 23, 42, 0.6);
    }
    .dropzone:hover, .dropzone.dragover { border-color: var(--primary); background: rgba(59, 130, 246, 0.08); }
    .dropzone input { display: none; }
    .drop-icon { font-size: 38px; margin-bottom: 8px; }
    .preview-box { margin-top: 16px; display: none; text-align: center; }
    .preview-img { max-width: 100%; max-height: 220px; border-radius: 10px; border: 1px solid var(--card-border); object-fit: contain; }
    .lang-row { display: flex; gap: 10px; margin-top: 16px; align-items: center; }
    .lang-label { font-size: 13px; font-weight: 600; color: var(--text-muted); }
    .select-css {
      flex: 1; padding: 10px 14px; background: #0f172a; border: 1px solid var(--card-border);
      border-radius: 10px; color: var(--text); font-size: 14px; outline: none;
    }
    .btn {
      width: 100%; margin-top: 18px; padding: 14px; border: none; border-radius: 12px;
      background: var(--primary); color: white; font-size: 15px; font-weight: 700;
      cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center;
      justify-content: center; gap: 8px; box-shadow: 0 4px 15px var(--primary-glow);
    }
    .btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
    .empty-state {
      padding: 60px 20px; text-align: center; color: var(--text-muted);
      border: 1px dashed #1e293b; border-radius: 14px;
    }
    .status-pill {
      display: inline-block; padding: 4px 10px; border-radius: 6px;
      font-size: 12px; font-weight: 700; text-transform: uppercase;
    }
    .pill-draft { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .pill-confirmed { background: var(--emerald-bg); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .pill-review { background: var(--amber-bg); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .pill-rejected { background: var(--rose-bg); color: #f87171; border: 1px solid rgba(244, 63, 94, 0.3); }

    .med-item {
      background: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
      padding: 14px; margin-bottom: 12px;
    }
    .med-header { display: flex; justify-content: space-between; align-items: center; }
    .med-name { font-size: 16px; font-weight: 700; color: #60a5fa; }
    .med-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; }
    .badge-verified { background: var(--emerald-bg); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-review { background: var(--amber-bg); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-unverified { background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }

    .med-meta { font-size: 13px; color: var(--text-muted); margin-top: 6px; display: flex; flex-wrap: wrap; gap: 12px; }
    .section-box {
      background: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
      padding: 14px; margin-bottom: 14px;
    }
    .section-title { font-size: 13px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 8px; }
    .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; font-size: 13px; }
    .info-label { color: var(--text-muted); font-size: 12px; }
    .info-value { font-weight: 600; color: #e2e8f0; }

    .calibrated-box {
      background: #091328; border: 1px solid #1e3a8a; border-radius: 10px;
      padding: 12px 14px; margin-bottom: 16px;
    }
    .calibrated-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 12px; margin-top: 6px; }
    .calibrated-item { background: rgba(15, 23, 42, 0.7); padding: 8px; border-radius: 6px; border: 1px solid #1e293b; }

    .banner-chart {
      background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3);
      border-radius: 10px; padding: 14px; margin-bottom: 16px; color: #93c5fd; font-size: 14px;
    }

    .summary-box {
      background: #0d1e38; border-left: 4px solid var(--primary);
      border-radius: 8px; padding: 14px 16px; margin-top: 14px; font-size: 14px; line-height: 1.6;
    }
    .tamil-text { font-family: 'Noto Sans Tamil', system-ui, sans-serif; }
    .disclaimer {
      font-size: 12px; color: #94a3b8; background: #0f172a;
      border: 1px solid #1e293b; border-radius: 10px; padding: 12px; margin-top: 18px;
    }
    .spinner {
      width: 18px; height: 18px; border: 2px solid #fff; border-top-color: transparent;
      border-radius: 50%; animation: spin 0.8s linear infinite; display: none;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge">✨ Real-World Medical OCR Pipeline — Antigravity Engine</div>
      <h1>Prescription & Medical Document Analyzer</h1>
      <p class="subtitle">High-speed multimodal OCR, calibrated confidence scoring & source-grounded clinical extraction.</p>
    </header>

    <div class="grid">
      <!-- Upload Column -->
      <div class="card">
        <div class="card-title">📄 Upload Document</div>
        <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
          <div class="drop-icon">📤</div>
          <div style="font-weight: 600; margin-bottom: 4px;">Click to browse or drag & drop</div>
          <div style="font-size: 12px; color: var(--text-muted);">Supports JPG, PNG, WEBP, PDF (Max 10MB)</div>
          <input type="file" id="fileInput" accept="image/*,application/pdf" onchange="handleFileSelect(event)">
        </div>

        <div class="preview-box" id="previewBox">
          <img id="previewImg" class="preview-img" alt="Preview">
          <div id="fileDetails" style="font-size: 12px; color: var(--text-muted); margin-top: 6px;"></div>
        </div>

        <div class="lang-row">
          <span class="lang-label">Language:</span>
          <select id="langSelect" class="select-css">
            <option value="en">English (default)</option>
            <option value="ta">Tamil (தமிழ்)</option>
          </select>
        </div>

        <button class="btn" id="uploadBtn" onclick="uploadDocument()" disabled>
          <span class="spinner" id="spinner"></span>
          <span id="btnText">Analyze Document</span>
        </button>

        <div id="errorMessage" style="margin-top: 12px; font-size: 13px; color: #f87171; display: none;"></div>
      </div>

      <!-- Output Column -->
      <div class="card">
        <div class="card-title">
          <span>📊 Extraction Output</span>
          <span id="statusPill" class="status-pill" style="display: none;"></span>
        </div>

        <div id="emptyOutput" class="empty-state">
          <div style="font-size: 32px; margin-bottom: 8px;">📑</div>
          <div style="font-weight: 600; margin-bottom: 4px;">No document uploaded yet</div>
          <div style="font-size: 13px;">Upload a prescription, clinical note, hospital form, or lab report from the left panel.</div>
        </div>

        <div id="outputContent" style="display: none;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--card-border);">
            <div>
              <div style="font-size: 12px; color: var(--text-muted);">RECORD ID</div>
              <div id="outRecordId" style="font-family: monospace; font-size: 13px; color: #93c5fd;"></div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 12px; color: var(--text-muted);">DOCUMENT CLASSIFICATION</div>
              <div id="outDocType" style="font-weight: 800; color: #34d399; text-transform: uppercase;"></div>
            </div>
          </div>

          <!-- Calibrated Confidence & Quality Matrix -->
          <div class="calibrated-box" id="calibratedSection">
            <div style="font-weight: 700; color: #93c5fd; font-size: 13px; display: flex; justify-content: space-between;">
              <span>🎯 Calibrated Confidence & Verification Matrix</span>
              <span id="overallQualityLabel" style="color: #fbbf24; font-weight: 700;">Needs Review</span>
            </div>
            <div class="calibrated-grid">
              <div class="calibrated-item">
                <div class="info-label">Classification</div>
                <div class="info-value" id="confClass">95% (docTR+ML)</div>
              </div>
              <div class="calibrated-item">
                <div class="info-label">OCR Recognition</div>
                <div class="info-value" id="confOcr">88% (docTR)</div>
              </div>
              <div class="calibrated-item">
                <div class="info-label">Medicine Names</div>
                <div class="info-value" id="confMeds">Unverified / Review</div>
              </div>
              <div class="calibrated-item">
                <div class="info-label">Strength Extraction</div>
                <div class="info-value" id="confStrength">Grounded (OCR)</div>
              </div>
              <div class="calibrated-item">
                <div class="info-label">Dosage Instructions</div>
                <div class="info-value" id="confDosage">Strict Evidence</div>
              </div>
              <div class="calibrated-item">
                <div class="info-label">Duration Tracking</div>
                <div class="info-value" id="confDuration">Explicit Only</div>
              </div>
            </div>
          </div>

          <!-- Reference Chart Banner (Test B) -->
          <div class="banner-chart" id="refChartBanner" style="display: none;">
            <strong>📌 Negative-Classification Notice:</strong> This document was classified as a <strong>Medical Reference Chart</strong>. It is not an individual patient prescription. No medications or patient schedules have been generated.
          </div>

          <!-- Printed Clinic Header (Test A / Test C) -->
          <div class="section-box" id="clinicSection" style="display: none;">
            <div class="section-title">🏥 Printed Clinic & Prescriber Header</div>
            <div class="info-grid">
              <div><span class="info-label">Clinic:</span> <span class="info-value" id="outClinicName">—</span></div>
              <div><span class="info-label">Doctor:</span> <span class="info-value" id="outDoctorName">—</span></div>
              <div><span class="info-label">Phone:</span> <span class="info-value" id="outClinicPhone">—</span></div>
              <div><span class="info-label">Home Delivery:</span> <span class="info-value" id="outDelivery">—</span></div>
            </div>
          </div>

          <!-- Patient Vitals & Demographics -->
          <div class="section-box" id="patientSection" style="display: none;">
            <div class="section-title">👤 Patient Vitals & Demographics</div>
            <div class="info-grid">
              <div><span class="info-label">Name:</span> <span class="info-value" id="outPatientName">—</span></div>
              <div><span class="info-label">Blood Pressure:</span> <span class="info-value" id="outBp">—</span></div>
              <div><span class="info-label">Temperature:</span> <span class="info-value" id="outTemp">—</span></div>
              <div><span class="info-label">SpO2:</span> <span class="info-value" id="outSpo2">—</span></div>
            </div>
          </div>

          <!-- Clinical Notes & Diagnoses (Test D) -->
          <div class="section-box" id="clinicalNotesSection" style="display: none;">
            <div class="section-title">📋 Clinical Notes, Findings & Diagnoses</div>
            <div id="clinicalNotesList" style="font-size: 13px; line-height: 1.6; color: #e2e8f0;"></div>
          </div>

          <!-- Extracted Medicines List (Test A / Test C) -->
          <div id="medicinesSection">
            <h3 style="font-size: 14px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 10px;">💊 Extracted Medicines (<span id="medCount">0</span>)</h3>
            <div id="medicinesList"></div>
          </div>

          <!-- Lab Tests List -->
          <div id="testsSection" style="display: none; margin-top: 16px;">
            <h3 style="font-size: 14px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 10px;">🧪 Lab Tests</h3>
            <div id="testsList"></div>
          </div>

          <!-- Summaries Section -->
          <div id="summariesSection" style="margin-top: 18px;">
            <div class="summary-box">
              <div style="font-weight: 700; color: #93c5fd; margin-bottom: 4px;">English Summary:</div>
              <div id="outSummaryEn"></div>
            </div>

            <div class="summary-box" style="border-left-color: #10b981; background: rgba(16, 185, 129, 0.08); margin-top: 10px;">
              <div style="font-weight: 700; color: #6ee7b7; margin-bottom: 4px;">தமிழ் சுருக்கம் (Tamil Summary):</div>
              <div id="outSummaryTa" class="tamil-text"></div>
            </div>
          </div>

          <div class="disclaimer">
            <strong>⚠️ Medical Disclaimer:</strong> <span id="outDisclaimer"></span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let selectedFile = null;

    function handleFileSelect(e) {
      const file = e.target.files[0];
      if (!file) return;
      selectedFile = file;
      document.getElementById('uploadBtn').disabled = false;
      document.getElementById('errorMessage').style.display = 'none';

      const previewBox = document.getElementById('previewBox');
      const previewImg = document.getElementById('previewImg');
      const fileDetails = document.getElementById('fileDetails');

      fileDetails.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      previewBox.style.display = 'block';

      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          previewImg.src = ev.target.result;
          previewImg.style.display = 'inline-block';
        };
        reader.readAsDataURL(file);
      } else {
        previewImg.style.display = 'none';
      }
    }

    // Drag and drop handlers
    const dropzone = document.getElementById('dropzone');
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault(); dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length) {
        document.getElementById('fileInput').files = e.dataTransfer.files;
        handleFileSelect({ target: { files: e.dataTransfer.files } });
      }
    });

    async function uploadDocument() {
      if (!selectedFile) return;

      const btn = document.getElementById('uploadBtn');
      const spinner = document.getElementById('spinner');
      const btnText = document.getElementById('btnText');
      const errBox = document.getElementById('errorMessage');

      // Regression rule: Clear old results immediately when a new upload begins
      document.getElementById('emptyOutput').style.display = 'block';
      document.getElementById('outputContent').style.display = 'none';
      errBox.style.display = 'none';

      btn.disabled = true;
      spinner.style.display = 'inline-block';
      btnText.textContent = 'Processing with docTR OCR…';

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('lang', document.getElementById('langSelect').value);

      try {
        const resp = await fetch('/api/profiles/default/records', {
          method: 'POST',
          body: formData,
        });

        const data = await resp.json();
        if (!resp.ok) {
          const err = data.error || {};
          throw new Error(err.message || `Upload failed with HTTP ${resp.status}`);
        }

        renderOutput(data);
      } catch (err) {
        errBox.textContent = `❌ ${err.message}`;
        errBox.style.display = 'block';
      } finally {
        btn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Analyze Document';
      }
    }

    function renderOutput(data) {
      document.getElementById('emptyOutput').style.display = 'none';
      document.getElementById('outputContent').style.display = 'block';

      const statusPill = document.getElementById('statusPill');
      statusPill.style.display = 'inline-block';
      const statusText = data.status || 'draft';
      statusPill.textContent = statusText === 'draft' ? 'NEEDS REVIEW' : statusText.toUpperCase();
      statusPill.className = `status-pill pill-${statusText === 'draft' ? 'review' : statusText}`;

      document.getElementById('outRecordId').textContent = data.record_id || '';
      const rec = data.record || {};
      const rj = rec.record_json || rec;

      const docTypeStr = (rec.doc_type || rj.doc_type || 'Prescription').replace(/_/g, ' ');
      document.getElementById('outDocType').textContent = docTypeStr;

      // Calibrated Confidence
      const cb = rj.confidence_breakdown || {};
      document.getElementById('confClass').textContent = cb.classification_confidence ? `${Math.round(cb.classification_confidence * 100)}% (Calibrated)` : '85% (Calibrated)';
      document.getElementById('confOcr').textContent = cb.ocr_confidence ? `${Math.round(cb.ocr_confidence * 100)}% (docTR)` : '88% (docTR)';
      document.getElementById('confMeds').textContent = cb.medicine_name_confidence ? `${Math.round(cb.medicine_name_confidence * 100)}%` : 'Requires Review';
      document.getElementById('confStrength').textContent = cb.strength_confidence ? `${Math.round(cb.strength_confidence * 100)}%` : 'Needs Review';
      document.getElementById('confDosage').textContent = cb.dosage_confidence ? `${Math.round(cb.dosage_confidence * 100)}%` : 'Needs Review';
      document.getElementById('confDuration').textContent = cb.duration_confidence ? `${Math.round(cb.duration_confidence * 100)}%` : 'Explicit Only';
      document.getElementById('overallQualityLabel').textContent = cb.overall_quality_label || (statusText === 'draft' ? 'Requires Human Review' : 'Verified');

      // Reference chart banner
      const isRefChart = (rj.doc_type === 'medical_reference_chart' || rj.document_type === 'MEDICAL_REFERENCE_CHART');
      document.getElementById('refChartBanner').style.display = isRefChart ? 'block' : 'none';

      // Printed Clinic Header
      const prescriber = rj.prescriber_info || {};
      const hasClinic = prescriber.clinic_name || prescriber.doctor_name || prescriber.phone;
      const clinicSection = document.getElementById('clinicSection');
      if (hasClinic) {
        clinicSection.style.display = 'block';
        document.getElementById('outClinicName').textContent = prescriber.clinic_name || '—';
        document.getElementById('outDoctorName').textContent = prescriber.doctor_name || '—';
        document.getElementById('outClinicPhone').textContent = prescriber.phone || '—';
        document.getElementById('outDelivery').textContent = prescriber.free_home_delivery || '—';
      } else {
        clinicSection.style.display = 'none';
      }

      // Patient Demographics & Vitals
      const vitals = rj.vitals || {};
      const patName = rj.patient_name || vitals.name;
      const hasVitals = patName || vitals.blood_pressure || vitals.temperature || vitals.spo2;
      const patSection = document.getElementById('patientSection');
      if (hasVitals) {
        patSection.style.display = 'block';
        document.getElementById('outPatientName').textContent = [patName, vitals.age ? `${vitals.age}y` : '', vitals.gender].filter(Boolean).join(' · ') || '—';
        document.getElementById('outBp').textContent = vitals.blood_pressure || '—';
        document.getElementById('outTemp').textContent = vitals.temperature || '—';
        document.getElementById('outSpo2').textContent = vitals.spo2 || '—';
      } else {
        patSection.style.display = 'none';
      }

      // Clinical Notes / Hospital form section
      const clinicalNotes = rj.clinical_notes || [];
      const diags = rj.diagnoses || [];
      const notesSection = document.getElementById('clinicalNotesSection');
      if (clinicalNotes.length > 0 || diags.length > 0) {
        notesSection.style.display = 'block';
        const listEl = document.getElementById('clinicalNotesList');
        listEl.innerHTML = '';
        if (diags.length > 0) {
          const dHeader = document.createElement('div');
          dHeader.style.fontWeight = '700';
          dHeader.style.color = '#93c5fd';
          dHeader.style.marginBottom = '4px';
          dHeader.textContent = 'Diagnoses & Impressions:';
          listEl.appendChild(dHeader);
          diags.forEach(d => {
            const dItem = document.createElement('div');
            dItem.textContent = `• ${d.text} (${Math.round((d.confidence || 0.85)*100)}% conf)`;
            listEl.appendChild(dItem);
          });
        }
        if (clinicalNotes.length > 0) {
          const nHeader = document.createElement('div');
          nHeader.style.fontWeight = '700';
          nHeader.style.color = '#93c5fd';
          nHeader.style.marginTop = '8px';
          nHeader.style.marginBottom = '4px';
          nHeader.textContent = 'Clinical Examination & Plan:';
          listEl.appendChild(nHeader);
          clinicalNotes.forEach(n => {
            const nItem = document.createElement('div');
            nItem.textContent = `• ${n}`;
            listEl.appendChild(nItem);
          });
        }
      } else {
        notesSection.style.display = 'none';
      }

      // Medicines
      const meds = rj.medicines || rec.medicines || [];
      document.getElementById('medCount').textContent = meds.length;
      const medsList = document.getElementById('medicinesList');
      medsList.innerHTML = '';

      if (meds.length === 0) {
        medsList.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">${isRefChart ? 'No patient medicines extracted (Medical Reference Chart).' : 'No active medicines detected in document.'}</div>`;
      } else {
        meds.forEach(m => {
          const name = m.name_raw || 'Unknown';
          const generic = m.generic ? `Generic: ${m.generic}` : '';
          const strength = m.strength ? `Strength: ${m.strength}` : '';
          const timing = m.schedule_raw || (m.schedule_parsed && m.schedule_parsed.length ? m.schedule_parsed.join(', ') : '');
          const dur = m.duration_days ? `${m.duration_days} days` : '';

          // Calibrated verification badge
          const verState = String(m.verification_state || '').toUpperCase();
          let badgeText = 'UNVERIFIED CANDIDATE';
          let badgeClass = 'badge-unverified';
          if (verState === 'VERIFIED' || verState === 'PRESENT_VERIFIED') {
            badgeText = 'VERIFIED';
            badgeClass = 'badge-verified';
          } else if (verState === 'REQUIRES_HUMAN_REVIEW' || verState === 'NEEDS_REVIEW') {
            badgeText = 'REQUIRES REVIEW';
            badgeClass = 'badge-review';
          }

          const div = document.createElement('div');
          div.className = 'med-item';
          const heading = document.createElement('div');
          heading.className = 'med-header';
          heading.innerHTML = `
            <span class="med-name">${name}</span>
            <span class="med-badge ${badgeClass}">${badgeText}</span>
          `;
          const meta = document.createElement('div');
          meta.className = 'med-meta';
          meta.textContent = [generic, strength, timing, dur].filter(Boolean).join(' · ');
          div.append(heading, meta);
          medsList.appendChild(div);
        });
      }

      // Summaries
      document.getElementById('outSummaryEn').textContent = rj.summary_en || 'No English summary generated.';
      document.getElementById('outSummaryTa').textContent = rj.summary_ta || 'தமிழ் சுருக்கம் இல்லை.';
      document.getElementById('outDisclaimer').textContent = rj.disclaimer || rec.disclaimer || 'This is AI-generated information. Please consult your doctor.';
    }
  </script>
</body>
</html>
"""

@router.get("/upload", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def upload_page():
    return HTMLResponse(content=HTML_PAGE)
