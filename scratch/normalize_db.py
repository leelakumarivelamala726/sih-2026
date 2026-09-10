import sqlite3

def run():
    conn = sqlite3.connect('database/medikiosk.db')
    c = conn.cursor()
    c.execute("UPDATE patient_sessions SET status = 'AI Completed' WHERE status = 'ready_for_doctor'")
    c.execute("UPDATE patient_sessions SET status = 'Completed' WHERE status = 'verified'")
    c.execute("UPDATE patient_sessions SET status = 'AI Case Taking' WHERE status = 'in_progress'")
    conn.commit()
    c.execute("SELECT DISTINCT status FROM patient_sessions")
    print("Current distinct statuses:", [r[0] for r in c.fetchall()])

if __name__ == '__main__':
    run()
