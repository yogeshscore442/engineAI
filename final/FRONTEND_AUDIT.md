# AI Health Copilot — Frontend Audit (Naveen Component)

## 1. Executive Summary
- **Module Path**: `naveen/hi-main/hi-main/frontend`
- **Framework**: React 19, TypeScript, Vite 8, Tailwind CSS.
- **Audit Date**: 2026-10-20
- **Status**: Critical client-side mock interception and missing rejection modal dialog identified and remediated.

---

## 2. Component Architecture & Workflow
- `src/screens/Upload.tsx`: Drag-and-drop zone, camera snap, 1-click sample cards, progress indicator.
- `src/screens/Verify.tsx`: Medical record verification and confirmation screen.
- `src/api/index.ts`: HTTP client talking to FastAPI backend via Vite proxy `/api`.

---

## 3. Discovered Defects & Root Causes

| Defect ID | Severity | File & Location | Description & Root Cause |
| :--- | :--- | :--- | :--- |
| **FRONT-01** | **CRITICAL** | `src/api/index.ts:116-144` (`uploadRecord`) | When `useMock` is `true` (which is enabled when clicking any sample card), any subsequently uploaded real file was intercepted locally by `getMockRecord()` and returned a fake lab report without ever reaching the backend. |
| **FRONT-02** | **CRITICAL** | `src/screens/Upload.tsx:34-40` & `240-253` | When the backend rejects a document, there was NO visible popup modal dialog for "Invalid Medical Document". Only a generic inline error banner was shown. |
| **FRONT-03** | **HIGH** | `src/screens/Upload.tsx` | No distinct modal/notice for `NEEDS_REVIEW` documents ("We could not confidently verify this document. Please upload a clearer image or verify the extracted information."). |
| **FRONT-04** | **HIGH** | `src/screens/Upload.tsx` | When a user uploads a new file after an error, old clinical results or previous error states were not thoroughly cleared. |
| **FRONT-05** | **MEDIUM** | `src/api/index.ts:69` | `getApiBase()` had hardcoded fallback `http://localhost:8000/api` instead of relative `/api`, causing port collisions when backend runs on 8001. |

---

## 4. Remediation Plan
1. In `src/api/index.ts`:
   - Change `getApiBase()` to default to `'/api'` (which proxies to the backend port).
   - In `uploadRecord`: ALWAYS send real file uploads to the backend API (`/api/profiles/{profileId}/records`). Never let `useMock` substitute a synthetic record for a user's uploaded file.
2. In `src/screens/Upload.tsx`:
   - Implement an explicit Modal Dialog:
     - **Title**: "Invalid Medical Document"
     - **Message**: "The uploaded file does not appear to be a supported medical document. Please upload a valid laboratory report, prescription, or diagnostic report."
     - **Action**: "Choose Another File" button that resets file input and state.
   - Implement an explicit Review Required Modal/Notice for `NEEDS_REVIEW`.
   - Ensure clean state resets between uploads.
