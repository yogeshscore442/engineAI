export type PatientProfile = {
  id: string; // Hospital Patient ID e.g. APL-PAT-2024-001
  name: string; // Rajesh Kumar
  age: number;
  gender: string;
  bloodGroup: string;
  hospitalName: string; // Apollo Speciality Hospitals, Greams Rd
  hospitalCode: string; // APL-CHE
  uhid: string; // Hospital UHID
  abhaId: string; // 91-2345-6789-0123
  primaryDoctor: string; // Dr. Arvind Swaminathan (Cardiology)
  primaryCondition: string; // Type 2 Diabetes & Hypertension
  emergencyContact: string; // +91 98401 23456
  lastSync: string;
  isLoggedIn: boolean;
};

// Aliased for components
export type UserProfile = PatientProfile;

export const DEMO_PATIENTS: PatientProfile[] = [
  {
    id: 'APL-PAT-2024-001',
    name: 'Rajesh Kumar',
    age: 52,
    gender: 'Male',
    bloodGroup: 'O+',
    hospitalName: 'Apollo Speciality Hospitals, Greams Rd',
    hospitalCode: 'APOLLO-CHE',
    uhid: 'UHID-APL-884920',
    abhaId: '91-2345-6789-0123',
    primaryDoctor: 'Dr. Arvind Swaminathan (Cardiology)',
    primaryCondition: 'Type 2 Diabetes & Mild Hypertension',
    emergencyContact: '+91 98401 23456 (Spouse)',
    lastSync: 'Today, 09:30 AM',
    isLoggedIn: true,
  },
  {
    id: 'AIIMS-MRN-9912',
    name: 'Ananya Sharma',
    age: 38,
    gender: 'Female',
    bloodGroup: 'B+',
    hospitalName: 'AIIMS Central Hospital, New Delhi',
    hospitalCode: 'AIIMS-DEL',
    uhid: 'UHID-AIIMS-551029',
    abhaId: '91-8841-2091-7712',
    primaryDoctor: 'Dr. Sanjeev Mehra (Endocrinology)',
    primaryCondition: 'Hypothyroidism & Vitamin D Deficiency',
    emergencyContact: '+91 98112 34567 (Father)',
    lastSync: 'Yesterday',
    isLoggedIn: true,
  },
  {
    id: 'FOR-UHID-3310',
    name: 'Karthik Swaminathan',
    age: 46,
    gender: 'Male',
    bloodGroup: 'A+',
    hospitalName: 'Fortis Malar Super Speciality Hospital',
    hospitalCode: 'FORTIS-CHE',
    uhid: 'UHID-FOR-102948',
    abhaId: '91-3049-8812-4421',
    primaryDoctor: 'Dr. Meenakshi Sundaram (Internal Med)',
    primaryCondition: 'Dyslipidemia & Fatty Liver Stage 1',
    emergencyContact: '+91 94440 12389 (Brother)',
    lastSync: '3 days ago',
    isLoggedIn: true,
  },
];

// For fallback references
export const DEMO_USERS = DEMO_PATIENTS;
