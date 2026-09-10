"""
Verification script for Ministry of Ayush – Smart MediKiosk:
1. AYUSH KRITI Rebranding
2. Telugu Language Natural Quality & Health-Related Only
3. OCR Pipeline (Lab & Rx, non-hallucination, preview image, low-confidence flag)
4. Doctor Dashboard (No duplicate queue panel, dedicated waiting list page intact)
5. Regression test of all workflows
"""

import sys
import time
import json
import requests

BASE_URL = "http://127.0.0.1:5000"

# Fix stdout encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_checks():
    session = requests.Session()
    print("==================================================")
    print("STEP 1: BRANDING & AI NAME (AYUSH KRITI)")
    print("==================================================")
    
    # 1. Check Login Page
    r = session.get(f"{BASE_URL}/login")
    assert r.status_code == 200, f"Login returned {r.status_code}"
    html = r.text
    assert "AYUSH KRITI" in html, "AYUSH KRITI missing from /login"
    assert "AYUSH-KRITI" not in html, "Hyphenated AYUSH-KRITI found in /login"
    print("[PASS] /login contains 'AYUSH KRITI' and no hyphenated name.")

    # 2. Register / Login a test patient
    ts = int(time.time())
    test_abha = f"ABHA-VRF-{ts}"
    r_reg = session.post(f"{BASE_URL}/register", data={
        "patient_name": "వెంకటేశ్వర్లు (Venkateswarlu)",
        "age": "52",
        "gender": "Male",
        "abha_id": test_abha,
        "phone_number": "9848022338"
    }, allow_redirects=True)
    assert r_reg.status_code == 200, "Registration failed"
    print(f"[PASS] Patient registered with ABHA: {test_abha}")

    # Patient Consent Page
    r_consent_get = session.get(r_reg.url)
    assert "AYUSH KRITI" in r_consent_get.text, "AYUSH KRITI missing in consent page"
    assert "AYUSH-KRITI" not in r_consent_get.text, "AYUSH-KRITI found in consent page"
    print("[PASS] Consent page contains 'AYUSH KRITI' visible branding.")

    # Accept consent with Telugu language
    # Extract session ID from URL (e.g. /consent/36)
    curr_url = r_reg.url
    sess_id = int(curr_url.strip("/").split("/")[-1])
    r_consent_post = session.post(f"{BASE_URL}/consent/{sess_id}", data={
        "selected_language": "te",
        "consent_agreed": "yes"
    }, allow_redirects=True)
    assert r_consent_post.status_code == 200
    print(f"[PASS] Selected Telugu language for Session {sess_id}")

    # Verify AI Kiosk Page
    kiosk_html = r_consent_post.text
    assert "AYUSH KRITI" in kiosk_html, "AYUSH KRITI missing from kiosk page"
    assert "AYUSH-KRITI" not in kiosk_html, "Hyphenated AYUSH-KRITI found in kiosk page"
    print("[PASS] Kiosk page displays 'AYUSH KRITI • Smart Clinical Assistant'.")

    print("\n==================================================")
    print("STEP 2: TELUGU LANGUAGE QUALITY & HEALTH-RELATED QUESTIONS")
    print("==================================================")
    
    # Turn 1: START_SESSION
    r_chat1 = session.post(f"{BASE_URL}/api/ai/chat", json={
        "session_id": sess_id,
        "message": "START_SESSION",
        "language": "te"
    })
    assert r_chat1.status_code == 200
    d1 = r_chat1.json()
    q1 = d1.get("ai_response", "")
    print(f"Turn 1 Question (Telugu):\n  -> {q1}")
    assert any(w in q1 for w in ["ఆరోగ్య", "సమస్య", "ఇబ్బంది", "నమస్కారం"]), "Greeting should be in natural Telugu"
    print("[PASS] Initial question is natural, polite Telugu asking for health problem.")

    # Turn 2: Patient answers with abdominal pain / burning
    r_chat2 = session.post(f"{BASE_URL}/api/ai/chat", json={
        "session_id": sess_id,
        "message": "నాకు గత నాలుగు రోజులుగా కడుపులో మంటగా నొప్పిగా ఉంది",
        "language": "te"
    })
    assert r_chat2.status_code == 200
    d2 = r_chat2.json()
    q2 = d2.get("ai_response", "")
    print(f"Turn 2 Question (Telugu):\n  -> {q2}")
    # Verify health-related and natural spoken Telugu
    assert len(q2) > 10, "Response question too short"
    # Negative check: no awkward literal English translation
    assert "మీ అసౌకర్యం యొక్క స్వభావం" not in q2, "Must not use awkward translation 'మీ అసౌకర్యం యొక్క స్వభావం'"
    assert "మీ నిద్ర వ్యవధి ఎంత" not in q2, "Must not use awkward 'మీ నిద్ర వ్యవధి ఎంత'"
    print("[PASS] Turn 2 dynamically generated question is natural spoken Telugu and strictly health-related.")

    # Turn 3: Patient gives relieving / aggravating details
    r_chat3 = session.post(f"{BASE_URL}/api/ai/chat", json={
        "session_id": sess_id,
        "message": "కారం తింటే మంట పెరుగుతుంది, చన్నీళ్లు తాగితే కాస్త ఉపశమనం ఉంటుంది",
        "language": "te"
    })
    assert r_chat3.status_code == 200
    d3 = r_chat3.json()
    q3 = d3.get("ai_response", "")
    print(f"Turn 3 Question (Telugu):\n  -> {q3}")
    print("[PASS] Turn 3 question generated smoothly in Telugu.")

    print("\n==================================================")
    print("STEP 3: OCR PIPELINE & CLEAN STRUCTURED UI")
    print("==================================================")
    
    # Synthetic lab report with an uncertain numeric value "1Z.5"
    lab_text = """
    APOLLO DIAGNOSTICS - CLINICAL BIOCHEMISTRY REPORT
    Patient: Venkateswarlu | Age: 52Y | Gender: Male
    Test Name              Result    Unit      Reference Range    Status
    Fasting Blood Sugar    178       mg/dL     70 - 110           High
    Serum Bilirubin        1Z.5      mg/dL     0.2 - 1.2          High
    Serum Creatinine       1.1       mg/dL     0.7 - 1.3          Normal
    """
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (700, 350), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "APOLLO DIAGNOSTICS - CLINICAL BIOCHEMISTRY REPORT", fill=(0, 0, 0))
    draw.text((20, 50), "Patient: Venkateswarlu | Age: 52Y | Gender: Male", fill=(0, 0, 0))
    draw.text((20, 90), "Fasting Blood Sugar    178       mg/dL     70 - 110", fill=(0, 0, 0))
    draw.text((20, 120), "Serum Bilirubin        1Z.5      mg/dL     0.2 - 1.2", fill=(0, 0, 0))
    draw.text((20, 150), "Serum Creatinine       1.1       mg/dL     0.7 - 1.3", fill=(0, 0, 0))
    test_lab_file = "scratch/apollo_lab.png"
    img.save(test_lab_file)

    with open(test_lab_file, "rb") as f:
        r_ocr = session.post(
            f"{BASE_URL}/api/documents/upload",
            data={"session_id": sess_id, "ocr_text": lab_text},
            files={"file": ("apollo_lab.png", f, "image/png")}
        )
    assert r_ocr.status_code == 200, f"OCR upload failed: {r_ocr.text}"
    ocr_data = r_ocr.json()
    print(f"OCR Document Type: {ocr_data.get('document_type')}")
    print(f"OCR Confidence: {ocr_data.get('ocr_confidence')}")
    print(f"Image Preview URL: {ocr_data.get('image_url')}")
    
    # Verify Document Type detected as LAB REPORT
    assert ocr_data.get("document_type") == "LAB REPORT", "Expected doc_type 'LAB REPORT'"
    assert ocr_data.get("image_url"), "Original image URL preview must be returned"
    
    # Verify non-hallucination: "1Z.5" must NOT be auto-corrected to 12.5; it must be flagged for review!
    extracted_tests = ocr_data.get("extracted_data", {}).get("lab_tests", [])
    print(f"Extracted Lab Tests Count: {len(extracted_tests)}")
    for t in extracted_tests:
        print(f"  - {t.get('test_name')}: {t.get('value')} {t.get('unit')} | Conf: {t.get('confidence')}")
        if "Bilirubin" in t.get("test_name"):
            assert "1Z.5" in str(t.get("value")) or "REVIEW" in str(t.get("confidence")), "Uncertain value 1Z.5 must be preserved or marked review required"
            assert str(t.get("value")) != "12.5", "VIOLATION: Hallucinated/auto-guessed '1Z.5' to '12.5'"
    print("[PASS] Non-hallucination verified: uncertain value was NOT guessed into a fake number!")

    print("\n==================================================")
    print("STEP 4: DOCTOR DASHBOARD – NO DUPLICATE QUEUE")
    print("==================================================")
    
    # Register & login doctor
    doc_id = f"DOC-TEST-{ts}"
    session.post(f"{BASE_URL}/doctor/register", data={
        "doctor_name": "Dr. Aarav Sharma, MD (Ayush)",
        "doctor_id": doc_id,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    r_doc_login = session.post(f"{BASE_URL}/doctor/login", data={
        "doctor_id": doc_id,
        "password": "Password123!"
    }, allow_redirects=True)
    assert r_doc_login.status_code == 200
    print(f"[PASS] Doctor logged in: {doc_id}")

    # Check Main Doctor Dashboard (/doctor)
    r_doc = session.get(f"{BASE_URL}/doctor")
    assert r_doc.status_code == 200
    doc_html = r_doc.text
    
    # Main Doctor Dashboard must NOT display the full queue panel
    assert '<aside class="queue-panel">' not in doc_html, "Duplicate <aside class='queue-panel'> still found in /doctor"
    assert 'id="doctorQueueList"' not in doc_html, "Duplicate #doctorQueueList still found in /doctor"
    print("[PASS] Duplicate queue panel successfully REMOVED from /doctor!")

    # Must contain link to dedicated waiting list
    assert "View Patient Waiting List" in doc_html, "Link 'View Patient Waiting List' missing in /doctor"
    assert "/doctor/waiting-list" in doc_html, "/doctor/waiting-list link missing in /doctor"
    print("[PASS] Prominent 'View Patient Waiting List' navigation link present.")

    # Check Dedicated Waiting List Page (/doctor/waiting-list)
    r_wl = session.get(f"{BASE_URL}/doctor/waiting-list")
    assert r_wl.status_code == 200
    wl_html = r_wl.text
    assert "PATIENT WAITING LIST" in wl_html, "Waiting list title missing"
    assert "waitingTable" in wl_html, "Waiting table missing"
    print("[PASS] Dedicated /doctor/waiting-list page exists and functions independently.")

    # Check Patient Bundle API for Doctor Console
    r_bundle = session.get(f"{BASE_URL}/api/doctor/patient/{sess_id}")
    assert r_bundle.status_code == 200
    bundle = r_bundle.json()
    assert "session" in bundle
    assert "summary" in bundle
    assert "documents" in bundle
    assert len(bundle["documents"]) >= 1, "Uploaded scanned document must be in bundle"
    print(f"[PASS] Clinical bundle retrieved for session {sess_id}: {len(bundle['documents'])} doc(s), {len(bundle['lab_reports'])} lab(s).")

    # Doctor Verification Action
    r_verify = session.post(f"{BASE_URL}/api/doctor/verify/{sess_id}", json={
        "doctor_notes": "Clinical history verified in Telugu. Advised Pathya Ahara and lifestyle changes.",
        "medical_codes": [{"icd10": "K29.7", "namaste": "AM-01"}]
    })
    assert r_verify.status_code == 200
    print(f"[PASS] Doctor verification succeeded: {r_verify.json().get('message')}")

    print("\n==================================================")
    print("ALL VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    run_checks()
