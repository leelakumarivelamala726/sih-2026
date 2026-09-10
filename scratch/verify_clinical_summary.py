"""
Comprehensive Verification Script for Doctor Dashboard Clinical Summary Feature
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_verification():
    print("================================================================")
    print("--- 1. Testing Doctor Authentication & Session Setup ---")
    session = requests.Session()

    # Register and login as a clean dedicated test doctor
    doc_id = "DOC-SUMMARY-TEST"
    doc_pass = "ClinicalPass123!"

    reg_payload = {
        "doctor_name": "Dr. Summary Tester, MD (Ayush)",
        "doctor_id": doc_id,
        "password": doc_pass,
        "confirm_password": doc_pass
    }
    session.post(f"{BASE_URL}/doctor/register", data=reg_payload, allow_redirects=True)

    login_payload = {
        "doctor_id": doc_id,
        "password": doc_pass
    }
    r_login = session.post(f"{BASE_URL}/doctor/login", data=login_payload, allow_redirects=False)
    assert r_login.status_code == 302, f"Expected 302 redirect on login, got {r_login.status_code}"
    print("[OK] Doctor authenticated successfully.")

    # 2. Fetch queue
    print("\n--- 2. Fetching Patient Queue ---")
    r_queue = session.get(f"{BASE_URL}/api/doctor/queue")
    assert r_queue.status_code == 200, f"Queue API failed: {r_queue.status_code}"
    queue_data = r_queue.json().get("queue", [])
    assert len(queue_data) > 0, "No patients in queue for testing!"
    first_patient = queue_data[0]
    session_id = first_patient["session_id"]
    patient_id = first_patient["patient_id"]
    print(f"[OK] Found patient: {first_patient['patient_name']} (Session {session_id}, Patient {patient_id})")

    # 3. Test patient clinical bundle
    print("\n--- 3. Testing Patient Clinical Bundle with Clinical Summary ---")
    r_bundle = session.get(f"{BASE_URL}/api/doctor/patient/{session_id}")
    assert r_bundle.status_code == 200, f"Bundle API failed: {r_bundle.status_code}"
    bundle = r_bundle.json()
    assert "clinical_summary" in bundle, "clinical_summary missing from bundle response!"
    cs = bundle["clinical_summary"]
    assert cs["status"] == "success", f"Clinical summary status not success: {cs}"

    # Verify 24 required sections in structured_details
    details = cs["structured_details"]
    required_fields = [
        "patient_name", "age", "gender", "abha_id", "phone_number",
        "chief_complaints", "symptoms", "duration_of_symptoms", "present_illness_hpi",
        "past_medical_history", "past_surgical_history", "family_history", "personal_history",
        "current_medications", "allergies", "lifestyle_information", "sleep_pattern",
        "diet_appetite", "bowel_habits", "stress_mental_wellness", "previous_treatments"
    ]
    for field in required_fields:
        assert field in details, f"Field '{field}' missing from structured_details!"
        val = details[field]
        assert val is not None, f"Field '{field}' is None!"
        assert str(val).lower() not in ("none", "null", "undefined", ""), f"Field '{field}' has forbidden blank/null value: {val}"
    print(f"[OK] All {len(required_fields)} structured clinical fields verified with zero null/undefined values.")

    # 4. Verify AI Clinical Summary Narrative Format
    print("\n--- 4. Verifying AI Clinical Summary Narrative ---")
    narrative = cs["clinical_summary_text"]
    assert narrative.startswith("Patient presents with"), f"Narrative does not start as expected: {narrative[:50]}"
    assert "Relevant symptoms include" in narrative, "Missing 'Relevant symptoms include' in narrative"
    assert "Past history includes" in narrative, "Missing 'Past history includes' in narrative"
    assert "Current medications/allergies:" in narrative, "Missing 'Current medications/allergies:' in narrative"
    assert "Lifestyle and wellness indicators show" in narrative, "Missing 'Lifestyle and wellness indicators show' in narrative"
    assert "Laboratory/OCR findings indicate" in narrative, "Missing 'Laboratory/OCR findings indicate' in narrative"
    print(f"[OK] Narrative format strictly verified:\n     \"{narrative[:160]}...\"")

    # 5. Verify Key Clinical Findings
    print("\n--- 5. Verifying Key Clinical Findings Subsection ---")
    kf = cs["key_clinical_findings"]
    assert "chief_complaint" in kf, "chief_complaint missing in key_findings"
    assert "important_symptoms" in kf, "important_symptoms missing in key_findings"
    assert "abnormal_lab_values" in kf, "abnormal_lab_values missing in key_findings"
    assert "risk_indicators" in kf, "risk_indicators missing in key_findings"
    assert "relevant_medical_history" in kf, "relevant_medical_history missing in key_findings"
    assert "ai_detected_concerns" in kf, "ai_detected_concerns missing in key_findings"
    print("[OK] Key Clinical Findings subsection verified with all 6 required clinical labels.")

    # 6. Verify Chronological Timeline (Latest First)
    print("\n--- 6. Verifying Chronological Timeline ---")
    timeline = cs["timeline"]
    assert isinstance(timeline, list), "timeline is not a list"
    if len(timeline) > 1:
        # Check latest first
        sids = [t["session_id"] for t in timeline if t.get("session_id")]
        assert sids == sorted(sids, reverse=True), f"Timeline is not sorted latest first: {sids}"
    print(f"[OK] Timeline verified ({len(timeline)} case(s) on file, sorted latest first).")

    # 7. Test Dedicated Endpoints
    print("\n--- 7. Testing Dedicated Backend Endpoints ---")
    r_pt = session.get(f"{BASE_URL}/api/doctor/patient/{patient_id}/clinical-summary")
    assert r_pt.status_code == 200, f"GET /api/doctor/patient/<id>/clinical-summary failed: {r_pt.status_code}"
    pt_data = r_pt.json()
    assert pt_data["status"] == "success", "Patient clinical summary endpoint status not success"

    r_sess = session.get(f"{BASE_URL}/api/doctor/session/{session_id}/clinical-summary")
    assert r_sess.status_code == 200, f"GET /api/doctor/session/<id>/clinical-summary failed: {r_sess.status_code}"
    sess_data = r_sess.json()
    assert sess_data["status"] == "success", "Session clinical summary endpoint status not success"
    print("[OK] Both dedicated clinical-summary endpoints (/patient/<id> and /session/<id>) return HTTP 200.")

    # 8. Verify UI Template & Script
    print("\n--- 8. Verifying UI Template & Frontend Actions ---")
    r_dash = session.get(f"{BASE_URL}/doctor")
    assert r_dash.status_code == 200, f"Doctor Dashboard GET failed: {r_dash.status_code}"
    assert "1. Clinical Summary" in r_dash.text, "Tab label '1. Clinical Summary' missing in dashboard HTML"
    assert "actionViewSummaryBtn" in r_dash.text, "actionViewSummaryBtn missing"
    assert "actionViewCaseBtn" in r_dash.text, "actionViewCaseBtn missing"
    assert "actionViewLabsBtn" in r_dash.text, "actionViewLabsBtn missing"
    assert "actionPrintSummaryBtn" in r_dash.text, "actionPrintSummaryBtn missing"
    print("[OK] UI template verified: '1. Clinical Summary' tab and all 4 quick action buttons present.")

    print("\n================================================================")
    print("ALL DOCTOR CLINICAL SUMMARY TESTS PASSED WITH ZERO DEFECTS! [SUCCESS]")
    print("================================================================")

if __name__ == "__main__":
    run_verification()
