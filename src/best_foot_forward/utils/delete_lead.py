"""Delete a jds row that was never applied to -- the single write path for
removing a lead, so its JD file gets removed from disk at the same time.

Before this existed, a `jds` row got deleted by hand (a raw `db_query.py`
DELETE), and nothing ever removed the JD file that row pointed at. The file
stayed on disk, and a later `scan_jds.py` pass over the same directory tree
found it, saw no `jds.file_path` match, and silently re-registered it as a
brand-new row -- resurrecting a lead that had been deliberately removed
(surfaced with Commerce, 2026-07-16; `scan_jds.py`'s canonical-company/role
matching added the same day closes half of this, this closes the other
half by not leaving the orphan file behind in the first place).

Refuses to delete a lead with any `applications` or `contacts` row still
pointing at it -- a real application or a scheduled interview should never
be casually deleted; deal with those explicitly first if this is genuinely
what's wanted. `jd_required_skills` cascades automatically (ON DELETE
CASCADE); any `file_registry` row for the removed file is deleted outright
rather than left dangling with a nulled jd_id.

Usage:
    python3 -m best_foot_forward.utils.delete_lead --jd-id 42 --dry-run
    python3 -m best_foot_forward.utils.delete_lead --jd-id 42
    python3 -m best_foot_forward.utils.delete_lead --file-path <path>
    python3 -m best_foot_forward.utils.delete_lead --company Affirm --role 'Backend Engineer'
"""
from __future__ import annotations

import argparse
import os
import sys

from best_foot_forward.db import get_conn
from best_foot_forward.utils.audit_log import log_event
from best_foot_forward.utils.scan_jds import is_jd_file
from best_foot_forward.utils.triage_lead import resolve_jd_id


def _blocking_refs(conn, jd_id: int) -> list[str]:
    reasons = []
    n = conn.execute("SELECT COUNT(*) FROM applications WHERE jd_id = ?", (jd_id,)).fetchone()[0]
    if n:
        reasons.append(f"{n} application(s)")
    n = conn.execute("SELECT COUNT(*) FROM contacts WHERE jd_id = ?", (jd_id,)).fetchone()[0]
    if n:
        reasons.append(f"{n} contact(s)")
    return reasons


def _jd_files_on_disk(file_path: str | None) -> list[str]:
    """The row's own file, plus any sibling file in the same directory that
    scan_jds.py's is_jd_file() would also treat as a JD -- an .odt/.txt pair
    left over from a format change is exactly the kind of leftover that
    would otherwise still get rediscovered."""
    if not file_path:
        return []
    found = []
    if os.path.exists(file_path):
        found.append(file_path)
    directory = os.path.dirname(file_path)
    if os.path.isdir(directory):
        for fname in os.listdir(directory):
            full = os.path.join(directory, fname)
            if full not in found and is_jd_file(fname) and os.path.isfile(full):
                found.append(full)
    return found


def delete_lead(conn, jd_id: int, dry_run: bool = False) -> dict:
    row = conn.execute(
        "SELECT id, company, role, file_path, lead_status FROM jds WHERE id = ?", (jd_id,)
    ).fetchone()
    if not row:
        raise LookupError(f"No jds row with id={jd_id}")

    blocking = _blocking_refs(conn, jd_id)
    if blocking:
        raise ValueError(
            f"Refusing to delete jds id={jd_id} ({row['company']} — {row['role']}): "
            f"referenced by {' and '.join(blocking)}. A real application or scheduled "
            "interview should not be casually deleted -- resolve those explicitly first "
            "if this is genuinely what's wanted."
        )

    files = _jd_files_on_disk(row["file_path"])
    result = {
        "jd_id": jd_id, "company": row["company"], "role": row["role"],
        "lead_status": row["lead_status"], "files_removed": files,
    }
    if dry_run:
        return result

    for f in files:
        os.remove(f)
    conn.execute("DELETE FROM file_registry WHERE jd_id = ?", (jd_id,))
    conn.execute("DELETE FROM jds WHERE id = ?", (jd_id,))
    conn.commit()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sel = p.add_mutually_exclusive_group(required=True)
    sel.add_argument("--jd-id", type=int, help="jds.id of the lead")
    sel.add_argument("--file-path", help="jds.file_path of the lead (canonicalized before lookup)")
    sel.add_argument("--company", help="company name (add --role if it has more than one open lead)")
    p.add_argument("--role", help="role name, to disambiguate --company")
    p.add_argument("--dry-run", action="store_true", help="show what would be deleted; delete nothing")
    args = p.parse_args()

    if args.role and not args.company:
        p.error("--role only applies with --company")

    conn = get_conn()
    try:
        jd_id = resolve_jd_id(conn, args.jd_id, args.file_path, args.company, args.role)
        result = delete_lead(conn, jd_id, dry_run=args.dry_run)
    except (LookupError, ValueError) as e:
        print(f"[delete_lead] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    verb = "Would delete" if args.dry_run else "Deleted"
    print(f"[delete_lead] {verb}: {result['company']} — {result['role']} "
          f"(jd_id={result['jd_id']}, lead_status={result['lead_status']})")
    if result["files_removed"]:
        for f in result["files_removed"]:
            print(f"  {'would remove' if args.dry_run else 'removed'}: {f}")
    else:
        print("  (no on-disk JD file found to remove)")

    if not args.dry_run:
        log_event("delete-lead", "delete_lead", **result)


if __name__ == "__main__":
    main()
