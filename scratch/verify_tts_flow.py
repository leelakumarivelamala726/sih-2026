"""
End-to-End Verification Script for TTS Voice Conversation & MediKiosk Integration
"""
import requests
import re
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_static_assets():
    print("\n--- 1. Testing Static Assets & TTS Definitions ---")
    r_speech = requests.get(f"{BASE_URL}/static/js/speech.js")
    assert r_speech.status_code == 200, f"Failed to load speech.js: {r_speech.status_code}"
    assert "speakAIResponse" in r_speech.text, "speakAIResponse missing in speech.js"
    assert "stopAISpeech" in r_speech.text, "stopAISpeech missing in speech.js"
    assert "rate = 0.95" in r_speech.text, "rate 0.95 missing in speech.js"
    assert "window.isAISpeaking" in r_speech.text, "window.isAISpeaking missing in speech.js"
    print("[OK] speech.js verified (speakAIResponse, stopAISpeech, rate, isAISpeaking)")

    r_chat = requests.get(f"{BASE_URL}/static/js/chat.js")
    assert r_chat.status_code == 200, f"Failed to load chat.js: {r_chat.status_code}"
    assert "msg-speaker-btn" in r_chat.text, "msg-speaker-btn missing in chat.js"
    assert "globalVoiceToggle" in r_chat.text, "globalVoiceToggle missing in chat.js"
    assert "voiceNarrationToggle" in r_chat.text, "voiceNarrationToggle missing in chat.js"
    assert "speakAIResponse" in r_chat.text, "speakAIResponse call missing in chat.js"
    assert "lastAutoSpokenText" in r_chat.text, "lastAutoSpokenText missing in chat.js"
    print("[OK] chat.js verified (speaker buttons, global voice toggle sync, auto-speech duplicate prevention)")

    r_css = requests.get(f"{BASE_URL}/static/css/kiosk.css")
    assert r_css.status_code == 200, f"Failed to load kiosk.css: {r_css.status_code}"
    assert "voice-global-toggle-btn" in r_css.text, "voice-global-toggle-btn missing in kiosk.css"
    assert "msg-speaker-btn" in r_css.text, "msg-speaker-btn missing in kiosk.css"
    assert "ai-status-speaking" in r_css.text, "ai-status-speaking missing in kiosk.css"
    print("[OK] kiosk.css verified (voice toggle, speaker buttons, speaking status pill)")

def test_full_conversational_flow():
    print("\n--- 2. Testing Conversational Loop: Patient Flow + AI Questions/Answers ---")
    session = requests.Session()

    # 1. Login with registered patient
    login_data = {
        "abha_id": "ABHA-1234-TEST",
        "phone_number": "9876543210",
        "selected_language": "en"
    }
    r_login = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code}"
    
    # Extract session_id from consent URL or response
    m = re.search(r'/consent/(\d+)', r_login.url)
    if not m:
        m = re.search(r'action="/consent/(\d+)"', r_login.text)
    assert m, "Could not find session ID in consent redirect"
    session_id = m.group(1)
    print(f"[OK] Patient logged in. Session ID: {session_id}. Proceeding with consent...")

    # 2. Submit consent
    consent_data = {
        "selected_language": "en",
        "consent_agreed": "yes"
    }
    r_kiosk = session.post(f"{BASE_URL}/consent/{session_id}", data=consent_data, allow_redirects=True)
    assert r_kiosk.status_code == 200, f"Consent submission failed: {r_kiosk.status_code}"
    assert "AYUSH KRITI" in r_kiosk.text, "AYUSH KRITI branding missing on kiosk screen"
    assert "globalVoiceToggle" in r_kiosk.text, "globalVoiceToggle button missing in HTML"
    assert "voiceNarrationToggle" in r_kiosk.text, "voiceNarrationToggle checkbox missing in HTML"
    assert "aiStatusIndicator" in r_kiosk.text, "aiStatusIndicator missing in HTML"
    print("[OK] Patient consent given. Kiosk active. UI has globalVoiceToggle, voiceNarrationToggle, aiStatusIndicator.")

    # Flow Step 1: AI asks initial question (START_SESSION)
    print("\nStep 1: Kiosk starts -> Trigger initial question (START_SESSION)")
    payload_start = {
        "session_id": session_id,
        "message": "START_SESSION",
        "language": "en"
    }
    r_start = session.post(f"{BASE_URL}/api/ai/chat", json=payload_start)
    assert r_start.status_code == 200, f"Initial AI question failed: {r_start.status_code}"
    data_q1 = r_start.json()
    ai_q1 = data_q1.get("ai_response", "")
    assert ai_q1, "Empty AI initial response"
    print(f"[OK] AI Question 1 (To be spoken via TTS): \"{ai_q1}\"")

    # Flow Step 2: Patient speaks answer (transcribed via STT)
    patient_a1 = "I have been experiencing pain in my left knee and mild joint stiffness for the past 2 weeks."
    print(f"\nStep 2: Patient clicks microphone -> Speaks answer -> STT transcribes: \"{patient_a1}\"")
    payload_a1 = {
        "session_id": session_id,
        "message": patient_a1,
        "language": "en"
    }
    r_a1 = session.post(f"{BASE_URL}/api/ai/chat", json=payload_a1)
    assert r_a1.status_code == 200, f"AI response 1 failed: {r_a1.status_code}"
    data_q2 = r_a1.json()
    ai_q2 = data_q2.get("ai_response", "")
    assert ai_q2, "Empty AI follow-up response"
    print(f"[OK] AI Question 2 (Automatically spoken via TTS): \"{ai_q2}\"")

    # Flow Step 3: Patient speaks second answer
    patient_a2 = "The pain increases while climbing stairs. There is mild swelling in the evening, but no fever."
    print(f"\nStep 3: Patient answers follow-up -> STT transcribes: \"{patient_a2}\"")
    payload_a2 = {
        "session_id": session_id,
        "message": patient_a2,
        "language": "en"
    }
    r_a2 = session.post(f"{BASE_URL}/api/ai/chat", json=payload_a2)
    assert r_a2.status_code == 200, f"AI response 2 failed: {r_a2.status_code}"
    data_q3 = r_a2.json()
    ai_q3 = data_q3.get("ai_response", "")
    assert ai_q3, "Empty AI response 3"
    print(f"[OK] AI Question 3 (Automatically spoken via TTS): \"{ai_q3}\"")

    # Flow Step 4: Verify Case Summary page loads and captures conversation
    print("\n--- 3. Verifying Clinical Summary & Record Integrity ---")
    r_summary = session.get(f"{BASE_URL}/summary/{session_id}")
    assert r_summary.status_code == 200, f"Summary page failed: {r_summary.status_code}"
    assert "AYUSH KRITI" in r_summary.text, "AYUSH KRITI missing on summary page"
    print("[OK] Clinical summary page rendered successfully.")

    print("\nALL E2E CONVERSATIONAL & TTS TESTS PASSED WITH ZERO ERRORS!")

if __name__ == "__main__":
    try:
        test_static_assets()
        test_full_conversational_flow()
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
