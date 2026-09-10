"""
Ministry of Ayush – Smart MediKiosk
Patient Experience & Case-Taking Routes
Government of India / Bharat • Clinical History Platform
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database.db import (
    get_session,
    get_clinical_history,
    get_patient_history_timeline,
    get_db_connection
)
from services.language_service import SUPPORTED_LANGUAGES, CONSENT_TEXTS, get_bcp47_code
from services.summary_service import generate_clinical_summary

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/consent/<int:session_id>', methods=['GET', 'POST'])
def consent(session_id):
    """Patient consent screen with multilingual options and audio guidance."""
    session_data = get_session(session_id)
    if not session_data:
        flash("Session not found.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        selected_lang = request.form.get('selected_language', 'en')
        consent_given = request.form.get('consent_agreed') == 'yes'

        if not consent_given:
            flash("Consent is required to proceed with clinical history collection.", "warning")
            return render_template('consent.html', session=session_data, languages=SUPPORTED_LANGUAGES, consent_texts=CONSENT_TEXTS)

        # Update session with consent and language
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE patient_sessions SET consent_status = 1, selected_language = ? WHERE id = ?",
                (selected_lang, session_id)
            )
            conn.commit()

        return redirect(url_for('patient.prakriti_ai_kiosk', session_id=session_id))

    return render_template(
        'consent.html',
        session=session_data,
        languages=SUPPORTED_LANGUAGES,
        consent_texts=CONSENT_TEXTS
    )

@patient_bp.route('/prakriti/<int:session_id>')
def prakriti_ai_kiosk(session_id):
    """
    Prakriti-AI Welcome & Case-Taking screen.
    Displays:
    - Patient Name, Age, Gender, ABHA ID, Token, Selected Language
    - Robot Doctor Avatar wearing stethoscope
    - "Your Assistant Doctor"
    - Big START button
    - 🟢 Green active indicator
    - Voice + Text interface
    """
    session_data = get_session(session_id)
    if not session_data:
        flash("Session not found.", "danger")
        return redirect(url_for('auth.login'))

    # Update session status to AI Case Taking if currently Waiting
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE patient_sessions SET status = 'AI Case Taking' WHERE id = ? AND status = 'Waiting'",
            (session_id,)
        )
        conn.commit()

    history = get_clinical_history(session_id) or {}
    bcp47 = get_bcp47_code(session_data.get('selected_language', 'en'))

    return render_template(
        'prakriti_ai.html',
        session=session_data,
        history=history,
        bcp47=bcp47,
        languages=SUPPORTED_LANGUAGES
    )

@patient_bp.route('/summary/<int:session_id>')
def summary_preview(session_id):
    """Patient confirmation and review screen with token, summary view, and edit capabilities."""
    session_data = get_session(session_id)
    if not session_data:
        flash("Session not found.", "danger")
        return redirect(url_for('auth.login'))

    # Mark session status as AI Completed (ready for doctor)
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE patient_sessions SET status = 'AI Completed' WHERE id = ? AND status IN ('Waiting', 'AI Case Taking')",
            (session_id,)
        )
        conn.commit()

    # Generate or refresh AI clinical summary
    summary_result = generate_clinical_summary(session_id)
    history = get_clinical_history(session_id) or {}

    return render_template(
        'summary_preview.html',
        session=session_data,
        summary=summary_result,
        history=history
    )

@patient_bp.route('/api/patient/edit-history/<int:session_id>', methods=['POST'])
def edit_patient_history(session_id):
    """
    Allow patient to review and correct structured history draft before doctor review.
    Original transcript remains strictly unchanged.
    """
    data = request.get_json() or {}
    session_data = get_session(session_id)
    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    # Update structured history fields
    from database.db import update_clinical_history
    update_clinical_history(session_id, data)

    # Regenerate AI summary with the corrected fields
    from services.summary_service import generate_clinical_summary
    new_summary = generate_clinical_summary(session_id)

    return jsonify({
        "status": "success",
        "message": "Clinical information updated successfully.",
        "summary": new_summary
    })

@patient_bp.route('/timeline/<int:patient_id>')
def patient_timeline(patient_id):
    """Retrieve chronological medical history across all visits for a patient."""
    timeline = get_patient_history_timeline(patient_id)
    return render_template('timeline.html', timeline=timeline)

