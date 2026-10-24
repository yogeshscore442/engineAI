export type DocType = 'prescription' | 'lab_report' | 'discharge_summary';

export type Language = 'en' | 'ta' | 'mixed';

export type Flag = 'LOW' | 'NORMAL' | 'HIGH' | 'UNKNOWN';

export type FoodInstruction = 'before_food' | 'after_food' | null;

export type ScheduleParsed = 'morning' | 'afternoon' | 'night';

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Medicine {
  name?: string;
  name_raw: string;
  generic: string | null;
  brand?: string | null;
  strength: string | null;
  schedule_raw: string | null;
  schedule_parsed: ScheduleParsed[];
  food_instruction: FoodInstruction;
  duration_days: number;
  confidence: number;
  bbox: number[] | null;
  formulation?: string;
  route?: string;
  review_candidates?: string[];
  jan_aushadhi_url?: string | null;
  pmbjp_price_inr?: number | null;
  verification_state?: string;
  source_text?: string;
  user_confirmed?: boolean;
  provenance?: {
    source_text?: string;
    method?: string;
  };
}

export interface Test {
  name: string;
  loinc: string | null;
  value: number;
  unit: string;
  ref_low: number;
  ref_high: number;
  flag: Flag;
  explanation_en: string | null;
  explanation_ta: string | null;
  confidence: number;
  bbox: number[] | null;
}

export interface Diagnosis {
  text: string;
  confidence: number;
}

export interface Record {
  record_id: string;
  doc_type: DocType;
  doc_date: string | null;
  language: Language;
  patient_name_present: boolean;
  medicines: Medicine[];
  tests: Test[];
  diagnoses: Diagnosis[];
  summary_en: string | null;
  summary_ta: string | null;
  short_summary?: string | null;
  detailed_summary?: string | null;
  needs_review: string[];
  ocr_text?: string | null;
  raw_text?: string | null;
  disclaimer: string;
  error: { code: string; message: string } | null;
  document_type?: string;
  confidence?: number;
  status?: string;
  warnings?: string[];
  field_provenance?: any;
  quality_assessment?: any;
  patient_name?: string | null;
  reason_codes?: string[];
}

export interface TimelineItem {
  record_id: string;
  doc_type: DocType;
  doc_date: string;
  status: 'draft' | 'confirmed';
  headline: string;
  medicines: Medicine[];
  tests: Test[];
}

export interface TimelineResponse {
  items: TimelineItem[];
}

export interface TrendPoint {
  date: string;
  value: number;
  flag: Flag;
  record_id: string;
}

export interface TrendsResponse {
  test: string;
  unit: string;
  points: TrendPoint[];
}

export interface Alert {
  type: 'duplicate_generic';
  generic: string;
  medicines: Medicine[];
  record_ids: string[];
  message: string;
}

export interface AlertsResponse {
  alerts: Alert[];
}

export interface UploadResponse {
  record_id: string;
  status: 'draft' | 'ACCEPTED' | 'NEEDS_REVIEW' | 'REJECTED';
  record: Record;
  message?: string;
  reason_codes?: string[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}

export type UploadProgressStep = 'reading' | 'extracting' | 'checking' | 'complete';

export interface UploadProgress {
  step: UploadProgressStep;
  message: string;
}

export interface DosageSuggestions {
  how_much?: string;
  when?: string;
  when_to_take?: string;
  food?: string;
  duration?: string;
  precautions?: string;
  tamil_instructions?: string;
}

export interface ProductRecord {
  product_id: string;
  product_name: string;
  brand_name?: string | null;
  active_ingredient: string;
  strength: string;
  dosage_form: string;
  route: string;
  manufacturer: string;
  pack_size?: string | null;
  category: 'medicine' | 'medical_device' | 'healthcare_equipment' | 'supplement';
  is_prescription_only: boolean;
  device_specifications?: { [key: string]: any } | null;
  product_image_url?: string | null;
  image_provenance?: {
    source: string;
    rights: string;
    retrieval_date: string;
    alt_text: string;
  } | null;
  purchase_url?: string | null;
  merchant_name?: string | null;
  dosage_suggestions?: DosageSuggestions | null;
  verification_status: string;
  country_region: string;
  license_info: string;
  last_checked: string;
}

export interface ProductMatchResult {
  match_state:
    | 'EXACT_MATCH_VERIFIED'
    | 'POSSIBLE_MATCH_NEEDS_REVIEW'
    | 'MULTIPLE_MATCHES'
    | 'NO_RELIABLE_MATCH'
    | 'SOURCE_UNAVAILABLE'
    | 'PRODUCT_INFORMATION_STALE';
  search_query: {
    name_raw: string;
    generic?: string | null;
    strength?: string | null;
    dosage_form?: string | null;
    ocr_confidence?: number;
    user_confirmed?: boolean;
  };
  product?: ProductRecord | null;
  candidate_products: ProductRecord[];
  image_display_allowed: boolean;
  purchase_link_allowed: boolean;
  image_disclaimer: string;
  general_disclaimer: string;
  prescription_warning?: string | null;
  reasons: string[];
}

export interface MedicalReference {
  title: string;
  source: string;
  url: string;
  description?: string | null;
  reference_type: string;
}

export interface ProductCard {
  product_id: string;
  product_name: string;
  category: string;
  price_inr?: number | null;
  price_display?: string | null;
  retailer: string;
  purchase_url?: string | null;
  image_url?: string | null;
  is_prescription_only: boolean;
  specifications?: { [key: string]: any } | null;
  comparison_notes?: string | null;
  availability_status: string;
  rating?: number | null;
}

export interface AskResponse {
  answer: string;
  intent_category:
    | 'MEDICAL_INFORMATION'
    | 'MEDICINE_QUERY'
    | 'PRODUCT_SHOPPING'
    | 'PRODUCT_ALTERNATIVES'
    | 'MEDICINE_SUBSTITUTION_REQUEST'
    | 'GENERAL_CONVERSATIONAL';
  medical_explanation?: string | null;
  medical_references: MedicalReference[];
  product_recommendations: ProductCard[];
  product_alternatives: ProductCard[];
  safety_notes: string[];
  needs_clinician_review: boolean;
  sources: Array<{ record_id: string; doc_type?: string; doc_date?: string | null; field?: string }>;
  disclaimer: string;
  lang: string;
}