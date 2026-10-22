import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useApp } from '../AppContext';
import { api } from '../api';
import ErrorState from '../components/ErrorState';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import Disclaimer from '../components/Disclaimer';
import type { Medicine } from '../types';

export default function Emergency() {
  const { id } = useParams<{ id: string }>();
  const { t, profileId, useMock } = useApp();
  const [conditions, setConditions] = useState<string[]>([]);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        if (id) {
          const data = await api.getRecord(id);
          const rec = data?.record;
          const diagList = (rec?.diagnoses || []).map((d) => d?.text || (d as any)?.name || '').filter(Boolean);
          setConditions(diagList);
          setMedicines(rec?.medicines || []);
        } else {
          // Load active patient timeline to aggregate emergency health data
          const timeline = await api.getTimeline(profileId);
          const allDiagnoses = new Set<string>();
          const allMeds: Medicine[] = [];
          const seenMeds = new Set<string>();

          for (const item of (timeline.items || [])) {
            // Find records for diagnoses
            try {
              const rec = await api.getRecord(item.record_id);
              const r = rec?.record;
              if (r) {
                (r.diagnoses || []).forEach((d) => {
                  const text = d?.text || (d as any)?.name;
                  if (text) allDiagnoses.add(text);
                });
                (r.medicines || []).forEach((m) => {
                  if (!m) return;
                  const key = `${m.name_raw || 'med'}_${m.strength || ''}`;
                  if (!seenMeds.has(key)) {
                    seenMeds.add(key);
                    allMeds.push(m);
                  }
                });
              }
            } catch {
              // fallback to item summary
            }
          }

          setConditions(Array.from(allDiagnoses));
          setMedicines(allMeds);
        }
      } catch (err) {
        const message = err && typeof err === 'object' && 'error' in err
          ? (err as { error: { message: string } }).error.message
          : 'Failed to compile emergency data';
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, profileId, useMock]);

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <h2 className="text-2xl font-bold text-text-primary">{t('emergency.title')}</h2>
        <LoadingSkeleton type="card" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold text-text-primary mb-4">{t('emergency.title')}</h2>
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge badge-high text-xs">🆘 Critical Patient Care</span>
            <span className="text-xs text-text-muted">ABDM Fast-Response Format</span>
          </div>
          <h2 className="text-2xl font-bold text-text-primary mt-1">{t('emergency.title')}</h2>
          <p className="text-sm text-text-secondary mt-0.5">{t('emergency.subtitle')}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="btn-primary text-sm py-2 px-4 shadow-md bg-rose-600 hover:bg-rose-700"
          >
            🖨️ {t('emergency.print')}
          </button>
        </div>
      </div>

      {/* Emergency Wallet Card Box */}
      <div className="card p-6 border-2 border-rose-300 bg-gradient-to-br from-rose-50/40 via-white to-white shadow-md relative overflow-hidden">
        <div className="absolute top-0 right-0 bg-rose-600 text-white font-bold text-[10px] px-4 py-1 rounded-bl-lg tracking-widest uppercase">
          EMERGENCY ID
        </div>

        {/* Patient Vitals Header */}
        <div className="flex items-center gap-4 pb-4 border-b border-rose-100">
          <div className="w-14 h-14 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-2xl shadow-inner">
            +
          </div>
          <div>
            <h3 className="text-lg font-bold text-text-primary">Demo Patient</h3>
            <p className="text-xs text-text-secondary">
              Profile: <span className="font-mono font-semibold">{profileId}</span> • Blood Group: <strong className="text-rose-700">Not verified</strong>
            </p>
            <p className="text-xs text-text-muted mt-0.5">Emergency contact: not verified</p>
          </div>
        </div>

        {/* Conditions & Medicines Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-5">
          {/* Conditions */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-rose-800 mb-2 flex items-center gap-1.5">
              <span>🩺</span>
              <span>{t('emergency.conditions')}</span>
            </h4>
            <div className="space-y-1.5">
              {conditions.map((c, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-rose-50/60 border border-rose-200 text-xs font-semibold text-rose-950 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-600"></span>
                  <span>{c}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Critical Medications */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-teal-800 mb-2 flex items-center gap-1.5">
              <span>💊</span>
              <span>Medicines recorded in documents</span>
            </h4>
            <div className="space-y-1.5">
              {medicines.map((m, i) => (
                <div key={i} className="p-2 rounded-lg bg-surface-50 border border-border-light text-xs flex items-center justify-between">
                  <span className="font-semibold text-text-primary">{m.name_raw}</span>
                  <span className="text-[11px] font-mono text-teal-700 font-bold bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                    {m.strength || m.schedule_raw}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Interactive QR Code for First Responders */}
        <div className="mt-6 pt-5 border-t border-border-light flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-center sm:text-left">
            <h4 className="text-xs font-bold uppercase tracking-wider text-text-primary">
              Paramedic / Emergency Scanner QR
            </h4>
            <p className="text-xs text-text-secondary mt-0.5 max-w-sm">
              Illustration only — this QR graphic does not encode patient data or open an emergency record.
            </p>
          </div>

          {/* SVG QR Code Graphic */}
          <div className="p-3 bg-white rounded-xl border border-border-medium shadow-sm flex items-center gap-3">
            <svg className="w-20 h-20 text-slate-800" viewBox="0 0 100 100" fill="currentColor">
              {/* Corner 1 */}
              <rect x="5" y="5" width="25" height="25" fill="#0f172a" />
              <rect x="10" y="10" width="15" height="15" fill="white" />
              <rect x="14" y="14" width="7" height="7" fill="#0f172a" />
              {/* Corner 2 */}
              <rect x="70" y="5" width="25" height="25" fill="#0f172a" />
              <rect x="75" y="10" width="15" height="15" fill="white" />
              <rect x="79" y="14" width="7" height="7" fill="#0f172a" />
              {/* Corner 3 */}
              <rect x="5" y="70" width="25" height="25" fill="#0f172a" />
              <rect x="10" y="75" width="15" height="15" fill="white" />
              <rect x="14" y="79" width="7" height="7" fill="#0f172a" />
              {/* Data matrix dots */}
              <rect x="35" y="10" width="5" height="10" fill="#0f172a" />
              <rect x="45" y="5" width="10" height="5" fill="#0f172a" />
              <rect x="50" y="20" width="10" height="5" fill="#0f172a" />
              <rect x="15" y="40" width="10" height="5" fill="#0f172a" />
              <rect x="35" y="35" width="10" height="10" fill="#0d9488" />
              <rect x="55" y="35" width="8" height="8" fill="#0f172a" />
              <rect x="70" y="45" width="10" height="10" fill="#0f172a" />
              <rect x="40" y="55" width="15" height="5" fill="#0f172a" />
              <rect x="65" y="70" width="8" height="8" fill="#0f172a" />
              <rect x="45" y="75" width="10" height="10" fill="#0d9488" />
              <rect x="75" y="80" width="15" height="10" fill="#0f172a" />
            </svg>
            <div className="text-[10px] text-text-muted space-y-0.5">
              <div className="font-bold text-slate-800">DEMO QR ILLUSTRATION</div>
              <div>No verified ABHA link</div>
              <div className="text-emerald-700 font-semibold">Not for emergency use</div>
            </div>
          </div>
        </div>
      </div>

      {/* Non-dismissible Disclaimer */}
      <Disclaimer />
    </div>
  );
}