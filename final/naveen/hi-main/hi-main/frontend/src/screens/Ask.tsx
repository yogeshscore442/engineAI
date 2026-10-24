import { useState, useRef } from 'react';
import { useApp } from '../AppContext';
import { api } from '../api';
import type { AskResponse } from '../types';
import ErrorState from '../components/ErrorState';
import Disclaimer from '../components/Disclaimer';

const SUGGESTED_QUESTIONS = [
  'What is my latest HbA1c result and trend?',
  'What are the precautions for my prescribed Metformin?',
  'Find a digital thermometer to buy',
  'Show alternatives to this blood pressure monitor',
  'Find a cheaper alternative to my prescribed medicine',
];

export default function Ask() {
  const { t, lang, profileId } = useApp();
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  const startVoiceInput = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.lang = lang === 'ta' ? 'ta-IN' : lang === 'hi' ? 'hi-IN' : 'en-IN';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join('');
        setQuestion(transcript);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const handleSend = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim()) return;
    setQuestion(q);
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const result = await api.askRecords(profileId, q);
      setResponse(result);
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'error' in err
          ? (err as { error: { message: string } }).error.message
          : 'Failed to query medical records';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const getIntentBadge = (intent?: string) => {
    switch (intent) {
      case 'MEDICAL_INFORMATION':
        return { label: '🩺 Medical Information & Guidance', bg: 'bg-teal-50 text-teal-800 border-teal-200' };
      case 'MEDICINE_QUERY':
        return { label: '💊 Medication Guidance & Pharmacology', bg: 'bg-indigo-50 text-indigo-800 border-indigo-200' };
      case 'PRODUCT_SHOPPING':
        return { label: '🛒 Healthcare Equipment & Devices', bg: 'bg-emerald-50 text-emerald-800 border-emerald-200' };
      case 'PRODUCT_ALTERNATIVES':
        return { label: '⚖️ Equipment Alternatives & Comparison', bg: 'bg-purple-50 text-purple-800 border-purple-200' };
      case 'MEDICINE_SUBSTITUTION_REQUEST':
        return { label: '⚠️ Prescription Substitution Safeguard', bg: 'bg-amber-50 text-amber-900 border-amber-300' };
      default:
        return { label: '🤖 Clinical Assistant', bg: 'bg-slate-50 text-slate-800 border-slate-200' };
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="badge badge-normal text-xs font-bold uppercase tracking-wider">
            🤖 Grounded Medical RAG & Intent Classification
          </span>
          <span className="text-xs text-text-muted">Clinical Guidance vs Equipment Shopping</span>
        </div>
        <h2 className="text-2xl font-bold text-text-primary mt-1">{t('ask.title')}</h2>
        <p className="text-sm text-text-secondary mt-0.5">
          Ask questions answered strictly using evidence extracted from your uploaded documents, official medical references, or verified healthcare products
        </p>
      </div>

      {/* Suggested Questions */}
      <div className="card p-4 space-y-2 bg-gradient-to-r from-teal-50/40 via-surface-50 to-white border-glow-teal">
        <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">
          Suggested Inquiries / மாதிரி வினாக்கள்:
        </span>
        <div className="flex flex-wrap gap-2 pt-1">
          {SUGGESTED_QUESTIONS.map((sq, i) => (
            <button
              key={i}
              onClick={() => handleSend(sq)}
              className="text-left text-xs px-3 py-2 rounded-lg bg-white border border-border-medium hover:border-primary-400 hover:text-primary-800 transition-colors shadow-2xs"
            >
              💬 {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Query Input Box with Voice Microphone Dictation */}
      <div className="card p-4 shadow-sm border-border-light relative overflow-hidden">
        {isListening && (
          <div className="mb-2 p-2 bg-rose-50 border border-rose-300 rounded-lg flex items-center justify-between text-xs text-rose-800 animate-pulse">
            <span className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-600 animate-ping"></span>
              <span>Listening to your voice ({lang.toUpperCase()})… Speak now!</span>
            </span>
            <span className="font-mono text-[10px]">Listening…</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <input
            id="ask-query-input"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={
              isListening
                ? 'Listening to speech…'
                : lang === 'ta'
                ? 'உங்கள் மருத்துவ பதிவேடுகள் பற்றி கேளுங்கள்…'
                : lang === 'hi'
                ? 'अपने मेडिकल रिकॉर्ड्स के बारे में पूछें…'
                : t('ask.placeholder')
            }
            className="input flex-1 text-sm"
            disabled={loading}
          />

          {/* Voice Microphone Button */}
          <button
            id="ask-voice-button"
            onClick={startVoiceInput}
            type="button"
            className={`p-3 rounded-lg border transition-all flex items-center justify-center ${
              isListening
                ? 'bg-rose-600 text-white border-rose-600 shadow-md animate-bounce'
                : 'bg-surface-50 text-slate-700 border-border-medium hover:bg-teal-50 hover:text-teal-700 hover:border-teal-300'
            }`}
            title="Speak Question (Voice Input in English / தமிழ் / हिंदी)"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
            </svg>
          </button>

          <button
            id="ask-submit-button"
            onClick={() => handleSend()}
            disabled={loading || !question.trim()}
            className="btn-primary py-3 px-6 shadow-sm"
          >
            {loading ? (
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>Searching…</span>
              </span>
            ) : (
              t('ask.send')
            )}
          </button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => handleSend()} />}

      {/* Answer & Comprehensive Results Box */}
      {response && (
        <div className="card p-6 border-l-4 border-l-teal-600 border-glow-teal shadow-md space-y-5">
          {/* Header row with Intent Badge & Verification Tag */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-light pb-3">
            <div className="flex items-center gap-2">
              <span
                id="intent-category-badge"
                className={`text-xs font-bold px-3 py-1 rounded-full border ${getIntentBadge(response.intent_category).bg}`}
              >
                {getIntentBadge(response.intent_category).label}
              </span>
            </div>
            {response.sources && response.sources.length > 0 && (
              <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                ✓ Verified Sourced
              </span>
            )}
          </div>

          {/* Clinician Review Required Warning */}
          {response.needs_clinician_review && (
            <div
              id="clinician-review-alert"
              className="p-3.5 bg-amber-50/90 border border-amber-300 rounded-xl flex items-start gap-3 text-amber-900 shadow-2xs"
            >
              <span className="text-xl shrink-0">⚠️</span>
              <div className="space-y-0.5">
                <div className="font-bold text-xs uppercase tracking-wide text-amber-950">
                  Requires Clinician or Pharmacist Verification
                </div>
                <p className="text-xs text-amber-800 leading-relaxed">
                  Prescription medicines, dosages, and handwritten instructions cannot be substituted or verified independently. Always confirm with your prescribing clinician or licensed pharmacist.
                </p>
              </div>
            </div>
          )}

          {/* Safety Notes Panel */}
          {response.safety_notes && response.safety_notes.length > 0 && (
            <div
              id="safety-notes-panel"
              className="p-3.5 bg-rose-50/80 border border-rose-200 rounded-xl space-y-1.5 text-xs text-rose-900"
            >
              <div className="font-bold uppercase tracking-wider text-[11px] text-rose-950 flex items-center gap-1.5">
                <span>🛡️</span>
                <span>Clinical Safety Notes:</span>
              </div>
              <ul className="list-disc pl-5 space-y-1 text-rose-800">
                {response.safety_notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Synthesis Answer */}
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-100 text-teal-800 flex items-center justify-center font-bold text-base flex-shrink-0">
              AI
            </div>
            <div className="flex-1 space-y-2">
              <h4 className="font-bold text-text-primary text-sm uppercase tracking-wider">
                Clinical Synthesis Answer
              </h4>
              <div
                id="clinical-answer-text"
                className="text-text-primary text-sm leading-relaxed bg-surface-50 p-4 rounded-xl border border-border-light whitespace-pre-wrap"
              >
                {response.answer}
              </div>
            </div>
          </div>

          {/* Medical Explanation (if distinct from answer) */}
          {response.medical_explanation && response.medical_explanation !== response.answer && (
            <div className="p-3.5 bg-teal-50/60 border border-teal-200 rounded-xl text-xs space-y-1">
              <div className="font-bold text-teal-950 uppercase tracking-wide text-[11px]">
                🧬 Clinical Evidence Summary
              </div>
              <p className="text-teal-900 leading-relaxed">{response.medical_explanation}</p>
            </div>
          )}

          {/* Verified Medical & Clinical References (Separate from shopping links) */}
          {response.medical_references && response.medical_references.length > 0 && (
            <div id="medical-references-section" className="p-4 bg-sky-50/60 border border-sky-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">📚</span>
                  <h5 className="font-bold text-xs text-sky-950 uppercase tracking-wider">
                    Verified Medical & Clinical References
                  </h5>
                </div>
                <span className="text-[10px] font-semibold text-sky-700 bg-sky-100 px-2 py-0.5 rounded-full border border-sky-300">
                  Authoritative Sources
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {response.medical_references.map((ref, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-white rounded-lg border border-sky-100 hover:border-sky-300 transition-colors shadow-2xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono font-bold text-sky-800 bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200 truncate">
                        {ref.source}
                      </span>
                      <span className="text-[9px] text-slate-500 font-semibold uppercase">{ref.reference_type}</span>
                    </div>
                    <div className="font-semibold text-xs text-slate-900 leading-snug">
                      {ref.title}
                    </div>
                    {ref.description && (
                      <p className="text-[11px] text-slate-600 line-clamp-2">{ref.description}</p>
                    )}
                    {ref.url && (
                      <a
                        href={ref.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-sky-700 hover:text-sky-900 pt-1"
                      >
                        <span>View Official Reference</span>
                        <span>↗</span>
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Verified Product Recommendations (ONLY when explicit shopping requested) */}
          {response.product_recommendations && response.product_recommendations.length > 0 && (
            <div
              id="product-recommendations-section"
              className="p-4 bg-emerald-50/50 border border-emerald-200 rounded-xl space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">🛒</span>
                  <h5 className="font-bold text-xs text-emerald-950 uppercase tracking-wider">
                    Verified Healthcare Equipment & Devices
                  </h5>
                </div>
                <span className="text-[10px] font-semibold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full border border-emerald-300">
                  Authorized Retailers Only
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {response.product_recommendations.map((prod) => (
                  <div
                    key={prod.product_id}
                    className="p-3.5 bg-white rounded-xl border border-emerald-200 hover:shadow-sm transition-all space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          {prod.category.replace('_', ' ')}
                        </span>
                        <h6 className="font-bold text-sm text-slate-900 mt-1">{prod.product_name}</h6>
                      </div>
                      {prod.price_display && (
                        <div className="text-right">
                          <span className="text-xs text-slate-500 block text-[10px]">Price</span>
                          <span className="text-base font-extrabold text-emerald-700">{prod.price_display}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <span className="font-semibold text-slate-700">Retailer:</span>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-medium text-[11px] border border-slate-200">
                        {prod.retailer}
                      </span>
                    </div>

                    {prod.specifications && Object.keys(prod.specifications).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {Object.entries(prod.specifications).map(([k, v]) => (
                          <span key={k} className="text-[10px] bg-slate-50 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                            <strong className="capitalize">{k.replace('_', ' ')}:</strong> {String(v)}
                          </span>
                        ))}
                      </div>
                    )}

                    {prod.purchase_url ? (
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-1">
                          <span>✓</span> Verified Retailer Link
                        </span>
                        <a
                          href={prod.purchase_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-primary text-xs py-1.5 px-3 rounded-lg shadow-2xs inline-flex items-center gap-1"
                        >
                          <span>View Product</span>
                          <span>↗</span>
                        </a>
                      </div>
                    ) : (
                      <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-500 italic">
                        Available at verified offline medical equipment dealers
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Product Alternatives Section */}
          {response.product_alternatives && response.product_alternatives.length > 0 && (
            <div
              id="product-alternatives-section"
              className="p-4 bg-purple-50/50 border border-purple-200 rounded-xl space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">⚖️</span>
                  <h5 className="font-bold text-xs text-purple-950 uppercase tracking-wider">
                    Comparable Equipment & Alternatives
                  </h5>
                </div>
                <span className="text-[10px] font-semibold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-full border border-purple-300">
                  Specification Comparison
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {response.product_alternatives.map((alt) => (
                  <div
                    key={alt.product_id}
                    className="p-3.5 bg-white rounded-xl border border-purple-200 hover:shadow-sm transition-all space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold text-purple-800 uppercase tracking-wider bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                          Alternative Option
                        </span>
                        <h6 className="font-bold text-sm text-slate-900 mt-1">{alt.product_name}</h6>
                      </div>
                      {alt.price_display && (
                        <div className="text-right">
                          <span className="text-xs text-slate-500 block text-[10px]">Price</span>
                          <span className="text-base font-extrabold text-purple-700">{alt.price_display}</span>
                        </div>
                      )}
                    </div>

                    {alt.comparison_notes && (
                      <div className="p-2 bg-purple-50/80 rounded-lg border border-purple-200 text-xs text-purple-900">
                        <strong>Key Comparison: </strong>
                        <span>{alt.comparison_notes}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <span className="font-semibold text-slate-700">Retailer:</span>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-medium text-[11px] border border-slate-200">
                        {alt.retailer}
                      </span>
                    </div>

                    {alt.specifications && Object.keys(alt.specifications).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {Object.entries(alt.specifications).map(([k, v]) => (
                          <span key={k} className="text-[10px] bg-slate-50 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                            <strong className="capitalize">{k.replace('_', ' ')}:</strong> {String(v)}
                          </span>
                        ))}
                      </div>
                    )}

                    {alt.purchase_url ? (
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[10px] text-purple-700 font-semibold flex items-center gap-1">
                          <span>✓</span> Verified Retailer Link
                        </span>
                        <a
                          href={alt.purchase_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-secondary text-xs py-1.5 px-3 rounded-lg shadow-2xs inline-flex items-center gap-1 border-purple-300 text-purple-900 hover:bg-purple-100"
                        >
                          <span>View Alternative</span>
                          <span>↗</span>
                        </a>
                      </div>
                    ) : (
                      <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-500 italic">
                        Check authorized medical equipment supplier
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Source Citations */}
          {response.sources && response.sources.length > 0 && (
            <div className="pt-3 border-t border-border-light">
              <p className="text-xs font-bold text-text-muted uppercase tracking-wider mb-2">
                Referenced Verification Sources:
              </p>
              <div className="flex flex-wrap gap-2">
                {response.sources.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 text-xs bg-slate-100 text-slate-800 px-2.5 py-1 rounded-md font-mono border border-slate-200"
                  >
                    <span>📄</span>
                    <span>{s.record_id}</span>
                    {s.field && <span className="text-teal-700 font-bold">[{s.field}]</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <Disclaimer />
    </div>
  );
}