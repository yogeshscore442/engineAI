import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useApp } from '../AppContext';
import { api } from '../api';
import Disclaimer from '../components/Disclaimer';
import ErrorState from '../components/ErrorState';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import ProductDetailsModal from '../components/ProductDetailsModal';
import type { Record as RecordType } from '../types';

export default function Summary() {
  const { id } = useParams<{ id: string }>();
  const { t, lang, useMock } = useApp();
  const [record, setRecord] = useState<RecordType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [downloadingFhir, setDownloadingFhir] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [selectedMedicine, setSelectedMedicine] = useState<any | null>(null);
  const [summaryTab, setSummaryTab] = useState<'plain' | 'short' | 'detailed'>('plain');
  const [streamedSummary, setStreamedSummary] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!id) return;
      setLoading(true);
      setError(null);
      setStreamedSummary(null);
      setIsStreaming(false);
      try {
        const data = await api.getRecord(id);
        setRecord(data.record);
      } catch (err) {
        const message = err && typeof err === 'object' && 'error' in err
          ? (err as { error: { message: string } }).error.message
          : 'Failed to load summary';
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, useMock]);

  const handleStartStreaming = () => {
    if (!id || isStreaming) return;
    setIsStreaming(true);
    setStreamedSummary('');
    setSummaryTab('plain');
    api.streamSummary(
      id,
      lang,
      (chunk) => {
        setStreamedSummary(chunk);
      },
      (full) => {
        setIsStreaming(false);
        setStreamedSummary(full);
      },
      () => {
        setIsStreaming(false);
      }
    );
  };

  const abnormalCount = useMemo(
    () => (record?.tests || []).filter((t) => t.flag === 'HIGH' || t.flag === 'LOW').length || 0,
    [record]
  );

  // Summary view mode computation - unconditionally declared before any returns
  const displayedSummary = useMemo(() => {
    if (!record) return '';
    if (summaryTab === 'plain' && streamedSummary !== null) {
      return streamedSummary;
    }
    const hasTamil = Boolean(record.summary_ta);
    const activeSummary = lang === 'ta' && hasTamil ? record.summary_ta! : record.summary_en || 'No summary generated.';
    if (summaryTab === 'short' && record.short_summary) {
      return record.short_summary;
    }
    if (summaryTab === 'detailed' && record.detailed_summary) {
      return record.detailed_summary;
    }
    return activeSummary;
  }, [summaryTab, record, lang, streamedSummary]);

  const speak = (text: string) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setVoiceNotice(null);

    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();

    if (lang === 'ta') {
      const taVoice = voices.find((v) => v.lang.startsWith('ta'));
      if (taVoice) {
        utterance.voice = taVoice;
      } else {
        setVoiceNotice('Tamil voice synthesis not found on system; reading in available voice engine.');
      }
    } else if (lang === 'hi') {
      const hiVoice = voices.find((v) => v.lang.startsWith('hi'));
      if (hiVoice) {
        utterance.voice = hiVoice;
      } else {
        setVoiceNotice('Hindi voice synthesis not found on system; reading in available voice engine.');
      }
    }

    utterance.rate = 0.95;
    utterance.pitch = 1;
    setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  const downloadFhir = async () => {
    if (!id) return;
    setDownloadingFhir(true);
    try {
      const fhirData = await api.getFhirBundle(id);
      const blob = new Blob([JSON.stringify(fhirData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FHIR_R4_Bundle_${id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert('Failed to generate FHIR Bundle');
    } finally {
      setDownloadingFhir(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto">
        <LoadingSkeleton type="detail" />
      </div>
    );
  }

  if (error && !record) {
    return (
      <div className="max-w-3xl mx-auto">
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!record) return null;

  const hasTamilSummary = Boolean(record.summary_ta);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header & Badges */}
      <div className="card p-6 bg-gradient-to-r from-teal-50/50 via-white to-sky-50/30 border-border-light shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              {/* Record Verification Status */}
              {record.status === 'confirmed' ? (
                <span className="badge badge-normal text-xs font-semibold">
                  ✓ Patient Reviewed
                </span>
              ) : record.needs_review ? (
                <span className="badge badge-high text-xs font-semibold">
                  ⚠️ Review Required
                </span>
              ) : (
                <span className="badge badge-warning text-xs font-semibold">
                  📄 Extracted (Not Verified)
                </span>
              )}

              {/* Lab Values Normal Range Badge — ONLY evaluated when lab tests are present */}
              {record.tests && record.tests.length > 0 && (
                abnormalCount > 0 ? (
                  <span className="badge badge-high text-xs font-semibold">
                    ▲ {abnormalCount} {t('timeline.abnormal')}
                  </span>
                ) : record.tests.every((t: any) => t.flag === 'NORMAL') ? (
                  <span className="badge badge-normal text-xs font-semibold">
                    ✓ All Evaluated Lab Values In Normal Range
                  </span>
                ) : (
                  <span className="badge badge-warning text-xs font-semibold">
                    ℹ️ Lab Reference Range Not Evaluated
                  </span>
                )
              )}

              <span className="text-xs text-text-muted capitalize">
                {record.doc_type.replace('_', ' ')} • {record.doc_date || 'No Date'}
              </span>
            </div>
            <h2 className="text-2xl font-bold text-text-primary tracking-tight">
              {t('summary.title')}
            </h2>
            <p className="text-xs text-text-secondary mt-1">
              {record.status === 'confirmed'
                ? 'AI-assisted clinical extraction reviewed by patient'
                : 'AI-assisted extraction draft — awaiting patient verification'}
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Link to={`/verify/${id}`} className="btn-secondary text-xs py-2 px-3">
              ✏️ {t('common.edit')}
            </Link>
            <button
              onClick={downloadFhir}
              disabled={downloadingFhir}
              className="btn-secondary text-xs py-2 px-3 border-teal-300 text-teal-800 bg-teal-50/50 hover:bg-teal-100"
              title="Download interoperable FHIR R4 Bundle JSON"
            >
              {downloadingFhir ? 'Exporting…' : '📥 FHIR R4 Export'}
            </button>
            <button
              onClick={() => window.print()}
              className="btn-secondary text-xs py-2 px-3"
              title="Print for doctor appointment"
            >
              🖨️ Print
            </button>
          </div>
        </div>
      </div>

      {/* Summary Box with Phase 5 Short & Detailed View Controls */}
      <div className="card p-6 border-l-4 border-l-primary-500 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-100 text-primary-700 flex items-center justify-center font-bold text-sm">
              AI
            </div>
            <div>
              <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide">
                {lang === 'ta' ? 'மருத்துவ சுருக்கம் (Health Summary)' : 'Clinical Health Summary'}
              </h3>
              <p className="text-[11px] text-text-muted">Evidence-grounded medical overview</p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* View Mode Toggle: Plain | Short Overview | Detailed Breakdown */}
            <div className="inline-flex rounded-lg border border-border-medium p-0.5 bg-surface-100 text-xs font-medium">
              <button
                type="button"
                onClick={() => setSummaryTab('plain')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  summaryTab === 'plain'
                    ? 'bg-white text-primary-800 shadow-xs font-bold'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                Plain Language
              </button>
              <button
                type="button"
                onClick={() => setSummaryTab('short')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  summaryTab === 'short'
                    ? 'bg-white text-primary-800 shadow-xs font-bold'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                Short Overview
              </button>
              <button
                type="button"
                onClick={() => setSummaryTab('detailed')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  summaryTab === 'detailed'
                    ? 'bg-white text-primary-800 shadow-xs font-bold'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                Detailed Breakdown
              </button>
            </div>

            {/* Live Streaming Button */}
            <button
              onClick={handleStartStreaming}
              disabled={isStreaming}
              title={lang === 'ta' ? 'நேரலை AI சுருக்கம்' : 'Stream AI summary in real time'}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                isStreaming
                  ? 'bg-teal-50 text-teal-800 border-teal-300 animate-pulse'
                  : 'bg-white text-slate-700 hover:bg-slate-50 border-slate-200 shadow-2xs'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-teal-500 animate-ping' : 'bg-teal-600'}`}></span>
              <span>{isStreaming ? (lang === 'ta' ? 'உருவாக்குகிறது…' : 'Generating…') : (lang === 'ta' ? '⚡ நேரலை AI' : '⚡ AI Stream')}</span>
            </button>

            {/* Read Aloud Button */}
            <button
              onClick={() => (speaking ? stopSpeaking() : speak(displayedSummary))}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                speaking
                  ? 'bg-rose-100 text-rose-800 animate-pulse border border-rose-300'
                  : 'bg-primary-50 text-primary-800 hover:bg-primary-100 border border-primary-200'
              }`}
            >
              {speaking ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-rose-600 animate-ping"></span>
                  <span>Stop Audio / நிறுத்து</span>
                </>
              ) : (
                <>
                  <span>🔊</span>
                  <span>{lang === 'ta' ? 'குரல் வாசிப்பு (Read Aloud)' : 'Read Aloud'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {voiceNotice && (
          <div className="mb-3 p-2 rounded bg-amber-50 text-amber-800 text-xs border border-amber-200">
            {voiceNotice}
          </div>
        )}

        {lang === 'ta' && !hasTamilSummary && (
          <div className="mb-3 p-2 rounded bg-amber-50 text-amber-800 text-xs border border-amber-200">
            குறிப்பு: இந்த ஆவணத்திற்கான தமிழ் சுருக்கம் தயாராக இல்லை; ஆங்கிலத்தில் காட்டப்படுகிறது.
          </div>
        )}

        <div className={`text-text-primary leading-relaxed bg-surface-50 p-4 rounded-xl border border-border-light font-normal relative ${
          summaryTab === 'detailed' ? 'whitespace-pre-line text-sm font-sans' : 'text-base'
        }`}>
          {displayedSummary}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-teal-600 animate-pulse align-middle rounded-xs"></span>
          )}
        </div>
      </div>

      {/* Lab Tests with Abnormal Explanation */}
      {record.tests && record.tests.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
              <span>🔬</span>
              <span>{t('timeline.tests')} & Biomarkers ({record.tests.length})</span>
            </h3>
            <span className="text-xs text-text-muted">Reference range evaluated by clinical rules</span>
          </div>

          <div className="space-y-3">
            {record.tests.map((test, i) => {
              const isHigh = test.flag === 'HIGH';
              const isLow = test.flag === 'LOW';
              const isNormal = test.flag === 'NORMAL';

              return (
                <div
                  key={i}
                  className={`card p-4 transition-all ${
                    isHigh
                      ? 'border-rose-200 bg-rose-50/20'
                      : isLow
                      ? 'border-blue-200 bg-blue-50/20'
                      : 'border-border-light'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2.5">
                      <span className="font-bold text-base text-text-primary">{test.name}</span>
                      {test.loinc && (
                        <span className="text-[10px] font-mono bg-surface-100 px-1.5 py-0.5 rounded text-text-muted">
                          LOINC {test.loinc}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold text-text-primary">
                        {test.value} <span className="text-xs font-normal text-text-secondary">{test.unit}</span>
                      </span>

                      {/* Flag with dual visual cues (Color + Icon) */}
                      {isHigh && (
                        <span className="badge badge-high text-xs">
                          ▲ HIGH
                        </span>
                      )}
                      {isLow && (
                        <span className="badge badge-low text-xs">
                          ▼ LOW
                        </span>
                      )}
                      {isNormal && (
                        <span className="badge badge-normal text-xs">
                          ✓ NORMAL
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Reference Range Bar */}
                  <div className="text-xs text-text-secondary mb-2 flex items-center gap-2">
                    <span>Clinical Normal Range:</span>
                    <span className="font-semibold text-text-primary">
                      {test.ref_low ?? '—'} - {test.ref_high ?? '—'} {test.unit}
                    </span>
                  </div>

                  {/* Plain Language Explanation */}
                  {test.explanation_en && (
                    <div className="p-2.5 rounded-lg bg-white border border-border-light text-xs text-text-secondary">
                      <span className="font-semibold text-text-primary">What this means: </span>
                      {test.explanation_en}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Prescribed Medicines */}
      {record.medicines && record.medicines.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
            <span>💊</span>
            <span>{t('timeline.medicines')} ({record.medicines.length})</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {record.medicines.map((med, i) => (
              <div key={i} className="card p-4 border-border-light bg-white hover:border-primary-300 transition-colors shadow-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-text-primary text-sm">{med.name_raw}</h4>
                      {(med.user_confirmed || med.verification_state === 'VERIFIED_BY_USER') ? (
                        <span className="badge badge-success text-[10px] py-0.5 px-1.5 font-bold">
                          ✓ Patient Confirmed
                        </span>
                      ) : med.verification_state === 'VERIFIED' ? (
                        <span className="badge badge-normal text-[10px] py-0.5 px-1.5 font-bold">
                          ✓ Catalog Matched
                        </span>
                      ) : (med.verification_state === 'REQUIRES_HUMAN_REVIEW' || med.verification_state === 'NEEDS_REVIEW') ? (
                        <span className="badge badge-warning text-[10px] py-0.5 px-1.5 font-bold">
                          ⚠️ Needs Review
                        </span>
                      ) : (
                        <span className="badge badge-neutral text-[10px] py-0.5 px-1.5 font-bold bg-surface-200 text-text-secondary">
                          Unverified Candidate
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-text-secondary mt-0.5">
                      {med.generic ? `Generic: ${med.generic}` : ''} {med.strength ? `• ${med.strength}` : '• (Strength not specified)'} {med.formulation ? `(${med.formulation})` : ''}
                    </p>
                  </div>
                  {med.food_instruction && (
                    <span className="badge badge-normal text-[10px] whitespace-nowrap">
                      {med.food_instruction === 'before_food' ? t('medicines.beforeFood') : t('medicines.afterFood')}
                    </span>
                  )}
                </div>

                <div className="mt-3 pt-2 border-t border-border-light flex items-center justify-between text-xs text-text-secondary">
                  <span>Schedule: <strong className="text-text-primary">{med.schedule_raw || 'Not specified in prescription'}</strong></span>
                  <span>{med.duration_days ? `${med.duration_days} days` : 'Duration not specified'}</span>
                </div>

                {/* View More Button (Phase 7 Mandatory Control) */}
                <div className="mt-2.5 pt-2 border-t border-border-light/60 flex justify-end">
                  <button
                    type="button"
                    onClick={() => setSelectedMedicine(med)}
                    className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5 hover:bg-primary-50 hover:text-primary-800 transition-colors"
                  >
                    <span>🔍</span>
                    <span>View More / விவரங்கள்</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Optional Phase 7 View More Medicine Detail Modal */}
      {selectedMedicine && (
        <ProductDetailsModal
          isOpen={Boolean(selectedMedicine)}
          onClose={() => setSelectedMedicine(null)}
          medicineName={selectedMedicine.name_raw}
          generic={selectedMedicine.generic}
          strength={selectedMedicine.strength}
          dosageForm={selectedMedicine.formulation}
          ocrConfidence={selectedMedicine.confidence ?? 1.0}
          userConfirmed={true}
          prescriptionInstructions={selectedMedicine.schedule_raw}
          scheduleParsed={selectedMedicine.schedule_parsed}
          foodInstruction={selectedMedicine.food_instruction}
          durationDays={selectedMedicine.duration_days}
        />
      )}

      {/* Diagnoses List */}
      {record.diagnoses && record.diagnoses.length > 0 && (
        <div className="card p-4 border-border-light bg-surface-50">
          <h4 className="text-xs font-bold uppercase tracking-wider text-text-muted mb-2">
            Clinical Diagnoses / Conditions
          </h4>
          <div className="flex flex-wrap gap-2">
            {record.diagnoses.map((d, i) => (
              <span key={i} className="px-3 py-1 bg-white border border-border-medium rounded-lg text-sm font-semibold text-text-primary shadow-xs">
                {d.text}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Non-dismissible Disclaimer */}
      <div className="pt-4">
        <Disclaimer />
      </div>
    </div>
  );
}