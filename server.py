"""
Ministry of Ayush – Smart MediKiosk
Main Flask Application Server
Government of India / Bharat • Clinical History Platform
"""

import os
import sys
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Database
from database.db import init_db

# Import Blueprints
from routes.auth import auth_bp
from routes.patient import patient_bp
from routes.ai import ai_bp
from routes.documents import documents_bp
from routes.doctor import doctor_bp

# Initialize Flask application correctly exposed for WSGI servers (Gunicorn)
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ayush-smart-medikiosk-secret-key-2026")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize SQLite database
init_db()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(patient_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(doctor_bp)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("login.html", error="The requested page was not found."), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error", "details": str(e)}), 500

def create_app():
    return app

if __name__ == "__main__":
    # Render binds dynamic port via the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    print("==================================================")
    print("MINISTRY OF AYUSH – SMART MEDIKIOSK")
    print("Prakriti-AI Clinical Platform Online")
    print(f"Port:        {port}")
    print(f"Kiosk URL:   http://127.0.0.1:{port}")
    print(f"Doctor URL:  http://127.0.0.1:{port}/doctor")
    print("==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
