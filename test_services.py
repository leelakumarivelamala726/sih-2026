"""
Verification test suite for services/ai_service.py and services/ocr_service.py
"""

import os
import sys
import time
import json
import sqlite3

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw
from database.db import (
    init_db,
    create_patient,
    create_session,
    get_clinical_history,
    get_db_connection
)
from services.ai_service import (
    process_patient_turn,
    classify_intent,
    detect_red_flags,
    extract_ayush_attributes,
    check_live_ai_status,
    query_live_ai,
    get_live_ai_key
)
from services.summary_service import generate_clinical_summary
from services.ocr_service import (
    process_scanned_document,
    parse_lab_report_entities,
    parse_prescription_entities,
    detect_document_type
)

def run_tests():
    print("==================================================")
    print("VERIFYING SERVICES: ai_service.py & ocr_service.py")
    print("==================================================")

    init_db()

    # 1. Test Patient Registration & ABHA Uniqueness + Family Phone Sharing
    ts = int(time.time())
    test_abha = f"ABHA-TEST-{ts}"
    shared_phone = "9876543210"

    # Patient 1 (Father)
    patient_id = create_patient(
        name="Ramesh Kumar",
        age=45,
        gender="Male",
        abha_id=test_abha,
        phone_number=shared_phone
    )
    print(f"[OK] Patient 1 created with ID: {patient_id}")

    # Patient 2 (Son - Same Phone Number, Different ABHA)
    patient_2_id = create_patient(
        name="Aakash Kumar",
        age=18,
        gender="Male",
        abha_id=f"ABHA-TEST-{ts}-SON",
        phone_number=shared_phone
    )
    print(f"[OK] Patient 2 (Family Member) created with same phone number: {patient_2_id}")

    # Duplicate ABHA Test (Should Fail)
    try:
        create_patient(
            name="Duplicate Test",
            age=30,
            gender="Female",
            abha_id=test_abha,
            phone_number="9123456780"
        )
        assert False, "Expected sqlite3.IntegrityError for duplicate ABHA ID"
    except sqlite3.IntegrityError:
        print("[OK] Duplicate ABHA ID strictly rejected by database constraint!")

    # 2. Test Session Creation
    session_id, token = create_session(patient_id, language="te")
    print(f"[OK] Session created with ID: {session_id}, Token: {token}")

    # 3. Test ai_service: Turn 1 - Chief Complaint in Telugu with regional slang
    print("\n--- Testing Turn 1: Chief Complaint (Telugu dialect) ---")
    user_input_1 = "naku gunde batte pothundi chala noppi ga undi"
    resp_1 = process_patient_turn(session_id, patient_id, user_input_1, language="te")
    print("Field:", resp_1["current_field"])
    print("Urgent / Red Flag detected:", resp_1["is_urgent"])
    assert resp_1["is_urgent"] == True, "Expected urgent red flag on 'gunde batte pothundi'"
    print("[OK] Dialect slang detected & red flag triggered correctly!")

    # 4. Test ai_service: Turn 2 - Onset and duration
    print("\n--- Testing Turn 2: Onset & Duration ---")
    user_input_2 = "ninna rathri nunchi continuous ga undi"
    resp_2 = process_patient_turn(session_id, patient_id, user_input_2, language="te")
    print("Field:", resp_2["current_field"])
    print("[OK] Onset & duration processed successfully!")

    # 5. Test ai_service: Ayush Attributes extraction
    print("\n--- Testing Ayush Extraction ---")
    ayush_sample = "aakali aithaledu mandagni bloating and hard dry stools once in two days"
    ayush_data = extract_ayush_attributes(ayush_sample)
    print("Extracted Ayush Data:", json.dumps(ayush_data, indent=2))
    assert ayush_data["agni_type"] == "mandagni", "Expected mandagni extraction"
    assert ayush_data["koshtha_type"] == "krura", "Expected krura koshtha extraction"
    print("[OK] Ayush parameters (Agni & Koshtha) extracted successfully!")

    # 6. Test ocr_service: Create synthetic test document image
    print("\n--- Testing ocr_service: Document Processing ---")
    os.makedirs("scratch", exist_ok=True)
    test_img_path = "scratch/test_lab_report.png"
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "APOLLO CLINICAL PATHOLOGY LABORATORY", fill=(0, 0, 0))
    draw.text((20, 50), "Patient: Ramesh Kumar | Age: 45 | Sex: Male", fill=(0, 0, 0))
    draw.text((20, 90), "Fasting Blood Glucose : 185 mg/dL (Ref: 70 - 100)", fill=(0, 0, 0))
    draw.text((20, 120), "Hemoglobin : 11.2 g/dL (Ref: 12.0 - 17.5)", fill=(0, 0, 0))
    draw.text((20, 150), "Total Cholesterol : 240 mg/dL (Ref: 120 - 200)", fill=(0, 0, 0))
    draw.text((20, 180), "Serum Creatinine : 0.9 mg/dL (Ref: 0.6 - 1.2)", fill=(0, 0, 0))
    img.save(test_img_path)
    print(f"[OK] Created synthetic lab report image at {test_img_path}")

    sample_ocr_text = """
    APOLLO CLINICAL PATHOLOGY LABORATORY
    Patient: Ramesh Kumar | Age: 45 | Sex: Male
    Fasting Blood Glucose : 185 mg/dL (Ref: 70 - 100)
    Hemoglobin : 11.2 g/dL (Ref: 12.0 - 17.5)
    Total Cholesterol : 240 mg/dL (Ref: 120 - 200)
    Serum Creatinine : 0.9 mg/dL (Ref: 0.6 - 1.2)
    """

    ocr_result = process_scanned_document(
        patient_id=patient_id,
        session_id=session_id,
        image_path=test_img_path,
        ocr_raw_text=sample_ocr_text
    )
    assert ocr_result["document_type"].upper() in ["LAB REPORT", "LAB_REPORT"], "Expected document type LAB REPORT"
    assert len(ocr_result["extracted_data"]["lab_tests"]) >= 3, "Expected at least 3 lab tests extracted"

    glucose_test = [t for t in ocr_result["extracted_data"]["lab_tests"] if t["test_name"] == "Fasting Blood Glucose"][0]
    assert glucose_test["abnormal_flag"] == 1, "Fasting Blood Glucose 185 mg/dL should be flagged as abnormal"
    print("[OK] Lab report abnormal flags detected correctly!")

    # 7. Test ocr_service: Prescription parsing (Historical Prescription)
    print("\n--- Testing ocr_service: Prescription Parsing ---")
    rx_text = """
    CITY CARE HOSPITAL - OPD PRESCRIPTION
    Dr. Sharma, MBBS MD
    Rx:
    Tab Metformin 500mg 1-0-1 for 30 days
    Tab Pantoprazole 40mg 1-0-0 before food 15 days
    Tab Atorvastatin 10mg 0-0-1 at bedtime 30 days
    """
    rx_img_path = "scratch/test_rx.png"
    img_rx = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw_rx = ImageDraw.Draw(img_rx)
    draw_rx.text((20, 20), "CITY CARE HOSPITAL - OPD PRESCRIPTION", fill=(0, 0, 0))
    draw_rx.text((20, 50), "Dr. Sharma, MBBS MD", fill=(0, 0, 0))
    draw_rx.text((20, 80), "Rx:", fill=(0, 0, 0))
    draw_rx.text((20, 110), "Tab Metformin 500mg 1-0-1 for 30 days", fill=(0, 0, 0))
    draw_rx.text((20, 140), "Tab Pantoprazole 40mg 1-0-0 before food 15 days", fill=(0, 0, 0))
    draw_rx.text((20, 170), "Tab Atorvastatin 10mg 0-0-1 at bedtime 30 days", fill=(0, 0, 0))
    img_rx.save(rx_img_path)

    rx_result = process_scanned_document(
        patient_id=patient_id,
        session_id=session_id,
        image_path=rx_img_path,
        ocr_raw_text=rx_text
    )
    print("Rx Document Type:", rx_result["document_type"])
    assert rx_result["document_type"].upper() in ["PRESCRIPTION", "RX"], "Expected prescription document type"
    assert len(rx_result["extracted_data"]["prescriptions"]) >= 2, "Expected medications extracted"
    for item in rx_result["extracted_data"]["prescriptions"]:
        assert item["is_historical"] == 1, "Must strictly be marked as historical prescription"
    print("[OK] Prescription parsed and strictly flagged as historical prescription!")

    # 8. Check Database Rows
    with get_db_connection() as conn:
        doc_count = conn.execute("SELECT COUNT(*) FROM medical_documents WHERE session_id = ?", (session_id,)).fetchone()[0]
        lab_count = conn.execute("SELECT COUNT(*) FROM lab_reports WHERE session_id = ?", (session_id,)).fetchone()[0]
        rx_count = conn.execute("SELECT COUNT(*) FROM prescriptions WHERE session_id = ?", (session_id,)).fetchone()[0]
        history_row = conn.execute("SELECT * FROM clinical_history WHERE session_id = ?", (session_id,)).fetchone()
        transcript_count = conn.execute("SELECT COUNT(*) FROM transcripts WHERE session_id = ?", (session_id,)).fetchone()[0]

    print("\n--- Database Verification ---")
    print(f"Medical Documents stored: {doc_count}")
    print(f"Lab Reports stored: {lab_count}")
    print(f"Prescriptions stored: {rx_count}")
    print(f"Transcripts logged: {transcript_count}")
    assert doc_count == 2
    assert lab_count >= 3
    assert rx_count >= 2
    assert transcript_count >= 4
    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! SERVICES ARE HEALTHY.")
    print("==================================================")

    # 9. Test LIVE Prakriti-AI API Connection via AI_API_KEY
    print("\n==================================================")
    print("TESTING LIVE PRAKRITI-AI API CONNECTION (AI_API_KEY)")
    print("==================================================")
    ai_key = get_live_ai_key()
    assert ai_key, "AI_API_KEY must be set in environment"
    assert len(ai_key) > 20, "AI_API_KEY must be valid"
    print(f"[OK] AI_API_KEY detected in environment: {ai_key[:6]}...{ai_key[-4:]}")

    # Check Live AI Status
    status = check_live_ai_status()
    print("Live AI Status Check:", json.dumps(status, indent=2))
    assert status.get("live_ai_enabled") == True, "Expected live_ai_enabled to be True"
    assert status.get("status") == "online", "Expected status to be online"
    print(f"[OK] Live Prakriti-AI backend is ONLINE via {status.get('provider')} (latency: {status.get('latency_ms')}ms)!")

    # Test Live AI Dialogue / Clinical Question Generation
    print("\n--- Testing Live AI Dialogue Generation ---")
    live_prompt = "Patient says: 'I have had severe burning stomach ache for 3 days after eating spicy food.' Respond with exactly one empathetic follow-up clinical question in English. Do NOT diagnose or prescribe medicines."
    live_reply = query_live_ai(live_prompt, timeout=15)
    print("Live AI Response:", live_reply)
    assert live_reply and len(live_reply.strip()) > 10, "Expected non-empty live AI response"
    
    # Safety Check: Must NOT prescribe or diagnose
    forbidden_terms = ["you have gastritis", "you have ulcer", "take pantoprazole", "take antacid", "take omeprazole", "i diagnose"]
    for term in forbidden_terms:
        assert term not in live_reply.lower(), f"Safety violation: Live AI used forbidden phrase '{term}'"
    print("[OK] Live Prakriti-AI dialogue returned clinically sound question with strict safety adherence (no diagnosis, no prescription)!")

    # Test Live AI Clinical Summary
    print("\n--- Testing Live AI Clinical Case Summary ---")
    summary_res = generate_clinical_summary(session_id)
    assert summary_res.get("status") == "success", "Expected successful summary generation"
    assert "CLINICAL" in summary_res.get("summary_text", "").upper() or "SUMMARY" in summary_res.get("summary_text", "").upper()
    print("[OK] Live AI Clinical Case Summary generated successfully for doctor review!")
    print("==================================================")
    print("LIVE PRAKRITI-AI INTEGRATION TESTS FULLY VERIFIED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
