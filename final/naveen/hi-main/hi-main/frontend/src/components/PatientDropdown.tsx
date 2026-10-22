import { useState, useRef, useEffect } from 'react';
import { useApp } from '../AppContext';
import { DEMO_PATIENTS, type PatientProfile } from '../types/auth';

export default function PatientDropdown() {
  const { user, setUser, setProfileId, openLoginModal } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPatient = (patient: PatientProfile) => {
    setUser(patient);
    if (setProfileId) {
      setProfileId(patient.id);
    }
    setIsOpen(false);
  };

  const currentInitials = (user?.name || 'R').charAt(0).toUpperCase();

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* ── Main Trigger Button (Patient Card Pill) ── */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        title="Click to switch hospital patient account"
        className={`flex items-center gap-2.5 px-3 py-1.5 rounded-xl border transition-all text-left shadow-2xs cursor-pointer select-none ${
          isOpen
            ? 'bg-teal-50 border-teal-500 ring-2 ring-teal-500/20 shadow-xs'
            : 'bg-surface-100 hover:bg-teal-50/70 border-slate-200 hover:border-teal-300'
        }`}
      >
        {/* Patient Avatar Circle */}
        <div className="w-8 h-8 rounded-lg bg-teal-800 text-white flex items-center justify-center font-bold text-xs shadow-sm flex-shrink-0">
          {currentInitials}
        </div>

        {/* Patient Name on Top (Bold) & Hospital Name Below */}
        <div className="min-w-0 pr-1">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-slate-900 text-xs truncate max-w-[170px] leading-tight">
              {user?.name || 'Rajesh Kumar'}
            </span>
            <span className="text-[9px] font-black uppercase px-1.5 py-0.2 rounded bg-teal-100 text-teal-900 border border-teal-300 leading-none">
              {user?.bloodGroup || 'O+'}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 font-medium truncate max-w-[180px] leading-tight mt-0.5">
            {(user?.hospitalName || 'Apollo Speciality Hospitals').split(',')[0]}
          </p>
        </div>

        {/* Subtle Dropdown Chevron Arrow */}
        <svg
          className={`w-4 h-4 text-slate-400 group-hover:text-teal-700 transition-transform duration-200 flex-shrink-0 ml-0.5 ${
            isOpen ? 'rotate-180 text-teal-700' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {/* ── Dropdown List of Patient Accounts ── */}
      {isOpen && (
        <div className="absolute left-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white border border-slate-200/90 shadow-2xl p-2 z-50 animate-fadeIn">
          {/* Dropdown Header */}
          <div className="px-3 py-2 flex items-center justify-between border-b border-slate-100 mb-1.5">
            <div>
              <p className="text-xs font-extrabold text-slate-900 flex items-center gap-1.5">
                <span>🪪</span> Switch Hospital Patient Account
              </p>
              <p className="text-[10px] text-slate-500">Select an authenticated clinical profile</p>
            </div>
            <span className="text-[10px] font-mono font-bold bg-teal-100 text-teal-800 px-2 py-0.5 rounded-full border border-teal-200">
              {DEMO_PATIENTS.length} Profiles
            </span>
          </div>

          {/* Accounts List */}
          <div className="space-y-1 max-h-[320px] overflow-y-auto pr-0.5">
            {DEMO_PATIENTS.map((demo) => {
              const isSelected = user?.id === demo.id;
              const demoInitial = demo.name.charAt(0).toUpperCase();

              return (
                <button
                  key={demo.id}
                  onClick={() => handleSelectPatient(demo)}
                  className={`w-full flex items-start gap-2.5 p-2.5 rounded-xl text-left transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-teal-50 border border-teal-300 shadow-2xs'
                      : 'hover:bg-slate-50 border border-transparent hover:border-slate-200'
                  }`}
                >
                  {/* Account Avatar */}
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5 shadow-2xs ${
                      isSelected
                        ? 'bg-teal-800 text-white'
                        : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {demoInitial}
                  </div>

                  {/* Account Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <p className="text-xs font-extrabold text-slate-900 truncate">
                        {demo.name}
                      </p>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <span className="text-[9px] font-black uppercase px-1.5 py-0.2 rounded bg-teal-100 text-teal-900 border border-teal-200">
                          {demo.bloodGroup}
                        </span>
                        {isSelected && (
                          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded flex items-center gap-0.5">
                            ✓ Active
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="font-mono text-[10px] font-bold text-teal-800">
                        {demo.id}
                      </span>
                      <span className="text-[10px] text-slate-400">•</span>
                      <span className="text-[10px] text-slate-500 font-medium truncate">
                        {demo.hospitalName.split(',')[0]}
                      </span>
                    </div>

                    <p className="text-[10px] text-slate-500 mt-0.5 truncate">
                      🩺 {demo.primaryDoctor.split('(')[0]}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Footer: Custom / Other Hospital Sign In */}
          <div className="pt-2 mt-1.5 border-t border-slate-100">
            <button
              onClick={() => {
                setIsOpen(false);
                openLoginModal();
              }}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold text-teal-800 bg-teal-50/70 hover:bg-teal-100/80 border border-teal-200 transition-colors cursor-pointer"
            >
              <span>➕</span> Enter Other Hospital / ABDM ID…
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
