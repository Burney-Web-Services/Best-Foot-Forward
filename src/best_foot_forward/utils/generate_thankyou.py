"""
Reads thank you email content from thankyou_data.py and generates a plain-text file.
Run with: python3 src/best_foot_forward/utils/generate_thankyou.py
"""

import sys as _sys, os as _os
_sys.path.insert(0, (_os.environ.get('BFF_DATA_DIR') or _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../../../data'))) + '/session')  # data/session/ for session files
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))        # src/best_foot_forward/
del _sys, _os

import os
from datetime import datetime, timezone

from db import get_conn, register_file, resolve_jd_path
from utils.audit_log import log_event
from thankyou_data import COMPANY, ROLE, JD_FILE_PATH, RECIPIENT_NAME, RECIPIENT_TITLE, INTERVIEW_DATE, EMAIL_BODY

JD_FILE_PATH = resolve_jd_path(JD_FILE_PATH)

# Get jd_id, app_id, and output directory from resolved JD path
conn = get_conn()
jd = conn.execute("SELECT id FROM jds WHERE file_path = ?", (JD_FILE_PATH,)).fetchone()
if not jd:
    print(f"Error: No JD found with file_path={JD_FILE_PATH}")
    exit(1)

jd_id = jd["id"]
output_dir = os.path.dirname(JD_FILE_PATH)

# Get application_id for this jd_id (if one exists)
app = conn.execute("SELECT id FROM applications WHERE jd_id = ? ORDER BY created_at DESC LIMIT 1", (jd_id,)).fetchone()
app_id = app["id"] if app else None

# Sanitize company and role for filename (remove special chars that could cause path issues)
def sanitize(s):
    return s.replace('/', '_').replace('\\', '_')

company_safe = sanitize(COMPANY)
role_safe = sanitize(ROLE)

# Generate filename and path
filename = f"{company_safe}_{role_safe}ThankYou.txt"
filepath = os.path.join(output_dir, filename)

# Write email to file
os.makedirs(output_dir, exist_ok=True)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(EMAIL_BODY)

print(f"Saved to: {filepath}")

# Register the file
register_file(
    filepath, "thankyou",
    f"Thank you email for {COMPANY} – {ROLE}",
    jd_id=jd_id,
    application_id=app_id,
)

log_event("write-thankyou", "generate", company=COMPANY, role=ROLE, filepath=filepath)

conn.close()
