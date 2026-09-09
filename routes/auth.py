"""
Ministry of Ayush – Smart MediKiosk
Authentication & Registration Routes
Government of India / Bharat • Clinical History Platform

Integrity Rules:
- ABHA ID must be UNIQUE.
- Phone number must NOT be unique (multiple family members can share a phone).
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from database.db import (
    get_patient_by_abha,
    get_patients_by_phone,
    create_patient,
    create_session,
    get_db_connection
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    """Default landing page redirects to login."""
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/auth/check-abha')
def check_abha():
    """Asynchronously check if an ABHA ID already exists for real-time validation."""
    abha_id = request.args.get('abha_id', '').strip().upper()
    if not abha_id or len(abha_id) < 3:
        return jsonify({"exists": False})
    
    patient = get_patient_by_abha(abha_id)
    if patient:
        return jsonify({
            "exists": True,
            "patient_name": patient['patient_name'],
            "message": "Patient already registered. Login instead.",
            "login_url": url_for('auth.login', abha_id=abha_id)
        })
    return jsonify({"exists": False})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Existing patient login with ABHA ID and phone number."""
    prefill_abha = request.args.get('abha_id', '').strip().upper()

    if request.method == 'POST':
        abha_id = request.form.get('abha_id', '').strip().upper()
        phone_number = request.form.get('phone_number', '').strip()

        if not abha_id:
            flash("Please enter your ABHA ID.", "danger")
            return render_template('login.html', abha_id=prefill_abha)

        patient = get_patient_by_abha(abha_id)
        if not patient:
            flash("No registered patient found with this ABHA ID. Please register first.", "warning")
            return render_template('login.html', abha_id=abha_id, phone_number=phone_number)

        # Create session
        session_id, token = create_session(patient['id'])
        session['patient_id'] = patient['id']
        session['session_id'] = session_id
        session['token_number'] = token
        session['patient_name'] = patient['patient_name']

        return redirect(url_for('patient.consent', session_id=session_id))

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """New patient registration with ABHA uniqueness check and shared phone support."""
    if request.method == 'POST':
        name = request.form.get('patient_name', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        abha_id = request.form.get('abha_id', '').strip().upper()
        phone_number = request.form.get('phone_number', '').strip()

        # Validation
        if not name or len(name) < 2:
            flash("Please enter a valid patient name.", "danger")
            return render_template('register.html', **request.form)

        try:
            age_int = int(age)
            if age_int < 0 or age_int > 125:
                raise ValueError
        except ValueError:
            flash("Please enter a reasonable age (0 to 125).", "danger")
            return render_template('register.html', **request.form)

        if not gender:
            flash("Please select patient gender.", "danger")
            return render_template('register.html', **request.form)

        if not abha_id or len(abha_id) < 4:
            flash("Please provide a valid ABHA ID.", "danger")
            return render_template('register.html', **request.form)

        if not phone_number or len(phone_number) < 10:
            flash("Please enter a valid 10-digit phone number.", "danger")
            return render_template('register.html', **request.form)

        # Check ABHA uniqueness
        existing_patient = get_patient_by_abha(abha_id)
        if existing_patient:
            flash("Patient already registered. Login instead.", "warning")
            return redirect(url_for('auth.login', abha_id=abha_id))

        # Register patient (Phone number uniqueness is NOT checked by design)
        try:
            patient_id = create_patient(name, age_int, gender, abha_id, phone_number)
            session_id, token = create_session(patient_id)

            session['patient_id'] = patient_id
            session['session_id'] = session_id
            session['token_number'] = token
            session['patient_name'] = name

            flash("Registration successful! Welcome to Smart MediKiosk.", "success")
            return redirect(url_for('patient.consent', session_id=session_id))
        except sqlite3.IntegrityError:
            flash("Patient already registered. Login instead.", "warning")
            return redirect(url_for('auth.login', abha_id=abha_id))
        except Exception as e:
            flash(f"Registration error: {str(e)}", "danger")
            return render_template('register.html', **request.form)

    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Session ended securely.", "info")
    return redirect(url_for('auth.login'))
