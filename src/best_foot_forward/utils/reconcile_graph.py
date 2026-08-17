"""Phase 6 (reverse sync): parse hand-edited Application pages back into the DB.

Markdown is master for the pipeline; the DB is the queryable index. When a human
edits a page's structured properties (status, stage, dates, score, ...) in
Logseq, this pulls those values back into best_foot_forward.db so reporting +
the MCP tools stay current.

Design (see the migration plan, risk #2): a **column-level UPSERT keyed on the
`bff-jd-id` / `bff-application-id` echoed in each page** — never drop-and-rebuild
(that would orphan application_bullets / application_skills / file_registry FKs).
Only the structured *property* fields are reconciled; prose body sections stay
markdown-only. Idempotent; `--dry-run` shows the diff without writing.

    python -m best_foot_forward.utils.reconcile_graph [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sqlite3
from pathlib import Path

import markdown_graph_kit as mgk

from best_foot_forward.db import DATA_DIR

PAGES = os.path.join(DATA_DIR, "BestFootForward", "pages")

# page property -> (table, column, caster). Keyed by the id property on the page.
JDS_FIELDS = {          # keyed by bff-jd-id
    "lead-status": ("lead_status", str),
    "lead-decided": ("lead_decided_at", "date"),
    "decline-reason": ("decline_reason", str),
    "decline-category": ("decline_category", str),
    "score": ("score", int),
    "salary-min": ("salary_min", int),
    "salary-max": ("salary_max", int),
    "salary-target": ("salary_target", int),
    "url": ("url", str),
}
APP_FIELDS = {          # keyed by bff-application-id
    "status": ("status", str),
    "stage": ("stage", str),
    "applied": ("applied_at", "date"),
    "concluded": ("concluded_at", "date"),
    "follow-up": ("follow_up_date", "date"),
    "follow-up-count": ("follow_up_count", int),
}




def _clean(val, caster):
    """Normalize a page value to a DB value. Strips [[..]], #, empty -> None."""
    if val is None:
        return None
    v = val.strip()
    if v in ("", "-"):
        return None
    v = re.sub(r"^\[\[|\]\]$", "", v).lstrip("#").strip()
    if caster == "date":
        m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", v)  # accepts YYYY/MM/DD or YYYY-MM-DD
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
    try:
        return caster(v)
    except (ValueError, TypeError):
        return v


def reconcile(db_path, dry_run=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    changes = []

    def apply_row(table, pk, id_val, fields, props):
        cur = conn.execute(f"SELECT * FROM {table} WHERE id=?", (id_val,)).fetchone()
        if not cur:
            return
        sets, args, diffs = [], [], []
        for prop, (col, caster) in fields.items():
            if prop not in props:
                continue
            new = _clean(props[prop], caster)
            old = cur[col]
            if caster == "date":
                # pages carry date-only; the DB may hold a full timestamp. Only
                # reconcile when the DATE actually differs, so we never truncate
                # the stored time on a no-op.
                if (str(old)[:10] if old else None) == (new or None):
                    continue
            elif str(old or "") == str(new or ""):
                continue
            sets.append(f"{col}=?"); args.append(new)
            diffs.append(f"{col}: {old!r} -> {new!r}")
        if sets:
            changes.append((table, id_val, diffs))
            if not dry_run:
                conn.execute(f"UPDATE {table} SET {','.join(sets)} WHERE id=?",
                             (*args, id_val))

    for p in glob.glob(PAGES + "/*___Application.md"):
        props = mgk.parse_page_properties(Path(p))
        if props.get("bff-jd-id", "").isdigit():
            apply_row("jds", "id", int(props["bff-jd-id"]), JDS_FIELDS, props)
        if props.get("bff-application-id", "").isdigit():
            apply_row("applications", "id", int(props["bff-application-id"]), APP_FIELDS, props)

    # #Lead pages share the JDS_FIELDS property set (lead-status/score/salary/url),
    # so hand-edits on a lead flow back to its jds row the same way.
    for p in glob.glob(PAGES + "/*___Lead.md"):
        props = mgk.parse_page_properties(Path(p))
        if props.get("bff-jd-id", "").isdigit():
            apply_row("jds", "id", int(props["bff-jd-id"]), JDS_FIELDS, props)

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"{'[dry-run] ' if dry_run else ''}reconciled {len(changes)} rows from pages")
    for table, idv, diffs in changes:
        print(f"  {table} #{idv}: " + "; ".join(diffs))
    return changes


def main():
    ap = argparse.ArgumentParser(description="Reverse-sync page edits into the DB index.")
    ap.add_argument("--db", default=os.path.join(DATA_DIR, "best_foot_forward.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    reconcile(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
