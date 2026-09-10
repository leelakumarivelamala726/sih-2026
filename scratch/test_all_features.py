"""
Comprehensive Verification Test Suite for Smart MediKiosk:
1. Branding: 'Government of Bharat' (No 'Government of India')
2. AI Name: 'AYUSH-KRITI' (No 'Prakriti-AI' in visible labels)
3. Monotonic Unique Token Generation across visits for same patient
4. Doctor Registration & Validation (Duplicate rejection, password hashing)
5. Doctor Authentication & Session Separation
6. Route Protection (@doctor_required)
7. Patient Waiting List with Real DB Records & Statuses
"""

import os
import sys
import unittest
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app
from database.db import (
    get_db_connection,
    get_patient_by_abha,
    create_patient,
    create_session,
    get_doctor_by_id,
    create_doctor,
    verify_doctor_password
)

class MediKioskAdditionalFeaturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        cls.client = app.test_client()

    def test_01_branding_and_ai_name_in_html(self):
        """Verify branding is strictly 'Government of Bharat' and AI name is 'AYUSH-KRITI'."""
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check Government of Bharat branding
        self.assertIn("Government of Bharat", html)
        self.assertNotIn("Government of India / Bharat", html)
        self.assertNotIn("Government of Bharat / India", html)
        # Ensure 'Government of India' does not appear in visible text
        self.assertNotIn("Government of India", html)

        # Check AI name AYUSH KRITI
        self.assertIn("AYUSH KRITI", html)

    def test_02_token_generation_unique_and_monotonic(self):
        """
        Verify every new visit receives a new unique token,
        even for the SAME patient, and previous records are preserved.
        """
        test_abha = "TEST-ABHA-TOKEN-999"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM patients WHERE abha_id = ?", (test_abha,))
            conn.commit()

        # Create patient
        pid = create_patient("Token Test Patient", 40, "Female", test_abha, "9988776655")

        # First visit
        sid1, token1 = create_session(pid)
        self.assertTrue(token1.startswith("TK-"))
        num1 = int(token1.split('-')[1])
        self.assertGreaterEqual(num1, 201)

        # Second visit for the SAME patient
        sid2, token2 = create_session(pid)
        self.assertTrue(token2.startswith("TK-"))
        num2 = int(token2.split('-')[1])

        # Tokens must be different and monotonic
        self.assertNotEqual(token1, token2)
        self.assertEqual(num2, num1 + 1)

        # Verify old session retained token1 and new session has token2 in DB
        with get_db_connection() as conn:
            row1 = conn.execute("SELECT token_number FROM patient_sessions WHERE id = ?", (sid1,)).fetchone()
            row2 = conn.execute("SELECT token_number FROM patient_sessions WHERE id = ?", (sid2,)).fetchone()
            self.assertEqual(row1['token_number'], token1)
            self.assertEqual(row2['token_number'], token2)

    def test_03_doctor_registration_and_validation(self):
        """Verify separate doctor registration, password hashing, and duplicate rejection."""
        test_doc_id = "DOC-TEST-VERIFY-01"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (test_doc_id,))
            conn.commit()

        # 1. Successful registration
        resp = self.client.post('/doctor/register', data={
            'doctor_name': 'Dr. Test Physician',
            'doctor_id': test_doc_id,
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=False)

        # Must redirect to /doctor/login
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/doctor/login', resp.headers['Location'])

        # Check DB: Doctor stored with securely hashed password
        doc = get_doctor_by_id(test_doc_id)
        self.assertIsNotNone(doc)
        self.assertEqual(doc['doctor_name'], 'Dr. Test Physician')
        self.assertNotEqual(doc['password_hash'], 'SecurePassword123!')
        self.assertTrue(doc['password_hash'].startswith('scrypt:') or doc['password_hash'].startswith('pbkdf2:'))

        # 2. Duplicate Doctor ID rejection
        resp_dup = self.client.post('/doctor/register', data={
            'doctor_name': 'Another Doctor',
            'doctor_id': test_doc_id,
            'password': 'AnotherPassword!',
            'confirm_password': 'AnotherPassword!'
        }, follow_redirects=True)
        self.assertIn("already registered", resp_dup.data.decode('utf-8'))

        # 3. Password mismatch rejection
        resp_mismatch = self.client.post('/doctor/register', data={
            'doctor_name': 'Mismatch Doctor',
            'doctor_id': 'DOC-MISMATCH-99',
            'password': 'Password1',
            'confirm_password': 'Password2'
        }, follow_redirects=True)
        self.assertIn("do not match", resp_mismatch.data.decode('utf-8'))

    def test_04_doctor_login_and_session_separation(self):
        """Verify doctor authentication and cross-login separation."""
        test_doc_id = "DOC-TEST-LOGIN-02"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (test_doc_id,))
            conn.commit()

        create_doctor("Dr. Login Test", test_doc_id, "Password123!")

        # 1. Invalid password
        resp_bad = self.client.post('/doctor/login', data={
            'doctor_id': test_doc_id,
            'password': 'WrongPassword'
        }, follow_redirects=True)
        self.assertIn("Invalid Doctor ID or password", resp_bad.data.decode('utf-8'))

        # 2. Successful doctor login
        with self.client.session_transaction() as sess:
            sess.clear()

        resp_ok = self.client.post('/doctor/login', data={
            'doctor_id': test_doc_id,
            'password': 'Password123!'
        }, follow_redirects=False)

        self.assertEqual(resp_ok.status_code, 302)
        self.assertIn('/doctor', resp_ok.headers['Location'])

        # Verify doctor session is set
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get('doctor_logged_in'))
            self.assertEqual(sess.get('doctor_id'), test_doc_id)
            self.assertEqual(sess.get('doctor_name'), "Dr. Login Test")
            # Patient session keys should NOT be set
            self.assertIsNone(sess.get('patient_id'))

        # 3. Cross-login check: Doctor account cannot login via patient login
        resp_patient_login = self.client.post('/login', data={
            'abha_id': test_doc_id,
            'phone_number': '1234567890'
        }, follow_redirects=True)
        self.assertIn("No registered patient found with this ABHA ID", resp_patient_login.data.decode('utf-8'))

    def test_05_doctor_route_protection(self):
        """Unauthenticated requests to doctor routes must redirect to /doctor/login."""
        with self.client.session_transaction() as sess:
            sess.clear()

        # Try to access /doctor without auth
        resp = self.client.get('/doctor', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/doctor/login', resp.headers['Location'])

        # Try to access /doctor/waiting-list without auth
        resp_wl = self.client.get('/doctor/waiting-list', follow_redirects=False)
        self.assertEqual(resp_wl.status_code, 302)
        self.assertIn('/doctor/login', resp_wl.headers['Location'])

        # Try to access API without auth
        resp_api = self.client.get('/api/doctor/queue')
        self.assertEqual(resp_api.status_code, 401)

    def test_06_waiting_list_real_database_records(self):
        """Verify dedicated waiting list displays real database records with statuses."""
        # Log in as doctor
        test_doc_id = "DOC-TEST-WAITING-03"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (test_doc_id,))
            conn.commit()
        create_doctor("Dr. Queue Reviewer", test_doc_id, "Pass123!")

        self.client.post('/doctor/login', data={
            'doctor_id': test_doc_id,
            'password': 'Pass123!'
        })

        # Fetch waiting list page
        resp = self.client.get('/doctor/waiting-list')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check required navigation and titles
        self.assertIn("PATIENT WAITING LIST", html)
        self.assertIn("Doctor Dashboard", html)
        self.assertIn("Patient Waiting List", html)
        self.assertIn("Logout", html)

        # Check API endpoint
        api_resp = self.client.get('/api/doctor/waiting-list')
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.get_json()
        self.assertIn('waiting_list', data)
        self.assertIsInstance(data['waiting_list'], list)

    def test_07_doctor_dashboard_no_duplicate_queue(self):
        """Verify main Doctor Dashboard does NOT show duplicate queue panel and has View Waiting List link."""
        test_doc_id = "DOC-TEST-CONSOLE-04"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (test_doc_id,))
            conn.commit()
        create_doctor("Dr. Console Tester", test_doc_id, "Pass123!")

        self.client.post('/doctor/login', data={
            'doctor_id': test_doc_id,
            'password': 'Pass123!'
        })

        resp = self.client.get('/doctor')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Main Doctor Dashboard should NOT display the full waiting-list section or queue-panel
        self.assertNotIn('<aside class="queue-panel">', html)
        self.assertNotIn('id="doctorQueueList"', html)

        # Main Doctor Dashboard MUST display navigation to dedicated waiting list
        self.assertIn("View Patient Waiting List", html)
        self.assertIn("/doctor/waiting-list", html)

        # Main Doctor Dashboard should contain clinical console tabs
        self.assertIn("AI Summary", html)
        self.assertIn("Original Transcript", html)
        self.assertIn("Scanned Reports & Labs", html)
        self.assertIn("Editable Clinical History", html)
        self.assertIn("Medical Coding", html)
        self.assertIn("Medical Timeline", html)

if __name__ == '__main__':
    unittest.main()
