"""
Ministry of Ayush – Smart MediKiosk
Doctor Dashboard & Verification Routes
Government of India / Bharat • Clinical History Platform

Safety Rule:
AI Summary is a draft. The qualified doctor must review, edit, code, and verify.
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from database.db import (
    get_db_connection,
    get_session,
    get_clinical_history,
    get_transcripts_for_session,
    get_patient_history_timeline
)
from services.summary_service import generate_clinical_summary, suggest_medical_codes

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/doctor')
def dashboard():
    """Doctor Dashboard main consultation console."""
    with get_db_connection() as conn:
        # Fetch queue of waiting patients
        queue_rows = conn.execute(
            """
            SELECT s.id as session_id, s.token_number, s.session_date, s.status, s.priority_level,
                   p.id as patient_id, p.patient_name, p.age, p.gender, p.abha_id, p.phone_number,
                   h.chief_complaint, h.red_flags
            FROM patient_sessions s
            JOIN patients p ON s.patient_id = p.id
            LEFT JOIN clinical_history h ON s.id = h.session_id
            ORDER BY
                CASE WHEN s.priority_level = 'urgent' THEN 0 ELSE 1 END,
                s.id ASC
            """
        ).fetchall()
        patient_queue = [dict(r) for r in queue_rows]

    return render_template('doctor_dashboard.html', queue=patient_queue)

@doctor_bp.route('/api/doctor/queue')
def get_queue():
    """API endpoint to refresh waiting patient queue."""
    with get_db_connection() as conn:
        queue_rows = conn.execute(
            """
            SELECT s.id as session_id, s.token_number, s.session_date, s.status, s.priority_level,
                   p.id as patient_id, p.patient_name, p.age, p.gender, p.abha_id, p.phone_number,
                   h.chief_complaint, h.red_flags
            FROM patient_sessions s
            JOIN patients p ON s.patient_id = p.id
            LEFT JOIN clinical_history h ON s.id = h.session_id
            ORDER BY
                CASE WHEN s.priority_level = 'urgent' THEN 0 ELSE 1 END,
                s.id ASC
            """
        ).fetchall()
        return jsonify({"queue": [dict(r) for r in queue_rows]})

@doctor_bp.route('/api/doctor/patient/<int:session_id>')
def patient_clinical_bundle(session_id):
    """
    Retrieve full clinical bundle for physician review:
    1. Demographics & Session info
    2. AI Structured Summary
    3. Verbatim Original Transcripts
    4. Scanned Document images & OCR extractions
    5. Lab tests with abnormal flags
    6. Historical Prescriptions
    7. Editable Clinical History
    8. Suggested ICD-10 and Ayush NAMASTE codes
    9. Previous Visits Timeline
    """
    session_data = get_session(session_id)
    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    # Ensure AI summary is compiled
    summary_data = generate_clinical_summary(session_id)
    history = get_clinical_history(session_id) or {}
    transcripts = get_transcripts_for_session(session_id)
    timeline = get_patient_history_timeline(session_data['patient_id'])

    with get_db_connection() as conn:
        # Scanned Documents
        docs = conn.execute(
            "SELECT * FROM medical_documents WHERE session_id = ? ORDER BY id DESC",
            (session_id,)
        ).fetchall()

        # Lab tests
        labs = conn.execute(
            "SELECT * FROM lab_reports WHERE session_id = ? ORDER BY abnormal_flag DESC, id ASC",
            (session_id,)
        ).fetchall()

        # Historical Prescriptions
        rxs = conn.execute(
            "SELECT * FROM prescriptions WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()

        # Previous doctor review if already verified
        review = conn.execute(
            "SELECT * FROM doctor_reviews WHERE session_id = ?",
            (session_id,)
        ).fetchone()

    # Medical coding suggestions
    coding_suggestions = suggest_medical_codes(
        history.get('chief_complaint') or '',
        history.get('history_of_present_illness') or '',
        history.get('ayush_specific_history') or ''
    )

    return jsonify({
        "session": session_data,
        "summary": summary_data,
        "history": history,
        "transcripts": transcripts,
        "documents": [dict(d) for d in docs],
        "lab_reports": [dict(l) for l in labs],
        "prescriptions": [dict(r) for r in rxs],
        "coding_suggestions": coding_suggestions,
        "timeline": timeline,
        "previous_review": dict(review) if review else None
    })

@doctor_bp.route('/api/doctor/verify/<int:session_id>', methods=['POST'])
def verify_clinical_history(session_id):
    """
    Final Verification action by the doctor:
    - Saves edited clinical history
    - Records physician ID, doctor notes, and finalized medical codes
    - Marks session as 'verified'
    """
    data = request.get_json() or {}
    doctor_id = data.get('doctor_id', 'DOC-AYUSH-01')
    doctor_name = data.get('doctor_name', 'Dr. Rohan Patel, MD (Ayush)')
    edited_history = data.get('edited_history', '')
    doctor_notes = data.get('doctor_notes', '')
    medical_codes = data.get('medical_codes', [])

    session_data = get_session(session_id)
    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert or update doctor review
        cursor.execute("SELECT id FROM doctor_reviews WHERE session_id = ?", (session_id,))
        existing = cursor.fetchone()

        codes_json = json.dumps(medical_codes) if isinstance(medical_codes, list) else str(medical_codes)

        if existing:
            cursor.execute(
                """
                UPDATE doctor_reviews
                SET doctor_id = ?, doctor_name = ?, edited_history = ?, doctor_notes = ?,
                    medical_codes = ?, verification_status = 'verified', verified_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (doctor_id, doctor_name, edited_history, doctor_notes, codes_json, existing['id'])
            )
        else:
            cursor.execute(
                """
                INSERT INTO doctor_reviews
                (patient_id, session_id, doctor_id, doctor_name, edited_history, doctor_notes, medical_codes, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'verified')
                """,
                (session_data['patient_id'], session_id, doctor_id, doctor_name, edited_history, doctor_notes, codes_json)
            )

        # Mark session as verified
        cursor.execute("UPDATE patient_sessions SET status = 'verified' WHERE id = ?", (session_id,))
        cursor.execute("UPDATE ai_summaries SET verification_status = 'verified', reviewed_by_doctor = 1 WHERE session_id = ?", (session_id,))
        conn.commit()

    return jsonify({
        "status": "success",
        "message": f"Clinical record successfully verified by {doctor_name}."
    })

@doctor_bp.route('/api/doctor/search')
def search_patients():
    """
    Search patients by ABHA ID, name, or phone number.
    Note: Searching by phone may return multiple family members.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"results": []})

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, COUNT(s.id) as visit_count, MAX(s.session_date) as last_visit
            FROM patients p
            LEFT JOIN patient_sessions s ON p.id = s.patient_id
            WHERE p.abha_id LIKE ? OR p.patient_name LIKE ? OR p.phone_number LIKE ?
            GROUP BY p.id
            ORDER BY p.id DESC
            LIMIT 20
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%")
        )
        patients = [dict(r) for r in cursor.fetchall()]

    return jsonify({
        "query": query,
        "note": "A single phone number may belong to multiple family members.",
        "results": patients
    })
