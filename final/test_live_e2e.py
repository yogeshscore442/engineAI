import requests
import io
import sys

def run_tests():
    print("==================================================================")
    print("LIVE INTEGRATION TEST: FRONTEND (PROXY) -> BACKEND -> AI ENGINE")
    print("==================================================================")

    # 1. Non-medical image: Cat / Selfie dummy
    cat_bytes = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
        b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
        b'\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37\x29\x2c\x30\x31\x34'
        b'\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34\x32\xff\xc0\x00\x0b\x08'
        b'\x00\n\x00\n\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
    )
    
    print("\n--- Test 1: Upload Non-Medical Image Directly to Backend (Port 8001) ---")
    r1 = requests.post(
        'http://127.0.0.1:8001/api/profiles/default/records',
        files={'file': ('cat_selfie.jpg', io.BytesIO(cat_bytes), 'image/jpeg')}
    )
    print("Status Code:", r1.status_code)
    print("Response JSON:", r1.json())
    assert r1.status_code == 422, f"Expected 422, got {r1.status_code}"
    err1 = r1.json().get('detail', {}).get('error', {}) or r1.json().get('error', {})
    assert err1.get('code') == 'NON_MEDICAL_DOCUMENT', f"Expected NON_MEDICAL_DOCUMENT, got {err1.get('code')}"
    assert err1.get('status') == 'REJECTED'
    print("[PASS] Direct backend properly returned HTTP 422 REJECTED with NON_MEDICAL_DOCUMENT")

    print("\n--- Test 2: Upload Non-Medical Image Through Frontend Vite Proxy (Port 5173) ---")
    r2 = requests.post(
        'http://127.0.0.1:5173/api/profiles/default/records',
        files={'file': ('cat_selfie.jpg', io.BytesIO(cat_bytes), 'image/jpeg')}
    )
    print("Status Code:", r2.status_code)
    print("Response JSON:", r2.json())
    assert r2.status_code == 422, f"Expected 422, got {r2.status_code}"
    err2 = r2.json().get('detail', {}).get('error', {}) or r2.json().get('error', {})
    assert err2.get('code') == 'NON_MEDICAL_DOCUMENT'
    print("[PASS] Vite proxy properly passed through HTTP 422 REJECTED")

    print("\n--- Test 3: Upload Valid Medical Document (lab1.jpg) to Backend ---")
    sample_lab_path = r'c:\Users\YOGESH\Downloads\ai-health-copilot-main\ai-health-copilot-main\final\yogesh\healthcare_copilot_AI-Engine-main\samples\lab1.jpg'
    with open(sample_lab_path, 'rb') as f:
        r3 = requests.post(
            'http://127.0.0.1:8001/api/profiles/default/records',
            files={'file': ('lab1.jpg', f, 'image/jpeg')}
        )
    print("Status Code:", r3.status_code)
    resp3 = r3.json()
    print("Record ID:", resp3.get('record_id'))
    print("Status:", resp3.get('status'))
    inner3 = resp3.get('record', {}).get('record_json', {}) or resp3.get('record', {})
    tests_count = len(inner3.get('tests', []))
    print(f"Extracted Tests Count: {tests_count}")
    assert r3.status_code == 201, f"Expected 201, got {r3.status_code}"
    assert resp3.get('record_id') is not None
    assert tests_count > 0
    print("[PASS] Valid medical document accepted with extracted test results")

    print("\n--- Test 4: Upload Valid Prescription (prescription1.jpg) via Vite Proxy ---")
    sample_rx_path = r'c:\Users\YOGESH\Downloads\ai-health-copilot-main\ai-health-copilot-main\final\yogesh\healthcare_copilot_AI-Engine-main\samples\prescription1.jpg'
    with open(sample_rx_path, 'rb') as f:
        r4 = requests.post(
            'http://127.0.0.1:5173/api/profiles/default/records',
            files={'file': ('prescription1.jpg', f, 'image/jpeg')}
        )
    print("Status Code:", r4.status_code)
    resp4 = r4.json()
    print("Record ID:", resp4.get('record_id'))
    print("Status:", resp4.get('status'))
    inner4 = resp4.get('record', {}).get('record_json', {}) or resp4.get('record', {})
    meds_count = len(inner4.get('medicines', []))
    print(f"Extracted Medicines Count: {meds_count}")
    assert r4.status_code == 201, f"Expected 201, got {r4.status_code}"
    assert resp4.get('record_id') is not None
    assert meds_count > 0
    print("[PASS] Valid prescription document accepted via frontend proxy with extracted medicines")

    print("\n==================================================================")
    print("ALL LIVE INTEGRATION TESTS PASSED (100% SPEC COMPLIANCE)!")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
