"""Populate a fresh, empty BFF database and Logseq graph from a tracked
example dataset — what `/onboard`'s Phase 0 "explore" path calls so a new
open-source user's first run has something real to look at instead of an
empty database.

Fixture contract (a directory under `examples/`, e.g. `examples/leia-organa/`):

    <fixture>/
      README.md              — provenance note (not read by this script)
      intake_data.py         — same shape as data/session/intake_data.py:
                                CONTACT, EDUCATION, EMPLOYERS, BULLETS, SKILLS
      user_profile.md        — optional; copied into memory/ if absent there
      voice_guide.md         — optional; copied into memory/ if absent there
      document_prefs.json    — optional; {"accent_color_hex": "...", "font_name": "..."}
      stories.json           — optional; [{title, employer, situation, task,
                                action, result, timeframe, raw_transcript,
                                source_type, notes, themes: [...],
                                linked_bullet_ids: [...]}]
      applications/
        <Company>/<Role_Slug>/
          JobDesc.md          — the JD text (property block + posting text)
          jd_eval.json        — {score, summary, url, salary_min, salary_max,
                                  salary_currency, required_skills: [...]}
          resume_data.py      — optional; only present if this JD was tailored.
                                Same shape as data/session/resume_data.py.
                                JD_FILE_PATH must be a RELATIVE path (checkout-
                                agnostic) — resolve_jd_path() anchors it at
                                whichever checkout is running.
          letter_data.py      — optional; same shape as data/session/letter_data.py.
                                Present iff resume_data.py is present.

Replay-based by design: this replays each fixture through the real production
scripts (import_intake.py, generate_resume.py, generate_letter.py,
track_application.py, scan_jds.py, export_graph.py, generate_home.py) rather
than hand-writing DB rows for every table. Those scripts already solve
natural-key resolution and join-table population correctly — reinventing that
here would just be a second, divergent copy of logic that's already right.

Usage:
    python3 -m best_foot_forward.utils.load_example_data examples/leia-organa
    python3 -m best_foot_forward.utils.load_example_data examples/leia-organa --force
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from best_foot_forward.db import DATA_DIR, _root, get_conn, init_db, resolve_jd_path
from best_foot_forward.utils.save_lead_jd import jd_paths
from best_foot_forward.utils.triage_lead import set_lead_status

# memory/ isn't part of DATA_DIR (it's referenced as a literal path in command
# markdown, not through db.py), so it needs its own BFF_DATA_DIR handling here
# to honor the same isolation contract documented in CLAUDE.md's "Execution
# context awareness" section for BFF_UAT runs. Without this, a scripted/UAT
# load would write into the real checkout's memory/ regardless of DATA_DIR --
# exactly the kind of contamination this whole mechanism exists to prevent.
MEMORY_DIR = os.path.join(os.environ.get("BFF_DATA_DIR") or _root, "memory")


def _run(module: str, *args: str) -> None:
    """Run a best_foot_forward.utils script as a subprocess, inheriting
    BFF_DATA_DIR from this process's environment. These scripts execute
    top-level code on import (no clean function boundary), so subprocess is
    the correct invocation shape here, same as a human running them by hand.

    Invoked as a direct file path (`python3 src/.../X.py`), not `-m
    best_foot_forward.utils.X`: several older scripts here (generate_resume.py
    among them) do a bare `from track_bullets import ...` relying on Python's
    implicit "add the script's own directory to sys.path" behavior, which
    only happens under direct execution -- `-m` uses package-relative import
    machinery instead and never adds that directory, so those bare imports
    fail. Direct-path invocation works for both the older bare-import scripts
    and the newer best_foot_forward.X-style ones, so it's the one style that
    is correct for every script in this directory.
    """
    script = os.path.join(_root, "src", "best_foot_forward", "utils", f"{module}.py")
    cmd = [sys.executable, script, *args]
    result = subprocess.run(cmd, cwd=_root, env=os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError(f"[load_example_data] {module} failed (exit {result.returncode})")


def _refuses_to_clobber_real_data(conn) -> bool:
    """True if a real, populated database already exists here. A brand-new
    empty DB (just created by init_db()'s CREATE TABLE IF NOT EXISTS) has no
    rows in contact or employers; anything else means a real user is already
    partway through their own onboarding, or further."""
    contact_rows = conn.execute("SELECT COUNT(*) FROM contact").fetchone()[0]
    employer_rows = conn.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
    return contact_rows > 0 or employer_rows > 0


def _copy_memory_file_if_absent(fixture_dir: str, filename: str) -> None:
    src = os.path.join(fixture_dir, filename)
    if not os.path.exists(src):
        return
    dst = os.path.join(MEMORY_DIR, filename)
    if os.path.exists(dst):
        return
    os.makedirs(MEMORY_DIR, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[load_example_data] copied {filename} into memory/")


def load(fixture_dir: str, force: bool = False) -> None:
    fixture_dir = os.path.abspath(fixture_dir)
    if not os.path.isdir(fixture_dir):
        raise FileNotFoundError(f"No such fixture directory: {fixture_dir}")

    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    conn = get_conn()
    if not force and _refuses_to_clobber_real_data(conn):
        conn.close()
        raise RuntimeError(
            "A real database already exists with data (contact or employers rows "
            "present) — refusing to load example data over it. Back up or remove "
            f"{os.path.join(DATA_DIR, 'best_foot_forward.db')} first, or pass "
            "--force if you understand the risk."
        )
    conn.close()

    session_dir = os.path.join(DATA_DIR, "session")
    os.makedirs(session_dir, exist_ok=True)

    # 1. Intake — profile, employers, bullets, skills.
    intake_src = os.path.join(fixture_dir, "intake_data.py")
    if not os.path.exists(intake_src):
        raise FileNotFoundError(f"Fixture is missing required intake_data.py: {intake_src}")
    shutil.copy2(intake_src, os.path.join(session_dir, "intake_data.py"))
    _run("import_intake")
    _run("export_cache")

    # 2. Document prefs.
    prefs_path = os.path.join(fixture_dir, "document_prefs.json")
    if os.path.exists(prefs_path):
        with open(prefs_path, encoding="utf-8") as f:
            prefs = json.load(f)
        from best_foot_forward.utils.init_document_prefs import ensure_document_prefs
        ensure_document_prefs(**prefs)

    # 3. Memory files — only where the caller doesn't already have one.
    for filename in ("user_profile.md", "voice_guide.md"):
        _copy_memory_file_if_absent(fixture_dir, filename)

    # 4. Stories.
    stories_path = os.path.join(fixture_dir, "stories.json")
    if os.path.exists(stories_path):
        _load_stories(stories_path)

    # 5. Applications — each is a scored JD, optionally tailored.
    apps_dir = os.path.join(fixture_dir, "applications")
    application_count = tailored_count = 0
    if os.path.isdir(apps_dir):
        for company in sorted(os.listdir(apps_dir)):
            company_dir = os.path.join(apps_dir, company)
            if not os.path.isdir(company_dir):
                continue
            for role_slug in sorted(os.listdir(company_dir)):
                role_dir = os.path.join(company_dir, role_slug)
                if not os.path.isdir(role_dir):
                    continue
                tailored = _load_application(role_dir, company, role_slug)
                application_count += 1
                if tailored:
                    tailored_count += 1

    # 6. Graph + dashboards.
    _run("init_graph")
    _run("export_graph")
    _run("generate_home")

    print(f"[load_example_data] loaded {fixture_dir}")
    print(f"  {application_count} scored JD(s), {tailored_count} tailored through to generated documents")
    print("  Suggested next step: /evaluate-job against a new posting, or /resume-tailor an existing one.")


def _load_stories(stories_path: str) -> None:
    with open(stories_path, encoding="utf-8") as f:
        stories = json.load(f)
    conn = get_conn()
    try:
        for story in stories:
            employer_row = conn.execute(
                "SELECT id FROM employers WHERE name = ?", (story.get("employer"),)
            ).fetchone()
            employer_id = employer_row["id"] if employer_row else None
            cur = conn.execute(
                "INSERT INTO stories (title, situation, task, action, result, employer_id, "
                "timeframe, raw_transcript, source_type, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (story.get("title"), story.get("situation"), story.get("task"),
                 story.get("action"), story.get("result"), employer_id,
                 story.get("timeframe"), story.get("raw_transcript"),
                 story.get("source_type", "conversation"), story.get("notes")),
            )
            story_id = cur.lastrowid
            for theme in story.get("themes", []):
                conn.execute("INSERT INTO story_themes (story_id, theme) VALUES (?, ?)", (story_id, theme))
            for bullet_id in story.get("linked_bullet_ids", []):
                conn.execute(
                    "INSERT INTO story_bullets (story_id, bullet_id) VALUES (?, ?)", (story_id, bullet_id)
                )
        conn.commit()
    finally:
        conn.close()
    print(f"[load_example_data] loaded {len(stories)} star stor{'y' if len(stories) == 1 else 'ies'}")


_JD_COMPANY_PROP_RE = re.compile(r'^company::\s*\[\[(.+?)\]\]\s*$', re.MULTILINE)
_JD_ROLE_PROP_RE = re.compile(r'^role::\s*(.+?)\s*$', re.MULTILINE)


def _read_jd_header(jd_text: str) -> tuple[str | None, str | None]:
    """Read (company, role) back out of a JobDesc.md's Logseq property
    block -- the exact format save_lead_jd.render_jd_file() writes:
    `company:: [[X]]`, `role:: Y`, punctuation intact. Returns (None, None)
    for either that isn't present.

    Deriving these from the slugified directory name instead (the original
    approach) loses punctuation ("Director/VP of Software" -> "Director VP
    of Software") and, worse, the directory name is *underscored* while the
    rest of the codebase's convention (JD_FILE_PATH in every fixture's
    resume_data.py, save_lead_jd.jd_paths()) is space-formatted -- that
    mismatch is what caused every tailored application to land as two
    separate `jds` rows. See examples/leia-organa/README.md.
    """
    company_match = _JD_COMPANY_PROP_RE.search(jd_text)
    role_match = _JD_ROLE_PROP_RE.search(jd_text)
    company = company_match.group(1).strip() if company_match else None
    role = role_match.group(1).strip() if role_match else None
    return company, role


def _strip_jd_header(jd_text: str) -> str:
    """The posting body of a JobDesc.md, stripping the leading property
    block render_jd_file() writes. Needed before re-passing the text
    through save_lead_jd.py (which writes its own header) -- passing the
    whole already-headered file back through it doubles the header."""
    _, _, body = jd_text.partition("\n\n")
    return body.strip()


def _load_application(role_dir: str, company: str, role_slug: str) -> bool:
    """Load one application fixture. Returns True if it was tailored through
    to generated documents, False if it's scored-but-not-applied (a lead)."""
    jd_src = os.path.join(role_dir, "JobDesc.md")
    eval_path = os.path.join(role_dir, "jd_eval.json")
    if not os.path.exists(jd_src) or not os.path.exists(eval_path):
        print(f"[load_example_data] skipping {company}/{role_slug}: missing JobDesc.md or jd_eval.json")
        return False

    with open(jd_src, encoding="utf-8") as f:
        jd_src_text = f.read()
    header_company, header_role = _read_jd_header(jd_src_text)
    company_display = header_company or company.replace("_", " ")
    role = header_role or role_slug.replace("_", " ")

    # Reuse save_lead_jd's own path convention rather than hand-rolling a
    # second, divergent copy of it -- see _read_jd_header's docstring.
    asset_dir, jd_dest = jd_paths(company_display, role)
    os.makedirs(asset_dir, exist_ok=True)
    shutil.copy2(jd_src, jd_dest)
    jd_dest = resolve_jd_path(jd_dest)

    with open(eval_path, encoding="utf-8") as f:
        jd_eval = json.load(f)

    conn = get_conn()
    try:
        existing = conn.execute("SELECT id FROM jds WHERE file_path = ?", (jd_dest,)).fetchone()
        if existing:
            jd_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO jds (company, role, file_path, lead_status) VALUES (?, ?, ?, 'pending')",
                (company_display, role, jd_dest),
            )
            jd_id = cur.lastrowid
        conn.execute(
            "UPDATE jds SET score = ?, evaluated_at = COALESCE(evaluated_at, datetime('now')), "
            "summary = ?, url = COALESCE(url, ?), salary_min = COALESCE(salary_min, ?), "
            "salary_max = COALESCE(salary_max, ?), salary_currency = COALESCE(salary_currency, ?) "
            "WHERE id = ?",
            (jd_eval.get("score"), jd_eval.get("summary"), jd_eval.get("url"),
             jd_eval.get("salary_min"), jd_eval.get("salary_max"),
             jd_eval.get("salary_currency", "USD"), jd_id),
        )
        conn.commit()
    finally:
        conn.close()

    _load_not_yet_loadable_lead_state(jd_id, jd_eval)

    required_skills = jd_eval.get("required_skills")
    if required_skills:
        # --text with the stripped posting body, not --text-file jd_dest --
        # jd_dest already carries the property-block header this copy
        # wrote, and save_lead_jd.py writes its own; passing the whole
        # headered file back through it would double the header.
        posting_body = _strip_jd_header(jd_src_text)
        _run("save_lead_jd", "--company", company_display, "--role", role,
             "--text", posting_body, "--overwrite", "--skills-json", json.dumps(required_skills))

    resume_src = os.path.join(role_dir, "resume_data.py")
    letter_src = os.path.join(role_dir, "letter_data.py")
    if not (os.path.exists(resume_src) and os.path.exists(letter_src)):
        return False  # scored lead, not tailored

    session_dir = os.path.join(DATA_DIR, "session")
    shutil.copy2(resume_src, os.path.join(session_dir, "resume_data.py"))
    shutil.copy2(letter_src, os.path.join(session_dir, "letter_data.py"))
    _run("generate_resume")
    _run("generate_letter")
    _run("track_application")
    _run("scan_jds", os.path.dirname(jd_dest), "--rescan")

    stage = jd_eval.get("_not_yet_loadable", {}).get("application_stage")
    if stage:
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE applications SET stage = ? WHERE jd_id = ?", (stage, jd_id)
            )
            conn.commit()
        finally:
            conn.close()

    _run("export_graph", "--only", company_display)
    return True


def _load_not_yet_loadable_lead_state(jd_id: int, jd_eval: dict) -> None:
    """Replay the parts of a fixture's real outcome that don't fit
    _load_application()'s normal shape -- a declined lead (lead_status,
    category, reason, decision date) or a scheduled-interview contact row --
    both captured under jd_eval.json's `_not_yet_loadable` key because the
    original loader had nowhere to put them (see examples/leia-organa/
    README.md's 'Known gaps' section, and the fixture's own jd_eval.json
    files for the real Nar Shaddaa decline / Obroa-skai screen-stage
    provenance this replays). `application_stage` is handled by the caller
    since it needs the applications row track_application.py creates, which
    doesn't exist yet at the point this runs.

    Idempotent: set_lead_status() is a plain UPDATE (safe to repeat), and the
    contact insert is guarded by a name+jd_id existence check so a re-run
    (or --force) doesn't pile up duplicate contact rows.
    """
    not_yet = jd_eval.get("_not_yet_loadable")
    if not not_yet:
        return

    conn = get_conn()
    try:
        if not_yet.get("lead_status") == "declined":
            set_lead_status(
                conn, jd_id, "declined",
                reason=not_yet.get("decline_reason"),
                decided_at=not_yet.get("lead_decided_at"),
                category=not_yet.get("decline_category"),
            )

        contact = not_yet.get("contact")
        if contact:
            existing = conn.execute(
                "SELECT id FROM contacts WHERE jd_id = ? AND name = ?",
                (jd_id, contact.get("name")),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO contacts (jd_id, name, title, role, interview_date, "
                    "interview_time, interview_stage, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        jd_id, contact.get("name"), contact.get("title"), contact.get("role"),
                        contact.get("interview_date"), contact.get("interview_time"),
                        contact.get("interview_stage"), contact.get("notes"),
                    ),
                )
                conn.commit()
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fixture_dir", help="Path to the fixture directory, e.g. examples/leia-organa")
    p.add_argument("--force", action="store_true",
                   help="Load even if a real, populated database already exists (dangerous).")
    args = p.parse_args()

    try:
        load(args.fixture_dir, force=args.force)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[load_example_data] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
