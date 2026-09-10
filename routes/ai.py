"""
Ministry of Ayush – Smart MediKiosk
Prakriti-AI Real-time API Routes
Government of India / Bharat • Clinical History Platform
"""

from flask import Blueprint, request, jsonify
from database.db import get_session, get_transcripts_for_session, get_clinical_history
from services.ai_service import process_patient_turn, check_live_ai_status

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/api/ai/status')
def ai_status():
    """Securely report live AI connection status without exposing the API key."""
    return jsonify(check_live_ai_status())

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

@ai_bp.route('/api/ai/summary', methods=['GET', 'POST'])
@ai_bp.route('/api/ai/summary/<int:session_id>', methods=['GET', 'POST'])
def ai_summary(session_id=None):
    """
    Generate or retrieve structured clinical AI summary for a patient session.
    Accepts session_id via URL parameter, JSON body, or query param.
    Supports force_refresh flag to recompile live AI draft if requested.
    """
    if session_id is None:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            force_refresh = bool(data.get('force_refresh', False))
        else:
            session_id = request.args.get('session_id', type=int)
            force_refresh = request.args.get('force_refresh', '0').lower() in ('1', 'true', 'yes')
    else:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            force_refresh = bool(data.get('force_refresh', False))
        else:
            force_refresh = request.args.get('force_refresh', '0').lower() in ('1', 'true', 'yes')

    if not session_id:
        return jsonify({"status": "error", "message": "Missing session_id parameter."}), 400

    from services.summary_service import generate_clinical_summary
    result = generate_clinical_summary(session_id, force_refresh=force_refresh)
    if result.get("status") == "error":
        return jsonify(result), 404
    return jsonify(result), 200
