"""
E2E Multilingual Voice & Consultation Flow Verification
Tests Telugu, English, Hindi, and Dynamic Mid-Consultation Language Switching
"""
import requests
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"

def test_static_assets():
    print("\n--- 1. Verifying Static Assets & Multilingual TTS Definitions ---")
    r_speech = requests.get(f"{BASE_URL}/static/js/speech.js")
    assert r_speech.status_code == 200, f"Failed to load speech.js: {r_speech.status_code}"
    assert "findBestVoiceForLanguage" in r_speech.text, "findBestVoiceForLanguage missing in speech.js"
    assert "resolveBcp47" in r_speech.text, "resolveBcp47 missing in speech.js"
    assert "te-IN" in r_speech.text, "te-IN missing in speech.js"
    assert "REGIONAL_VOICE_KEYWORDS" in r_speech.text, "REGIONAL_VOICE_KEYWORDS missing in speech.js"
    assert "setSessionLanguage" in r_speech.text, "setSessionLanguage missing in speech.js"
    print("[OK] speech.js verified (findBestVoiceForLanguage, resolveBcp47, te-IN, keywords, setSessionLanguage)")

    r_chat = requests.get(f"{BASE_URL}/static/js/chat.js")
    assert r_chat.status_code == 200, f"Failed to load chat.js: {r_chat.status_code}"
    assert "sessionLanguageSelect" in r_chat.text, "sessionLanguageSelect missing in chat.js"
    assert "change-language" in r_chat.text, "change-language API call missing in chat.js"
    assert "setSessionLanguage" in r_chat.text, "setSessionLanguage call missing in chat.js"
    print("[OK] chat.js verified (sessionLanguageSelect listener, change-language API, speechEngine sync)")

    r_css = requests.get(f"{BASE_URL}/static/css/kiosk.css")
    assert r_css.status_code == 200, f"Failed to load kiosk.css: {r_css.status_code}"
    assert "meta-language-select" in r_css.text, "meta-language-select styles missing in kiosk.css"
    print("[OK] kiosk.css verified (.meta-language-select styles)")

def test_telugu_consultation_flow():
    print("\n--- 2. Verifying Telugu Patient Case-Taking & TTS Voice Flow ---")
    session = requests.Session()

    # Login with Telugu language
    login_data = {
        "abha_id": "ABHA-1234-TEST",
        "phone_number": "9876543210",
        "selected_language": "te"
    }
    r_login = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"

    m = re.search(r'/consent/(\d+)', r_login.url)
    if not m:
        m = re.search(r'action="/consent/(\d+)"', r_login.text)
    assert m, "Could not find session ID in consent redirect"
    session_id = m.group(1)
    print(f"[OK] Patient logged in with Telugu. Session ID: {session_id}")

    # Submit consent with Telugu
    consent_data = {
        "selected_language": "te",
        "consent_agreed": "yes"
    }
    r_kiosk = session.post(f"{BASE_URL}/consent/{session_id}", data=consent_data, allow_redirects=True)
    assert r_kiosk.status_code == 200, f"Consent failed: {r_kiosk.status_code}"
    assert 'id="sessionLanguageSelect"' in r_kiosk.text, "sessionLanguageSelect missing in kiosk HTML"
    assert 'data-bcp47="te-IN"' in r_kiosk.text, "Telugu BCP-47 tag missing on chatInterface"
    print("[OK] Kiosk active in Telugu mode with sessionLanguageSelect and data-bcp47='te-IN'.")

    # Step 1: AI initial question in Telugu
    payload_q1 = {
        "session_id": session_id,
        "message": "START_SESSION",
        "language": "te"
    }
    r_q1 = session.post(f"{BASE_URL}/api/ai/chat", json=payload_q1)
    assert r_q1.status_code == 200, f"AI Q1 failed: {r_q1.status_code}"
    data_q1 = r_q1.json()
    ai_q1 = data_q1.get("ai_response", "")
    assert ai_q1, "Empty AI initial response"
    assert ("నమస్కారం" in ai_q1 or "సమస్య" in ai_q1), f"AI response must be in Telugu, got: {ai_q1}"
    print(f"[OK] Telugu AI Question 1: \"{ai_q1}\"")

    # Step 2: Patient speaks Telugu answer into microphone (transcribed by STT)
    patient_a1 = "నాకు గత రెండు వారాలుగా ఎడమ మోకాలిలో విపరీతమైన నొప్పి మరియు వాపు ఉంది."
    print(f"[OK] Patient mic answer (STT te-IN): \"{patient_a1}\"")
    payload_a1 = {
        "session_id": session_id,
        "message": patient_a1,
        "language": "te"
    }
    r_a1 = session.post(f"{BASE_URL}/api/ai/chat", json=payload_a1)
    assert r_a1.status_code == 200, f"AI Q2 failed: {r_a1.status_code}"
    data_q2 = r_a1.json()
    ai_q2 = data_q2.get("ai_response", "")
    assert ai_q2, "Empty AI Q2 response"
    print(f"[OK] Telugu AI Question 2 (To be spoken via te-IN TTS): \"{ai_q2}\"")

    # Step 3: Dynamic Language Switch Mid-Consultation (Telugu -> English)
    print("\n--- 3. Testing Dynamic Language Switch Mid-Consultation (Telugu -> English) ---")
    r_change_en = session.post(f"{BASE_URL}/api/patient/change-language/{session_id}", json={"language": "en"})
    assert r_change_en.status_code == 200, f"Language change failed: {r_change_en.status_code}"
    data_change = r_change_en.json()
    assert data_change["language"] == "en"
    assert data_change["bcp47"] == "en-IN"
    print("[OK] Backend session successfully switched to English ('en-IN').")

    patient_a2_en = "The pain increases when climbing stairs, but there is no fever."
    payload_a2_en = {
        "session_id": session_id,
        "message": patient_a2_en,
        "language": "en"
    }
    r_a2_en = session.post(f"{BASE_URL}/api/ai/chat", json=payload_a2_en)
    assert r_a2_en.status_code == 200, f"AI Q3 failed: {r_a2_en.status_code}"
    data_q3 = r_a2_en.json()
    ai_q3 = data_q3.get("ai_response", "")
    assert any(w in ai_q3.lower() for w in ["what", "does", "feel", "when", "symptom", "pain", "make"]), f"Expected English question, got: {ai_q3}"
    print(f"[OK] English AI Question 3 (To be spoken via en-IN TTS): \"{ai_q3}\"")

    # Step 4: Switch Back to Telugu Mid-Consultation
    print("\n--- 4. Testing Switch Back to Telugu (English -> Telugu) ---")
    r_change_te = session.post(f"{BASE_URL}/api/patient/change-language/{session_id}", json={"language": "te"})
    assert r_change_te.status_code == 200
    assert r_change_te.json()["language"] == "te"
    print("[OK] Switched back to Telugu. Testing next turn in Telugu...")

    patient_a3_te = "విశ్రాంతి తీసుకున్నప్పుడు నొప్పి కొద్దిగా తగ్గుతుంది."
    payload_a3_te = {
        "session_id": session_id,
        "message": patient_a3_te,
        "language": "te"
    }
    r_a3_te = session.post(f"{BASE_URL}/api/ai/chat", json=payload_a3_te)
    assert r_a3_te.status_code == 200
    ai_q4 = r_a3_te.json().get("ai_response", "")
    assert ai_q4, "Empty AI response 4"
    print(f"[OK] Telugu AI Question 4: \"{ai_q4}\"")

def test_hindi_flow():
    print("\n--- 5. Verifying Hindi Patient Case-Taking Flow ---")
    session = requests.Session()
    login_data = {
        "abha_id": "ABHA-1234-TEST",
        "phone_number": "9876543210",
        "selected_language": "hi"
    }
    r_login = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
    m = re.search(r'/consent/(\d+)', r_login.url)
    if not m:
        m = re.search(r'action="/consent/(\d+)"', r_login.text)
    session_id = m.group(1)

    consent_data = { "selected_language": "hi", "consent_agreed": "yes" }
    session.post(f"{BASE_URL}/consent/{session_id}", data=consent_data, allow_redirects=True)

    payload_start = { "session_id": session_id, "message": "START_SESSION", "language": "hi" }
    r_start = session.post(f"{BASE_URL}/api/ai/chat", json=payload_start)
    assert r_start.status_code == 200
    ai_hi = r_start.json().get("ai_response", "")
    assert "स्वास्थ्य" in ai_hi or "समस्या" in ai_hi or "लक्षण" in ai_hi, f"Expected Hindi question, got: {ai_hi}"
    print(f"[OK] Hindi AI Question 1 (To be spoken via hi-IN TTS): \"{ai_hi}\"")

if __name__ == "__main__":
    try:
        test_static_assets()
        test_telugu_consultation_flow()
        test_hindi_flow()
        print("\nALL MULTILINGUAL E2E CONVERSATION & TTS FLOW TESTS PASSED! 🌟")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
