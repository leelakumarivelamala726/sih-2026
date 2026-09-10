"""
Ministry of Ayush – Smart MediKiosk
Doctor Dashboard & Verification Routes
Government of India / Bharat • Clinical History Platform

Safety Rule:
AI Summary is a draft. The qualified doctor must review, edit, code, and verify.
"""

import json
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from database.db import (
    get_db_connection,
    get_session,
    get_clinical_history,
    get_transcripts_for_session,
    get_patient_history_timeline,
    create_doctor,
    get_doctor_by_id,
    verify_doctor_password,
    update_session_status
)
from services.summary_service import (
    generate_clinical_summary,
    suggest_medical_codes,
    build_structured_clinical_summary_payload
)

doctor_bp = Blueprint('doctor', __name__)

def doctor_required(f):
    """Decorator to require doctor authentication for protected doctor routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('doctor_logged_in'):
            if request.path.startswith('/api/doctor/'):
                return jsonify({"error": "Unauthorized. Doctor authentication required."}), 401
            flash("Please log in with your Doctor credentials to access the Doctor Portal.", "warning")
            return redirect(url_for('doctor.doctor_login'))
        return f(*args, **kwargs)
    return decorated_function

@doctor_bp.route('/doctor/register', methods=['GET', 'POST'])
def doctor_register():
    """Dedicated Doctor Registration Flow."""
    if session.get('doctor_logged_in'):
        return redirect(url_for('doctor.dashboard'))

    if request.method == 'POST':
        doctor_name = request.form.get('doctor_name', '').strip()
        doctor_id = request.form.get('doctor_id', '').strip().upper()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # All fields are mandatory
        if not doctor_name or not doctor_id or not password or not confirm_password:
            flash("All fields are mandatory. Please fill in Doctor Name, Doctor ID, and Passwords.", "danger")
            return render_template('doctor_register.html', doctor_name=doctor_name, doctor_id=doctor_id)

        if len(doctor_id) < 3:
            flash("Doctor ID must be at least 3 characters long.", "danger")
            return render_template('doctor_register.html', doctor_name=doctor_name, doctor_id=doctor_id)

        if len(password) < 4:
            flash("Password must be at least 4 characters long.", "danger")
            return render_template('doctor_register.html', doctor_name=doctor_name, doctor_id=doctor_id)

        if password != confirm_password:
            flash("Password and Confirm Password do not match. Please re-enter.", "danger")
            return render_template('doctor_register.html', doctor_name=doctor_name, doctor_id=doctor_id)

        # Validate unique Doctor ID
        existing = get_doctor_by_id(doctor_id)
        if existing:
            flash(f"Doctor ID '{doctor_id}' is already registered. Please log in instead.", "warning")
            return redirect(url_for('doctor.doctor_login', doctor_id=doctor_id))

        try:
            create_doctor(doctor_name, doctor_id, password)
            flash(f"Registration successful! Welcome Dr. {doctor_name}. Please log in with your credentials.", "success")
            return redirect(url_for('doctor.doctor_login', doctor_id=doctor_id))
        except Exception as e:
            flash(f"Registration error: {str(e)}", "danger")
            return render_template('doctor_register.html', doctor_name=doctor_name, doctor_id=doctor_id)

    return render_template('doctor_register.html')

@doctor_bp.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    """Dedicated Doctor Login Flow."""
    if session.get('doctor_logged_in'):
        return redirect(url_for('doctor.dashboard'))

    prefill_id = request.args.get('doctor_id', '').strip().upper()

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id', '').strip().upper()
        password = request.form.get('password', '')

        if not doctor_id or not password:
            flash("Please enter both Doctor ID and Password.", "danger")
            return render_template('doctor_login.html', doctor_id=doctor_id)

        doctor = verify_doctor_password(doctor_id, password)
        if not doctor:
            flash("Invalid Doctor ID or password. Please verify your credentials.", "danger")
            return render_template('doctor_login.html', doctor_id=doctor_id)

        # Independent Doctor Session
        session['doctor_logged_in'] = True
        session['doctor_id'] = doctor['doctor_id']
        session['doctor_name'] = doctor['doctor_name']

        flash(f"Welcome back, Dr. {doctor['doctor_name']}!", "success")
        return redirect(url_for('doctor.dashboard'))

    return render_template('doctor_login.html', doctor_id=prefill_id)

@doctor_bp.route('/doctor/logout')
def doctor_logout():
    """Log out from Doctor portal without affecting patient session."""
    session.pop('doctor_logged_in', None)
    session.pop('doctor_id', None)
    session.pop('doctor_name', None)
    flash("Doctor session ended securely.", "info")
    return redirect(url_for('doctor.doctor_login'))

@doctor_bp.route('/doctor/waiting-list')
@doctor_required
def waiting_list():
    """Dedicated Patient Waiting List Page."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id as session_id, s.token_number, s.session_date, s.status, s.priority_level,
                   p.id as patient_id, p.patient_name, p.age, p.gender, p.abha_id, p.phone_number,
                   h.chief_complaint, h.red_flags,
                   (SELECT COUNT(*) FROM transcripts t WHERE t.session_id = s.id AND t.speaker = 'ai') as ai_questions_count
            FROM patient_sessions s
            JOIN patients p ON s.patient_id = p.id
            LEFT JOIN clinical_history h ON s.id = h.session_id
            ORDER BY
                CASE WHEN s.priority_level = 'urgent' THEN 0 ELSE 1 END,
                CASE 
                    WHEN s.status = 'AI Completed' THEN 0
                    WHEN s.status = 'Waiting' THEN 1
                    WHEN s.status = 'AI Case Taking' THEN 2
                    WHEN s.status = 'With Doctor' THEN 3
                    ELSE 4
                END,
                s.id DESC
            """
        ).fetchall()
        patients = [dict(r) for r in rows]

    return render_template(
        'waiting_list.html',
        patients=patients,
        doctor_name=session.get('doctor_name', 'Doctor'),
        doctor_id=session.get('doctor_id', 'DOC-01')
    )

@doctor_bp.route('/api/doctor/waiting-list')
@doctor_required
def api_waiting_list():
    """API endpoint for live auto-refresh of the patient waiting list."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id as session_id, s.token_number, s.session_date, s.status, s.priority_level,
                   p.id as patient_id, p.patient_name, p.age, p.gender, p.abha_id, p.phone_number,
                   h.chief_complaint, h.red_flags,
                   (SELECT COUNT(*) FROM transcripts t WHERE t.session_id = s.id AND t.speaker = 'ai') as ai_questions_count
            FROM patient_sessions s
            JOIN patients p ON s.patient_id = p.id
            LEFT JOIN clinical_history h ON s.id = h.session_id
            ORDER BY
                CASE WHEN s.priority_level = 'urgent' THEN 0 ELSE 1 END,
                CASE 
                    WHEN s.status = 'AI Completed' THEN 0
                    WHEN s.status = 'Waiting' THEN 1
                    WHEN s.status = 'AI Case Taking' THEN 2
                    WHEN s.status = 'With Doctor' THEN 3
                    ELSE 4
                END,
                s.id DESC
            """
        ).fetchall()
        return jsonify({"waiting_list": [dict(r) for r in rows]})

@doctor_bp.route('/doctor')
@doctor_required
def dashboard():
    """Doctor Dashboard main consultation console."""
    active_session_id = request.args.get('session_id', type=int)
    if active_session_id:
        update_session_status(active_session_id, 'With Doctor')

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

    return render_template(
        'doctor_dashboard.html',
        queue=patient_queue,
        active_session_id=active_session_id,
        doctor_name=session.get('doctor_name', 'Dr. Rohan Patel, MD (Ayush)'),
        doctor_id=session.get('doctor_id', 'DOC-AYUSH-01')
    )

@doctor_bp.route('/api/doctor/queue')
@doctor_required
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
@doctor_required
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

    structured_summary = build_structured_clinical_summary_payload(session_id)

    return jsonify({
        "session": session_data,
        "summary": summary_data,
        "clinical_summary": structured_summary,
        "history": history,
        "transcripts": transcripts,
        "documents": [dict(d) for d in docs],
        "lab_reports": [dict(l) for l in labs],
        "labs": [dict(l) for l in labs],
        "prescriptions": [dict(r) for r in rxs],
        "coding_suggestions": coding_suggestions,
        "timeline": timeline,
        "previous_review": dict(review) if review else None
    })

@doctor_bp.route('/api/doctor/patient/<int:patient_id>/clinical-summary', methods=['GET'])
@doctor_required
def get_patient_clinical_summary(patient_id):
    """
    Retrieve structured clinical summary for a patient:
    Accepts optional ?session_id=<id> query parameter; otherwise selects the patient's latest session.
    """
    target_session_id = request.args.get('session_id')
    if not target_session_id:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id FROM patient_sessions WHERE patient_id = ? ORDER BY id DESC LIMIT 1",
                (patient_id,)
            ).fetchone()
            if not row:
                return jsonify({"error": f"No clinical session found for patient ID {patient_id}"}), 404
            target_session_id = row['id']
    else:
        try:
            target_session_id = int(target_session_id)
        except ValueError:
            return jsonify({"error": "Invalid session_id parameter"}), 400

    summary_payload = build_structured_clinical_summary_payload(target_session_id)
    if not summary_payload:
        return jsonify({"error": f"Clinical summary not found for session {target_session_id}"}), 404
    return jsonify(summary_payload)

@doctor_bp.route('/api/doctor/session/<int:session_id>/clinical-summary', methods=['GET'])
@doctor_required
def get_session_clinical_summary(session_id):
    """Retrieve structured clinical summary directly by session ID."""
    summary_payload = build_structured_clinical_summary_payload(session_id)
    if not summary_payload:
        return jsonify({"error": f"Clinical summary not found for session {session_id}"}), 404
    return jsonify(summary_payload)

@doctor_bp.route('/api/doctor/summary/<int:session_id>', methods=['GET', 'POST'])
@doctor_required
def doctor_patient_summary(session_id):
    """Retrieve or refresh AI clinical summary for a patient."""
    force_refresh = False
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        force_refresh = bool(data.get('force_refresh', False))
    else:
        force_refresh = request.args.get('force_refresh', '0').lower() in ('1', 'true', 'yes')

    res = generate_clinical_summary(session_id, force_refresh=force_refresh)
    if res.get('status') == 'error':
        return jsonify(res), 404
    return jsonify(res)

@doctor_bp.route('/api/doctor/verify/<int:session_id>', methods=['POST'])
@doctor_required
def verify_clinical_history(session_id):
    """
    Final Verification action by the doctor:
    - Saves edited clinical history
    - Records physician ID, doctor notes, and finalized medical codes
    - Marks session as 'Completed' and verification_status as 'verified'
    """
    data = request.get_json() or {}
    doctor_id = session.get('doctor_id') or data.get('doctor_id', 'DOC-AYUSH-01')
    doctor_name = session.get('doctor_name') or data.get('doctor_name', 'Dr. Rohan Patel, MD (Ayush)')
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

        # Mark session as Completed and verified
        cursor.execute("UPDATE patient_sessions SET status = 'Completed' WHERE id = ?", (session_id,))
        cursor.execute("UPDATE ai_summaries SET verification_status = 'verified', reviewed_by_doctor = 1 WHERE session_id = ?", (session_id,))
        conn.commit()

    return jsonify({
        "status": "success",
        "message": f"Clinical record successfully verified by {doctor_name}."
    })

@doctor_bp.route('/api/doctor/search')
@doctor_required
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
