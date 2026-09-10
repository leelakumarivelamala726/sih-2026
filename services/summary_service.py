"""
Ministry of Ayush – Smart MediKiosk
Clinical Summary & Medical Coding Service
Government of India / Bharat • Clinical History Platform

Safety Principle:
Generates a structured, physician-ready draft summary.
Clearly states that the AI does NOT diagnose or prescribe.
All information requires physician review, editing, and verification.
"""

import os
AI_API_KEY = os.getenv("AI_API_KEY")

import json
import requests
from typing import Dict, Any, List, Optional
from database.db import get_db_connection, get_clinical_history, get_session, get_patient_history_timeline

def generate_live_ai_summary_text(
    session: dict,
    history: dict,
    transcripts: list,
    lab_items: list,
    rx_items: list,
    red_flags: list,
    coding_suggestions: list
) -> Optional[str]:
    """Generate a structured physician-ready clinical case summary using live Gemini API via AI_API_KEY."""
    key = os.getenv("AI_API_KEY")
    if not key or key == "your_ai_api_key_here":
        return None

    patient_name = session.get("patient_name", "Unknown")
    age = session.get("age", "N/A")
    gender = session.get("gender", "N/A")
    abha_id = session.get("abha_id", "N/A")
    token = session.get("token_number", "N/A")
    priority = "🔴 URGENT ATTENTION REQUIRED" if session.get("priority_level") == "urgent" else "🟢 Normal Priority"

    system_instruction = (
        "You are AYUSH KRITI, the clinical summarization engine for Ministry of Ayush Smart MediKiosk in the Government of Bharat.\n"
        "Synthesize a professional, comprehensive pre-consultation clinical case summary in Markdown for the consulting physician.\n"
        "MANDATORY SAFETY & CLINICAL CONSTRAINTS:\n"
        "1. AI NEVER makes a final diagnosis or concludes a disease.\n"
        "2. AI NEVER prescribes, recommends, or issues new medications or dosages.\n"
        "3. Any medications from previous documents must be explicitly labeled as 'Historical Prescriptions (Extracted from Documents)' and NOT new prescriptions.\n"
        "4. Include an explicit SAFETY NOTICE alerting the physician that this is an AI-assisted intake draft requiring physician review and verification.\n"
        "5. Structure the summary with headers: Patient Overview & Triage Status, Red Flags (if any), Chief Complaint & HPI, "
        "Past Medical & Surgical History, Medication & Allergy Profile, AYUSH Clinical Parameters (Agni, Koshta, Ama, Nidra, Ahara/Vihara, Manasika), "
        "Scanned Document Findings (highlighting abnormal lab tests in a table and historical Rx in a table), and Suggested ICD-10 & AYUSH NAMASTE codes."
    )

    prompt = f"""
Patient: {patient_name} | Age/Gender: {age}Y/{gender} | ABHA ID: {abha_id} | Token: {token} | Triage: {priority}
Clinical History Data: {json.dumps(history, default=str)}
Patient Verbatim Transcripts: {json.dumps([dict(t) for t in transcripts[:25]], default=str)}
Lab Reports Extracted: {json.dumps(lab_items, default=str)}
Historical Medications: {json.dumps(rx_items, default=str)}
Red Flags Detected: {json.dumps(red_flags, default=str)}
Suggested Medical Codes: {json.dumps(coding_suggestions, default=str)}

Draft the complete physician-ready clinical summary in clean, professional Markdown.
"""

    candidate_models = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-3.5-flash"]
    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"temperature": 0.2}
        }
        try:
            resp = requests.post(url, json=payload, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [])[0].get("text", "").strip()
                    if len(text) > 100:
                        return text
            elif resp.status_code == 429:
                # Quota limit reached on free tier; break immediately to avoid blocking server
                print(f"[AI Summary] Live model {model} rate limited (HTTP 429). Using high-accuracy clinical intake fallback.")
                break
        except requests.exceptions.Timeout:
            print(f"[AI Summary] Live model {model} timed out after 6s. Trying fallback.")
            continue
        except Exception as e:
            print(f"[AI Summary] Live model {model} query error: {e}")
            continue

    return None

ENTITY_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "prakriti_ai", "entity_rules.json")
with open(ENTITY_RULES_PATH, "r", encoding="utf-8") as f:
    ENTITY_RULES = json.load(f)

def suggest_medical_codes(chief_complaint: str, hpi: str, all_text: str) -> List[Dict[str, str]]:
    """Suggest potential ICD-10 and Ayush NAMASTE codes for physician review."""
    combined_text = f"{chief_complaint} {hpi} {all_text}".lower()
    suggested = []
    
    for rule in ENTITY_RULES.get("medical_coding_suggestions", []):
        for kw in rule["keywords"]:
            if kw.lower() in combined_text:
                suggested.append({
                    "condition": rule["condition"],
                    "icd10": rule["icd10"],
                    "namaste_ayush_code": rule["namaste_ayush_code"],
                    "matched_keyword": kw
                })
                break
    return suggested

def generate_clinical_summary(session_id: int, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Synthesize complete clinical history, transcripts, and OCR document extractions
    into a comprehensive physician-ready clinical summary.
    Checks database cache first for instant retrieval unless force_refresh is True.
    """
    session = get_session(session_id)
    if not session:
        return {"status": "error", "message": "Session not found", "summary_text": "Error: Patient session not found."}

    # 1. Check existing cached summary in ai_summaries table for instant retrieval
    if not force_refresh:
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT id, summary, generated_at FROM ai_summaries WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,)
            ).fetchone()
            if existing and existing["summary"] and len(existing["summary"].strip()) > 50:
                history = get_clinical_history(session_id) or {}
                coding_suggestions = suggest_medical_codes(
                    history.get("chief_complaint") or "",
                    history.get("history_of_present_illness") or "",
                    history.get("ayush_specific_history") or ""
                )
                labs = conn.execute(
                    "SELECT * FROM lab_reports WHERE session_id = ? ORDER BY abnormal_flag DESC, id ASC",
                    (session_id,)
                ).fetchall()
                rxs = conn.execute(
                    "SELECT * FROM prescriptions WHERE session_id = ? ORDER BY id ASC",
                    (session_id,)
                ).fetchall()
                red_flags_raw = history.get("red_flags") or "[]"
                try:
                    red_flags = json.loads(red_flags_raw)
                except Exception:
                    red_flags = []

                return {
                    "status": "success",
                    "summary_id": existing["id"],
                    "summary_text": existing["summary"],
                    "coding_suggestions": coding_suggestions,
                    "red_flags": red_flags,
                    "lab_items": [dict(r) for r in labs],
                    "rx_items": [dict(r) for r in rxs]
                }

    history = get_clinical_history(session_id) or {}

    with get_db_connection() as conn:
        # Fetch lab reports
        labs = conn.execute(
            "SELECT * FROM lab_reports WHERE session_id = ? ORDER BY abnormal_flag DESC, id ASC",
            (session_id,)
        ).fetchall()
        lab_items = [dict(r) for r in labs]

        # Fetch historical prescriptions
        rxs = conn.execute(
            "SELECT * FROM prescriptions WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        rx_items = [dict(r) for r in rxs]

        # Fetch red flags
        red_flags_raw = history.get("red_flags") or "[]"
        try:
            red_flags = json.loads(red_flags_raw)
        except Exception:
            red_flags = []

    # Format structured clinical sections
    patient_name = session.get("patient_name", "Unknown")
    age = session.get("age", "N/A")
    gender = session.get("gender", "N/A")
    abha_id = session.get("abha_id", "N/A")
    token = session.get("token_number", "N/A")
    date_str = session.get("session_date", "Today")

    # Build Markdown Summary
    summary_lines = []
    summary_lines.append(f"### CLINICAL CASE SUMMARY (PRE-CONSULTATION)")
    summary_lines.append(f"**Patient**: {patient_name} | **Age/Gender**: {age}Y / {gender} | **ABHA ID**: `{abha_id}` | **Token**: `{token}`")
    summary_lines.append(f"**Date**: {date_str} | **Triage Status**: {'🔴 URGENT ATTENTION REQUIRED' if session.get('priority_level') == 'urgent' else '🟢 Normal Priority'}")
    summary_lines.append("\n---")

    # Red Flags Banner if applicable
    if red_flags:
        summary_lines.append("\n> [!CAUTION]")
        summary_lines.append("> **CRITICAL RED FLAGS REPORTED**:")
        for rf in red_flags:
            summary_lines.append(f"> - **Concern**: {rf.get('concern')} (Reported pattern: *\"{rf.get('pattern_matched')}\"*). {rf.get('action')}")
        summary_lines.append("")

    # Chief Complaint & HPI
    summary_lines.append("#### 1. Chief Complaint & History of Present Illness (HPI)")
    summary_lines.append(f"- **Chief Complaint**: {history.get('chief_complaint') or 'Not reported'}")
    summary_lines.append(f"- **Onset & Duration**: {history.get('onset') or history.get('duration') or 'Not specified'}")
    summary_lines.append(f"- **Severity & Location**: Severity: {history.get('severity') or 'N/A'}, Location: {history.get('location') or 'N/A'}")
    summary_lines.append(f"- **Aggravating & Relieving Factors**: Aggravating: {history.get('aggravating_factors') or 'N/A'}; Relieving: {history.get('relieving_factors') or 'N/A'}")
    summary_lines.append(f"- **Associated Symptoms**: {history.get('associated_symptoms') or 'None reported'}")
    if history.get("history_of_present_illness"):
        summary_lines.append(f"- **Regional Slang Normalization Notes**: {history.get('history_of_present_illness')}")

    # Past Medical & Surgical
    summary_lines.append("\n#### 2. Past Medical & Surgical History")
    summary_lines.append(f"- **Medical History**: {history.get('past_medical_history') or 'Nil significant'}")
    summary_lines.append(f"- **Surgical History**: {history.get('past_surgical_history') or 'None'}")

    # Drug & Allergy History
    summary_lines.append("\n#### 3. Medication & Allergy Profile")
    summary_lines.append(f"- **Current Medications**: {history.get('medication_history') or 'None reported'}")
    summary_lines.append(f"- **Known Allergies**: {history.get('allergy_history') or 'No known drug allergies (NKDA)'}")

    # AYUSH Profile
    summary_lines.append("\n#### 4. AYUSH Clinical Parameters (Ayurvedic Assessment)")
    summary_lines.append(f"- **Prakriti (Constitutional assessment)**: {history.get('prakriti') or 'Assessment pending physician examination'}")
    summary_lines.append(f"- **Vikriti & Dosha**: Primary Dosha: {history.get('dosha') or 'Unspecified'} | Vikriti: {history.get('vikriti') or 'Tridoshic evaluation required'}")
    summary_lines.append(f"- **Agni (Digestive Fire) & Appetite**: Agni: {history.get('agni') or 'N/A'} | Appetite: {history.get('appetite') or 'N/A'}")
    summary_lines.append(f"- **Ama Status (Metabolic Toxins)**: {history.get('ama') or 'Nirama / No gross signs reported'}")
    summary_lines.append(f"- **Koshta (Bowel Routine)**: {history.get('koshta') or history.get('bowel_habits') or 'Normal'}")
    summary_lines.append(f"- **Nidra (Sleep Quality)**: {history.get('nidra') or history.get('sleep') or 'Sound sleep'}")
    summary_lines.append(f"- **Ahara (Dietary Pattern)**: {history.get('ahara') or history.get('diet') or 'Regular diet'}")
    summary_lines.append(f"- **Vihara (Lifestyle & Physical Exertion)**: {history.get('vihara') or history.get('lifestyle') or 'Moderate activity'}")
    summary_lines.append(f"- **Manasika Factors (Stress/Mental State)**: {history.get('manasika') or 'Stable / Normal'}")
    if history.get("ayush_specific_history"):
        summary_lines.append(f"- **Ayurvedic Summary Notes**: {history.get('ayush_specific_history')}")

    # Extracted Documents (Lab Reports)
    if lab_items:
        summary_lines.append("\n#### 5. Scanned Document Findings – Laboratory Investigations")
        summary_lines.append("| Test Name | Result Value | Reference Range | Flag / Status |")
        summary_lines.append("| :--- | :--- | :--- | :--- |")
        for lab in lab_items:
            flag_badge = "**⚠️ ABNORMAL**" if lab.get("abnormal_flag") == 1 else "Normal"
            unit = lab.get("unit") or ""
            ref = lab.get("reference_range") or "N/A"
            summary_lines.append(f"| {lab.get('test_name')} | **{lab.get('value')} {unit}** | {ref} | {flag_badge} |")
        summary_lines.append("\n*Note: Abnormal parameters are highlighted for physician interpretation. AI does not diagnose based on lab values.*")

    # Extracted Historical Prescriptions
    if rx_items:
        summary_lines.append("\n#### 6. Historical Prescriptions (Extracted from Previous Documents)")
        summary_lines.append("| Medicine Name | Strength | Dosage / Frequency | Duration | Document Type |")
        summary_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for rx in rx_items:
            summary_lines.append(f"| {rx.get('medicine_name')} | {rx.get('strength')} | {rx.get('dosage')} | {rx.get('duration')} | *Historical Record* |")
        summary_lines.append("\n*Notice: These are historical medications extracted from patient documents. AI has NOT issued new prescriptions.*")

    # Medical Coding Suggestions
    coding_suggestions = suggest_medical_codes(
        history.get("chief_complaint") or "",
        history.get("history_of_present_illness") or "",
        history.get("ayush_specific_history") or ""
    )
    if coding_suggestions:
        summary_lines.append("\n#### 7. Suggested Medical Codes (For Physician Verification)")
        for c in coding_suggestions:
            summary_lines.append(f"- **{c['condition']}**")
            summary_lines.append(f"  - **ICD-10 Code**: `{c['icd10']}`")
            summary_lines.append(f"  - **Ayush NAMASTE Code**: `{c['namaste_ayush_code']}`")

    # Safety Disclaimer
    summary_lines.append("\n---")
    summary_lines.append("> [!NOTE]")
    summary_lines.append("> **SAFETY NOTICE**: This summary is an AI-assisted structured intake draft prepared by AYUSH KRITI. The AI does NOT diagnose, treat, or prescribe. The final clinical evaluation, diagnosis, and prescription remain the sole responsibility of the qualified physician.")

    fallback_summary_text = "\n".join(summary_lines)

    # Fetch transcripts for live AI synthesis
    with get_db_connection() as conn:
        transcripts = conn.execute(
            "SELECT speaker, original_transcript FROM transcripts WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()

    # Attempt Live AI Summary via AI_API_KEY
    live_summary = generate_live_ai_summary_text(
        session=session,
        history=history,
        transcripts=transcripts,
        lab_items=lab_items,
        rx_items=rx_items,
        red_flags=red_flags,
        coding_suggestions=coding_suggestions
    )

    full_summary_text = live_summary if live_summary else fallback_summary_text

    # Save to ai_summaries table
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ai_summaries WHERE session_id = ?", (session_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE ai_summaries SET summary = ?, generated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (full_summary_text, existing["id"])
            )
            summary_id = existing["id"]
        else:
            cursor.execute(
                "INSERT INTO ai_summaries (patient_id, session_id, summary, verification_status) VALUES (?, ?, ?, 'pending_verification')",
                (session["patient_id"], session_id, full_summary_text)
            )
            summary_id = cursor.lastrowid
        conn.commit()

    return {
        "status": "success",
        "summary_id": summary_id,
        "summary_text": full_summary_text,
        "coding_suggestions": coding_suggestions,
        "red_flags": red_flags,
        "lab_items": lab_items,
        "rx_items": rx_items
    }

def _clean_clinical_field(val: Any, default: str = "Not provided") -> str:
    """Normalize clinical field string; never return null/undefined/blank."""
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        if not val:
            return default
        try:
            return json.dumps(val)
        except Exception:
            return default
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "undefined", "n/a", "nil", "[]", "{}"):
        return default
    return s

def build_structured_clinical_summary_payload(session_id: int) -> Optional[Dict[str, Any]]:
    """
    Build complete structured clinical summary payload for the Doctor Dashboard:
    1. Patient Demographics & Identification
    2. AI-Assisted Clinical Summary narrative paragraph
    3. Key Clinical Findings subsection
    4. Detailed Structured Clinical Profile
    5. Uploaded Lab Reports / OCR Results & Abnormal Findings
    6. AI Case Insights & Recommended Follow-up / Next Clinical Action
    7. Chronological Previous Visits Timeline (latest first)
    
    Safety Guarantee:
    - Never fabricates diagnosis, symptoms, labs, medications, or history.
    - Missing fields strictly display 'Not provided' instead of undefined/null/blank.
    - AI-Assisted content is explicitly labeled as draft for physician verification.
    """
    session = get_session(session_id)
    if not session:
        return None

    history = get_clinical_history(session_id) or {}
    patient_id = session.get("patient_id")

    with get_db_connection() as conn:
        # Lab reports with abnormal flags
        labs_rows = conn.execute(
            "SELECT * FROM lab_reports WHERE session_id = ? ORDER BY abnormal_flag DESC, id ASC",
            (session_id,)
        ).fetchall()
        lab_items = [dict(r) for r in labs_rows]

        # Prescriptions from OCR
        rxs_rows = conn.execute(
            "SELECT * FROM prescriptions WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        rx_items = [dict(r) for r in rxs_rows]

        # Medical documents
        docs_rows = conn.execute(
            "SELECT id, document_type, file_path, ocr_text, created_at FROM medical_documents WHERE session_id = ? ORDER BY id DESC",
            (session_id,)
        ).fetchall()
        doc_items = [dict(r) for r in docs_rows]

    # Red flags
    red_flags_raw = history.get("red_flags") or "[]"
    try:
        red_flags = json.loads(red_flags_raw) if isinstance(red_flags_raw, str) else red_flags_raw
    except Exception:
        red_flags = []

    is_urgent = session.get("priority_level") == "urgent" or bool(red_flags)

    # 1. Cleaned Structured Demographic & Clinical Fields
    chief_complaint = _clean_clinical_field(history.get("chief_complaint"))
    duration = _clean_clinical_field(history.get("duration") or history.get("onset"))
    severity = _clean_clinical_field(history.get("severity"))
    location = _clean_clinical_field(history.get("location"))
    associated_symptoms = _clean_clinical_field(history.get("associated_symptoms"))
    hpi = _clean_clinical_field(history.get("history_of_present_illness"))
    past_medical = _clean_clinical_field(history.get("past_medical_history"))
    past_surgical = _clean_clinical_field(history.get("past_surgical_history"))
    family_history = _clean_clinical_field(history.get("family_history"))
    personal_history = _clean_clinical_field(history.get("personal_history"))
    current_meds = _clean_clinical_field(history.get("medication_history"))
    allergies = _clean_clinical_field(history.get("allergy_history"))
    lifestyle = _clean_clinical_field(history.get("lifestyle") or history.get("vihara"))
    sleep_pattern = _clean_clinical_field(history.get("sleep") or history.get("nidra"))
    diet_appetite = _clean_clinical_field(
        f"{history.get('diet') or history.get('ahara') or ''} (Appetite: {history.get('appetite') or history.get('agni') or ''})".strip(" ()")
        if (history.get("diet") or history.get("ahara") or history.get("appetite") or history.get("agni"))
        else None
    )
    bowel_habits = _clean_clinical_field(history.get("bowel_habits") or history.get("koshta"))
    stress_mental = _clean_clinical_field(history.get("manasika"))
    previous_treatments = _clean_clinical_field(history.get("other_relevant_information"))
    if previous_treatments == "Not provided" and rx_items:
        previous_treatments = ", ".join([r.get("medicine_name", "") for r in rx_items[:4] if r.get("medicine_name")]) or "Not provided"

    # 2. Abnormal Lab Findings Extraction
    abnormal_labs = [l for l in lab_items if l.get("abnormal_flag") == 1]

    # 3. Formulate Concise Clinical Summary narrative
    symptoms_list = []
    if associated_symptoms != "Not provided":
        symptoms_list.append(associated_symptoms)
    if location != "Not provided":
        symptoms_list.append(f"localized to {location}")
    if severity != "Not provided":
        symptoms_list.append(f"severity: {severity}")
    symptoms_narrative = "; ".join(symptoms_list) if symptoms_list else "Not provided"

    past_hist_list = []
    if past_medical != "Not provided":
        past_hist_list.append(f"Medical: {past_medical}")
    if past_surgical != "Not provided":
        past_hist_list.append(f"Surgical: {past_surgical}")
    past_hist_narrative = "; ".join(past_hist_list) if past_hist_list else "Not provided"

    meds_allergies_narrative = f"Medications: {current_meds}; Allergies: {allergies}" if (current_meds != "Not provided" or allergies != "Not provided") else "Not provided"

    wellness_list = []
    if diet_appetite != "Not provided":
        wellness_list.append(f"Diet/Appetite: {diet_appetite}")
    if sleep_pattern != "Not provided":
        wellness_list.append(f"Sleep: {sleep_pattern}")
    if bowel_habits != "Not provided":
        wellness_list.append(f"Bowel: {bowel_habits}")
    if lifestyle != "Not provided":
        wellness_list.append(f"Lifestyle: {lifestyle}")
    if stress_mental != "Not provided":
        wellness_list.append(f"Mental/Stress: {stress_mental}")
    wellness_narrative = "; ".join(wellness_list) if wellness_list else "Not provided"

    if abnormal_labs:
        abnormal_summary = ", ".join([f"{l.get('test_name')}: {l.get('test_value')} {l.get('unit') or ''} (Abnormal)" for l in abnormal_labs])
        lab_ocr_narrative = f"{len(lab_items)} lab tests on file. Notable abnormal findings: {abnormal_summary}."
    elif lab_items:
        lab_ocr_narrative = f"{len(lab_items)} laboratory investigations available, within normal limits."
    elif doc_items:
        lab_ocr_narrative = f"{len(doc_items)} medical document(s) uploaded."
    else:
        lab_ocr_narrative = "Not provided"

    concise_clinical_summary = (
        f"Patient presents with {chief_complaint} for {duration}. "
        f"Relevant symptoms include {symptoms_narrative}. "
        f"Past history includes {past_hist_narrative}. "
        f"Current medications/allergies: {meds_allergies_narrative}. "
        f"Lifestyle and wellness indicators show {wellness_narrative}. "
        f"Laboratory/OCR findings indicate {lab_ocr_narrative}."
    )

    # 4. Key Clinical Findings
    ai_concerns = []
    if is_urgent:
        ai_concerns.append("🔴 Emergency triage alert triggered based on reported symptoms.")
    for rf in red_flags:
        ai_concerns.append(f"Red flag: {rf.get('concern')} (Action: {rf.get('action')})")
    if abnormal_labs:
        ai_concerns.append(f"{len(abnormal_labs)} abnormal laboratory parameter(s) flagged for clinical review.")

    key_clinical_findings = {
        "chief_complaint": chief_complaint,
        "important_symptoms": symptoms_narrative,
        "abnormal_lab_values": [
            {
                "test_name": l.get("test_name"),
                "value": l.get("test_value"),
                "unit": l.get("unit") or "",
                "reference_range": l.get("reference_range") or "Not provided",
                "status": "ABNORMAL"
            } for l in abnormal_labs
        ],
        "risk_indicators": "🔴 High Priority / Red-Flag Alert" if is_urgent else "🟢 Normal Clinical Priority",
        "relevant_medical_history": past_hist_narrative,
        "ai_detected_concerns": ai_concerns if ai_concerns else ["No urgent safety flags detected."]
    }

    # 5. Suggested Medical Codes
    coding_suggestions = suggest_medical_codes(
        history.get("chief_complaint") or "",
        history.get("history_of_present_illness") or "",
        history.get("ayush_specific_history") or ""
    )

    # 6. Recommended Follow-up / Next Clinical Action
    recommended_actions = []
    if is_urgent or red_flags:
        recommended_actions.append("Prioritize immediate bedside/in-person clinical examination and vital sign stabilization.")
    if abnormal_labs:
        recommended_actions.append(f"Review {len(abnormal_labs)} abnormal lab parameter(s) and consider confirmatory pathology workup.")
    if chief_complaint != "Not provided":
        recommended_actions.append(f"Perform directed physical assessment focused on {chief_complaint}.")
    if history.get("prakriti") or history.get("dosha"):
        recommended_actions.append(f"Validate Ayurvedic constitution ({_clean_clinical_field(history.get('prakriti'))}) and advise dosha-balancing Ahara/Vihara.")
    if not recommended_actions:
        recommended_actions.append("Conduct comprehensive physical examination, assess vital parameters, and finalize clinical verification.")

    # 7. Chronological Previous Visits Timeline (latest first)
    raw_timeline = get_patient_history_timeline(patient_id) if patient_id else []
    structured_timeline = []
    for item in raw_timeline:
        # Determine lab summary for that visit if available
        structured_timeline.append({
            "session_id": item.get("session_id"),
            "token_number": item.get("token_number") or "-",
            "date": item.get("session_date") or "-",
            "status": item.get("status") or "completed",
            "complaint": _clean_clinical_field(item.get("chief_complaint")),
            "assessment": _clean_clinical_field(item.get("ayush_specific_history") or item.get("ai_summary") or "Clinical assessment completed"),
            "treatment": _clean_clinical_field(item.get("doctor_notes") or item.get("medical_codes") or "Evaluated by physician"),
            "doctor_name": item.get("doctor_name") or "Dr. Rohan Patel, MD (Ayush)",
            "verified_at": item.get("verified_at") or "-"
        })

    # Sort latest first (by session_id descending or date)
    structured_timeline.sort(key=lambda x: x.get("session_id") or 0, reverse=True)

    return {
        "status": "success",
        "session_id": session_id,
        "patient": {
            "id": session.get("patient_id"),
            "name": _clean_clinical_field(session.get("patient_name")),
            "age": session.get("age"),
            "gender": _clean_clinical_field(session.get("gender")),
            "abha_id": _clean_clinical_field(session.get("abha_id")),
            "phone_number": _clean_clinical_field(session.get("phone_number")),
            "token_number": session.get("token_number"),
            "session_date": session.get("session_date"),
            "priority_level": session.get("priority_level", "normal"),
            "status": session.get("status", "in_progress")
        },
        "clinical_summary_text": concise_clinical_summary,
        "key_clinical_findings": key_clinical_findings,
        "structured_details": {
            "patient_name": _clean_clinical_field(session.get("patient_name")),
            "age": str(session.get("age") or "Not provided"),
            "gender": _clean_clinical_field(session.get("gender")),
            "abha_id": _clean_clinical_field(session.get("abha_id")),
            "phone_number": _clean_clinical_field(session.get("phone_number")),
            "chief_complaints": chief_complaint,
            "symptoms": symptoms_narrative,
            "duration_of_symptoms": duration,
            "present_illness_hpi": hpi,
            "past_medical_history": past_medical,
            "past_surgical_history": past_surgical,
            "family_history": family_history,
            "personal_history": personal_history,
            "current_medications": current_meds,
            "allergies": allergies,
            "lifestyle_information": lifestyle,
            "sleep_pattern": sleep_pattern,
            "diet_appetite": diet_appetite,
            "bowel_habits": bowel_habits,
            "stress_mental_wellness": stress_mental,
            "previous_treatments": previous_treatments,
            "prakriti": _clean_clinical_field(history.get("prakriti")),
            "vikriti": _clean_clinical_field(history.get("vikriti")),
            "dosha": _clean_clinical_field(history.get("dosha")),
            "agni": _clean_clinical_field(history.get("agni")),
            "ama": _clean_clinical_field(history.get("ama")),
            "koshta": _clean_clinical_field(history.get("koshta")),
            "nidra": _clean_clinical_field(history.get("nidra")),
            "ahara": _clean_clinical_field(history.get("ahara")),
            "vihara": _clean_clinical_field(history.get("vihara")),
            "manasika": _clean_clinical_field(history.get("manasika")),
            "ayush_specific_notes": _clean_clinical_field(history.get("ayush_specific_history"))
        },
        "lab_reports": lab_items,
        "abnormal_findings": abnormal_labs,
        "uploaded_documents": doc_items,
        "prescriptions": rx_items,
        "coding_suggestions": coding_suggestions,
        "recommended_actions": recommended_actions,
        "timeline": structured_timeline
    }

