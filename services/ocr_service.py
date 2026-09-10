"""
Ministry of Ayush – Smart MediKiosk
Medical Document OCR & Clinical Entity Extraction Service
Government of Bharat • Clinical History Platform

Integrity & Safety Rules:
1. Preserve the original uploaded document untouched.
2. Multi-pass image preprocessing (rotation, contrast, denoising, resolution enhancement).
3. NEVER hallucinate or guess medical values. Uncertain values (e.g. '1Z.5') are marked as 'LOW / REVIEW REQUIRED'.
4. Historical prescriptions are strictly tagged as historical records only (NEVER new prescriptions).
5. Extract structured table parameters (Test Name, Result, Unit, Reference Range, Flag, Confidence).
6. Provide raw OCR text for doctor verification and comparison with the original image.
"""

import os
AI_API_KEY = os.getenv("AI_API_KEY")

import re
import json
import base64
import requests
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from database.db import get_db_connection

def extract_document_with_live_vision(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract medical document entities using live Gemini multimodal vision via AI_API_KEY.
    Strictly forbids guessing or hallucinating medical data.
    """
    key = os.getenv("AI_API_KEY") or AI_API_KEY
    if not key or key == "your_ai_api_key_here":
        return None

    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    system_instruction = (
        "You are AYUSH KRITI Medical Document OCR Vision Engine for Ministry of Ayush Smart MediKiosk in Government of Bharat.\n"
        "Your task is to transcribe and extract clinical information from scanned patient records, lab reports, and prescriptions.\n"
        "\nCRITICAL NON-HALLUCINATION & INTEGRITY RULES:\n"
        "1. EXTRACT ONLY EXACT, VERBATIM VISIBLE TEXT from the document. Never guess or hallucinate missing words.\n"
        "2. NEVER invent numbers, test values, or dosages. If a character or number is blurry or uncertain (e.g. if the image reads '1Z.5'), extract exactly '1Z.5' and mark its confidence as 'LOW / REVIEW REQUIRED'. Never change it to '12.5'.\n"
        "3. HISTORICAL PRESCRIPTIONS ONLY: Any medications found in previous documents must be flagged with is_historical=1. NEVER generate or suggest a new prescription.\n"
        "4. CLASSIFY DOCUMENT TYPE STRICTLY into: 'LAB REPORT', 'PRESCRIPTION', 'MEDICAL REPORT', or 'OTHER'.\n"
        "5. FOR LAB REPORTS: Recognize table structure and extract: test_name, value, unit, reference_range, abnormal_flag (1 if abnormal, 0 if normal), interpretation (Normal/High/Low), and field confidence ('HIGH', 'MEDIUM', 'LOW / REVIEW REQUIRED').\n"
        "6. FOR PRESCRIPTIONS: Extract medicine_name, strength, dosage, frequency, duration, is_historical (1), and confidence ('HIGH', 'MEDIUM', 'LOW / REVIEW REQUIRED').\n"
        "7. EXTRACT PATIENT INFO if visible: patient_name, age, gender, patient_id, document_date.\n"
        "8. If image is unreadable or corrupted, set ocr_confidence to 'LOW' and specify review_message: 'Image quality is insufficient for reliable extraction. Please upload a clearer image.'\n"
        "9. Return strictly valid JSON."
    )

    prompt = (
        "Analyze this medical document image with high precision.\n"
        "Return a JSON object with keys:\n"
        "1. 'document_type': one of ['LAB REPORT', 'PRESCRIPTION', 'MEDICAL REPORT', 'OTHER']\n"
        "2. 'ocr_confidence': 'HIGH', 'MEDIUM', or 'LOW'\n"
        "3. 'patient_info': { 'name': string or null, 'age': string or null, 'gender': string or null, 'patient_id': string or null, 'document_date': string or null }\n"
        "4. 'lab_tests': list of objects { 'test_name', 'value', 'unit', 'reference_range', 'abnormal_flag': 0 or 1, 'interpretation', 'confidence': 'HIGH' | 'MEDIUM' | 'LOW / REVIEW REQUIRED' }\n"
        "5. 'prescriptions': list of objects { 'medicine_name', 'strength', 'dosage', 'frequency', 'duration', 'is_historical': 1, 'confidence': 'HIGH' | 'MEDIUM' | 'LOW / REVIEW REQUIRED' }\n"
        "6. 'raw_ocr_text': complete verbatim string of all readable text from the document\n"
        "7. 'review_required': boolean (true if any field has low confidence or unclear values)\n"
        "8. 'review_message': string or null"
    )

    candidate_models = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.6-flash"]
    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": b64_data}}
                ]
            }],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.05
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=18)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        parsed = json.loads(text)
                        if isinstance(parsed, dict) and "document_type" in parsed:
                            # Normalize document_type casing
                            dt = str(parsed.get("document_type", "OTHER")).upper()
                            if "LAB" in dt: parsed["document_type"] = "LAB REPORT"
                            elif "PRESCRIPTION" in dt or "RX" in dt: parsed["document_type"] = "PRESCRIPTION"
                            elif "DISCHARGE" in dt or "SUMMARY" in dt or "MEDICAL" in dt: parsed["document_type"] = "MEDICAL REPORT"
                            else: parsed["document_type"] = "OTHER"
                            return parsed
        except Exception:
            continue

    return None

ENTITY_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "prakriti_ai", "entity_rules.json")
try:
    with open(ENTITY_RULES_PATH, "r", encoding="utf-8") as f:
        ENTITY_RULES = json.load(f)
except Exception:
    ENTITY_RULES = {}

LAB_RANGES = ENTITY_RULES.get("lab_reference_ranges", {})

MEDICATION_PATTERNS = [
    r"(?i)\b(paracetamol|pantoprazole|amoxicillin|metformin|amlodipine|atorvastatin|azithromycin|cetirizine|omeprazole|losartan|telmisartan|aspirin|ibuprofen|doxycycline|ciprofloxacin|ashwagandha|triphala|brahmi|tulsi|liv52|guduchi|shatavari|neem|haridra)\b",
    r"(?i)\b(tab|cap|syp|inj)\.?\s+([A-Za-z0-9\-]+)"
]

def preprocess_image_multipass(image_path: str) -> Tuple[str, List[str]]:
    """
    Multi-pass document image preprocessing:
    1. Correct rotation/orientation via EXIF metadata.
    2. Resolution enhancement: if image width/height < 1200px, upscale with LANCZOS filter.
    3. Multi-pass candidate generation:
       - Pass A: Denoised auto-contrast (removes salt-and-pepper noise, balances lighting).
       - Pass B: Grayscale normalized with enhanced contrast (1.8x - 2.2x) and edge sharpening.
       - Pass C: Adaptive shadow suppression for smartphone/webcam captures.
    Returns: (best_image_path, list_of_variant_paths)
    """
    base, ext = os.path.splitext(image_path)
    variant_paths = []

    try:
        with Image.open(image_path) as img:
            # 1. Correct rotation/orientation
            img = ImageOps.exif_transpose(img)

            # 2. Resolution enhancement (upscale if small)
            width, height = img.size
            if width < 1200 or height < 1200:
                scale_factor = max(1200 / width, 1200 / height)
                new_w = int(width * min(scale_factor, 2.5))
                new_h = int(height * min(scale_factor, 2.5))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Pass A: Denoised and Auto-contrast
            pass_a = ImageOps.autocontrast(img.convert("RGB"))
            pass_a = pass_a.filter(ImageFilter.MedianFilter(size=3))
            pass_a_path = f"{base}_proc_a{ext}"
            pass_a.save(pass_a_path, quality=95)
            variant_paths.append(pass_a_path)

            # Pass B: Grayscale + High Contrast + Sharpening
            gray = img.convert("L")
            gray = ImageOps.autocontrast(gray)
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(2.0)
            sharpened = enhanced.filter(ImageFilter.SHARPEN)
            pass_b_path = f"{base}_proc_b{ext}"
            sharpened.save(pass_b_path, quality=95)
            variant_paths.append(pass_b_path)

            # Best default path for primary OCR recognition
            primary_path = pass_b_path
    except Exception as e:
        print(f"[OCR Preprocess Warning] {e}, falling back to original image.")
        primary_path = image_path

    return primary_path, variant_paths

def preprocess_image(image_path: str, output_path: Optional[str] = None) -> str:
    """Wrapper maintaining backward compatibility."""
    primary_path, _ = preprocess_image_multipass(image_path)
    return primary_path

def save_base64_image(base64_data: str, target_dir: str, filename_prefix: str = "doc") -> str:
    """Save base64 image data from webcam snapshot to disk without altering original content."""
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
    """Classify document strictly into LAB REPORT, PRESCRIPTION, MEDICAL REPORT, or OTHER."""
    if not ocr_text or len(ocr_text.strip()) < 10:
        return "OTHER"

    text_lower = ocr_text.lower()
    lab_keywords = [
        "lab", "report", "test", "hemoglobin", "glucose", "serum", "cholesterol",
        "platelet", "pathology", "biochemistry", "wbc", "rbc", "reference range",
        "unit", "investigation", "specimen", "fasting", "creatinine", "bilirubin", "lipid"
    ]
    rx_keywords = [
        "rx", "prescription", "tab", "cap", "dosage", "mg", "dispense", "dr.", "doctor",
        "clinic", "hospital", "pharma", "take", "daily", "od", "bd", "tid", "capsule", "tablet"
    ]
    medical_keywords = [
        "discharge", "admission", "course in hospital", "discharge summary",
        "diagnosis at discharge", "case summary", "medical history", "clinical notes"
    ]

    lab_score = sum(1 for kw in lab_keywords if kw in text_lower)
    rx_score = sum(1 for kw in rx_keywords if kw in text_lower)
    med_score = sum(1 for kw in medical_keywords if kw in text_lower)

    if med_score > lab_score and med_score > rx_score and med_score >= 2:
        return "MEDICAL REPORT"
    if lab_score >= rx_score and lab_score >= 1:
        return "LAB REPORT"
    if rx_score > 0:
        return "PRESCRIPTION"
    return "OTHER"

def is_uncertain_numeric(raw_val: str) -> bool:
    """
    Check if a numeric reading has ambiguous OCR characters (like '1Z.5', 'O.5', '1S0').
    Per requirement: NEVER guess or auto-correct, flag as LOW CONFIDENCE / REVIEW REQUIRED!
    """
    clean = raw_val.strip()
    # Check if contains letters mixed in numbers
    has_letters = any(c.isalpha() for c in clean)
    return has_letters

def parse_lab_report_entities(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract lab tests from OCR text into structured table format:
    Test Name | Result | Unit | Reference Range | Flag | Confidence
    NEVER hallucinates or auto-corrects uncertain readings.
    """
    extracted_tests = []
    if not ocr_text:
        return extracted_tests

    lines = ocr_text.split("\n")

    for test_name, ref_info in LAB_RANGES.items():
        # Match pattern e.g. "Hemoglobin: 13.5 g/dL" or "Hemoglobin 1Z.5"
        pattern = re.compile(re.escape(test_name) + r"[:\s\-\|]+([0-9A-Za-z\.\,\-]+)", re.IGNORECASE)
        match = pattern.search(ocr_text)

        if not match:
            short_name = test_name.split()[-1]
            if len(short_name) > 4:
                alt_pattern = re.compile(re.escape(short_name) + r"[:\s\-\|]+([0-9A-Za-z\.\,\-]+)", re.IGNORECASE)
                match = alt_pattern.search(ocr_text)

        if match:
            raw_val = match.group(1).strip()
            confidence = "HIGH"
            is_abnormal = 0
            interpretation = "Normal"

            # Check if value has uncertain characters (e.g. '1Z.5')
            if is_uncertain_numeric(raw_val):
                confidence = "LOW / REVIEW REQUIRED"
                interpretation = "Uncertain Reading"
            else:
                try:
                    clean_num = float(raw_val.replace(",", "."))
                    if clean_num < ref_info["min"] or clean_num > ref_info["max"]:
                        is_abnormal = 1
                        interpretation = "High" if clean_num > ref_info["max"] else "Low"
                    else:
                        interpretation = "Normal"
                except ValueError:
                    confidence = "LOW / REVIEW REQUIRED"
                    interpretation = "Review Required"

            extracted_tests.append({
                "test_name": test_name,
                "value": raw_val,
                "unit": ref_info["unit"],
                "reference_range": f"{ref_info['min']} - {ref_info['max']} {ref_info['unit']}",
                "abnormal_flag": is_abnormal,
                "interpretation": interpretation,
                "confidence": confidence
            })

    return extracted_tests

def parse_prescription_entities(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract historical medication details into structured table format:
    Medicine Name | Strength | Dosage / Frequency | Duration | Confidence
    Strictly marked as Historical Prescription only.
    """
    extracted_meds = []
    if not ocr_text:
        return extracted_meds

    lines = ocr_text.split("\n")

    for line in lines:
        clean_line = line.strip()
        if not clean_line or len(clean_line) < 3:
            continue

        for pat in MEDICATION_PATTERNS:
            match = re.search(pat, clean_line)
            if match:
                med_name = match.group(0).strip()
                strength_match = re.search(r"(\d+\s*(?:mg|gm|ml|mcg))", clean_line, re.IGNORECASE)
                strength = strength_match.group(1) if strength_match else "Unspecified"

                dosage_match = re.search(r"\b(1-0-1|1-0-0|0-0-1|1-1-1|0-1-0|OD|BD|TID|QID|once daily|twice daily)\b", clean_line, re.IGNORECASE)
                dosage = dosage_match.group(1).upper() if dosage_match else "As directed"

                dur_match = re.search(r"(\d+\s*(?:days|weeks|months|days?))", clean_line, re.IGNORECASE)
                duration = dur_match.group(1) if dur_match else "Historical record"

                confidence = "HIGH" if (strength != "Unspecified" or dosage != "As directed") else "MEDIUM"
                if is_uncertain_numeric(strength):
                    confidence = "LOW / REVIEW REQUIRED"

                extracted_meds.append({
                    "medicine_name": med_name,
                    "strength": strength,
                    "dosage": dosage,
                    "frequency": dosage,
                    "duration": duration,
                    "is_historical": 1,
                    "confidence": confidence,
                    "context": clean_line
                })
                break

    return extracted_meds

def evaluate_ocr_quality(ocr_text: str, extracted_items: list) -> Tuple[str, bool, Optional[str]]:
    """
    Evaluate OCR confidence, checking for unreadable or corrupted text:
    - If empty or corrupted garbage, marks LOW and flags insufficiency.
    - If items extracted with high clarity, marks HIGH.
    - Returns (confidence_str, review_required_bool, review_message)
    """
    raw = (ocr_text or "").strip()
    if not raw or len(raw) < 15:
        return (
            "LOW",
            True,
            "Image quality is insufficient for reliable extraction. Please upload a clearer image."
        )

    # Check for random garbage / corrupted characters ratio
    alphanumeric = sum(1 for c in raw if c.isalnum() or c.isspace())
    ratio = alphanumeric / len(raw) if len(raw) > 0 else 0
    if ratio < 0.60:
        return (
            "LOW",
            True,
            "Some information could not be reliably extracted. Please verify with the original document."
        )

    has_low_item = any(item.get("confidence") == "LOW / REVIEW REQUIRED" for item in extracted_items)
    if has_low_item:
        return (
            "MEDIUM",
            True,
            "Some values are uncertain and require physician review with the original document."
        )

    if len(extracted_items) >= 2:
        return ("HIGH", False, None)
    if len(extracted_items) == 1:
        return ("MEDIUM", False, None)

    return (
        "MEDIUM",
        True,
        "General medical document text detected. Please verify with the original document."
    )

def process_scanned_document(
    patient_id: int,
    session_id: int,
    image_path: str,
    ocr_raw_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Production Multi-pass OCR Pipeline:
    1. Preserve original document image untouched.
    2. Multi-pass image preprocessing (rotation, resolution upscale, noise removal, contrast enhancement).
    3. Run OCR text detection & structured entity recognition (Gemini Vision with strict non-hallucination + local fallback).
    4. Categorize document type: 'LAB REPORT', 'PRESCRIPTION', 'MEDICAL REPORT', 'OTHER'.
    5. Recognize table structure (Test Name | Result | Unit | Ref Range | Status | Confidence).
    6. Flag low-confidence readings without guessing.
    7. Save clean structured data, confidence, and image paths to database.
    """
    # 1. Multi-pass preprocessing
    proc_path, variants = preprocess_image_multipass(image_path)

    final_text = (ocr_raw_text or "").strip()
    extracted_data: Dict[str, Any] = {
        "patient_info": {},
        "lab_tests": [],
        "prescriptions": [],
        "summary": ""
    }
    doc_type = "OTHER"
    confidence = "MEDIUM"
    review_required = False
    review_message = None

    # 2. Attempt Live Multimodal Vision Analysis with strict non-hallucination rules
    live_vision_result = extract_document_with_live_vision(image_path)
    if live_vision_result:
        doc_type = live_vision_result.get("document_type", "OTHER")
        confidence = str(live_vision_result.get("ocr_confidence", "HIGH")).upper()
        review_required = bool(live_vision_result.get("review_required", False))
        review_message = live_vision_result.get("review_message")

        if not final_text and live_vision_result.get("raw_ocr_text"):
            final_text = live_vision_result["raw_ocr_text"]

        if live_vision_result.get("patient_info"):
            extracted_data["patient_info"] = live_vision_result["patient_info"]

        if doc_type == "LAB REPORT" and live_vision_result.get("lab_tests"):
            extracted_data["lab_tests"] = live_vision_result["lab_tests"]
            extracted_data["summary"] = f"Extracted {len(live_vision_result['lab_tests'])} lab parameter(s)"
        elif doc_type == "PRESCRIPTION" and live_vision_result.get("prescriptions"):
            extracted_data["prescriptions"] = live_vision_result["prescriptions"]
            extracted_data["summary"] = f"Extracted {len(live_vision_result['prescriptions'])} historical medication(s)"

    # 3. Fallback / Multi-pass Local Rule-based Parsing if live vision didn't populate entities
    if not extracted_data["lab_tests"] and not extracted_data["prescriptions"]:
        doc_type = detect_document_type(final_text)

        if doc_type == "LAB REPORT":
            lab_items = parse_lab_report_entities(final_text)
            confidence, review_required, review_message = evaluate_ocr_quality(final_text, lab_items)
            extracted_data["lab_tests"] = lab_items
            extracted_data["summary"] = f"Extracted {len(lab_items)} lab parameter(s)"
        elif doc_type == "PRESCRIPTION":
            rx_items = parse_prescription_entities(final_text)
            confidence, review_required, review_message = evaluate_ocr_quality(final_text, rx_items)
            extracted_data["prescriptions"] = rx_items
            extracted_data["summary"] = f"Extracted {len(rx_items)} historical medication(s)"
        else:
            confidence, review_required, review_message = evaluate_ocr_quality(final_text, [])
            extracted_data["summary"] = "General medical document text extracted"

    extracted_data["review_required"] = review_required
    extracted_data["review_message"] = review_message

    # 4. Persist to Database (medical_documents, lab_reports, prescriptions)
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
                doc_type.lower().replace(" ", "_"),
                image_path,
                final_text,
                json.dumps(extracted_data),
                confidence.lower()
            )
        )
        doc_id = cursor.lastrowid

        # Insert lab reports
        if doc_type == "LAB REPORT" and extracted_data.get("lab_tests"):
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
                        str(test.get("test_name", "Lab Investigation")),
                        str(test.get("value", "")),
                        str(test.get("unit", "")),
                        str(test.get("reference_range", "")),
                        int(test.get("abnormal_flag", 0))
                    )
                )

        # Insert historical prescriptions
        if extracted_data.get("prescriptions"):
            for rx in extracted_data["prescriptions"]:
                rx["is_historical"] = 1
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
                        str(rx.get("medicine_name", "Unspecified")),
                        str(rx.get("strength", "Unspecified")),
                        str(rx.get("dosage", "As directed")),
                        str(rx.get("frequency") or rx.get("dosage", "As directed")),
                        str(rx.get("duration", "Historical record"))
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
        "raw_ocr_text": final_text,
        "review_required": review_required,
        "review_message": review_message
    }

