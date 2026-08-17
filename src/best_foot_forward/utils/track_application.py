"""
Auto-tracks a tailored application in best_foot_forward.db.
Reads COMPANY, ROLE, JD_FILE_PATH from resume_data.py.
Idempotent: skips if application already exists for this JD.
Called automatically after generate_resume.py via PostToolUse hook.
"""

import sys
import os as _os
sys.path.insert(0, (_os.environ.get('BFF_DATA_DIR') or _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../../../data'))) + '/session')  # data/session/ for session files
sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))        # src/best_foot_forward/
del _os

from datetime import date, datetime
from db import get_conn, register_file, resolve_jd_path, resolve_or_create_jd
from utils.audit_log import log_event
from best_foot_forward.utils.triage_lead import set_lead_status

try:
    from resume_data import COMPANY, ROLE, JD_FILE_PATH
except ImportError as e:
    print(f"[track_application] Could not import resume_data: {e}")
    raise SystemExit(1)

import resume_data as _rd
SOURCE_APPLICATION_ID = getattr(_rd, 'SOURCE_APPLICATION_ID', None)
TAILORING_NOTES       = getattr(_rd, 'TAILORING_NOTES', None)

JD_FILE_PATH = resolve_jd_path(JD_FILE_PATH)

conn = get_conn()

jd_id, jd_action = resolve_or_create_jd(conn, COMPANY, ROLE, JD_FILE_PATH)
if jd_action == "created":
    # track_application.py runs after generate_resume.py (or generate_letter.py) in
    # the resume-tailor pipeline, reading COMPANY/ROLE/JD_FILE_PATH from the same
    # resume_data.py those scripts just used. A legitimate "never evaluated before"
    # JD is created THERE (or earlier still, by save_lead_jd.py under the
    # tailor-without-evaluating flow) -- by the time this script runs, a matching
    # jds row should already exist and resolve via file_path or company+role. A
    # "created" result here means this call's file_path/company/role didn't match
    # what an earlier step just wrote, which silently produced a duplicate
    # scoreless jds row three times before path canonicalization was added
    # (CLAUDE.md's JD-file-conventions section). Rather than compounding that with
    # a fourth silent duplicate now that the file_paths *should* agree, roll back
    # and fail loudly so the actual mismatch gets fixed instead of hidden.
    conn.rollback()
    conn.close()
    print(
        f"[track_application] No existing jds row found for {COMPANY} — {ROLE} "
        f"(file_path={JD_FILE_PATH!r}), and generate_resume.py/generate_letter.py "
        "should have already created or adopted one before this ran. Refusing to "
        "insert a fresh duplicate stub. Check that COMPANY/ROLE/JD_FILE_PATH in "
        "resume_data.py match what was used earlier in this same tailoring "
        "session -- a mismatched value (extra whitespace, a re-slugified path, "
        "a retyped role) is the usual cause.",
        file=sys.stderr,
    )
    raise SystemExit(1)
if jd_action == "adopted":
    print(f"[track_application] Linked existing jds row (id={jd_id}) to file_path for {COMPANY} — {ROLE}.")
# Commit the resolve before going further: the "already exists" branch below exits
# via SystemExit without committing, which would otherwise discard an adopted row's
# file_path back-fill.
conn.commit()

existing = conn.execute(
    "SELECT id, status FROM applications WHERE jd_id = ?", (jd_id,)
).fetchone()

if existing:
    print(f"[track_application] Application already exists (id={existing[0]}, status={existing[1]}) for {COMPANY} — {ROLE}. Skipping.")
    conn.close()
    raise SystemExit(0)

now = datetime.now().isoformat()
conn.execute(
    """INSERT INTO applications
       (jd_id, created_at, status, stage, applied_at, resume_summary, letter_salutation, letter_closing,
        source_application_id, tailoring_notes)
       VALUES (?, ?, 'applied', 'application', ?, '', '', '', ?, ?)""",
    (jd_id, now, date.today().isoformat(), SOURCE_APPLICATION_ID, TAILORING_NOTES)
)
conn.commit()

app_id = conn.execute(
    "SELECT id FROM applications WHERE jd_id = ? ORDER BY id DESC LIMIT 1", (jd_id,)
).fetchone()[0]

# Applying is a triage decision like any other, so it goes through the same
# entry point — that's what stamps lead_decided_at rather than leaving the
# lead's decision date implicit in evaluated_at.
set_lead_status(conn, jd_id, 'applied')

print(f"[track_application] Tracked: {COMPANY} — {ROLE} (app id={app_id}, jd_id={jd_id}, applied={date.today()})")
log_event("resume-tailor", "track_application", application_id=app_id, jd_id=jd_id, company=COMPANY, role=ROLE)
conn.close()

register_file(
    JD_FILE_PATH, "jd",
    f"Job description: {COMPANY} – {ROLE}",
    jd_id=jd_id, application_id=app_id,
)
