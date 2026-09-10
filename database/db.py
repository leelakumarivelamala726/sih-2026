import sqlite3
import os
import json
from datetime import datetime

DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'medikiosk.db'))

def get_db_connection():
    """Get a SQLite database connection with row factory enabled."""
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

from werkzeug.security import generate_password_hash, check_password_hash

def init_db():
    """Initialize database tables using schema.sql and apply any missing column migrations."""
    schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    with get_db_connection() as conn:
        conn.executescript(schema_sql)
        # Check and add any missing AYUSH columns to clinical_history
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(clinical_history)")
        existing_cols = {row['name'] for row in cursor.fetchall()}
        
        ayush_cols = [
            'prakriti', 'vikriti', 'dosha', 'agni', 'ama',
            'koshta', 'nidra', 'ahara', 'vihara', 'manasika', 'appetite'
        ]
        for col in ayush_cols:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE clinical_history ADD COLUMN {col} TEXT")
        
        # Ensure doctors table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_name TEXT NOT NULL,
                doctor_id TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_doctor_id ON doctors(doctor_id)")
        conn.commit()
    print("[DB] MediKiosk database initialized and migrated successfully.")

def dict_from_row(row):
    """Convert sqlite3.Row to python dict."""
    if row is None:
        return None
    return dict(row)

# Doctor Management and Authentication Helpers

def create_doctor(doctor_name, doctor_id, password):
    """Register a new doctor with securely hashed password."""
    doctor_id = doctor_id.strip().upper()
    doctor_name = doctor_name.strip()
    if not doctor_name or not doctor_id or not password:
        raise ValueError("All doctor registration fields are required.")
    
    password_hash = generate_password_hash(password)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO doctors (doctor_name, doctor_id, password_hash)
            VALUES (?, ?, ?)
            """,
            (doctor_name, doctor_id, password_hash)
        )
        conn.commit()
        return cursor.lastrowid

def get_doctor_by_id(doctor_id):
    """Fetch doctor account by unique doctor_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id.strip().upper(),))
        row = cursor.fetchone()
        return dict_from_row(row)

def verify_doctor_password(doctor_id, password):
    """Verify credentials for doctor login."""
    doctor = get_doctor_by_id(doctor_id)
    if not doctor:
        return None
    if check_password_hash(doctor['password_hash'], password):
        return doctor
    return None

# Helper functions for common patient queries

def get_patient_by_abha(abha_id):
    """Fetch patient by unique ABHA ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE abha_id = ?", (abha_id.strip(),))
        row = cursor.fetchone()
        return dict_from_row(row)

def get_patients_by_phone(phone_number):
    """Fetch all patients sharing a phone number (family members)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE phone_number = ? ORDER BY created_at DESC", (phone_number.strip(),))
        rows = cursor.fetchall()
        return [dict_from_row(r) for r in rows]

def create_patient(name, age, gender, abha_id, phone_number):
    """Register a new patient. ABHA must be unique. Phone is NOT unique."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO patients (patient_name, age, gender, abha_id, phone_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), int(age), gender.strip(), abha_id.strip().upper(), phone_number.strip())
        )
        conn.commit()
        return cursor.lastrowid

def generate_unique_token(cursor):
    """
    Generate a monotonic, database-unique token for every new visit/session (e.g. TK-201, TK-202...).
    Checks all existing tokens in patient_sessions and finds the maximum numerical token suffix,
    starting from 200 so new visits start at TK-201.
    Never resets daily, never reuses a token, and assigns a new token per visit even for the same patient.
    """
    cursor.execute("SELECT token_number FROM patient_sessions WHERE token_number LIKE 'TK-%'")
    rows = cursor.fetchall()
    max_num = 200  # Default base so new tokens start at TK-201
    for r in rows:
        tok = r[0] if isinstance(r, (tuple, list)) else r['token_number']
        if tok and '-' in tok:
            parts = tok.split('-')
            if len(parts) == 2 and parts[1].isdigit():
                val = int(parts[1])
                if val > max_num:
                    max_num = val

    next_num = max_num + 1
    while True:
        candidate_token = f"TK-{next_num}"
        cursor.execute("SELECT 1 FROM patient_sessions WHERE token_number = ?", (candidate_token,))
        if not cursor.fetchone():
            return candidate_token
        next_num += 1

def create_session(patient_id, language='en'):
    """Create a new session with an autogenerated unique monotonic token."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        token = generate_unique_token(cursor)
        
        cursor.execute(
            """
            INSERT INTO patient_sessions (patient_id, token_number, selected_language, status)
            VALUES (?, ?, ?, 'Waiting')
            """,
            (patient_id, token, language)
        )
        session_id = cursor.lastrowid
        
        # Initialize empty clinical history record for this session
        cursor.execute(
            """
            INSERT INTO clinical_history (patient_id, session_id)
            VALUES (?, ?)
            """,
            (patient_id, session_id)
        )
        conn.commit()
        return session_id, token

def update_session_status(session_id, status):
    """Update status of a patient session (e.g. 'Waiting', 'AI Case Taking', 'AI Completed', 'With Doctor', 'Completed')."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE patient_sessions SET status = ? WHERE id = ?", (status, session_id))
        conn.commit()

def get_session(session_id):
    """Fetch session with patient details."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.*, p.patient_name, p.age, p.gender, p.abha_id, p.phone_number
            FROM patient_sessions s
            JOIN patients p ON s.patient_id = p.id
            WHERE s.id = ?
            """,
            (session_id,)
        )
        return dict_from_row(cursor.fetchone())

def add_transcript(patient_id, session_id, speaker, language, original_text, translated_text=None):
    """Store verbatim transcript entry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO transcripts (patient_id, session_id, speaker, language, original_transcript, translated_transcript)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_id, session_id, speaker, language, original_text, translated_text)
        )
        conn.commit()
        return cursor.lastrowid

def get_transcripts_for_session(session_id):
    """Retrieve full verbatim dialogue for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transcripts WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        return [dict_from_row(r) for r in cursor.fetchall()]

def update_clinical_history(session_id, updates: dict):
    """Update fields of clinical history for a session."""
    valid_fields = [
        'chief_complaint', 'history_of_present_illness', 'onset', 'duration',
        'severity', 'location', 'associated_symptoms', 'aggravating_factors',
        'relieving_factors', 'past_medical_history', 'past_surgical_history',
        'medication_history', 'allergy_history', 'family_history', 'personal_history',
        'diet', 'lifestyle', 'sleep', 'bowel_habits', 'review_of_systems',
        'ayush_specific_history', 'prakriti', 'vikriti', 'dosha', 'agni', 'ama',
        'koshta', 'nidra', 'ahara', 'vihara', 'manasika', 'appetite',
        'red_flags', 'other_relevant_information'
    ]
    set_clauses = []
    values = []
    for k, v in updates.items():
        if k in valid_fields:
            set_clauses.append(f"{k} = ?")
            values.append(v if not isinstance(v, (dict, list)) else json.dumps(v))
    
    if not set_clauses:
        return
    
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE clinical_history SET {', '.join(set_clauses)} WHERE session_id = ?"
    values.append(session_id)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(values))
        conn.commit()

def get_clinical_history(session_id):
    """Get clinical history for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clinical_history WHERE session_id = ?", (session_id,))
        return dict_from_row(cursor.fetchone())

def get_patient_history_timeline(patient_id):
    """Fetch complete chronological medical timeline for a patient across all visits."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.id as session_id, s.token_number, s.session_date, s.status, s.priority_level,
                   h.chief_complaint, h.history_of_present_illness, h.ayush_specific_history,
                   a.summary as ai_summary,
                   r.edited_history, r.medical_codes, r.doctor_notes, r.doctor_name, r.verified_at
            FROM patient_sessions s
            LEFT JOIN clinical_history h ON s.id = h.session_id
            LEFT JOIN ai_summaries a ON s.id = a.session_id
            LEFT JOIN doctor_reviews r ON s.id = r.session_id
            WHERE s.patient_id = ?
            ORDER BY s.session_date DESC
            """,
            (patient_id,)
        )
        return [dict_from_row(r) for r in cursor.fetchall()]
