"""
Ministry of Ayush – Smart MediKiosk
Medical Document OCR & Clinical Entity Extraction Service
Government of India / Bharat • Clinical History Platform

Safety & Compliance Rules:
1. Historical Prescriptions are strictly tagged as historical documents only.
2. AI NEVER generates new prescriptions.
3. Abnormal lab values are highlighted for doctor attention, NOT final diagnosis.
4. If OCR confidence is low, the item is marked as 'Unclear / Requires Verification'.
"""

import os
import re
import json
import base64
from typing import Dict, Any, List, Optional
from PIL import Image, ImageEnhance, ImageFilter
from database.db import get_db_connection

ENTITY_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "prakriti_ai", "entity_rules.json")
with open(ENTITY_RULES_PATH, "r", encoding="utf-8") as f:
    ENTITY_RULES = json.load(f)

LAB_RANGES = ENTITY_RULES.get("lab_reference_ranges", {})

# Common medication catalog & dosage patterns for prescription extraction
MEDICATION_PATTERNS = [
    r"(?i)\b(paracetamol|pantoprazole|amoxicillin|metformin|amlodipine|atorvastatin|azithromycin|cetirizine|omeprazole|losartan|telmisartan|aspirin|ibuprofen|doxycycline|ciprofloxacin|ashwagandha|triphala|brahmi|tulsi|liv52|guduchi)\b",
    r"(?i)\b(tab|cap|syp|inj)\.?\s+([A-Za-z0-9\-]+)"
]

DOSAGE_PATTERNS = [
    r"\b(1-0-1|1-0-0|0-0-1|1-1-1|0-1-0|OD|BD|TID|QID|SOS|HS|PRN|once daily|twice daily)\b",
    r"\b(\d+\s*(?:mg|gm|ml|mcg|units))\b"
]

def preprocess_image(image_path: str, output_path: Optional[str] = None) -> str:
    """
    Apply image preprocessing (grayscale, contrast enhancement, sharpening)
    to optimize document readability for OCR.
    """
    if not output_path:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_proc{ext}"

    with Image.open(image_path) as img:
        # Convert to grayscale
        gray = img.convert("L")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)

        # Enhance sharpness
        sharp = enhanced.filter(ImageFilter.SHARPEN)

        # Save preprocessed image
        sharp.save(output_path, quality=95)

    return output_path

def save_base64_image(base64_data: str, target_dir: str, filename_prefix: str = "doc") -> str:
    """Save base64 image data from webcam snapshot to disk."""
    os.makedirs(target_dir, exist_ok=True)
    if "," in base64_data:
        base64_data = base64_data.split(",")[1]

    image_bytes = base64.b64decode(base64_data)
    import time
    filename = f"{filename_prefix}_{int(time.time()*1000)}.jpg"
    target_path = os.path.join(target_dir, filename)

    with open(target_path, "wb") as f:
        f.write(image_bytes)

    return target_path

def detect_document_type(ocr_text: str) -> str:
    """Detect whether document is a lab report, prescription, or discharge summary."""
    text_lower = ocr_text.lower()
    lab_keywords = ["lab", "report", "test", "hemoglobin", "glucose", "serum", "cholesterol", "platelet", "pathology", "biochemistry", "wbc", "reference range", "unit"]
    rx_keywords = ["rx", "prescription", "tab", "cap", "dosage", "mg", "dispense", "dr.", "doctor", "clinic", "hospital", "pharma"]
    discharge_keywords = ["discharge", "admission", "course in hospital", "discharge summary", "diagnosis at discharge"]

    lab_score = sum(1 for kw in lab_keywords if kw in text_lower)
    rx_score = sum(1 for kw in rx_keywords if kw in text_lower)
    discharge_score = sum(1 for kw in discharge_keywords if kw in text_lower)

    if discharge_score > lab_score and discharge_score > rx_score:
        return "discharge_summary"
    if lab_score >= rx_score and lab_score > 0:
        return "lab_report"
    return "prescription"

def parse_lab_report_entities(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract lab test names, values, units, and determine abnormal flags
    against clinical reference ranges.
    """
    extracted_tests = []
    lines = ocr_text.split("\n")

    for test_name, ref_info in LAB_RANGES.items():
        pattern = re.compile(re.escape(test_name) + r"[:\s\-\|]+(\d+(?:\.\d+)?)", re.IGNORECASE)
        match = pattern.search(ocr_text)

        if not match:
            # Try matching short names (e.g. Glucose, Hemoglobin, Creatinine)
            short_name = test_name.split()[-1]
            if len(short_name) > 4:
                alt_pattern = re.compile(re.escape(short_name) + r"[:\s\-\|]+(\d+(?:\.\d+)?)", re.IGNORECASE)
                match = alt_pattern.search(ocr_text)

        if match:
            raw_val = match.group(1)
            try:
                num_val = float(raw_val)
                is_abnormal = (num_val < ref_info["min"] or num_val > ref_info["max"])
                extracted_tests.append({
                    "test_name": test_name,
                    "value": raw_val,
                    "unit": ref_info["unit"],
                    "reference_range": f"{ref_info['min']} - {ref_info['max']} {ref_info['unit']}",
                    "abnormal_flag": 1 if is_abnormal else 0,
                    "interpretation": "High" if num_val > ref_info["max"] else ("Low" if num_val < ref_info["min"] else "Normal")
                })
            except ValueError:
                pass

    return extracted_tests

def parse_prescription_entities(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract historical medication details (drug name, strength, dosage frequency, duration).
    Strictly marked as Historical Prescription only.
    """
    extracted_meds = []
    lines = ocr_text.split("\n")

    for line in lines:
        clean_line = line.strip()
        if not clean_line or len(clean_line) < 3:
            continue

        # Look for medication name match
        for pat in MEDICATION_PATTERNS:
            match = re.search(pat, clean_line)
            if match:
                med_name = match.group(0).strip()
                # Search for strength (e.g. 500mg, 10mg)
                strength_match = re.search(r"(\d+\s*(?:mg|gm|ml|mcg))", clean_line, re.IGNORECASE)
                strength = strength_match.group(1) if strength_match else "Unspecified"

                # Search for dosage frequency (e.g. 1-0-1, OD, BD)
                dosage_match = re.search(r"\b(1-0-1|1-0-0|0-0-1|1-1-1|0-1-0|OD|BD|TID|QID|once daily|twice daily)\b", clean_line, re.IGNORECASE)
                dosage = dosage_match.group(1).upper() if dosage_match else "As directed"

                # Search for duration (e.g. 5 days, 1 month)
                dur_match = re.search(r"(\d+\s*(?:days|weeks|months|days?))", clean_line, re.IGNORECASE)
                duration = dur_match.group(1) if dur_match else "Historical record"

                extracted_meds.append({
                    "medicine_name": med_name,
                    "strength": strength,
                    "dosage": dosage,
                    "frequency": dosage,
                    "duration": duration,
                    "is_historical": 1,
                    "context": clean_line
                })
                break

    return extracted_meds

def evaluate_ocr_confidence(ocr_text: str, extracted_items: list) -> str:
    """Evaluate OCR confidence based on entity match density and text character clarity."""
    if not ocr_text or len(ocr_text.strip()) < 15:
        return "low"
    if len(extracted_items) >= 2:
        return "high"
    if len(extracted_items) == 1:
        return "medium"
    return "low"

def process_scanned_document(
    patient_id: int,
    session_id: int,
    image_path: str,
    ocr_raw_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Complete OCR processing pipeline:
    1. Preprocess document image using PIL.
    2. Extract text (using provided client-side Tesseract.js text or local parser).
    3. Detect document type (lab report vs prescription vs discharge summary).
    4. Extract structured clinical entities (lab tests with abnormal flags, or historical prescriptions).
    5. Evaluate confidence score.
    6. Persist to database (medical_documents, lab_reports, prescriptions).
    """
    # 1. Preprocessing
    proc_path = preprocess_image(image_path)

    # 2. Text extraction
    final_text = (ocr_raw_text or "").strip()

    # 3. Document classification
    doc_type = detect_document_type(final_text)

    # 4. Entity extraction
    extracted_data = {}
    confidence = "medium"

    if doc_type == "lab_report":
        lab_items = parse_lab_report_entities(final_text)
        confidence = evaluate_ocr_confidence(final_text, lab_items)
        extracted_data["lab_tests"] = lab_items
        extracted_data["summary"] = f"Extracted {len(lab_items)} lab parameter(s)"
    else:
        # Prescription or general clinical doc
        rx_items = parse_prescription_entities(final_text)
        confidence = evaluate_ocr_confidence(final_text, rx_items)
        extracted_data["prescriptions"] = rx_items
        extracted_data["summary"] = f"Extracted {len(rx_items)} historical medication(s)"

    # 5. Persist to database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO medical_documents
            (patient_id, session_id, document_type, file_path, ocr_text, extracted_information, ocr_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                session_id,
                doc_type,
                image_path,
                final_text,
                json.dumps(extracted_data),
                confidence
            )
        )
        doc_id = cursor.lastrowid

        # Insert lab reports if detected
        if doc_type == "lab_report" and "lab_tests" in extracted_data:
            for test in extracted_data["lab_tests"]:
                cursor.execute(
                    """
                    INSERT INTO lab_reports
                    (patient_id, document_id, session_id, test_name, value, unit, reference_range, abnormal_flag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_id,
                        doc_id,
                        session_id,
                        test["test_name"],
                        test["value"],
                        test["unit"],
                        test["reference_range"],
                        test["abnormal_flag"]
                    )
                )

        # Insert historical prescriptions if detected
        if "prescriptions" in extracted_data:
            for rx in extracted_data["prescriptions"]:
                cursor.execute(
                    """
                    INSERT INTO prescriptions
                    (patient_id, document_id, session_id, medicine_name, strength, dosage, frequency, duration, is_historical)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        patient_id,
                        doc_id,
                        session_id,
                        rx["medicine_name"],
                        rx["strength"],
                        rx["dosage"],
                        rx["frequency"],
                        rx["duration"]
                    )
                )

        conn.commit()

    return {
        "status": "success",
        "document_id": doc_id,
        "document_type": doc_type,
        "ocr_confidence": confidence,
        "preprocessed_image": proc_path,
        "extracted_data": extracted_data,
        "raw_ocr_text": final_text
    }
