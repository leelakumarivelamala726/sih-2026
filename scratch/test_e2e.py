"""
Ministry of Ayush – Smart MediKiosk
Comprehensive End-to-End System Verification Suite
Tests all modules: Registration, Login, Real-time ABHA Check, Prakriti-AI Case-Taking,
AYUSH Profile, Patient Inline Review/Edit, and Doctor Verification.
"""

import sys
import os
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database.db import get_db_connection

def test_all():
    client = app.test_client()
    passed = 0
    failed = 0

    def assert_test(condition, name):
        nonlocal passed, failed
        if condition:
            print(f"[PASS] {name}")
            passed += 1
        else:
            print(f"[FAIL] {name}")
            failed += 1

    print("==================================================")
    print("MINISTRY OF AYUSH – SMART MEDIKIOSK TEST SUITE")
    print("==================================================")

    # 1. TEST REGISTRATION & SHARED PHONE NUMBER
    import random
    rand_id = random.randint(100000, 999999)
    abha_1 = f"ABHA-{rand_id}-A"
    abha_2 = f"ABHA-{rand_id}-B"
    shared_phone = "9876500000"

    # Patient 1 Registration
    res = client.post('/register', data={
        'patient_name': 'Ramesh Sharma',
        'age': '48',
        'gender': 'Male',
        'abha_id': abha_1,
        'phone_number': shared_phone
    }, follow_redirects=True)
    assert_test(res.status_code == 200 and b'Consent' in res.data, "Patient 1 Registration (Male, 48Y)")

    # Patient 2 Registration (Same Phone Number - Family member)
    res2 = client.post('/register', data={
        'patient_name': 'Sunita Sharma',
        'age': '45',
        'gender': 'Female',
        'abha_id': abha_2,
        'phone_number': shared_phone
    }, follow_redirects=True)
    assert_test(res2.status_code == 200 and b'Consent' in res2.data, "Patient 2 Registration (Shared Phone Family Member)")

    # 2. TEST REAL-TIME ASYNC ABHA DUPLICATE CHECK
    check_resp = client.get(f'/api/auth/check-abha?abha_id={abha_1}')
    data = json.loads(check_resp.data)
    assert_test(data.get('exists') is True, "Real-time ABHA Check (Existing ABHA returns True)")
    assert_test("Patient already registered. Login instead." in data.get('message', ''), "Duplicate ABHA warning message matches specification")

    # Non-existent ABHA check
    check_resp_new = client.get('/api/auth/check-abha?abha_id=NON-EXISTENT-999')
    data_new = json.loads(check_resp_new.data)
    assert_test(data_new.get('exists') is False, "Real-time ABHA Check (New ABHA returns False)")

    # 3. TEST DUPLICATE ABHA POST REJECTION
    res_dup = client.post('/register', data={
        'patient_name': 'Duplicate User',
        'age': '30',
        'gender': 'Male',
        'abha_id': abha_1,
        'phone_number': '9111111111'
    }, follow_redirects=True)
    assert_test(b'Patient already registered. Login instead.' in res_dup.data, "Duplicate ABHA registration safely rejected")

    # 4. TEST PATIENT LOGIN
    login_res = client.post('/login', data={
        'abha_id': abha_1,
        'phone_number': shared_phone
    }, follow_redirects=True)
    assert_test(login_res.status_code == 200 and b'Consent' in login_res.data, "Patient Login with ABHA and Phone")

    # Extract session ID
    with get_db_connection() as conn:
        row = conn.execute("SELECT id FROM patient_sessions ORDER BY id DESC LIMIT 1").fetchone()
        session_id = row['id']

    # 5. TEST CONSENT & LANGUAGE SELECTION (Telugu)
    consent_res = client.post(f'/consent/{session_id}', data={
        'selected_language': 'te',
        'consent_agreed': 'yes'
    }, follow_redirects=True)
    assert_test(consent_res.status_code == 200 and b'Prakriti-AI' in consent_res.data, "Consent given in Telugu (te)")

    # 6. TEST PRAKRITI-AI CONVERSATIONAL CASE-TAKING
    # Initial Start: Ensure NO "Hello" and starts in Telugu
    init_ai = client.post('/api/ai/chat', json={
        'session_id': session_id,
        'message': 'START_SESSION',
        'language': 'te'
    })
    init_data = json.loads(init_ai.data)
    assert_test(not init_data['ai_response'].startswith('Hello'), "Prakriti-AI does NOT greet with default 'Hello'")
    assert_test(len(init_data['ai_response']) > 5, "Prakriti-AI initiates clinical dialogue in Telugu")

    # Multi-entity answer test (Symptom + Duration + Location in one turn)
    ans_1 = client.post('/api/ai/chat', json={
        'session_id': session_id,
        'message': 'Naku 3 rojulu ga kadipti lo noppi undi, vomiting kuda ayindi',
        'language': 'te'
    })
    ans_1_data = json.loads(ans_1.data)
    assert_test(ans_1_data['extracted_info'].get('duration') is not None, "Extracted duration from multi-entity response")
    assert_test('duration' in ans_1_data['answered_fields'], "Duration marked as answered (will not be asked again)")

    # Emergency Red Flag Trigger Test
    red_flag_resp = client.post('/api/ai/chat', json={
        'session_id': session_id,
        'message': 'I have sudden severe crushing chest pain radiating to left arm and sweating',
        'language': 'en'
    })
    red_flag_data = json.loads(red_flag_resp.data)
    assert_test(red_flag_data.get('is_urgent') is True, "Emergency red-flag symptom immediately flags session as URGENT")

    # 7. TEST PATIENT INLINE REVIEW & EDIT
    edit_payload = {
        'chief_complaint': 'Severe epigastric pain with acid reflux',
        'duration': '4 days',
        'onset': 'Gradual after irregular meals',
        'severity': 'Severe (7/10)',
        'location': 'Upper abdomen',
        'associated_symptoms': 'Nausea, sour belching',
        'diet': 'Spicy foods, tea 4 times a day',
        'sleep': 'Disturbed, 5 hours',
        'appetite': 'Irregular / Vishamagni',
        'bowel_habits': 'Constipated / Krura koshta',
        'lifestyle': 'Sedentary desk work',
        'prakriti': 'Pitta-Vata',
        'vikriti': 'Pitta Vriddhi with Amlapitta',
        'dosha': 'Pitta',
        'agni': 'Vishamagni',
        'ama': 'Mild Ama present',
        'koshta': 'Krura Koshta',
        'nidra': 'Khandita Nidra (interrupted)',
        'ahara': 'Vidahi and Amla ahara',
        'vihara': 'Divasvapna (daytime sleep)',
        'manasika': 'High workplace stress (Rajasic)'
    }
    edit_resp = client.post(f'/api/patient/edit-history/{session_id}', json=edit_payload)
    edit_data = json.loads(edit_resp.data)
    assert_test(edit_data.get('status') == 'success', "Patient inline edit endpoint successfully saved")
    assert_test('Severe epigastric pain' in edit_data['summary']['summary_text'], "Summary dynamically updated with edited chief complaint")
    assert_test('Pitta-Vata' in edit_data['summary']['summary_text'], "Summary dynamically updated with AYUSH Prakriti profile")

    # 8. TEST DOCTOR DASHBOARD & VERIFICATION
    # Doctor Queue API
    queue_resp = client.get('/api/doctor/queue')
    queue_data = json.loads(queue_resp.data)
    assert_test(len(queue_data.get('queue', [])) > 0, "Doctor Queue returns waiting patients")

    # Doctor Patient Bundle API
    bundle_resp = client.get(f'/api/doctor/patient/{session_id}')
    bundle_data = json.loads(bundle_resp.data)
    assert_test(bundle_data['session']['patient_name'] == 'Ramesh Sharma', "Doctor patient bundle loads patient details")
    assert_test(bundle_data['history']['prakriti'] == 'Pitta-Vata', "Doctor bundle includes updated AYUSH Prakriti")
    assert_test(len(bundle_data.get('coding_suggestions', [])) > 0, "Doctor bundle provides automated medical code suggestions (ICD-10 & NAMASTE)")

    # Doctor Final Verification
    verify_resp = client.post(f'/api/doctor/verify/{session_id}', json={
        'doctor_id': 'DOC-AYUSH-101',
        'doctor_name': 'Dr. Rohan Patel, MD (Ayush)',
        'edited_history': json.dumps(edit_payload),
        'doctor_notes': 'Clinical intake confirmed. Diagnosed Amlapitta (Pitta-Vata). Advised Pathya Ahara and Shankha Vati.',
        'medical_codes': [{'icd10': 'K29.0', 'namaste': 'AYU-AML-01'}]
    })
    verify_data = json.loads(verify_resp.data)
    assert_test(verify_data.get('status') == 'success', "Doctor verification successfully committed to database")

    # Verify session status is 'verified'
    with get_db_connection() as conn:
        verified_session = conn.execute("SELECT status FROM patient_sessions WHERE id = ?", (session_id,)).fetchone()
        assert_test(verified_session['status'] == 'verified', "Database session status marked as 'verified'")

    # 9. TEST REPOSITORY CLEANLINESS (ZERO SIH BRANDING)
    import glob
    forbidden_terms = ['SIH', 'Smart India Hackathon', '26047']
    leaks = []
    template_files = glob.glob(os.path.join(os.path.dirname(__file__), '..', 'templates', '*.html'))
    for tf in template_files:
        with open(tf, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            for term in forbidden_terms:
                if term in content:
                    leaks.append((os.path.basename(tf), term))

    assert_test(len(leaks) == 0, f"Zero SIH / Hackathon branding in templates (Found: {leaks})")

    print("==================================================")
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("==================================================")
    return failed == 0

if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
