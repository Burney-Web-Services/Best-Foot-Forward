import sqlite3
import os
from datetime import datetime
from typing import Any

_here    = os.path.dirname(os.path.abspath(__file__))         # src/best_foot_forward/
_root    = os.path.normpath(os.path.join(_here, '..', '..'))  # project root
# BFF_DATA_DIR override exists so a scripted/UAT run (or any tooling that
# needs to point at a throwaway data directory) never has to fall back to a
# separate repo clone to get isolation. Before this, the only way to keep a
# fictional-persona test run from touching real data was a second clone --
# and a clone whose `origin` happened to point at the real GitHub repo is
# exactly what let one such run get mistaken for a real working copy and
# used for real applications. An env var makes that mistake structurally
# harder, not just a matter of remembering to be careful.
DATA_DIR = os.environ.get('BFF_DATA_DIR') or os.path.join(_root, 'data')
DB_PATH  = os.path.join(DATA_DIR, 'best_foot_forward.db')
_SCHEMA  = os.path.join(_here, 'schema.sql')


def resolve_jd_path(path: str) -> str:
    """Canonicalize a JD file path to an absolute path anchored at the project
    root. `jds.file_path` is compared with exact-match SQL (`WHERE file_path = ?`)
    across independently-run processes (evaluate-job, scan_jds, track_application,
    generate_resume/letter) — without a shared canonicalization step, equivalent
    paths built relative to different cwds produce different strings, silently
    missing the lookup and inserting a duplicate `jds` row.

    A relative path starting with "data/" (the convention every fixture and
    every command's JD_FILE_PATH uses) anchors at DATA_DIR specifically, not
    just _root — otherwise a BFF_DATA_DIR override redirects the database
    location but every JD path still resolves inside the real checkout's
    data/, which is exactly backwards for an isolated/UAT run. For a real
    user with no override this is byte-identical (DATA_DIR defaults to
    _root/data)."""
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        if path == "data" or path.startswith("data/") or path.startswith("data" + os.sep):
            rest = path[len("data/"):] if len(path) > 4 else ""
            path = os.path.join(DATA_DIR, rest)
        else:
            path = os.path.join(_root, path)
    return os.path.normpath(path)


def resolve_or_create_jd(conn: sqlite3.Connection, company: str, role: str,
                         file_path: str) -> tuple[int, str]:
    """Find the jds row for this job, creating it if the job was never evaluated.

    Returns (jd_id, action), where action is 'found' | 'adopted' | 'created' so the
    caller can report what happened in its own voice. Never returns None for the id:
    an application with a NULL jd_id is orphaned from every report that joins through
    jds, and a NULL jd_id also makes `WHERE jd_id IS ?` match *any* other orphan.

    Does not commit — the caller owns the transaction.

    This is the single definition of the operation. It previously existed as three
    hand-maintained copies (generate_resume, track_application, generate_letter) that
    drifted apart twice, each time producing a data bug.
    """
    row = conn.execute("SELECT id FROM jds WHERE file_path = ?", (file_path,)).fetchone()
    if row:
        return row[0], "found"

    # Fall back to company+role before inserting, so a row created with a different
    # or absent file_path (a pasted-JD lead stub, or a collaborator-sourced import)
    # gets adopted rather than duplicated.
    row = conn.execute(
        "SELECT id FROM jds WHERE company = ? AND role = ?", (company, role)
    ).fetchone()
    if row:
        conn.execute("UPDATE jds SET file_path = ? WHERE id = ?", (file_path, row[0]))
        return row[0], "adopted"

    cur = conn.execute(
        "INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
        (company, role, file_path),
    )
    return cur.lastrowid, "created"


def get_conn() -> sqlite3.Connection:
    # DATA_DIR is entirely gitignored (nothing under data/ is tracked), so a
    # genuinely fresh clone has no data/ directory at all -- sqlite3.connect()
    # can create the DB file itself but not a missing parent directory, and
    # every one of this function's several dozen callers shouldn't each have
    # to remember to mkdir first. Confirmed 2026-08-16 testing a clean-clone
    # setup: this raised sqlite3.OperationalError on the very first init_db()
    # call, which would have hit every new user on first setup.
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with open(_SCHEMA) as f:
        sql = f.read()
    with get_conn() as conn:
        conn.executescript(sql)


def get_contact() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM contact ORDER BY id LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("No contact record found. Run migrate.py first.")
        return dict(row)


def get_education() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM education ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]


def register_file(
    file_path: str,
    file_type: str,
    summary: str,
    description: str | None = None,
    jd_id: int | None = None,
    application_id: int | None = None,
    story_id: int | None = None,
    source: str = "auto",
    source_urls: list[str] | None = None,
) -> int:
    """Insert or update a file_registry record. Returns the row id."""
    import json as _json
    abs_path = os.path.abspath(file_path)
    try:
        rel_path = os.path.relpath(abs_path, _root)
    except ValueError:
        rel_path = abs_path

    file_size = None
    file_mtime = None
    if os.path.exists(abs_path):
        st = os.stat(abs_path)
        file_size = st.st_size
        file_mtime = datetime.fromtimestamp(st.st_mtime).isoformat()

    urls_json = _json.dumps(source_urls) if source_urls else None

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO file_registry
               (jd_id, application_id, story_id, file_path, file_type, summary, description,
                file_size, file_mtime, source_urls, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(file_path) DO UPDATE SET
                   jd_id=excluded.jd_id,
                   application_id=excluded.application_id,
                   story_id=excluded.story_id,
                   file_type=excluded.file_type,
                   summary=excluded.summary,
                   description=excluded.description,
                   file_size=excluded.file_size,
                   file_mtime=excluded.file_mtime,
                   source_urls=COALESCE(excluded.source_urls, file_registry.source_urls),
                   source=excluded.source""",
            (jd_id, application_id, story_id, rel_path, file_type, summary, description,
             file_size, file_mtime, urls_json, source),
        )
        return cur.lastrowid
