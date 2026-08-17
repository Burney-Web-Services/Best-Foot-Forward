"""Backfill jd_required_skills for JDs indexed before the skill-gap-vocabulary
fix (jd_skills.py) — either re-extracting from JD text (for rows with a
readable file_path) or re-canonicalizing existing labels in place (for
imported rows with no file, from a secondary machine's sync_leads payload).

Never touches evaluated_at, score, summary, or lead_status — those are
evaluate-job's and triage_lead's, and a reindex is purely an indexing pass,
same discipline scan_jds.py --rescan already follows.

Usage:
    python3 -m best_foot_forward.utils.reindex_jd_skills --all [--dry-run] [--llm]
    python3 -m best_foot_forward.utils.reindex_jd_skills --jd-id 42
    python3 -m best_foot_forward.utils.reindex_jd_skills --since 2026-07-01

--llm is opt-in and off by default: a bulk reindex over every JD in the DB
would otherwise silently burn an API call per row from what looks like a
local housekeeping script. Without it, only the shipped lexicon and the
user's own skills table are used -- the same fully-offline extraction every
other reindex path already relies on.
"""
from __future__ import annotations

import argparse
import os
import sys

from best_foot_forward.db import get_conn
from best_foot_forward.utils.jd_skills import (
    Term,
    build_compound_part_index,
    build_term_index,
    canonicalize,
    extract_terms,
)
from best_foot_forward.utils.scan_jds import extract_odt_text


def _select_jds(conn, jd_id=None, since=None):
    if jd_id is not None:
        return conn.execute("SELECT id, file_path FROM jds WHERE id = ?", (jd_id,)).fetchall()
    if since is not None:
        return conn.execute(
            "SELECT id, file_path FROM jds WHERE evaluated_at >= ? OR created_at >= ?",
            (since, since),
        ).fetchall()
    return conn.execute("SELECT id, file_path FROM jds").fetchall()


def _read_jd_text(file_path: str) -> str | None:
    if not file_path or not os.path.exists(file_path):
        return None
    if file_path.lower().endswith(".odt"):
        return extract_odt_text(file_path) or None
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _profile_lookup(conn) -> dict[str, str]:
    """term_lower -> skill_id for everything the profile claims, including the
    halves of slash-joined entries ("JavaScript/TypeScript").

    build_term_index() is sorted longest-first and comes first, so a direct
    match wins over a compound half — the same precedence extract_terms() uses.
    """
    lookup: dict[str, str] = {}
    for term, skill_id in list(build_term_index(conn)) + list(build_compound_part_index(conn)):
        lookup.setdefault(term, skill_id)
    return lookup


def reindex_one(conn, jd_id: int, file_path: str | None, use_llm: bool = False, dry_run: bool = False) -> dict:
    """Reindex a single JD's jd_required_skills. Returns a summary dict."""
    text = _read_jd_text(file_path) if file_path else None

    if text:
        # Readable file: re-extract from source text, same as a fresh evaluation would.
        terms = extract_terms(text, conn)
        mode = "re-extracted"
    else:
        # No readable text (imported row, or file moved/deleted): re-canonicalize
        # the labels already on file rather than losing them.
        existing = conn.execute(
            "SELECT skill_label, skill_id, source FROM jd_required_skills WHERE jd_id = ?", (jd_id,)
        ).fetchall()
        # Re-derive skill_id against the *current* profile instead of carrying the
        # stored value forward. skill_id is written at index time, so a row indexed
        # before a skill existed in the profile stayed NULL forever — and these
        # file-less rows (imported leads) can never be re-extracted to fix it. That
        # is the "my skills never get updated" case: on a real database, 28 Python
        # mentions read as unclaimed purely because their leads arrived over sync
        # with no JD file behind them.
        lookup = _profile_lookup(conn)
        terms = []
        for row in existing:
            canonical = canonicalize(row["skill_label"]) or row["skill_label"]
            skill_id = (row["skill_id"]
                        or lookup.get(row["skill_label"].strip().lower())
                        or lookup.get(canonical.strip().lower()))
            terms.append(Term(label=row["skill_label"], canonical=canonical,
                              skill_id=skill_id, source=row["source"] or "profile"))
        mode = "re-canonicalized in place"

    if dry_run:
        return {"jd_id": jd_id, "mode": mode, "term_count": len(terms), "written": False}

    conn.execute("DELETE FROM jd_required_skills WHERE jd_id = ?", (jd_id,))
    for term in terms:
        conn.execute(
            "INSERT INTO jd_required_skills (jd_id, skill_label, skill_id, canonical_label, source) "
            "VALUES (?, ?, ?, ?, ?)",
            (jd_id, term.label, term.skill_id, term.canonical, term.source),
        )
    conn.commit()
    return {"jd_id": jd_id, "mode": mode, "term_count": len(terms), "written": True}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sel = p.add_mutually_exclusive_group(required=True)
    sel.add_argument("--all", action="store_true", help="reindex every jds row")
    sel.add_argument("--jd-id", type=int, help="reindex a single jds row")
    sel.add_argument("--since", help="reindex jds evaluated or created on/after this ISO date")
    p.add_argument("--llm", action="store_true",
                   help="not yet supported for bulk backfill (no cached subagent output to "
                        "reuse) -- reserved for future use; currently a no-op flag")
    p.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = p.parse_args()

    conn = get_conn()
    try:
        rows = _select_jds(conn, jd_id=args.jd_id, since=args.since)
        if not rows:
            print("No matching jds rows.")
            return

        re_extracted = re_canonicalized = total_terms = 0
        for row in rows:
            result = reindex_one(conn, row["id"], row["file_path"], use_llm=args.llm, dry_run=args.dry_run)
            total_terms += result["term_count"]
            if result["mode"] == "re-extracted":
                re_extracted += 1
            else:
                re_canonicalized += 1

        verb = "would reindex" if args.dry_run else "reindexed"
        print(f"{verb} {len(rows)} JD(s): {re_extracted} re-extracted from source text, "
              f"{re_canonicalized} re-canonicalized in place ({total_terms} total term rows)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
