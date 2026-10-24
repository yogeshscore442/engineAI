import type { DocType, TimelineResponse, TrendsResponse, AlertsResponse, UploadResponse, ApiError, Record as RecordType, UploadProgress, ProductRecord, ProductMatchResult, AskResponse } from '../types';

export type { UploadProgress, ProductRecord, ProductMatchResult, AskResponse };

const MOCK_CONTRACT_BASE = '/contract';

let useMock = import.meta.env.VITE_USE_MOCK === 'true';

try {
  const stored = localStorage.getItem('health-copilot-use-mock');
  if (stored !== null) {
    useMock = stored === 'true';
  }
} catch {
  // localStorage not available
}

function persistMockMode() {
  try {
    localStorage.setItem('health-copilot-use-mock', String(useMock));
  } catch {
    // ignore
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadMockJson<T>(filename: string): Promise<T> {
  const res = await fetch(`${MOCK_CONTRACT_BASE}/${filename}`);
  if (!res.ok) {
    throw { error: { code: 'MOCK_LOAD_FAILED', message: `Failed to load ${filename}` } } as ApiError;
  }
  return res.json() as Promise<T>;
}

const mockRecordMap: Record<string, RecordType> = {};
const mockStatuses: Record<string, 'draft' | 'confirmed'> = {};

async function initDefaultMockRecords(): Promise<void> {
  if (Object.keys(mockRecordMap).length > 0) return;
  try {
    const [lab, rx, discharge] = await Promise.all([
      loadMockJson<RecordType>('mock_lab.json'),
      loadMockJson<RecordType>('mock_prescription.json'),
      loadMockJson<RecordType>('mock_discharge.json'),
    ]);
    if (lab) mockRecordMap[lab.record_id || 'mock-lab-001'] = { ...lab, record_id: lab.record_id || 'mock-lab-001' };
    if (rx) mockRecordMap[rx.record_id || 'mock-rx-001'] = { ...rx, record_id: rx.record_id || 'mock-rx-001' };
    if (discharge) mockRecordMap[discharge.record_id || 'mock-discharge-001'] = { ...discharge, record_id: discharge.record_id || 'mock-discharge-001' };
  } catch (err) {
    console.warn('Failed to load initial mock records:', err);
  }
}

async function getMockRecord(docType: DocType): Promise<RecordType> {
  const filename = `mock_${docType}.json`.replace('lab_report', 'lab').replace('discharge_summary', 'discharge');
  const record = await loadMockJson<RecordType>(filename);
  mockRecordMap[record.record_id] = record;
  return record;
}

function getApiBase(): string {
  return import.meta.env.VITE_API_URL || '/api';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${getApiBase()}${path}`;
  const res = await fetch(url, {
    signal: AbortSignal.timeout(30000),
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
  });

  if (!res.ok) {
    let message = 'Request failed';
    try {
      const err = (await res.json()) as ApiError;
      message = err.error?.message || message;
    } catch {
      message = `HTTP ${res.status}: ${res.statusText}`;
    }
    throw { error: { code: `HTTP_${res.status}`, message } } as ApiError;
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  async loadSample(kind: 'lab' | 'prescription' | 'discharge'): Promise<RecordType> {
    return getMockRecord(kind === 'lab' ? 'lab_report' : kind === 'discharge' ? 'discharge_summary' : 'prescription');
  },
  setUseMock(value: boolean) {
    useMock = value;
    persistMockMode();
  },

  getUseMock(): boolean {
    return useMock;
  },

  async uploadRecord(file: File, onProgress?: (progress: UploadProgress) => void, profileId: string = 'default'): Promise<UploadResponse> {
    useMock = false;
    persistMockMode();
    onProgress?.({ step: 'reading', message: 'Reading document file…' });
    await delay(100);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('lang', 'en');

      onProgress?.({ step: 'extracting', message: 'Validating and analyzing with Clinical AI…' });

      const res = await fetch(`${getApiBase()}/profiles/${profileId}/records`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!res.ok) {
        let message = 'Upload failed';
        let code = `HTTP_${res.status}`;
        let status = 'ERROR';
        let reasonCodes: string[] = [];

        try {
          const body = await res.json();
          const errDetail = body.detail?.error || body.error || body.detail || body;
          message = errDetail.message || message;
          code = errDetail.code || code;
          status = errDetail.status || (res.status === 422 ? 'REJECTED' : 'ERROR');
          reasonCodes = errDetail.reason_codes || [];
        } catch {
          message = `HTTP ${res.status}: ${res.statusText}`;
        }

        const rejectionErr = new Error(message) as any;
        rejectionErr.error = {
          code,
          message,
          status,
          reason_codes: reasonCodes,
        };
        rejectionErr.code = code;
        rejectionErr.status = status;
        rejectionErr.reason_codes = reasonCodes;
        rejectionErr.httpStatus = res.status;
        throw rejectionErr;
      }

      onProgress?.({ step: 'checking', message: 'Verifying clinical findings…' });

      const jsonResp = (await res.json()) as any;
      const inner = (jsonResp.record && (jsonResp.record.record || jsonResp.record.record_json)) || jsonResp.record || jsonResp;
      const normalizedRecord: RecordType = {
        record_id: inner.record_id || jsonResp.record_id || '',
        doc_type: inner.doc_type || 'lab_report',
        doc_date: inner.doc_date || null,
        language: inner.language || 'en',
        patient_name_present: Boolean(inner.patient_name_present),
        medicines: Array.isArray(inner.medicines) ? inner.medicines : [],
        tests: Array.isArray(inner.tests) ? inner.tests : [],
        diagnoses: Array.isArray(inner.diagnoses) ? inner.diagnoses : [],
        summary_en: inner.summary_en || null,
        summary_ta: inner.summary_ta || null,
        needs_review: Array.isArray(inner.needs_review) ? inner.needs_review : [],
        disclaimer: inner.disclaimer || '',
        error: inner.error || null,
      };

      onProgress?.({ step: 'complete', message: 'Ready for clinical review!' });

      return {
        record_id: jsonResp.record_id || inner.record_id,
        status: jsonResp.status || 'draft',
        record: normalizedRecord,
      };
    } catch (err: any) {
      if (err && err.error) {
        throw err;
      }
      throw {
        error: {
          code: 'UPLOAD_FAILED',
          message: err instanceof Error ? err.message : 'Upload failed. Please retry.',
          status: 'ERROR',
        },
      } as ApiError;
    }
  },

  async getRecord(id: string): Promise<{ record_id: string; status: 'draft' | 'confirmed'; record: RecordType }> {
    if (useMock) {
      await initDefaultMockRecords();
      if (mockRecordMap[id]) {
        return { record_id: id, status: mockStatuses[id] || 'draft', record: mockRecordMap[id] };
      }
      // If requested record is not in sample map, seamlessly query live backend
    }

    const data = await request<any>(`/records/${id}`);
    const inner = (data && (data.record || data.record_json)) || data || {};
    const normalizedRecord: RecordType = {
      record_id: inner.record_id || data?.record_id || id,
      doc_type: inner.doc_type || data?.doc_type || 'lab_report',
      doc_date: inner.doc_date || data?.doc_date || null,
      language: inner.language || data?.language || 'en',
      patient_name_present: Boolean(inner.patient_name_present),
      medicines: Array.isArray(inner.medicines) ? inner.medicines : (Array.isArray(data?.medicines) ? data.medicines : []),
      tests: Array.isArray(inner.tests) ? inner.tests : (Array.isArray(data?.tests) ? data.tests : []),
      diagnoses: Array.isArray(inner.diagnoses) ? inner.diagnoses : [],
      summary_en: inner.summary_en || null,
      summary_ta: inner.summary_ta || null,
      needs_review: Array.isArray(inner.needs_review) ? inner.needs_review : (Array.isArray(data?.needs_review) ? data.needs_review : []),
      disclaimer: inner.disclaimer || data?.disclaimer || '',
      error: inner.error || null,
    };

    return {
      record_id: data.record_id || id,
      status: data.status || 'draft',
      record: normalizedRecord,
    };
  },

  async getRecordFile(id: string): Promise<Blob> {
    if (useMock && (id.startsWith('mock-') || mockRecordMap[id])) {
      return new Blob(['Sample document preview unavailable'], { type: 'text/plain' });
    }
    const res = await fetch(`${getApiBase()}/records/${id}/file`, { credentials: 'include' });
    if (!res.ok) throw new Error(`Document unavailable (HTTP ${res.status})`);
    return res.blob();
  },

  async confirmRecord(id: string, record: RecordType): Promise<{ record_id: string; status: 'confirmed'; record: RecordType }> {
    if (useMock && (id.startsWith('mock-') || mockRecordMap[id])) {
      mockRecordMap[id] = record;
      mockStatuses[id] = 'confirmed';
      return { record_id: id, status: 'confirmed', record };
    }
    return request(`/records/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ record }),
    });
  },

  async streamSummary(
    recordId: string,
    lang: string = 'en',
    onChunk: (chunk: string) => void,
    onDone?: (fullText: string) => void,
    onError?: (err: any) => void
  ): Promise<() => void> {
    const controller = new AbortController();
    let accumulated = '';
    (async () => {
      try {
        const url = `${getApiBase()}/records/${encodeURIComponent(recordId)}/summary/stream?lang=${encodeURIComponent(lang)}`;
        const res = await fetch(url, {
          signal: controller.signal,
          credentials: 'include',
        });
        if (!res.ok) {
          throw new Error(`Stream failed (HTTP ${res.status})`);
        }
        const reader = res.body?.getReader();
        if (!reader) {
          throw new Error('Streaming response body unavailable');
        }
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunkStr = decoder.decode(value, { stream: true });
          const lines = chunkStr.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataPayload = line.slice(6);
              if (dataPayload === '[DONE]') {
                onDone?.(accumulated);
                return;
              }
              accumulated += dataPayload;
              onChunk(accumulated);
            }
          }
        }
        onDone?.(accumulated);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          onError?.(err);
        }
      }
    })();
    return () => controller.abort();
  },

  async getTimeline(profileId: string = 'default'): Promise<TimelineResponse> {
    if (useMock) {
      await initDefaultMockRecords();
      const allRecords = Object.values(mockRecordMap);
      const items = allRecords.map((r) => ({
        record_id: r.record_id,
        doc_type: r.doc_type,
        doc_date: r.doc_date || new Date().toISOString().split('T')[0],
        status: mockStatuses[r.record_id] || 'draft' as const,
        headline: r.tests && r.tests.length > 0 ? `${r.tests.length} Lab Test(s)` : `${r.medicines?.length || 0} Medicine(s)`,
        medicines: r.medicines || [],
        tests: r.tests || [],
      }));
      return { items: items.sort((a, b) => b.doc_date.localeCompare(a.doc_date)) };
    }
    return request(`/profiles/${profileId}/timeline`);
  },

  async getTrends(profileId: string = 'default', test: string = 'HbA1c'): Promise<TrendsResponse> {
    if (useMock) {
      await initDefaultMockRecords();
      const points = Object.values(mockRecordMap).flatMap(record =>
        (record.tests || []).filter(item => item.name.toLowerCase() === test.toLowerCase() && item.value !== null && record.doc_date)
          .map(item => ({ date: record.doc_date!, value: item.value!, flag: item.flag, record_id: record.record_id, unit: item.unit }))
      ).sort((a, b) => a.date.localeCompare(b.date));
      return { test, unit: points[0]?.unit || '', points };

    }
    return request(`/profiles/${profileId}/trends?test=${encodeURIComponent(test)}`);
  },

  async getAlerts(profileId: string = 'default'): Promise<AlertsResponse> {
    if (useMock) {
      return {
        alerts: [
          {
            type: 'duplicate_generic',
            generic: 'Metformin',
            medicines: [
              { name_raw: 'Glucophage 500mg', generic: 'Metformin', strength: '500 mg', schedule_raw: '1-0-1', schedule_parsed: ['morning', 'night'], food_instruction: 'after_food', duration_days: 30, confidence: 0.94, bbox: [0.1, 0.25, 0.4, 0.05] },
              { name_raw: 'Obimet SR 500', generic: 'Metformin', strength: '500 mg', schedule_raw: '0-0-1', schedule_parsed: ['night'], food_instruction: 'after_food', duration_days: 30, confidence: 0.91, bbox: [0.1, 0.35, 0.4, 0.05] },
            ],
            record_ids: ['rec-001', 'rec-002'],
            message: "The same active ingredient 'metformin' appears under different brand names (Glucophage, Obimet SR). This may indicate duplicate medication. Please confirm with your doctor or pharmacist.",
          },
        ],
      };
    }
    return request(`/profiles/${profileId}/alerts`);
  },

  async linkAbha(profileId: string = 'default', abhaId: string): Promise<{ mock: true; status: 'linked'; abha_id: string }> {
    if (useMock) {
      await delay(500);
      return { mock: true, status: 'linked', abha_id: abhaId };
    }
    return request(`/profiles/${profileId}/abha/link`, { method: 'POST', body: JSON.stringify({ abha_id: abhaId }) });
  },

  async importAbha(profileId: string = 'default'): Promise<{ mock: true; imported_record_ids: string[] }> {
    if (useMock) {
      await delay(800);
      return { mock: true, imported_record_ids: ['mock-imported-rec-1', 'mock-imported-rec-2'] };
    }
    return request(`/profiles/${profileId}/abha/import`, { method: 'POST' });
  },

  async deleteProfile(profileId: string = 'default'): Promise<{ deleted: true }> {
    if (useMock) {
      await delay(300);
      Object.keys(mockRecordMap).forEach((k) => delete mockRecordMap[k]);
      return { deleted: true };
    }
    return request(`/profiles/${profileId}`, { method: 'DELETE' });
  },

  async askRecords(profileId: string = 'default', question: string): Promise<AskResponse> {
    if (useMock) {
      await delay(800);
      return {
        answer: `Based on your verified medical records, your latest HbA1c is 6.8% (down from 9.2%), showing good glycemic control. You are currently prescribed Metformin 500mg (1-0-1 after food). Always verify specific medication changes with your physician.`,
        intent_category: 'MEDICAL_INFORMATION',
        medical_explanation: 'HbA1c reflects average blood sugar levels over the past 2-3 months. 6.8% indicates well-controlled diabetes management.',
        medical_references: [
          {
            title: 'American Diabetes Association: Standards of Care (Glycemic Targets)',
            source: 'American Diabetes Association (ADA)',
            url: 'https://diabetes.org',
            reference_type: 'CLINICAL_GUIDELINE',
            description: 'Standard clinical thresholds for HbA1c targets in adults with type 2 diabetes.'
          }
        ],
        product_recommendations: [],
        product_alternatives: [],
        safety_notes: [
          'Do not adjust medication dosage without consulting your prescribing physician or certified endocrinologist.'
        ],
        needs_clinician_review: false,
        sources: [
          { record_id: 'demo-patient-001', field: 'tests[HbA1c]' },
          { record_id: 'demo-patient-001', field: 'medicines[Metformin]' }
        ],
        disclaimer: 'This information is for clinical and educational reference only and should not replace professional medical advice.',
        lang: 'en'
      };
    }
    return request(`/profiles/${profileId}/ask`, { method: 'POST', body: JSON.stringify({ question }) });
  },

  async getFhirBundle(recordId: string): Promise<any> {
    if (useMock) {
      await delay(300);
      return {
        resourceType: 'Bundle',
        type: 'collection',
        id: `bundle-${recordId}`,
        timestamp: new Date().toISOString(),
        entry: [
          {
            resource: {
              resourceType: 'Patient',
              id: 'demo-patient',
              active: true,
            }
          },
          {
            resource: {
              resourceType: 'Observation',
              status: 'final',
              code: { coding: [{ system: 'http://loinc.org', code: '4548-4', display: 'HbA1c' }] },
              valueQuantity: { value: 6.8, unit: '%' }
            }
          }
        ]
      };
    }
    return request(`/records/${recordId}/fhir`);
  },

  async matchProduct(params: {
    name: string;
    generic?: string | null;
    strength?: string | null;
    dosage_form?: string | null;
    ocr_confidence?: number;
    user_confirmed?: boolean;
  }): Promise<ProductMatchResult> {
    const q = new URLSearchParams();
    q.set('name', params.name);
    if (params.generic) q.set('generic', params.generic);
    if (params.strength) q.set('strength', params.strength);
    if (params.dosage_form) q.set('dosage_form', params.dosage_form);
    if (params.ocr_confidence != null) q.set('ocr_confidence', String(params.ocr_confidence));
    if (params.user_confirmed != null) q.set('user_confirmed', String(params.user_confirmed));
    return request(`/catalog/products/match?${q.toString()}`);
  },

  async getProductById(productId: string): Promise<ProductRecord> {
    return request(`/catalog/products/${encodeURIComponent(productId)}`);
  },

  async listCatalogProducts(category?: string): Promise<ProductRecord[]> {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return request(`/catalog/products${q}`);
  },

  async validateUrl(url: string): Promise<{ url: string; is_safe: boolean; error?: string }> {
    return request('/catalog/validate-url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  },

  async healthCheck(): Promise<{ status: 'ok' }> {
    if (useMock) return { status: 'ok' };
    return request('/health');
  },
};

export default api;