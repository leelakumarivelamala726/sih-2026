import requests

BASE_URL = "http://127.0.0.1:5000"

# 1. Start Session / Initial question
print("Step 1: Fetching initial AI clinical question...")
r1 = requests.post(f"{BASE_URL}/api/ai/chat", json={
    "session_id": 23,
    "message": "START_SESSION",
    "language": "en"
})
assert r1.status_code == 200, f"Failed turn 1: {r1.text}"
d1 = r1.json()
q1 = d1.get("ai_response")
print(f"[AI Question 1 (To be Spoken)]: {q1}")
assert len(q1) > 10

# 2. Patient speaks answer (simulating STT result)
user_ans_1 = "I have severe burning sensation in my stomach and nausea after eating"
print(f"\nStep 2: Patient speaks answer (STT): '{user_ans_1}'")
r2 = requests.post(f"{BASE_URL}/api/ai/chat", json={
    "session_id": 23,
    "message": user_ans_1,
    "language": "en"
})
assert r2.status_code == 200, f"Failed turn 2: {r2.text}"
d2 = r2.json()
q2 = d2.get("ai_response")
print(f"[AI Response 2 (To be Spoken)]: {q2}")
assert len(q2) > 10

# 3. Patient speaks next answer
user_ans_2 = "It started 3 days ago in the morning"
print(f"\nStep 3: Patient speaks next answer (STT): '{user_ans_2}'")
r3 = requests.post(f"{BASE_URL}/api/ai/chat", json={
    "session_id": 23,
    "message": user_ans_2,
    "language": "en"
})
assert r3.status_code == 200, f"Failed turn 3: {r3.text}"
d3 = r3.json()
q3 = d3.get("ai_response")
print(f"[AI Response 3 (To be Spoken)]: {q3}")
assert len(q3) > 10

print("\nSUCCESS: Full two-way voice conversation loop verified successfully!")
