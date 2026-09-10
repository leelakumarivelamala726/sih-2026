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
from database.db import get_db_connection, get_clinical_history, get_session

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
