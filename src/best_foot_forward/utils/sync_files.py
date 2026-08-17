"""
Syncs the file_registry table with files on disk.

Walks data/applications/ and data/media/, classifies each file by type,
infers the linked jd_id where possible, and inserts records into file_registry.
Safe to run repeatedly — already-registered files are skipped unless --refresh.

Usage:
    python3 src/best_foot_forward/utils/sync_files.py
    python3 src/best_foot_forward/utils/sync_files.py --dry-run
    python3 src/best_foot_forward/utils/sync_files.py --refresh
    python3 src/best_foot_forward/utils/sync_files.py --company Acme
    python3 src/best_foot_forward/utils/sync_files.py --check-orphans
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))  # src/best_foot_forward/
del _sys, _os

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

from db import get_conn, init_db, register_file, DATA_DIR, _root as PROJECT_ROOT

# ── Constants ─────────────────────────────────────────────────────────────────

SKIP_PREFIXES = (".~lock.", ".DS_Store")
SKIP_DIRS = {"__pycache__", ".git"}

# ── File type classification ──────────────────────────────────────────────────

def classify_file(path: str, rel_path: str) -> str:
    """Return a file_type string based on filename patterns and location."""
    name = os.path.basename(path)
    name_lower = name.lower()
    ext = os.path.splitext(name)[1].lower()

    # Media directory rules take precedence
    if "media/recordings" in rel_path.replace("\\", "/") or "media\\recordings" in rel_path:
        return "recording"
    if "media/transcripts" in rel_path.replace("\\", "/") or "media\\transcripts" in rel_path:
        return "transcript"
    if ext in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
        return "recording"

    # Application directory filename patterns
    if "resume" in name_lower:
        return "resume"
    if "cover letter" in name_lower or "coverletter" in name_lower:
        return "letter"
    if "screenprep" in name_lower or "screen_prep" in name_lower or "screen-prep" in name_lower:
        return "screen_prep"
    if "interviewprep" in name_lower or "interview_prep" in name_lower or "interview-prep" in name_lower or "prepguide" in name_lower:
        return "interview_prep"
    if "applicationquestions" in name_lower or "application_questions" in name_lower:
        return "questions"
    if "jobdesc" in name_lower or "job_desc" in name_lower or "job-desc" in name_lower:
        return "jd"
    if "thankyou" in name_lower or "thank_you" in name_lower:
        return "notes"
    if "notes" in name_lower or "companynotes" in name_lower:
        return "notes"

    # Research subdirectory
    parts = rel_path.replace("\\", "/").split("/")
    if any("research" in p.lower() for p in parts):
        return "research"

    # Extension-based fallbacks
    if ext in {".odt", ".txt"} and "assets" in rel_path:
        return "jd"
    if ext == ".md" and "assets" in rel_path:
        return "notes"

    return "misc"


def make_summary(file_type: str, name: str, company: str | None, role: str | None) -> str:
    company_role = f"{company} – {role}" if company and role else (company or name)
    summaries = {
        "resume":        f"Resume tailored for {company_role}",
        "letter":        f"Cover letter for {company_role}",
        "screen_prep":   f"Screen prep for {company_role}",
        "interview_prep": f"Interview prep for {company_role}",
        "jd":            f"Job description: {company_role}",
        "questions":     f"Application questions for {company_role}",
        "notes":         f"Notes: {name}",
        "research":      f"Research: {name}",
        "transcript":    f"Transcript: {name}",
        "recording":     f"Recording: {name}",
        "misc":          f"File: {name}",
    }
    return summaries.get(file_type, f"File: {name}")


# ── JD lookup ─────────────────────────────────────────────────────────────────

def lookup_jd_id(conn, rel_path: str) -> int | None:
    """Try to find a matching jds.id for a file based on its directory path."""
    parts = rel_path.replace("\\", "/").split("/")
    # Extract Company / Role_Slug from data/BestFootForward/assets/{Company}/{Role_Slug}/...
    try:
        app_idx = parts.index("assets")
    except ValueError:
        return None
    if app_idx + 2 >= len(parts):
        return None

    company_dir = parts[app_idx + 1]
    role_dir = parts[app_idx + 2] if app_idx + 2 < len(parts) - 1 else None

    # Match any jds record whose file_path contains Company/Role_Slug/
    if role_dir:
        pattern = f"{company_dir}/{role_dir}/"
        row = conn.execute(
            "SELECT id FROM jds WHERE INSTR(file_path, ?) > 0 LIMIT 1",
            (pattern,),
        ).fetchone()
        if row:
            return row[0]

    # Fallback: match company name only (strip underscores/hyphens for comparison)
    company_name = company_dir.replace("_", " ").replace("-", " ")
    row = conn.execute(
        "SELECT id FROM jds WHERE LOWER(company) = LOWER(?) LIMIT 1",
        (company_name,),
    ).fetchone()
    return row[0] if row else None


def parse_company_role(rel_path: str) -> tuple[str | None, str | None]:
    """Extract (company, role_slug) from a relative path under data/BestFootForward/assets/."""
    parts = rel_path.replace("\\", "/").split("/")
    try:
        app_idx = parts.index("assets")
    except ValueError:
        return None, None
    company = parts[app_idx + 1] if app_idx + 1 < len(parts) else None
    role = parts[app_idx + 2].replace("_", " ") if app_idx + 2 < len(parts) - 1 else None
    return company, role


# ── File walking ──────────────────────────────────────────────────────────────

def should_skip(name: str) -> bool:
    return (
        any(name.startswith(p) for p in SKIP_PREFIXES)
        or name in SKIP_DIRS
        or name.startswith(".")
    )


def walk_files(root_dir: str, company_filter: str | None = None):
    """Yield absolute file paths under root_dir."""
    if not os.path.isdir(root_dir):
        return
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not should_skip(d)]

        if company_filter:
            # Only descend into the matching company folder under applications/
            rel_dir = os.path.relpath(dirpath, root_dir)
            depth = len(rel_dir.split(os.sep)) if rel_dir != "." else 0
            if depth == 1:
                top = rel_dir.split(os.sep)[0]
                if top.lower() != company_filter.lower():
                    dirnames.clear()
                    continue

        for fname in filenames:
            if not should_skip(fname):
                yield os.path.join(dirpath, fname)


# ── Orphan detection ──────────────────────────────────────────────────────────

def check_orphans(conn):
    print("\n── Orphan check ─────────────────────────────────────────────────────────")

    # Registry entries whose file is missing on disk
    rows = conn.execute("SELECT file_path FROM file_registry").fetchall()
    missing = []
    for row in rows:
        abs_path = os.path.join(PROJECT_ROOT, row[0])
        if not os.path.exists(abs_path):
            missing.append(row[0])

    if missing:
        print(f"\nRegistered but missing on disk ({len(missing)}):")
        for p in missing:
            print(f"  MISSING  {p}")
    else:
        print("\nAll registered files exist on disk. ✓")

    # Files on disk not in registry
    registered = {row[0] for row in conn.execute("SELECT file_path FROM file_registry").fetchall()}
    unregistered = []
    for scan_dir in [
        os.path.join(DATA_DIR, "BestFootForward", "assets"),
        os.path.join(DATA_DIR, "media"),
    ]:
        for abs_path in walk_files(scan_dir):
            rel = os.path.relpath(abs_path, PROJECT_ROOT)
            if rel not in registered:
                unregistered.append(rel)

    if unregistered:
        print(f"\nOn disk but not in registry ({len(unregistered)}):")
        for p in unregistered[:50]:
            print(f"  UNREGISTERED  {p}")
        if len(unregistered) > 50:
            print(f"  ... and {len(unregistered) - 50} more")
    else:
        print("All files on disk are registered. ✓")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sync file_registry table with files on disk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 sync_files.py --dry-run          # preview without writing\n"
            "  python3 sync_files.py                    # register all new files\n"
            "  python3 sync_files.py --refresh          # re-stat already-registered files\n"
            "  python3 sync_files.py --company Acme     # limit to one company\n"
            "  python3 sync_files.py --check-orphans    # find missing or unregistered files\n"
        ),
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be registered without writing")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-stat and update metadata on already-registered files")
    parser.add_argument("--company", default=None, metavar="COMPANY",
                        help="Limit scan to this company folder name")
    parser.add_argument("--check-orphans", action="store_true",
                        help="Report missing and unregistered files")
    args = parser.parse_args()

    init_db()
    conn = get_conn()

    if args.check_orphans:
        check_orphans(conn)
        conn.close()
        return

    scan_dirs = [
        os.path.join(DATA_DIR, "BestFootForward", "assets"),
        os.path.join(DATA_DIR, "media"),
    ]

    apps_found = any(os.path.isdir(d) for d in scan_dirs)
    if not apps_found:
        print("No applications or media directory found — nothing to sync.")
        conn.close()
        return

    registered_paths = {
        row[0] for row in conn.execute("SELECT file_path FROM file_registry").fetchall()
    }

    n_inserted = 0
    n_skipped = 0
    n_refreshed = 0
    n_unlinked = 0

    for scan_dir in scan_dirs:
        for abs_path in walk_files(scan_dir, company_filter=args.company):
            rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
            already_registered = rel_path in registered_paths

            if already_registered and not args.refresh:
                n_skipped += 1
                continue

            file_type = classify_file(abs_path, rel_path)
            company, role = parse_company_role(rel_path)
            name = os.path.basename(abs_path)
            summary = make_summary(file_type, name, company, role)
            jd_id = lookup_jd_id(conn, rel_path)

            if jd_id is None:
                n_unlinked += 1

            if args.dry_run:
                linked = f"jd_id={jd_id}" if jd_id else "unlinked"
                action = "REFRESH" if already_registered else "REGISTER"
                print(f"  {action:<8} [{file_type:<12}] {linked:<12}  {rel_path}")
                if already_registered:
                    n_refreshed += 1
                else:
                    n_inserted += 1
            else:
                st = os.stat(abs_path)
                file_size = st.st_size
                file_mtime = datetime.fromtimestamp(st.st_mtime).isoformat()

                conn.execute(
                    """INSERT INTO file_registry
                       (jd_id, application_id, story_id, file_path, file_type, summary,
                        file_size, file_mtime, source)
                       VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, 'sync')
                       ON CONFLICT(file_path) DO UPDATE SET
                           jd_id=excluded.jd_id,
                           file_type=excluded.file_type,
                           summary=excluded.summary,
                           file_size=excluded.file_size,
                           file_mtime=excluded.file_mtime,
                           source=excluded.source""",
                    (jd_id, rel_path, file_type, summary, file_size, file_mtime),
                )
                if already_registered:
                    n_refreshed += 1
                else:
                    n_inserted += 1

    if not args.dry_run:
        conn.commit()

    conn.close()

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}Sync complete:")
    print(f"  Registered : {n_inserted}")
    if args.refresh:
        print(f"  Refreshed  : {n_refreshed}")
    print(f"  Skipped    : {n_skipped}  (already registered)")
    print(f"  Unlinked   : {n_unlinked}  (no matching jds record found)")


if __name__ == "__main__":
    main()
