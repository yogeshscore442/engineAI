import { AppContext, type AppContextType } from './AppContext';
import { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import type { Language } from './i18n';
import { useI18n } from './i18n';
import { api } from './api';
import type { UserProfile } from './types/auth';
import { DEMO_USERS } from './types/auth';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import BottomNav from './components/BottomNav';
import AppShell from './components/AppShell';
import LoginModal from './components/LoginModal';
import HospitalNodeModal from './components/HospitalNodeModal';
import EmergencySosModal from './components/EmergencySosModal';

import AiCopilotWidget from './components/AiCopilotWidget';
const LoginScreen = lazy(() => import('./screens/LoginScreen'));
const Upload = lazy(() => import('./screens/Upload'));
const Verify = lazy(() => import('./screens/Verify'));
const Summary = lazy(() => import('./screens/Summary'));
const Timeline = lazy(() => import('./screens/Timeline'));
const Medicines = lazy(() => import('./screens/Medicines'));
const Trends = lazy(() => import('./screens/Trends'));
const Alerts = lazy(() => import('./screens/Alerts'));
const Abha = lazy(() => import('./screens/Abha'));
const Settings = lazy(() => import('./screens/Settings'));
const Emergency = lazy(() => import('./screens/Emergency'));
const Ask = lazy(() => import('./screens/Ask'));
const Compare = lazy(() => import('./screens/Compare'));
const DoctorPrep = lazy(() => import('./screens/DoctorPrep'));

export default function App() {
  const [lang, setLang] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem('health-copilot-lang');
      return saved === 'ta' || saved === 'hi' ? saved : 'en';
    } catch {
      return 'en';
    }
  });

  const [profileId, setProfileId] = useState<string>(() => {
    try {
      return localStorage.getItem('health-copilot-profile') || 'demo-patient-001';
    } catch {
      return 'demo-patient-001';
    }
  });

  const [user, setUser] = useState<UserProfile>(() => {
    try {
      const saved = localStorage.getItem('health-copilot-user');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.primaryDoctor && parsed.bloodGroup && parsed.hospitalName) {
          return parsed;
        }
      }
    } catch {
      // fallback
    }
    return DEMO_USERS[0];
  });

  // By default false, so opening the website always requires logging in first!
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    try {
      localStorage.removeItem('health-copilot-auth');
      sessionStorage.removeItem('health-copilot-session');
    } catch {
      // ignore
    }
    return false;
  });

  const [useMock, setUseMock] = useState(() => api.getUseMock());
  const [isReady, setIsReady] = useState(false);

  // Modals state
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isNodeModalOpen, setIsNodeModalOpen] = useState(false);
  const [isEmergencyModalOpen, setIsEmergencyModalOpen] = useState(false);

  const i18n = useI18n(lang);
  const t = i18n.t;

  useEffect(() => {
    try {
      localStorage.setItem('health-copilot-lang', lang);
    } catch {
      // ignore
    }
  }, [lang]);

  useEffect(() => {
    try {
      localStorage.setItem('health-copilot-profile', profileId);
    } catch {
      // ignore
    }
  }, [profileId]);

  useEffect(() => {
    try {
      localStorage.setItem('health-copilot-user', JSON.stringify(user));
    } catch {
      // ignore
    }
  }, [user]);

  useEffect(() => {
    api.setUseMock(useMock);
  }, [useMock]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await api.healthCheck();
      } catch {
        // ignore
      }
      setIsReady(true);
    };
    checkHealth();
  }, []);

  const logout = () => {
    setIsAuthenticated(false);
    try {
      localStorage.removeItem('health-copilot-auth');
    } catch {
      // ignore
    }
  };

  const contextValue: AppContextType = {
    lang,
    setLang,
    t,
    profileId,
    setProfileId,
    useMock,
    setUseMock,
    user,
    setUser,
    isAuthenticated,
    logout,
    openLoginModal: () => setIsLoginModalOpen(true),
    openNodeModal: () => setIsNodeModalOpen(true),
    openEmergencyModal: () => setIsEmergencyModalOpen(true),
  };

  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-white">
        <div className="text-center p-8">
          <div className="w-12 h-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-300 font-medium">Initializing AI Health Copilot…</p>
        </div>
      </div>
    );
  }

  // If user is not yet logged in with their Hospital Patient ID, present full-screen LoginScreen
  if (!isAuthenticated) {
    return (
      <AppContext.Provider value={contextValue}>
        <Suspense fallback={<p role="status">Loading demo…</p>}><LoginScreen
          lang={lang}
          setLang={setLang}
          onLogin={(loggedPatient) => {
            setUser(loggedPatient);
            setProfileId(loggedPatient.id === 'AIIMS-MRN-9912' ? 'patient-002' : 'demo-patient-001');
            setIsAuthenticated(true);
          }}
        /></Suspense>
      </AppContext.Provider>
    );
  }

  return (
    <AppContext.Provider value={contextValue}>
      <BrowserRouter>
        <div className="app-frame min-h-screen bg-surface-50 flex">
          {/* Desktop Left Sidebar (w-72) */}
          <Sidebar />

          {/* Main Content Area (Offset by sidebar width 330px on md+) */}
          <div className="app-workspace flex-1 flex flex-col min-w-0">
            <Header />
            <main className="workspace-main flex-1">
              <p role="note" className="workspace-notice text-amber-900 text-sm">Local demo — no secure sign-in or real hospital/ABHA connection. Use synthetic records only. {useMock ? 'Sample data mode — changes stay in this session.' : 'Backend connected mode — check extraction source before use.'}</p>
              <Suspense fallback={<p role="status" className="p-8">Loading page…</p>}><Routes>
                <Route path="/" element={<AppShell />}>
                  <Route index element={<Navigate to="/timeline" replace />} />
                  <Route path="upload" element={<Upload />} />
                  <Route path="verify/:id" element={<Verify />} />
                  <Route path="summary/:id" element={<Summary />} />
                  <Route path="timeline" element={<Timeline />} />
                  <Route path="medicines" element={<Medicines />} />
                  <Route path="trends" element={<Trends />} />
                  <Route path="alerts" element={<Alerts />} />
                  <Route path="abha" element={<Abha />} />
                  <Route path="emergency" element={<Emergency />} />
                  <Route path="emergency/:id" element={<Emergency />} />
                  <Route path="compare" element={<Compare />} />
                  <Route path="doctor-prep" element={<DoctorPrep />} />
                  <Route path="ask" element={<Ask />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="*" element={<Navigate to="/timeline" replace />} />
                </Route>
              </Routes></Suspense>
            </main>
            <BottomNav />
          </div>



          {/* Multimodal AI Copilot Floating Widget */}
          <AiCopilotWidget />

          {/* Interactive Pop-up Modals */}
          <LoginModal
            isOpen={isLoginModalOpen}
            onClose={() => setIsLoginModalOpen(false)}
            currentUser={user}
            onLogin={(updatedUser) => {
              setUser(updatedUser);
              setProfileId(updatedUser.id === 'AIIMS-MRN-9912' ? 'patient-002' : 'demo-patient-001');
            }}
          />

          <HospitalNodeModal
            isOpen={isNodeModalOpen}
            onClose={() => setIsNodeModalOpen(false)}
            user={user}
            useMock={useMock}
          />

          <EmergencySosModal
            isOpen={isEmergencyModalOpen}
            onClose={() => setIsEmergencyModalOpen(false)}
            profileId={profileId}
          />
        </div>
      </BrowserRouter>
    </AppContext.Provider>
  );
}
