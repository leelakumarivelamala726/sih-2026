# Ministry of Ayush – Smart MediKiosk (Prakriti-AI)
### Government of India / Bharat • Clinical History Platform

A complete, clean, functional AI-assisted clinical history-taking and document-scanning kiosk platform.

---

## 🚀 Live Access URLs
- **Smart MediKiosk (Patient Case-Taking Portal)**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Doctor Dashboard (Clinical Consultation Console)**: [http://127.0.0.1:5000/doctor](http://127.0.0.1:5000/doctor)

---

## 🛠️ How to Run Locally

1. **Activate Environment & Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Train / Evaluate Prakriti-AI Model**:
   ```bash
   python train_model.py
   ```

3. **Start the Flask Server**:
   ```bash
   python app.py
   ```

4. **Run Verification Test Suite**:
   ```bash
   python test_services.py
   ```

---

## 📋 Core Architectural Principles
- **ABHA ID**: Strictly **UNIQUE** in database.
- **Phone Number**: **NOT UNIQUE** (multiple family members can register with the same phone number).
- **AI Safety**: Prakriti-AI collects, structures, and summarizes history. It **NEVER** diagnoses or prescribes medicines.
- **Doctor Verification**: The physician reviews, edits, assigns medical codes (ICD-10 / NAMASTE Ayush), and verifies the final record.
- **Prescriptions**: Extracted prescriptions are strictly marked as *Historical Documents* and never converted into new prescriptions.
- **Regional Languages**: Understands 11 Indian languages and regional dialects/slangs (e.g. Telangana, Rayalaseema, and Coastal Andhra Telugu variations) while preserving verbatim original transcripts.
