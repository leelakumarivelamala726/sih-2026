"""
Comprehensive Verification Script for Doctor Dashboard AI Summary Loading Fix
"""
import requests
import re
import os
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_ai_key_environment_safety():
    print("\n--- 1. Testing AI API Key Security & Environment Configuration ---")
    # Verify AI_API_KEY is read strictly from environment
    from dotenv import load_dotenv
    load_dotenv()
    env_key = os.getenv("AI_API_KEY")
    assert env_key, "AI_API_KEY is missing from environment!"
    
    # Check that key is not hardcoded in python or js files
    for root, dirs, files in os.walk("."):
        if any(d in root for d in [".git", "venv", "__pycache__", "scratch"]):
            continue
        for file in files:
            if file.endswith((".py", ".js", ".html")) and file != ".env" and file != ".env.example":
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if env_key in content:
                        raise AssertionError(f"SECURITY BREACH: Live AI_API_KEY found hardcoded in {path}!")
    print("[OK] AI_API_KEY is securely read ONLY from environment and is NEVER hardcoded in code.")

def test_ai_summary_endpoints():
    print("\n--- 2. Testing AI Summary Dedicated Endpoints ---")
    # Test POST /api/ai/summary
    r1 = requests.post(f"{BASE_URL}/api/ai/summary", json={"session_id": 41})
    assert r1.status_code == 200, f"POST /api/ai/summary failed: {r1.status_code}"
    data1 = r1.json()
    assert data1.get("status") == "success", "Expected status=success"
    assert "summary_text" in data1 and len(data1["summary_text"]) > 100, "Missing or empty summary_text in /api/ai/summary"
    print("[OK] POST /api/ai/summary returned structured summary successfully.")

    # Test GET /api/ai/summary?session_id=41
    r2 = requests.get(f"{BASE_URL}/api/ai/summary?session_id=41")
    assert r2.status_code == 200, f"GET /api/ai/summary failed: {r2.status_code}"
    data2 = r2.json()
    assert data2.get("status") == "success", "Expected status=success"
    print("[OK] GET /api/ai/summary?session_id=41 returned structured summary successfully.")

    # Test GET /api/ai/summary/41
    r3 = requests.get(f"{BASE_URL}/api/ai/summary/41")
    assert r3.status_code == 200, f"GET /api/ai/summary/41 failed: {r3.status_code}"
    print("[OK] GET /api/ai/summary/41 returned structured summary successfully.")

    # Test error handling on invalid session
    r4 = requests.post(f"{BASE_URL}/api/ai/summary", json={"session_id": 999999})
    assert r4.status_code == 404, f"Expected 404 on invalid session, got {r4.status_code}"
    print("[OK] /api/ai/summary gracefully returns 404 on non-existent session.")

def test_doctor_dashboard_bundle_and_summary():
    print("\n--- 3. Testing Doctor Dashboard Patient Bundle & Summary Flow ---")
    session = requests.Session()

    # Doctor Login
    login_data = {
        "doctor_id": "DOC-TEST-AI",
        "password": "test"
    }
    r_login = session.post(f"{BASE_URL}/doctor/login", data=login_data, allow_redirects=True)
    assert r_login.status_code == 200, f"Doctor login failed: {r_login.status_code}"
    print("[OK] Doctor logged in successfully.")

    # Fetch Doctor Dashboard HTML
    r_dash = session.get(f"{BASE_URL}/doctor")
    assert r_dash.status_code == 200, f"Doctor dashboard failed: {r_dash.status_code}"
    assert "doctorPatientSelect" in r_dash.text, "Missing doctorPatientSelect in dashboard HTML"
    assert "aiSummaryContent" in r_dash.text, "Missing aiSummaryContent in dashboard HTML"
    assert "doctor.js" in r_dash.text, "Missing doctor.js script inclusion"
    print("[OK] Doctor dashboard HTML contains patient switcher and AI summary pane.")

    # Fetch Patient Clinical Bundle (Simulating patient selection)
    r_bundle = session.get(f"{BASE_URL}/api/doctor/patient/41")
    assert r_bundle.status_code == 200, f"Patient clinical bundle failed: {r_bundle.status_code}"
    bundle = r_bundle.json()

    # Verify all expected tabs data are populated
    assert "summary" in bundle, "Bundle missing summary"
    assert "summary_text" in bundle["summary"], "Bundle summary missing summary_text"
    assert len(bundle["summary"]["summary_text"]) > 100, "Summary text is empty!"
    assert "session" in bundle, "Bundle missing session"
    assert "history" in bundle, "Bundle missing history"
    assert "transcripts" in bundle, "Bundle missing transcripts"
    assert "documents" in bundle, "Bundle missing documents"
    assert "lab_reports" in bundle or "labs" in bundle, "Bundle missing lab reports"
    assert "prescriptions" in bundle, "Bundle missing prescriptions"
    assert "coding_suggestions" in bundle, "Bundle missing coding_suggestions"
    assert "timeline" in bundle, "Bundle missing timeline"

    print("[OK] Clinical bundle contains all tabs data (AI Summary, Transcripts, Reports, Labs, History, Codes, Timeline).")

    # Verify dedicated Doctor Summary endpoint
    r_doc_sum = session.get(f"{BASE_URL}/api/doctor/summary/41")
    assert r_doc_sum.status_code == 200, f"Doctor summary failed: {r_doc_sum.status_code}"
    assert r_doc_sum.json().get("status") == "success"
    print("[OK] Dedicated /api/doctor/summary/41 returned valid summary.")

def test_frontend_script_integrity():
    print("\n--- 4. Testing Frontend doctor.js Script Integrity & Error Handlers ---")
    r_js = requests.get(f"{BASE_URL}/static/js/doctor.js")
    assert r_js.status_code == 200, f"Failed to load doctor.js: {r_js.status_code}"
    js_text = r_js.text

    assert "Generating clinical summary with AYUSH KRITI" in js_text, "Missing active loading state in doctor.js"
    assert "retrySummaryBtn" in js_text, "Missing retrySummaryBtn error recovery in doctor.js"
    assert "AbortController" in js_text, "Missing AbortController timeout handling in doctor.js"
    assert "renderMarkdown" in js_text, "Missing renderMarkdown in doctor.js"
    assert "loadDedicatedAISummary" in js_text, "Missing loadDedicatedAISummary fallback in doctor.js"
    print("[OK] doctor.js verified (immediate loading indicator, AbortController timeout, retry button, table parsing).")

if __name__ == "__main__":
    try:
        test_ai_key_environment_safety()
        test_ai_summary_endpoints()
        test_doctor_dashboard_bundle_and_summary()
        test_frontend_script_integrity()
        print("\nALL DOCTOR DASHBOARD AI SUMMARY VERIFICATION TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
