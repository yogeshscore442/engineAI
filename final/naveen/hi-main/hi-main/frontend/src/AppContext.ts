import { createContext, useContext } from 'react';
import { useI18n, type Language } from './i18n';
import { DEMO_USERS, type UserProfile } from './types/auth';

export type AppContextType = {
  lang: Language;
  setLang: (lang: Language) => void;
  t: ReturnType<typeof useI18n>['t'];
  profileId: string;
  setProfileId: (id: string) => void;
  useMock: boolean;
  setUseMock: (value: boolean) => void;
  user: UserProfile;
  setUser: (user: UserProfile) => void;
  isAuthenticated: boolean;
  logout: () => void;
  openLoginModal: () => void;
  openNodeModal: () => void;
  openEmergencyModal: () => void;
};

export const AppContext = createContext<AppContextType>({
  lang: 'en',
  setLang: () => {},
  t: (key: string) => key,
  profileId: 'demo-patient-001',
  setProfileId: () => {},
  useMock: true,
  setUseMock: () => {},
  user: DEMO_USERS[0],
  setUser: () => {},
  isAuthenticated: false,
  logout: () => {},
  openLoginModal: () => {},
  openNodeModal: () => {},
  openEmergencyModal: () => {},
});

export function useApp() {
  return useContext(AppContext);
}

