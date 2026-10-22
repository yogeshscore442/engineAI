import React from 'react';
import { NavLink } from 'react-router-dom';
import { useApp } from '../AppContext';
import HospitalLogo from './HospitalLogo';
import LanguageDropdown from './LanguageDropdown';

type NavItem = {
  to: string;
  label: string;
  icon: string;
  badge?: string;
  badgeColor?: 'teal' | 'emerald' | 'purple' | 'amber' | 'rose' | 'slate';
  isDanger?: boolean;
};

type NavGroup = {
  groupTitle: string;
  items: NavItem[];
};

export default function Sidebar() {
  const { lang, setLang, openNodeModal } = useApp();

  const navGroups: NavGroup[] = [
    {
      groupTitle: lang === 'ta' ? 'ஆவணங்கள் & ஸ்கேன்' : lang === 'hi' ? 'रिकॉर्ड्स और स्कैन' : 'RECORDS & AI SCAN',
      items: [
        {
          to: '/timeline',
          label: lang === 'ta' ? 'டைம்லைன்' : lang === 'hi' ? 'टाइमलाइन' : 'Health Timeline',
          icon: 'timeline',
          badge: '12 Rec',
          badgeColor: 'teal',
        },
        {
          to: '/upload',
          label: lang === 'ta' ? 'பதிவேற்று & ஸ்கேன்' : lang === 'hi' ? 'अपलोड और स्कैन' : 'Upload & AI Scan',
          icon: 'upload',
          badge: 'OCR v2',
          badgeColor: 'slate',
        },
        {
          to: '/compare',
          label: lang === 'ta' ? 'லேப் ஒப்பீடு' : lang === 'hi' ? 'लैब रिपोर्ट तुलना' : 'Lab Diff Analyzer',
          icon: 'compare',
          badge: 'NEW',
          badgeColor: 'emerald',
        },
      ],
    },
    {
      groupTitle: lang === 'ta' ? 'மருத்துவ AI & ஆலோசனை' : lang === 'hi' ? 'क्लिनिकल एआई' : 'CLINICAL AI & INSIGHTS',
      items: [
        {
          to: '/doctor-prep',
          label: lang === 'ta' ? 'மருத்துவர் சந்திப்பு' : lang === 'hi' ? 'डॉक्टर विजिट प्रेप' : 'Doctor Visit Prep',
          icon: 'doctor',
          badge: 'PRO',
          badgeColor: 'purple',
        },
        {
          to: '/trends',
          label: lang === 'ta' ? 'டிரெண்ட்ஸ்' : lang === 'hi' ? 'बायोमार्कर्स' : 'Biomarker Trends',
          icon: 'trends',
        },
        {
          to: '/medicines',
          label: lang === 'ta' ? 'மருந்துகள்' : lang === 'hi' ? 'दवाइयां' : 'Medication Pillbox',
          icon: 'medicines',
          badge: '3 Doses',
          badgeColor: 'teal',
        },
        {
          to: '/alerts',
          label: lang === 'ta' ? 'பாதுகாப்பு எச்சரிக்கை' : lang === 'hi' ? 'दवा सुरक्षा' : 'Drug Safety Alerts',
          icon: 'alerts',
          badge: '1 Alert',
          badgeColor: 'amber',
        },
      ],
    },
    {
      groupTitle: lang === 'ta' ? 'அரசு ஆபா & அவசரம்' : lang === 'hi' ? 'ஆभा और इमरजेंसी' : 'ABDM & EMERGENCY',
      items: [
        {
          to: '/abha',
          label: lang === 'ta' ? 'ஆபா (ABHA) கார்டு' : lang === 'hi' ? 'आभा (ABHA) कार्ड' : 'ABHA Health ID',
          icon: 'abha',
          badge: 'M1/M2',
          badgeColor: 'teal',
        },
        {
          to: '/emergency',
          label: lang === 'ta' ? 'அவசர மருத்துவ அட்டை' : lang === 'hi' ? 'इमरजेंसी मेडिकल कार्ड' : 'Emergency Medical SOS',
          icon: 'emergency',
          isDanger: true,
          badge: 'SOS',
          badgeColor: 'rose',
        },
        {
          to: '/ask',
          label: lang === 'ta' ? 'AI-யிடம் கேளுங்கள்' : lang === 'hi' ? 'एआई से पूछें' : 'Ask Clinical AI',
          icon: 'ask',
          badge: 'Voice',
          badgeColor: 'teal',
        },
        {
          to: '/settings',
          label: lang === 'ta' ? 'அமைப்புகள்' : lang === 'hi' ? 'सेटिंग्स' : 'System Settings',
          icon: 'settings',
        },
      ],
    },
  ];

  return (
    <aside className="sidebar">
      {/* 1. Brand Header + Click-to-Reveal Language Dropdown */}
      <div className="p-4 border-b border-slate-200/80 bg-white flex flex-wrap items-center justify-between gap-3">
        <HospitalLogo size="md" showSubtitle={true} className="w-full" />
        <div className="ml-auto"><LanguageDropdown lang={lang} setLang={setLang} /></div>
      </div>

      {/* 2. Real-time Node Status Pill */}
      <div className="px-3 pt-2.5">
        <button
          onClick={openNodeModal}
          className="w-full px-2.5 py-1.5 rounded-xl bg-teal-50 hover:bg-teal-100/80 border border-teal-200/80 flex items-center justify-between text-xs text-teal-900 font-bold transition-all shadow-2xs group cursor-pointer"
        >
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="tracking-wide uppercase text-[11px] font-extrabold text-teal-900">
              ABDM Gateway: Active
            </span>
          </div>
          <span className="font-mono text-[10.5px] font-extrabold text-teal-900 bg-white px-1.5 py-0.5 rounded border border-teal-200 group-hover:bg-teal-600 group-hover:text-white transition-colors">
            18ms
          </span>
        </button>
      </div>

      {/* 4. Categorized Navigation Menu with Smooth Scroll */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-3.5 scrollbar-thin">
        {navGroups.map((group, groupIdx) => (
          <div key={groupIdx} className="space-y-1">
            {/* Section Header */}
            <div className="px-2.5 pb-1 flex items-center gap-1.5 text-[11px] font-extrabold tracking-wider text-slate-600 uppercase">
              <span className="w-2 h-2 rounded-full bg-teal-600"></span>
              <span>{group.groupTitle}</span>
            </div>

            {/* Nav Items */}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-xs transition-all duration-150 ${
                    isActive
                      ? 'bg-teal-50/90 text-teal-950 font-bold border border-teal-200 shadow-2xs border-l-4 border-l-teal-600'
                      : 'text-slate-800 hover:bg-slate-100 hover:text-slate-950 font-bold'
                  } ${item.isDanger ? 'hover:text-rose-700 hover:bg-rose-50' : ''}`
                }
              >
                {/* Left Icon + Text */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <NavIcon name={item.icon} isDanger={item.isDanger} />
                  <span className="truncate text-[13.5px] font-bold tracking-tight text-slate-800 group-hover:text-slate-950">
                    {item.label}
                  </span>
                </div>

                {/* Right Badge */}
                {item.badge && (
                  <span
                    className={`text-[9.5px] font-black px-1.5 py-0.5 rounded border uppercase tracking-wider flex-shrink-0 ${
                      item.badgeColor === 'emerald'
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300 font-extrabold'
                        : item.badgeColor === 'purple'
                        ? 'bg-purple-50 text-purple-800 border-purple-300 font-extrabold'
                        : item.badgeColor === 'amber'
                        ? 'bg-amber-50 text-amber-900 border-amber-300 font-extrabold'
                        : item.badgeColor === 'rose'
                        ? 'bg-rose-50 text-rose-800 border-rose-300 font-extrabold animate-pulse'
                        : 'bg-teal-50 text-teal-900 border-teal-300 font-extrabold'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* 5. Clinical Vitals HUD Card */}
      <div className="p-3 border-t border-slate-200/90 bg-slate-50/90">
        <div className="rounded-2xl bg-white border border-slate-200/90 p-2.5 shadow-2xs">
          <div className="flex items-center justify-between mb-2 px-0.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[11px] font-black uppercase tracking-wider text-slate-700">
                {lang === 'ta' ? 'நோயாளி முக்கிய அளவுகள்' : lang === 'hi' ? 'महत्वपूर्ण संकेत' : 'Patient Vitals'}
              </span>
            </div>
            <span className="text-[10px] font-extrabold text-teal-900 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded-full">
              Today
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {/* Blood Sugar Card */}
            <div className="rounded-xl border border-amber-200/90 bg-gradient-to-br from-amber-50/60 to-orange-50/30 p-2 transition-all hover:border-amber-300">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-extrabold text-amber-950 flex items-center gap-1">
                  <span>🩸</span> Sugar
                </span>
                <span className="text-[9.5px] font-black text-amber-900 bg-amber-100/90 px-1.5 py-0.2 rounded border border-amber-300/80">
                  142 ▲
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-base font-black font-mono text-amber-950">142</span>
                <span className="text-[10px] font-bold text-amber-800">mg/dL</span>
              </div>
            </div>

            {/* Blood Pressure Card */}
            <div className="rounded-xl border border-teal-200/90 bg-gradient-to-br from-teal-50/60 to-emerald-50/30 p-2 transition-all hover:border-teal-300">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-extrabold text-teal-950 flex items-center gap-1">
                  <span>🫀</span> BP
                </span>
                <span className="text-[9.5px] font-black text-teal-900 bg-teal-100/90 px-1.5 py-0.2 rounded border border-teal-300/80">
                  Pre-HTN
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-base font-black font-mono text-teal-950">138/88</span>
                <span className="text-[10px] font-bold text-teal-800">mmHg</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

/** Premium hospital-grade icon with colored gradient tile */
function NavIcon({ name, isDanger }: { name: string; isDanger?: boolean }) {
  // Config map: gradient colors + SVG path per route
  const config: Record<string, { from: string; to: string; shadow: string; content: React.ReactNode }> = {
    timeline: {
      from: '#0d9488', to: '#0891b2', shadow: 'rgba(13,148,136,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Clock with pulse line — health timeline */}
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 3" />
          <path d="M3.5 12.5h2M18.5 12.5h2M12 3.5v2M12 18.5v2" strokeWidth={1.5} />
        </svg>
      ),
    },
    upload: {
      from: '#6366f1', to: '#8b5cf6', shadow: 'rgba(99,102,241,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Cloud + AI scan lines */}
          <path d="M12 15V5m0 0-3.5 3.5M12 5l3.5 3.5" strokeWidth={2.2} />
          <path d="M4.5 17.5A3.5 3.5 0 0 0 6 20h12a3.5 3.5 0 0 0 1.5-6.68" />
          <path d="M9 20h6" strokeWidth={1.5} />
        </svg>
      ),
    },
    compare: {
      from: '#059669', to: '#10b981', shadow: 'rgba(5,150,105,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Side-by-side diff bars */}
          <rect x="3" y="5" width="7" height="14" rx="1.5" strokeWidth={1.8} />
          <rect x="14" y="5" width="7" height="14" rx="1.5" strokeWidth={1.8} />
          <path d="M7 9h3M7 12h3M7 15h1.5" strokeWidth={1.5} />
          <path d="M15 9h4M15 12h3M15 15h2" strokeWidth={1.5} />
        </svg>
      ),
    },
    doctor: {
      from: '#7c3aed', to: '#a855f7', shadow: 'rgba(124,58,237,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          {/* Stethoscope */}
          <path d="M6 3h4a1 1 0 0 1 1 1v5a4 4 0 0 1-8 0V4a1 1 0 0 1 1-1Z" />
          <path d="M8 13v3a5 5 0 0 0 10 0v-2" />
          <circle cx="19" cy="13" r="2" fill="white" stroke="white" strokeWidth={1} />
        </svg>
      ),
    },
    trends: {
      from: '#0891b2', to: '#06b6d4', shadow: 'rgba(8,145,178,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* ECG / biomarker pulse chart */}
          <path d="M2 12h3l2-7 3 14 2-10 2 5 2-3 2 1h4" strokeWidth={2.1} />
        </svg>
      ),
    },
    medicines: {
      from: '#0d9488', to: '#14b8a6', shadow: 'rgba(13,148,136,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          {/* Pill capsule */}
          <path d="M10.5 3.5a5 5 0 0 1 7 7l-7.5 7.5a5 5 0 0 1-7-7l7.5-7.5Z" />
          <path d="M8.5 10.5l5 5" />
        </svg>
      ),
    },
    alerts: {
      from: '#d97706', to: '#f59e0b', shadow: 'rgba(217,119,6,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Shield + exclamation — drug safety */}
          <path d="M12 3 4 7v5c0 4.4 3.4 8.5 8 9.5 4.6-1 8-5.1 8-9.5V7l-8-4Z" />
          <path d="M12 10v3" strokeWidth={2.3} />
          <circle cx="12" cy="16" r=".8" fill="white" />
        </svg>
      ),
    },
    abha: {
      from: '#0d9488', to: '#0f766e', shadow: 'rgba(13,148,136,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          {/* Government ID / ABHA card */}
          <rect x="2" y="5" width="20" height="14" rx="2" />
          <circle cx="8" cy="11" r="2.2" />
          <path d="M5.5 17c0-1.4 1.1-2.5 2.5-2.5s2.5 1.1 2.5 2.5" />
          <path d="M14 10h4M14 13h3" />
        </svg>
      ),
    },
    emergency: {
      from: '#dc2626', to: '#ef4444', shadow: 'rgba(220,38,38,0.4)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Cross / SOS heartbeat */}
          <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2Z" />
          <path d="M12 8v4M12 16h.01" strokeWidth={2.5} />
        </svg>
      ),
    },
    ask: {
      from: '#0891b2', to: '#6366f1', shadow: 'rgba(99,102,241,0.35)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          {/* AI chat sparkle bubble */}
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
          <path d="M9.5 9.5h.01M12 9.5h.01M14.5 9.5h.01" strokeWidth={2.4} />
        </svg>
      ),
    },
    settings: {
      from: '#475569', to: '#64748b', shadow: 'rgba(71,85,105,0.3)',
      content: (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
        </svg>
      ),
    },
  };

  // Emergency SOS override
  if (isDanger || name === 'emergency') {
    return (
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 relative overflow-hidden"
        style={{
          background: 'linear-gradient(135deg,#dc2626,#ef4444)',
          boxShadow: '0 4px 12px rgba(220,38,38,0.4)',
        }}
      >
        <div className="absolute inset-0 animate-pulse" style={{ background: 'rgba(255,255,255,0.08)' }} />
        {config.emergency.content}
      </div>
    );
  }

  const c = config[name];
  if (!c) return null;

  return (
    <div
      className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform duration-150 group-hover:scale-110"
      style={{
        background: `linear-gradient(135deg, ${c.from}, ${c.to})`,
        boxShadow: `0 4px 10px ${c.shadow}`,
      }}
    >
      {c.content}
    </div>
  );
}
