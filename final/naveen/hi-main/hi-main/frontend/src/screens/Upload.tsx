import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../AppContext';
import { api, type UploadProgress } from '../api';

export default function Upload() {
  const { t, lang, profileId, setUseMock } = useApp();
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRejectedModalOpen, setIsRejectedModalOpen] = useState(false);
  const [rejectionMessage, setRejectionMessage] = useState('');
  const [isNeedsReviewModalOpen, setIsNeedsReviewModalOpen] = useState(false);
  const [needsReviewRecordId, setNeedsReviewRecordId] = useState<string | null>(null);
  const [needsReviewMeta, setNeedsReviewMeta] = useState<{
    docType?: string;
    reasons?: string[];
    medsCount?: number;
    testsCount?: number;
    diagnosesCount?: number;
    confidence?: number;
    fileName?: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleChooseAnotherFile = useCallback(() => {
    setIsRejectedModalOpen(false);
    setIsNeedsReviewModalOpen(false);
    setNeedsReviewMeta(null);
    setError(null);
    setProgress(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  }, []);

  const handleFile = useCallback(async (file: File) => {
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|jfif)$/i.test(file.name);
    if (!isImage && !isPdf) {
      setError('Please upload a PDF, JPG, or PNG file');
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError('File must be smaller than 25MB');
      return;
    }

    // Ensure mock mode is deactivated for real file uploads so new records are processed live
    api.setUseMock(false);
    setUseMock(false);

    // Reset old states completely
    setError(null);
    setIsRejectedModalOpen(false);
    setIsNeedsReviewModalOpen(false);
    setNeedsReviewRecordId(null);
    setNeedsReviewMeta(null);
    setIsLoading(true);
    setProgress({ step: 'reading', message: t('upload.stepReading') });

    try {
      const response = await api.uploadRecord(file, setProgress, profileId);
      const isReviewRequired = response.status === 'NEEDS_REVIEW' ||
        Boolean(response.record?.needs_review && (
          Array.isArray(response.record.needs_review)
            ? response.record.needs_review.length > 0 && response.record.needs_review[0] !== ''
            : response.record.needs_review === true
        )) ||
        Boolean(response.record?.status === 'NEEDS_REVIEW' || (response.record as any)?.document_state === 'NEEDS_REVIEW');

      if (isReviewRequired) {
        setNeedsReviewRecordId(response.record_id);
        const record = response.record || {};
        setNeedsReviewMeta({
          docType: (record.doc_type || record.document_type || 'Unknown').replace(/_/g, ' ').toUpperCase(),
          reasons: Array.isArray(record.needs_review) ? record.needs_review : (response.reason_codes || []),
          medsCount: record.medicines?.length ?? 0,
          testsCount: record.tests?.length ?? 0,
          diagnosesCount: record.diagnoses?.length ?? 0,
          confidence: typeof record.confidence === 'number' ? Math.round(record.confidence * 100) : undefined,
          fileName: file.name,
        });
        setIsNeedsReviewModalOpen(true);
        return;
      }

      navigate(`/verify/${response.record_id}`);
    } catch (err: any) {
      setProgress(null);
      const errObj = err?.error || err;
      const isRejected = err?.status === 'REJECTED'
        || err?.httpStatus === 422
        || errObj?.status === 'REJECTED'
        || errObj?.code === 'NON_MEDICAL_DOCUMENT'
        || (errObj?.reason_codes && errObj.reason_codes.includes('NON_MEDICAL_DOCUMENT'))
        || (err?.reasonCodes && err.reasonCodes.includes('NON_MEDICAL_DOCUMENT'));

      if (isRejected) {
        const msg = errObj?.message || err?.message ||
          (lang === 'ta'
            ? 'பதிவேற்றப்பட்ட கோப்பு செல்லுபடியாகும் மருத்துவ ஆவணமாகத் தெரியவில்லை. தயவுசெய்து ஆதரிக்கப்பட்ட லேப் அறிக்கை, மருந்து சீட்டு அல்லது பரிசோதனை அறிக்கையைப் பதிவேற்றவும்.'
            : 'The uploaded file does not appear to be a supported medical document. Please upload a valid laboratory report, prescription, or diagnostic report.');
        setRejectionMessage(msg);
        setIsRejectedModalOpen(true);
      } else {
        const message = errObj?.message || err?.message || 'Upload failed. Please try again.';
        setError(message);
      }
    } finally {
      setIsLoading(false);
    }
  }, [navigate, t, profileId, lang]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const openCamera = () => {
    fileInputRef.current?.click();
  };

  const handleQuickSample = async (docType: 'lab' | 'prescription' | 'discharge') => {
    setIsLoading(true);
    setError(null);
    setProgress({ step: 'reading', message: 'Loading verified sample medical report…' });

    try {
      api.setUseMock(true);
      setUseMock(true);
      const record = await api.loadSample(docType);
      navigate(`/verify/${record.record_id}`);
    } catch {
      setError('Could not load the sample. Please retry.');
      setProgress(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* ── Radiant Hero Header ── */}
      <div className="text-center sm:text-left">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-teal-50 text-teal-800 border border-teal-200/80 mb-3 shadow-2xs">
          <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse"></span>
          <span>{lang === 'ta' ? 'மருத்துவ ஆவண AI பகுப்பாய்வு' : 'Clinical AI Vision OCR & Document Decoding'}</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          {lang === 'ta' ? 'மருத்துவ ஆவணங்களைப் பதிவேற்றவும்' : 'Upload & Decode Health Documents'}
        </h1>
        <p className="text-slate-600 text-sm mt-1.5 max-w-2xl leading-relaxed">
          {lang === 'ta'
            ? 'மருத்துவரின் மருந்து சீட்டு, லேப் பரிசோதனை அறிக்கை அல்லது டிஸ்சார்ஜ் ஆவணங்களைப் பதிவேற்றுங்கள். எங்களின் AI கையெழுத்தை படித்து, மருந்து அட்டவணை மற்றும் இரத்த பரிசோதனை முடிவுகளை உடனடி விளக்கத்துடன் தரும்.'
            : 'Upload or photograph any lab report, doctor prescription, or hospital discharge summary. Our Clinical AI reads handwriting, extracts medications, verifies reference ranges, and generates bilingual summaries.'}
        </p>

        {/* Feature Pills */}
        <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5 mt-3 text-xs">
          {[
            { icon: '🛡️', label: 'Local demo — synthetic data only' },
            { icon: '⚡', label: 'Review all extracted values' },
            { icon: '🇮🇳', label: 'ABDM & FHIR R4 Ready' },
            { icon: '🔊', label: 'Voice Audio in தமிழ் & English' },
          ].map((pill) => (
            <span
              key={pill.label}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 font-semibold shadow-2xs"
            >
              <span>{pill.icon}</span>
              <span>{pill.label}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ── Upload Drag & Drop Zone ── */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => !isLoading && fileInputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-3xl p-8 sm:p-12 text-center cursor-pointer
          transition-all duration-300 overflow-hidden
          ${isDragging 
            ? 'border-teal-500 bg-teal-50/70 scale-[1.01] shadow-xl' 
            : 'border-teal-300/80 bg-gradient-to-b from-white via-teal-50/20 to-emerald-50/30 hover:border-teal-500 hover:shadow-lg hover:bg-white'}
          ${isLoading ? 'opacity-70 pointer-events-none' : ''}
        `}
        style={{
          boxShadow: isDragging ? '0 12px 35px -8px rgba(13, 148, 136, 0.25)' : '0 8px 30px -6px rgba(0, 0, 0, 0.05)',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf"
          capture="environment"
          onChange={onInputChange}
          className="hidden"
        />

        {!progress && !isLoading && (
          <div className="space-y-4">
            <div className="relative w-20 h-20 mx-auto rounded-3xl bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center text-white shadow-lg shadow-teal-500/25 group-hover:scale-105 transition-transform">
              <span className="text-3xl">📄</span>
              <div className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-white text-teal-700 border-2 border-teal-500 flex items-center justify-center text-xs font-black shadow-sm">
                +
              </div>
            </div>

            <div>
              <p className="text-lg font-bold text-slate-900">
                {lang === 'ta' ? 'ஆவணத்தை இங்கே இழுத்துப் போடவும்' : 'Drag & drop your document here'}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {lang === 'ta' ? 'PDF, JPG, PNG (அதிகபட்சம் 10MB)' : 'Supports PDF, JPG, PNG up to 10MB • Clear photos give highest accuracy'}
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2 max-w-sm mx-auto">
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); openCamera(); }}
                className="w-full sm:w-auto px-5 py-3 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white font-bold text-sm shadow-md shadow-teal-600/25 flex items-center justify-center gap-2 transition-all cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>📷</span>
                <span>{lang === 'ta' ? 'கேமராவில் படம் எடு' : 'Snap with Camera'}</span>
              </button>

              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                className="w-full sm:w-auto px-5 py-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-300 text-slate-800 font-bold text-sm shadow-sm flex items-center justify-center gap-2 transition-all cursor-pointer hover:border-teal-400 hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>📁</span>
                <span>{lang === 'ta' ? 'கோப்பைத் தேர்ந்தெடு' : 'Browse Files'}</span>
              </button>
            </div>
          </div>
        )}

        {/* ── Uploading / Extraction Animated Stepper ── */}
        {progress && (
          <div className="py-6 max-w-md mx-auto space-y-5">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center shadow-inner">
              <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin"></div>
            </div>

            <div>
              <p className="text-base font-bold text-slate-900">
                {lang === 'ta' ? 'AI ஆவணத்தை ஆராய்கிறது…' : 'AI is decoding medical entities…'}
              </p>
              <p className="text-xs text-teal-700 font-semibold mt-1 animate-pulse">
                {progress.message}
              </p>
            </div>

            {/* Stepper items */}
            <div className="grid grid-cols-4 gap-2 text-[10px] font-bold text-slate-500 pt-2">
              {[
                { id: 'reading', label: '1. Reading', icon: '📄' },
                { id: 'extracting', label: '2. Vision AI', icon: '🤖' },
                { id: 'checking', label: '3. Ranges', icon: '⚖️' },
                { id: 'complete', label: '4. Summary', icon: '✅' },
              ].map((step) => {
                const isCurrent = progress.step === step.id;
                const isDone = (progress.step === 'complete') || (step.id === 'reading' && progress.step !== 'reading');
                return (
                  <div
                    key={step.id}
                    className={`p-2 rounded-xl border text-center transition-all ${
                      isCurrent
                        ? 'bg-teal-50 border-teal-500 text-teal-900 shadow-xs'
                        : isDone
                        ? 'bg-emerald-50 border-emerald-400 text-emerald-800'
                        : 'bg-white/60 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className="text-base mb-0.5">{step.icon}</div>
                    <div className="truncate">{step.label}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-300 rounded-2xl flex items-center justify-between text-rose-800 text-sm shadow-xs">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="px-3 py-1 rounded-lg bg-white border border-rose-200 font-bold text-xs hover:bg-rose-100 cursor-pointer"
          >
            {t('common.retry')}
          </button>
        </div>
      )}

      {/* ── 1-Click Interactive Demo Cards ── */}
      <div className="pt-2">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-extrabold text-slate-800 flex items-center gap-2">
            <span>✨</span>
            <span>{lang === 'ta' ? 'மாதிரி ஆவணங்களை உடனே சோதிக்க (1-Click Test):' : 'Or Try with Sample Medical Documents (1-Click Demo):'}</span>
          </h2>
          <span className="text-[11px] text-teal-700 font-bold bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200">
            No File Needed
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              type: 'lab' as const,
              icon: '🔬',
              title: 'Lab Blood Report',
              subtitle: 'HbA1c: 6.8%, TLC: 8,400',
              tag: 'Biomarkers',
              color: 'from-blue-500/10 to-teal-500/10 hover:border-blue-400',
            },
            {
              type: 'prescription' as const,
              icon: '💊',
              title: 'Doctor Prescription',
              subtitle: 'Metformin 500mg, Atorvastatin',
              tag: 'Medications',
              color: 'from-emerald-500/10 to-teal-500/10 hover:border-emerald-400',
            },
            {
              type: 'discharge' as const,
              icon: '📋',
              title: 'Discharge Summary',
              subtitle: 'Post-op Vitiligo & Vitals',
              tag: 'Hospital Note',
              color: 'from-purple-500/10 to-indigo-500/10 hover:border-purple-400',
            },
          ].map((sample) => (
            <button
              key={sample.type}
              type="button"
              disabled={isLoading}
              onClick={() => handleQuickSample(sample.type)}
              className={`p-4 rounded-2xl bg-gradient-to-br ${sample.color} bg-white border border-slate-200/90 text-left transition-all duration-200 cursor-pointer hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{sample.icon}</span>
                <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-700 shadow-2xs">
                  {sample.tag}
                </span>
              </div>
              <h3 className="font-extrabold text-slate-800 text-sm">{sample.title}</h3>
              <p className="text-xs text-slate-500 mt-0.5 truncate">{sample.subtitle}</p>
              <div className="mt-3 text-[11px] font-bold text-teal-700 flex items-center gap-1">
                <span>Load & Verify</span>
                <span>→</span>
              </div>
            </button>
          ))}
        </div>
      </div>
      {/* ── Invalid Medical Document Rejection Modal ── */}
      {isRejectedModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="invalid-doc-title"
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
        >
          <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-rose-100 p-6 sm:p-8 text-center space-y-5 animate-in zoom-in-95 duration-200">
            {/* Warning Icon Badge */}
            <div className="w-16 h-16 mx-auto rounded-3xl bg-rose-50 border-2 border-rose-200 flex items-center justify-center text-3xl shadow-inner text-rose-600">
              🚫
            </div>

            <div className="space-y-2">
              <h3 id="invalid-doc-title" className="text-xl font-extrabold text-slate-900 tracking-tight">
                {lang === 'ta' ? 'செல்லுபடியாகாத மருத்துவ ஆவணம்' : 'Invalid Medical Document'}
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                {rejectionMessage || (lang === 'ta'
                  ? 'பதிவேற்றப்பட்ட கோப்பு செல்லுபடியாகும் மருத்துவ ஆவணமாகத் தெரியவில்லை. தயவுசெய்து ஆதரிக்கப்பட்ட லேப் அறிக்கை, மருந்து சீட்டு அல்லது பரிசோதனை அறிக்கையைப் பதிவேற்றவும்.'
                  : 'The uploaded file does not appear to be a supported medical document. Please upload a valid laboratory report, prescription, or diagnostic report.')}
              </p>
            </div>

            {/* Supported formats checklist */}
            <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 text-left text-xs space-y-1.5 text-slate-700">
              <p className="font-bold text-slate-800">
                {lang === 'ta' ? 'ஆதரிக்கப்படும் மருத்துவ ஆவணங்கள்:' : 'Supported Medical Documents:'}
              </p>
              <ul className="space-y-1 pl-1 text-[11px] text-slate-600">
                <li className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{lang === 'ta' ? 'இரத்த / சிறுநீர் பரிசோதனை அறிக்கைகள் (Lab Reports)' : 'Laboratory Blood / Urine Reports'}</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{lang === 'ta' ? 'மருத்துவர் மருந்து சீட்டுகள் (Prescriptions)' : 'Doctor Prescriptions (Rx)'}</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{lang === 'ta' ? 'மருத்துவமனை டிஸ்சார்ஜ் சுருக்கங்கள் (Discharge Summaries)' : 'Hospital Discharge Summaries'}</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{lang === 'ta' ? 'ரேடியாலஜி / எக்ஸ்ரே / ஈசிஜி அறிக்கைகள் (Diagnostic Reports)' : 'Radiology / X-Ray / ECG / Ultrasound Reports'}</span>
                </li>
              </ul>
            </div>

            {/* Modal Actions */}
            <div className="pt-2 flex flex-col sm:flex-row gap-2.5 justify-center">
              <button
                type="button"
                onClick={handleChooseAnotherFile}
                className="w-full sm:flex-1 px-5 py-3 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white font-bold text-sm shadow-md shadow-teal-600/25 flex items-center justify-center gap-2 cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>📁</span>
                <span>{lang === 'ta' ? 'வேறொரு கோப்பைத் தேர்ந்தெடுக்கவும்' : 'Choose Another File'}</span>
              </button>
              <button
                type="button"
                onClick={() => setIsRejectedModalOpen(false)}
                className="w-full sm:w-auto px-4 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm cursor-pointer transition-colors"
              >
                {lang === 'ta' ? 'மூடு' : 'Dismiss'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Needs Review Modal ── */}
      {isNeedsReviewModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="review-doc-title"
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
        >
          <div className="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-amber-100 p-6 sm:p-8 text-center space-y-5 animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 mx-auto rounded-3xl bg-amber-50 border-2 border-amber-200 flex items-center justify-center text-3xl shadow-inner text-amber-600">
              ⚠️
            </div>

            <div className="space-y-2">
              <h3 id="review-doc-title" className="text-xl font-extrabold text-slate-900 tracking-tight">
                {lang === 'ta' ? 'மருத்துவ சரிபார்ப்பு தேவைப்படுகிறது' : 'Clinical Review Required'}
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                {lang === 'ta'
                  ? 'இந்த ஆவணம் கண்டறியப்பட்டது, ஆனால் சில புலங்கள் குறைந்த நம்பிக்கை அல்லது தெளிவற்ற கையெழுத்தைக் கொண்டுள்ளன. மனித பாதுகாப்பு உறுதிப்படுத்தல் தேவைப்படுகிறது.'
                  : 'This document was recognized, but one or more fields have low confidence or require clinical confirmation before being added to your health record.'}
              </p>
            </div>

            {/* Diagnostic Information Card */}
            {needsReviewMeta && (
              <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-4 text-left space-y-3">
                <div className="flex items-center justify-between text-xs border-b border-amber-200/50 pb-2.5">
                  <span className="font-semibold text-amber-900">
                    {lang === 'ta' ? 'ஆவண வகை:' : 'Detected Document:'}
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-amber-200/70 text-amber-900 font-bold text-[11px]">
                    {needsReviewMeta.docType || 'MEDICAL DOCUMENT'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-700">
                  <div className="bg-white/80 rounded-xl p-2.5 border border-amber-100 shadow-2xs">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-semibold">
                      {lang === 'ta' ? 'கண்டறியப்பட்டவை' : 'Extracted Items'}
                    </span>
                    <span className="text-sm font-bold text-slate-800">
                      {(needsReviewMeta.medsCount ?? 0) > 0 || (needsReviewMeta.testsCount ?? 0) > 0
                        ? `${needsReviewMeta.medsCount ?? 0} ${lang === 'ta' ? 'மருந்துகள்' : 'Meds'}, ${needsReviewMeta.testsCount ?? 0} ${lang === 'ta' ? 'பரிசோதனைகள்' : 'Tests'}`
                        : (needsReviewMeta.diagnosesCount ?? 0) > 0
                        ? `${needsReviewMeta.diagnosesCount} ${lang === 'ta' ? 'நோயறிதல்' : 'Diagnosis'}`
                        : lang === 'ta' ? 'மருத்துவ குறிப்புகள்' : 'Clinical Note'}
                    </span>
                  </div>

                  <div className="bg-white/80 rounded-xl p-2.5 border border-amber-100 shadow-2xs">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-semibold">
                      {lang === 'ta' ? 'ஒட்டுமொத்த நம்பிக்கை' : 'Confidence'}
                    </span>
                    <span className="text-sm font-bold text-slate-800">
                      {needsReviewMeta.confidence !== undefined ? `${needsReviewMeta.confidence}%` : 'Moderate'}
                    </span>
                  </div>
                </div>

                {needsReviewMeta.reasons && needsReviewMeta.reasons.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="font-semibold text-amber-900 text-[11px] block">
                      {lang === 'ta' ? 'சரிபார்ப்புக்கான காரணங்கள்:' : 'Triggers Requiring Confirmation:'}
                    </span>
                    <ul className="list-disc list-inside text-[11px] text-amber-800 space-y-0.5">
                      {needsReviewMeta.reasons.slice(0, 3).map((r, i) => (
                        <li key={i} className="truncate">
                          {r.replace(/_/g, ' ')}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <div className="pt-2 flex flex-col sm:flex-row gap-2.5 justify-center">
              {needsReviewRecordId && (
                <button
                  type="button"
                  onClick={() => {
                    setIsNeedsReviewModalOpen(false);
                    navigate(`/verify/${needsReviewRecordId}`);
                  }}
                  className="w-full sm:flex-1 px-5 py-3 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white font-bold text-sm shadow-md shadow-amber-600/25 flex items-center justify-center gap-2 cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <span>🔍</span>
                  <span>{lang === 'ta' ? 'ஆவணத்தை ஆய்வு செய்து சரிபார்க்கவும்' : 'Inspect & Verify Details'}</span>
                </button>
              )}
              <button
                type="button"
                onClick={handleChooseAnotherFile}
                className="w-full sm:w-auto px-4 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm cursor-pointer transition-colors"
              >
                <span>{lang === 'ta' ? 'தெளிவான படத்தை பதிவேற்று' : 'Upload Clearer Image'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
