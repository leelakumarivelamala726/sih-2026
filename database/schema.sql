-- Ministry of Ayush – Smart MediKiosk Database Schema
-- Government of India / Bharat • Patient Case-Taking Software

PRAGMA foreign_keys = ON;

-- Patients Table
-- Crucial rule: abha_id is UNIQUE, phone_number is NOT UNIQUE (shared by families)
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    abha_id TEXT UNIQUE NOT NULL,
    phone_number TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Patient Sessions Table
CREATE TABLE IF NOT EXISTS patient_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    token_number TEXT NOT NULL,
    session_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    selected_language TEXT DEFAULT 'en',
    consent_status INTEGER DEFAULT 0,
    priority_level TEXT DEFAULT 'normal', -- 'normal', 'urgent' (triggered by red-flag detector)
    status TEXT DEFAULT 'in_progress',    -- 'in_progress', 'ready_for_doctor', 'verified'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- Clinical History Table (Detailed Structured Clinical History + AYUSH specifics)
CREATE TABLE IF NOT EXISTS clinical_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    chief_complaint TEXT,
    history_of_present_illness TEXT,
    onset TEXT,
    duration TEXT,
    severity TEXT,
    location TEXT,
    associated_symptoms TEXT,
    aggravating_factors TEXT,
    relieving_factors TEXT,
    past_medical_history TEXT,
    past_surgical_history TEXT,
    medication_history TEXT,
    allergy_history TEXT,
    family_history TEXT,
    personal_history TEXT,
    diet TEXT,
    lifestyle TEXT,
    sleep TEXT,
    bowel_habits TEXT,
    review_of_systems TEXT,
    ayush_specific_history TEXT, -- Comprehensive Ayurvedic summary
    prakriti TEXT,               -- Vata, Pitta, Kapha constitutional assessment
    vikriti TEXT,                -- Current dosha imbalance
    dosha TEXT,                  -- Primary dosha involved
    agni TEXT,                   -- Mandagni, Tikshnagni, Vishamagni, Samagni
    ama TEXT,                    -- Presence of metabolic toxins (Sama / Nirama)
    koshta TEXT,                 -- Krura, Mridu, Madhyama
    nidra TEXT,                  -- Sleep quality, duration, disturbances
    ahara TEXT,                  -- Dietary habits, tastes, timings
    vihara TEXT,                 -- Physical routine, exercise, exertion
    manasika TEXT,               -- Mental factors, stress, emotions
    appetite TEXT,               -- Appetite status
    red_flags TEXT,              -- JSON array of urgent safety alerts detected
    other_relevant_information TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Transcripts Table (Never overwrite original patient statements)
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    speaker TEXT NOT NULL, -- 'patient' or 'ai'
    language TEXT NOT NULL,
    original_transcript TEXT NOT NULL,
    translated_transcript TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Medical Documents Table (Scanned Prescriptions & Lab Reports via Webcam/Upload)
CREATE TABLE IF NOT EXISTS medical_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    document_type TEXT NOT NULL, -- 'prescription', 'lab_report', 'discharge_summary', 'other'
    file_path TEXT NOT NULL,
    ocr_text TEXT,
    extracted_information TEXT, -- Structured JSON of extracted clinical entities
    ocr_confidence TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
    document_date TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Lab Reports Table (Individual test parameters, values, and flags)
CREATE TABLE IF NOT EXISTS lab_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    document_id INTEGER,
    session_id INTEGER,
    test_name TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT,
    reference_range TEXT,
    abnormal_flag INTEGER DEFAULT 0, -- 0: normal, 1: abnormal for doctor alert
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES medical_documents(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Historical Prescriptions Table (Previous Prescriptions Extracted - NEVER a new prescription)
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    document_id INTEGER,
    session_id INTEGER,
    medicine_name TEXT NOT NULL,
    strength TEXT,
    dosage TEXT,
    frequency TEXT,
    duration TEXT,
    doctor_hospital_info TEXT,
    is_historical INTEGER DEFAULT 1, -- ALWAYS 1: historical document extraction only
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES medical_documents(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- AI Summaries Table
CREATE TABLE IF NOT EXISTS ai_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    summary TEXT NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_by_doctor INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT 'pending_verification', -- 'pending_verification', 'verified', 'edited_and_verified'
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Doctor Reviews & Verification Table
CREATE TABLE IF NOT EXISTS doctor_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    doctor_id TEXT DEFAULT 'DOC-AYUSH-01',
    doctor_name TEXT DEFAULT 'Dr. Rohan Patel, MD (Ayush)',
    edited_history TEXT,
    medical_codes TEXT, -- JSON array of ICD-10 / NAMASTE Ayush codes
    verification_status TEXT DEFAULT 'verified',
    doctor_notes TEXT,
    verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES patient_sessions(id) ON DELETE CASCADE
);

-- Indexes for fast patient lookup and doctor dashboard queries
CREATE INDEX IF NOT EXISTS idx_patients_abha ON patients(abha_id);
CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone_number);
CREATE INDEX IF NOT EXISTS idx_sessions_patient ON patient_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON patient_sessions(status);
CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id);
