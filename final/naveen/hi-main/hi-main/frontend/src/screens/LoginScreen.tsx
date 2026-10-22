import React, { useState } from 'react';
import type { PatientProfile } from '../types/auth';
import { DEMO_PATIENTS } from '../types/auth';
import type { Language } from '../i18n';
import HospitalLogo from '../components/HospitalLogo';
import InfoTooltip from '../components/InfoTooltip';

type LoginScreenProps = {
  onLogin: (patient: PatientProfile) => void;
  lang: Language;
  setLang: (lang: Language) => void;
};

export default function LoginScreen({ onLogin, lang, setLang }: LoginScreenProps) {
  const [selectedHospital, setSelectedHospital] = useState(DEMO_PATIENTS[0].hospitalName);
  const [patientId, setPatientId] = useState(DEMO_PATIENTS[0].id);
  const [patientName, setPatientName] = useState(DEMO_PATIENTS[0].name);
  const [pin, setPin] = useState('••••');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleQuickSelect = (demo: PatientProfile) => {
    setSelectedHospital(demo.hospitalName);
    setPatientId(demo.id);
    setPatientName(demo.name);
    setPin('••••');
    setFeedback(
      lang === 'ta'
        ? `${demo.name} விவரங்கள் தேர்ந்தெடுக்கப்பட்டது!`
        : lang === 'hi'
        ? `${demo.name} का विवरण चुना गया!`
        : `Selected: ${demo.name}`
    );
    setTimeout(() => setFeedback(null), 2500);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsAuthenticating(true);
    setFeedback(
      lang === 'ta'
        ? 'ABDM நெட்வொர்க்குடன் இணைக்கப்படுகிறது…'
        : lang === 'hi'
        ? 'ABDM नेटवर्क से कनेक्ट हो रहा है…'
        : 'Opening local demo profile…'
    );

    setTimeout(() => {
      const matched = DEMO_PATIENTS.find((d) => d.id.toLowerCase() === patientId.toLowerCase());
      const loggedPatient: PatientProfile = matched || {
        id: patientId || 'APL-PAT-2024-001',
        name: patientName || 'Verified Patient',
        age: 52,
        gender: 'Male',
        bloodGroup: 'O+',
        hospitalName: selectedHospital,
        hospitalCode: selectedHospital.includes('AIIMS')
          ? 'AIIMS-DEL'
          : selectedHospital.includes('Fortis')
          ? 'FORTIS-CHE'
          : 'APOLLO-CHE',
        uhid: `UHID-${patientId.replace(/[^A-Za-z0-9]/g, '')}`,
        abhaId: '91-2345-6789-0123',
        primaryDoctor: 'Dr. Arvind Swaminathan (Cardiology)',
        primaryCondition: 'Type 2 Diabetes & Mild Hypertension',
        emergencyContact: '+91 98401 23456 (Family)',
        lastSync: 'Just now',
        isLoggedIn: true,
      };
      onLogin(loggedPatient);
      setIsAuthenticating(false);
    }, 700);
  };

  return (
    <div
      className="login-screen min-h-screen w-full flex flex-col relative overflow-hidden select-none"
      style={{ background: 'linear-gradient(135deg, #f0fdf9 0%, #e0f2fe 40%, #ede9fe 100%)' }}
    >
      {/* ── Decorative blobs ── */}
      <div
        className="absolute -top-32 -left-32 w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(13,148,136,0.18) 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-32 -right-32 w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)' }}
      />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.07) 0%, transparent 70%)' }}
      />

      {/* ── Top grid pattern ── */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: 'linear-gradient(rgba(13,148,136,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(13,148,136,0.08) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* ── Header ── */}
      <header
        className="relative z-10 w-full px-6 py-4 flex items-center justify-between border-b border-white/60"
        style={{ background: 'rgba(255,255,255,0.7)', backdropFilter: 'blur(20px)' }}
      >
        <HospitalLogo size="md" showSubtitle={true} />

        <div className="flex items-center gap-3">
          {/* Live badge */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-black tracking-wide"
            style={{
              background: 'linear-gradient(135deg,rgba(16,185,129,0.12),rgba(13,148,136,0.12))',
              border: '1px solid rgba(16,185,129,0.3)',
              color: '#065f46',
            }}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Local Demo — No Live Gateway
          </div>

          {/* Language toggle */}
          <div
            className="flex items-center rounded-xl p-1"
            style={{ background: 'rgba(255,255,255,0.8)', border: '1px solid rgba(13,148,136,0.2)', backdropFilter: 'blur(8px)' }}
          >
            {(['en', 'ta', 'hi'] as Language[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-3 py-1 rounded-lg text-xs font-black transition-all cursor-pointer ${
                  lang === l ? 'text-white shadow-sm' : 'text-slate-500 hover:text-slate-800'
                }`}
                style={
                  lang === l
                    ? { background: 'linear-gradient(135deg,#0d9488,#0891b2)', boxShadow: '0 2px 8px rgba(13,148,136,0.3)' }
                    : {}
                }
              >
                {l === 'en' ? 'EN' : l === 'ta' ? 'தமிழ்' : 'हिंदी'}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 py-8">
        <div className="w-full max-w-lg">
          {/* Card */}
          <div
            className="rounded-3xl overflow-hidden"
            style={{
              background: 'rgba(255,255,255,0.92)',
              backdropFilter: 'blur(32px)',
              border: '1.5px solid rgba(255,255,255,0.9)',
              boxShadow: '0 32px 64px -12px rgba(15,23,42,0.12), 0 0 0 1px rgba(13,148,136,0.08)',
            }}
          >
            {/* Top gradient bar */}
            <div
              className="h-1.5 w-full"
              style={{ background: 'linear-gradient(90deg, #0d9488, #06b6d4, #6366f1, #8b5cf6)' }}
            />

            <div className="p-7 sm:p-9">
              {/* Portal badge */}
              <div className="flex items-center gap-2 mb-4">
                <span
                  className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-widest px-3 py-1 rounded-full"
                  style={{
                    background: 'linear-gradient(135deg,rgba(13,148,136,0.1),rgba(6,182,212,0.1))',
                    border: '1px solid rgba(13,148,136,0.25)',
                    color: '#0f766e',
                  }}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                  {lang === 'ta' ? 'நோயாளி உள்நுழைவு' : lang === 'hi' ? 'मरीज लॉगिन पोर्टल' : 'Patient Hospital Portal'}
                </span>
              </div>

              {/* Main Topic / Heading with Info Icon */}
              <div className="flex items-center justify-between gap-3 mb-5">
                <h1
                  className="font-black tracking-tight"
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(1.65rem, 4.2vw, 2.2rem)',
                    fontWeight: 900,
                    background: 'linear-gradient(135deg, #0f172a 0%, #0d9488 60%, #6366f1 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                    lineHeight: 1.15,
                  }}
                >
                  {lang === 'ta'
                    ? 'மருத்துவமனை நோயாளி ஐடி மூலம் உள்நுழைக'
                    : lang === 'hi'
                    ? 'Hospital Patient ID से Login करें'
                    : 'Login with Hospital Patient ID'}
                </h1>
                <div className="flex-shrink-0">
                  <InfoTooltip
                    size="md"
                    align="right"
                    text={
                      lang === 'ta'
                        ? 'உங்கள் தனித்துவமான மருத்துவமனை நோயாளி ஐடியைப் பயன்படுத்தி மருந்துச்சீட்டுகள், ஆய்வக அறிக்கைகள், பயோमार्க்கர் போக்குகள் மற்றும் AI ஹெல்த் கோபைலட்டை அணுகலாம்.'
                        : lang === 'hi'
                        ? 'अपने विशिष्ट अस्पताल मरीज आईडी का उपयोग करके नुस्खे, लैब रिपोर्ट, बायोमार्कर रुझान और एआई हेल्थ कोपायलट तक सुरक्षित पहुंच प्राप्त करें।'
                        : 'Access your prescriptions, lab reports, biomarker trends & AI health copilot using your unique Hospital Patient ID.'
                    }
                  />
                </div>
              </div>

              {/* Feedback toast */}
              {feedback && (
                <div
                  className="mb-4 p-3 rounded-xl text-xs font-black flex items-center gap-2 animate-fadeIn"
                  style={{
                    background: 'linear-gradient(135deg,rgba(240,253,250,0.95),rgba(209,250,229,0.95))',
                    border: '1px solid rgba(16,185,129,0.4)',
                    color: '#065f46',
                  }}
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
                  {feedback}
                </div>
              )}

              {/* Quick demo patients */}
              <div className="mb-5 p-3.5 rounded-2xl bg-slate-50/70 border border-slate-200/80">
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-slate-800">
                    <span className="text-teal-600">⚡</span>
                    <span>{lang === 'ta' ? 'விரைவு மாதிரி நோயாளி:' : lang === 'hi' ? 'त्वरित डेमो रोगी:' : 'Quick Demo Patients:'}</span>
                  </div>
                  <InfoTooltip
                    size="sm"
                    align="right"
                    text={
                      lang === 'ta'
                        ? 'மாதிரி நோயாளியைத் தேர்ந்தெடுத்து 1-கிளிக்கில் மருத்துவமனை மற்றும் நோயாளி விவரங்களை நிரப்பவும்.'
                        : lang === 'hi'
                        ? 'डेमो रोगी चुनें और 1-क्लिक में अस्पताल क्रेडेंशियल्स ऑटो-फिल करें।'
                        : 'Select any verified demo profile to auto-fill hospital, patient ID, name, and test the timeline.'
                    }
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  {DEMO_PATIENTS.map((demo) => {
                    const isSelected = patientId.trim().toLowerCase() === demo.id.toLowerCase();
                    return (
                      <button
                        key={demo.id}
                        type="button"
                        onClick={() => handleQuickSelect(demo)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-black border transition-all cursor-pointer flex items-center gap-1.5 ${
                          isSelected
                            ? 'bg-teal-600 text-white border-teal-700 shadow-md scale-[1.02]'
                            : 'bg-white text-slate-700 border-slate-200 hover:border-teal-400 hover:bg-teal-50/60'
                        }`}
                      >
                        <span>👤</span>
                        <span className="font-black">{demo.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Credentials Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Hospital selector */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <label className="text-sm font-black text-slate-900 tracking-wide">
                        {lang === 'ta' ? 'மருத்துவமனையை தேர்ந்தெடுக்கவும்:' : lang === 'hi' ? 'अस्पताल चुनें:' : 'Select Your Hospital:'}
                      </label>
                      <InfoTooltip
                        size="sm"
                        align="left"
                        text={
                          lang === 'ta'
                            ? 'உங்கள் மருத்துவ வரலாற்று பதிவுகள் பதிவு செய்யப்பட்டுள்ள மருத்துவமனையைத் தேர்ந்தெடுக்கவும்.'
                            : lang === 'hi'
                            ? 'वह अस्पताल चुनें जहां आपके इलेक्ट्रॉनिक स्वास्थ्य रिकॉर्ड पंजीकृत हैं।'
                            : 'Select the registered hospital where your clinical EHR and diagnostic records reside.'
                        }
                      />
                    </div>
                  </div>
                  <select
                    value={selectedHospital}
                    onChange={(e) => setSelectedHospital(e.target.value)}
                    className="w-full px-4 py-3 text-sm font-bold text-slate-800 rounded-xl outline-none transition-all cursor-pointer appearance-none"
                    style={{
                      background: 'rgba(248,250,252,0.95)',
                      border: '1.5px solid rgba(203,213,225,0.85)',
                      boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.03)',
                    }}
                    onFocus={(e) => (e.target.style.border = '1.5px solid rgba(13,148,136,0.8)')}
                    onBlur={(e) => (e.target.style.border = '1.5px solid rgba(203,213,225,0.85)')}
                  >
                    <option value="Apollo Speciality Hospitals, Greams Rd">Apollo Speciality Hospitals (Greams Rd, Chennai)</option>
                    <option value="AIIMS Central Hospital, New Delhi">AIIMS Central Hospital (New Delhi)</option>
                    <option value="Fortis Malar Super Speciality Hospital">Fortis Malar Super Speciality Hospital</option>
                    <option value="Kauvery Hospital, Alwarpet">Kauvery Hospital (Alwarpet, Chennai)</option>
                    <option value="Manipal Hospital, Bangalore">Manipal Hospital (Bangalore)</option>
                    <option value="Govt Multi Super Speciality Hospital">Govt Multi Super Speciality Hospital (Omandurar)</option>
                  </select>
                </div>

                {/* Patient ID */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <label className="text-sm font-black text-slate-900 tracking-wide">
                        {lang === 'ta' ? 'நோயாளி ஐடி / UHID எண்:' : lang === 'hi' ? 'Patient ID / UHID नंबर:' : 'Hospital Patient ID / UHID Number:'}
                      </label>
                      <InfoTooltip
                        size="sm"
                        align="left"
                        text={
                          lang === 'ta'
                            ? 'உங்கள் மருத்துவமனை வழங்கிய பிரத்யேக UHID அல்லது நோயாளி ஐடியை (எ.கா: APL-PAT-2024-001) உள்ளிடவும்.'
                            : lang === 'hi'
                            ? 'अस्पताल द्वारा जारी विशिष्ट UHID या पेशेंट आईडी (जैसे APL-PAT-2024-001) दर्ज करें।'
                            : 'Enter the unique Hospital Patient ID (UHID / MRN) issued by your hospital (e.g. APL-PAT-2024-001).'
                        }
                      />
                    </div>
                    <span
                      className="font-mono text-[10px] px-2 py-0.5 rounded-full font-black tracking-tight"
                      style={{ background: 'rgba(13,148,136,0.1)', color: '#0f766e', border: '1px solid rgba(13,148,136,0.25)' }}
                    >
                      e.g. APL-PAT-2024-001
                    </span>
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      required
                      value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}
                      placeholder="e.g. APL-PAT-2024-001"
                      className="w-full pl-10 pr-4 py-3 text-sm font-mono font-black rounded-xl outline-none transition-all"
                      style={{
                        background: 'rgba(248,250,252,0.95)',
                        border: '1.5px solid rgba(203,213,225,0.85)',
                        color: '#0f766e',
                      }}
                      onFocus={(e) => (e.target.style.border = '1.5px solid rgba(13,148,136,0.8)')}
                      onBlur={(e) => (e.target.style.border = '1.5px solid rgba(203,213,225,0.85)')}
                    />
                    <span className="absolute left-3.5 top-3.5 text-teal-600 text-sm">🪪</span>
                  </div>
                </div>

                {/* Patient Name */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <label className="text-sm font-black text-slate-900 tracking-wide">
                        {lang === 'ta' ? 'நோயாளி பெயர்:' : lang === 'hi' ? 'पूरा नाम:' : 'Patient Full Name:'}
                      </label>
                      <InfoTooltip
                        size="sm"
                        align="left"
                        text={
                          lang === 'ta'
                            ? 'மருத்துவமனையில் பதிவு செய்யப்பட்டுள்ள நோயாளியின் முழுப்பெயர்.'
                            : lang === 'hi'
                            ? 'अस्पताल रिकॉर्ड के अनुसार मरीज का पूरा नाम।'
                            : 'Enter the legal full name of the patient as recorded during hospital registration.'
                        }
                      />
                    </div>
                  </div>
                  <input
                    type="text"
                    required
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder="e.g. Rajesh Kumar"
                    className="w-full px-4 py-3 text-sm font-bold rounded-xl outline-none transition-all"
                    style={{
                      background: 'rgba(248,250,252,0.95)',
                      border: '1.5px solid rgba(203,213,225,0.85)',
                      color: '#1e293b',
                    }}
                    onFocus={(e) => (e.target.style.border = '1.5px solid rgba(13,148,136,0.8)')}
                    onBlur={(e) => (e.target.style.border = '1.5px solid rgba(203,213,225,0.85)')}
                  />
                </div>

                {/* PIN */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <label className="text-sm font-black text-slate-900 tracking-wide">
                        {lang === 'ta' ? 'கடவுச்சொல் / PIN குறியீடு:' : lang === 'hi' ? 'Portal PIN / Access Code:' : 'Patient Portal PIN / Access Code:'}
                      </label>
                      <InfoTooltip
                        size="sm"
                        align="left"
                        text={
                          lang === 'ta'
                            ? 'மருத்துவமனை போர்ட்டல் அணுகலுக்கான 4 இலக்க PIN (மாதிரி இயல்புநிலை: 4-digit PIN).'
                            : lang === 'hi'
                            ? 'पोर्टल एक्सेस के लिए 4 अंकों का सुरक्षा पिन (डिफ़ॉल्ट डेमो: 4-digit PIN)।'
                            : '4-digit security PIN or access code for patient records portal authentication (Default: 4-digit PIN).'
                        }
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 font-bold">Default: 4-digit PIN</span>
                  </div>
                  <input
                    type="password"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    placeholder="Enter PIN"
                    className="w-full px-4 py-3 text-sm font-mono font-black tracking-widest rounded-xl outline-none transition-all"
                    style={{
                      background: 'rgba(248,250,252,0.95)',
                      border: '1.5px solid rgba(203,213,225,0.85)',
                      color: '#1e293b',
                    }}
                    onFocus={(e) => (e.target.style.border = '1.5px solid rgba(13,148,136,0.8)')}
                    onBlur={(e) => (e.target.style.border = '1.5px solid rgba(203,213,225,0.85)')}
                  />
                </div>

                {/* Submit */}
                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isAuthenticating}
                    className="w-full py-4 px-6 rounded-2xl text-sm font-black text-white transition-all flex items-center justify-center gap-2 cursor-pointer hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 shadow-lg"
                    style={{
                      background: 'linear-gradient(135deg, #0d9488 0%, #0891b2 50%, #6366f1 100%)',
                      boxShadow: '0 8px 24px rgba(13,148,136,0.35), 0 2px 8px rgba(99,102,241,0.2)',
                      letterSpacing: '0.02em',
                    }}
                  >
                    {isAuthenticating ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span className="font-black">
                          {lang === 'ta' ? 'சரிபார்க்கப்படுகிறது…' : lang === 'hi' ? 'Authenticating…' : 'Opening demo…'}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-base">🔐</span>
                        <span className="font-black">
                          {lang === 'ta'
                            ? 'மருத்துவமனை கணக்கில் உள்நுழைக'
                            : lang === 'hi'
                            ? 'Hospital Records में Login करें'
                            : 'Login with Hospital Patient ID'}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Security badges */}
              <div
                className="mt-6 pt-4 flex items-center justify-between text-[11px]"
                style={{ borderTop: '1px solid rgba(226,232,240,0.8)' }}
              >
                <span className="flex items-center gap-1.5 font-black text-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  Sample patient records — not verified by ABDM
                </span>
                <span className="font-mono font-black text-slate-500">FHIR-style export · Demo only</span>
              </div>
            </div>
          </div>

          {/* Trust badges below card */}
          <div className="flex items-center justify-center gap-6 mt-5">
            {[
              { icon: '🏥', label: 'Not ABDM Certified' },
              { icon: '🔒', label: 'Local Demo Storage' },
              { icon: '🤖', label: 'Gemini AI Powered' },
            ].map((b) => (
              <div key={b.label} className="flex items-center gap-1.5 text-[11px] font-black text-slate-600">
                <span>{b.icon}</span>
                <span className="font-black">{b.label}</span>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        className="relative z-10 w-full px-4 py-3 text-center text-xs font-bold text-slate-400"
        style={{ borderTop: '1px solid rgba(226,232,240,0.5)' }}
      >
        AI Health Copilot · Altrix Labs Challenge · Personal Healthcare AI Platform
      </footer>
    </div>
  );
}
