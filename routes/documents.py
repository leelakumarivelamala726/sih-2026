"""
Ministry of Ayush – Smart MediKiosk
Document Scanning & OCR Routes
Government of India / Bharat • Clinical History Platform
"""

import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, send_from_directory
from database.db import get_session, get_db_connection
from services.ocr_service import process_scanned_document, save_base64_image

documents_bp = Blueprint('documents', __name__)

@documents_bp.route('/scanner/<int:session_id>')
def scanner_view(session_id):
    """Webcam document scanner and OCR review interface."""
    session_data = get_session(session_id)
    if not session_data:
        return redirect(url_for('auth.login'))

    # Fetch already scanned documents for this session
    with get_db_connection() as conn:
        docs = conn.execute(
            "SELECT * FROM medical_documents WHERE session_id = ? ORDER BY id DESC",
            (session_id,)
        ).fetchall()
        documents = [dict(d) for d in docs]

    return render_template('scanner.html', session=session_data, documents=documents)

@documents_bp.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """
    Handle webcam snapshot (base64) or file upload, run preprocessing,
    extract clinical entities (labs & historical Rx), and store in database.
    """
    session_id = request.form.get('session_id') or request.json.get('session_id')
    raw_ocr_text = request.form.get('ocr_text') or (request.json.get('ocr_text') if request.is_json else "")

    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    session_data = get_session(int(session_id))
    if not session_data:
        return jsonify({"error": "Invalid session"}), 404

    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    # Check for base64 webcam capture
    image_path = None
    if request.is_json and request.json.get('image_base64'):
        base64_data = request.json.get('image_base64')
        image_path = save_base64_image(base64_data, upload_dir, filename_prefix=f"scan_s{session_id}")
    elif 'file' in request.files:
        file = request.files['file']
        if file.filename:
            import time
            from werkzeug.utils import secure_filename
            safe_name = f"scan_s{session_id}_{int(time.time())}_{secure_filename(file.filename)}"
            image_path = os.path.join(upload_dir, safe_name)
            file.save(image_path)

    if not image_path:
        return jsonify({"error": "No image data provided"}), 400

    # Execute OCR and clinical entity extraction pipeline
    result = process_scanned_document(
        patient_id=session_data['patient_id'],
        session_id=int(session_id),
        image_path=image_path,
        ocr_raw_text=raw_ocr_text
    )

    # Relative path for frontend preview
    result["image_url"] = f"/uploads/{os.path.basename(image_path)}"
    return jsonify(result)

@documents_bp.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded document images."""
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(upload_dir, filename)
