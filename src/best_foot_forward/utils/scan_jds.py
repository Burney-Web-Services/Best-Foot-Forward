"""
Walks a directory of job description files (.md/.txt/.odt, recursively), extracts skill
mentions matched against the skills taxonomy, and populates the jds and
jd_required_skills tables.

Usage:
    python3 src/best_foot_forward/utils/scan_jds.py /path/to/jd/root
    python3 src/best_foot_forward/utils/scan_jds.py /path/to/jd/root --rescan
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../../../data')))  # data/ for session files
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))        # src/best_foot_forward/
del _sys, _os

import os
import re
import sys
import argparse
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

from db import get_conn, init_db, resolve_jd_path
from utils.audit_log import log_event
from utils.company_normalize import alnum_key, canonical_company
from utils.jd_skills import build_term_index, extract_terms  # noqa: F401 (re-exported for backward compat)

# ── ODT text extraction ───────────────────────────────────────────────────────

def extract_odt_text(path):
    try:
        with ZipFile(path) as z:
            with z.open("content.xml") as f:
                root = ET.parse(f).getroot()
        texts = [e.text.strip() for e in root.iter() if e.text and e.text.strip()]
        return "\n".join(texts)
    except Exception as e:
        print(f"  WARNING: could not read {path}: {e}")
        return ""

# ── Skill term extraction ─────────────────────────────────────────────────────
# build_term_index and the actual extraction logic now live in jd_skills.py —
# see that module's docstring for why (the circular-vocabulary bug: this file
# used to build its entire matching vocabulary from the user's own skills
# table plus a small hardcoded list, so jd_required_skills could only ever
# contain skills the user already had). Both re-exported above; use
# jd_skills.extract_terms(text, conn) directly — it returns Term objects
# (label, canonical, skill_id, source), not the old (label, skill_id) tuples.

# ── Salary extraction ─────────────────────────────────────────────────────────

def extract_salary(text):
    patterns = [
        (r'\$(\d{1,3}(?:,\d{3})+)\s*[-–—to]+\s*\$(\d{1,3}(?:,\d{3})+)', 1),
        (r'\$(\d+(?:\.\d+)?)[Kk]\s*[-–—to]+\s*\$(\d+(?:\.\d+)?)[Kk]', 1000),
        (r'\b(\d+(?:\.\d+)?)[Kk]\s*[-–—to]+\s*(\d+(?:\.\d+)?)[Kk]\b', 1000),
    ]
    for pattern, multiplier in patterns:
        m = re.search(pattern, text)
        if m:
            low  = int(float(m.group(1).replace(',', '')) * multiplier)
            high = int(float(m.group(2).replace(',', '')) * multiplier)
            if 30_000 <= low <= 1_000_000 and low <= high:
                return low, high
    return None, None

# ── Company / role from path ──────────────────────────────────────────────────

# Only files whose names contain one of these substrings are treated as JDs.
# Filters out ApplicationQuestions.txt, ClaudeNotes.md, ScreenPrep.odt, etc.
JD_NAME_PATTERNS = ['jobdesc', 'job-desc', 'job_desc', 'jobdescription']

def is_jd_file(fname):
    lower = fname.lower()
    return any(p in lower for p in JD_NAME_PATTERNS)

def infer_company_role(file_path):
    # Structure: .../applications/{Company}/{Role_Slug}/{Company}JobDesc.txt
    role_dir    = os.path.dirname(file_path)
    company_dir = os.path.dirname(role_dir)
    company = os.path.basename(company_dir).replace('_', ' ')
    role    = os.path.basename(role_dir).replace('_', ' ')
    return company, role

# ── Main scan ─────────────────────────────────────────────────────────────────

def _canonical_key(company, role):
    return (alnum_key(canonical_company(company)), alnum_key(role))


def _load_canonical_index(conn):
    """(canonical company, canonical role) -> jds.id, for every existing row.

    Lets a file with no file_path match still be recognized as already
    covered -- the fix for the orphaned-file bug: a jds row deleted without
    also removing its asset file (no row-deletion tooling did that cleanup
    before delete_lead.py existed) left the file on disk, and a later scan
    silently re-registered it as a brand-new row purely because file_path no
    longer matched anything. Company/role can still collide by coincidence
    across unrelated real JDs, but that's the same risk resolve_or_create_jd()
    already accepts for its own company+role fallback -- consistent behavior
    across the codebase's several JD-matching call sites beats a stricter
    rule here that would just reintroduce the duplicate-row problem from the
    other direction."""
    index = {}
    for row in conn.execute("SELECT id, company, role FROM jds"):
        if row["company"] and row["role"]:
            index[_canonical_key(row["company"], row["role"])] = row["id"]
    return index


def scan(root_dir, rescan=False):
    root_dir = os.path.abspath(root_dir)
    init_db()
    conn = get_conn()
    canonical_index = _load_canonical_index(conn)

    jd_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith((".odt", ".txt", ".md")) and is_jd_file(fname):
                jd_files.append(os.path.join(dirpath, fname))

    print(f"Found {len(jd_files)} JD file(s) under {root_dir}")
    new_count = 0
    skip_count = 0
    orphan_skip_count = 0

    for path in sorted(jd_files):
        path = resolve_jd_path(path)
        existing = conn.execute("SELECT id FROM jds WHERE file_path = ?", (path,)).fetchone()
        if existing and not rescan:
            skip_count += 1
            continue

        company, role = infer_company_role(path)
        if not existing:
            covering_id = canonical_index.get(_canonical_key(company, role))
            if covering_id is not None:
                print(
                    f"  Skipping (already covered by jds id={covering_id}, "
                    f"canonical match): {os.path.relpath(path, root_dir)}"
                )
                orphan_skip_count += 1
                continue

        print(f"  Processing: {os.path.relpath(path, root_dir)}")
        if path.lower().endswith((".txt", ".md")):
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                print(f"  WARNING: could not read {path}: {e}")
                text = ""
        else:
            text = extract_odt_text(path)
        if not text:
            continue

        salary_min, salary_max = extract_salary(text)
        now = datetime.now(timezone.utc).isoformat()

        if existing:
            jd_id = existing["id"]
            # Never touch company/role on an existing row: infer_company_role() only
            # derives a folder-slug placeholder, and a rescan would silently clobber
            # a hand-corrected role name (e.g. "Director, Engineering – AI Platform"
            # -> "Director Engineering AI Platform"), orphaning its Logseq page since
            # export_graph.py computes filenames fresh from the current role text with
            # no rename tracking. Salary uses COALESCE for the same reason: only add,
            # never overwrite a good value with NULL just because this file's text
            # doesn't match the regex this time. evaluated_at gets the same treatment:
            # everywhere else it means "when the lead was scored" (evaluate-job writes
            # it alongside score and summary), so a scan may stamp a row that was never
            # scored but must never restamp a real score time — that would turn the
            # column into "scored or scanned, whichever was last" and destroy the only
            # thing it measures, how long a lead sat between scoring and applying.
            conn.execute(
                "UPDATE jds SET evaluated_at=COALESCE(evaluated_at, ?), "
                "salary_min=COALESCE(?, salary_min), salary_max=COALESCE(?, salary_max) WHERE id=?",
                (now, salary_min, salary_max, jd_id)
            )
            conn.execute("DELETE FROM jd_required_skills WHERE jd_id=?", (jd_id,))
        else:
            cur = conn.execute(
                "INSERT INTO jds (company, role, file_path, salary_min, salary_max) VALUES (?, ?, ?, ?, ?)",
                (company, role, path, salary_min, salary_max)
            )
            jd_id = cur.lastrowid
            new_count += 1

        skills_found = extract_terms(text, conn)
        for term in skills_found:
            conn.execute(
                "INSERT INTO jd_required_skills (jd_id, skill_label, skill_id, canonical_label, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (jd_id, term.label, term.skill_id, term.canonical, term.source)
            )

        log_event(
            "scan_jds", "rescan" if existing else "insert",
            jd_id=jd_id, company=company, role=role,
            salary_min=salary_min, salary_max=salary_max, skills_found=len(skills_found),
        )

    conn.commit()
    conn.close()
    print(
        f"\nDone. New JDs: {new_count}  Skipped (already scanned): {skip_count}"
        f"  Skipped (orphaned, already covered): {orphan_skip_count}"
    )
    print("Run with --rescan to reprocess existing entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan JD directory and extract skills.")
    parser.add_argument("root_dir", help="Root directory containing JD .odt files")
    parser.add_argument("--rescan", action="store_true", help="Reprocess already-scanned files")
    args = parser.parse_args()

    if not os.path.isdir(args.root_dir):
        print(f"Error: {args.root_dir} is not a directory")
        sys.exit(1)

    scan(args.root_dir, rescan=args.rescan)
