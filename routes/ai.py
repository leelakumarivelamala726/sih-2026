"""
Ministry of Ayush – Smart MediKiosk
Prakriti-AI Real-time API Routes
Government of India / Bharat • Clinical History Platform
"""

from flask import Blueprint, request, jsonify
from database.db import get_session, get_transcripts_for_session, get_clinical_history
from services.ai_service import process_patient_turn

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """
    Handle one turn of patient-AI conversation (text or transcribed voice).
    Calls the adaptive questioning engine, evaluates red flags,
    records transcripts verbatim, and updates structured history.
    """
    data = request.get_json() or {}
    session_id = data.get('session_id')
    patient_input = data.get('message', '').strip()
    language = data.get('language', 'en')

    if not session_id or not patient_input:
        return jsonify({"error": "Missing session_id or message"}), 400

    session_data = get_session(session_id)
    if not session_data:
        return jsonify({"error": "Invalid session"}), 404

    result = process_patient_turn(
        session_id=session_id,
        patient_id=session_data['patient_id'],
        patient_input=patient_input,
        language=language
    )

    return jsonify(result)

@ai_bp.route('/api/ai/transcripts/<int:session_id>')
def session_transcripts(session_id):
    """Retrieve full verbatim transcripts for a session."""
    transcripts = get_transcripts_for_session(session_id)
    return jsonify({"transcripts": transcripts})

@ai_bp.route('/api/ai/history/<int:session_id>')
def session_history(session_id):
    """Retrieve structured clinical history for a session."""
    history = get_clinical_history(session_id)
    return jsonify({"clinical_history": history})
