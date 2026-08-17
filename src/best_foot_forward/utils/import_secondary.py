"""
Shared logic for importing leads from a secondary sourcer into the primary DB.

Used by:
  - mcp_server.py    (sync_leads MCP tool — receives inline leads array, live per-job push)
  - /push-leads      (drains a secondary's local bff-leads graph → sync_leads)

Dedupe key is (company, role). Existing rows are UPSERTed — a re-scored lead updates its
score/url/summary/salary rather than being silently skipped.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))
del _sys, _os

from db import get_conn, register_file


def _first_url(lead: dict):
    """Prefer an explicit `url`; fall back to the first of `source_urls`."""
    if lead.get("url"):
        return lead["url"]
    urls = lead.get("source_urls") or []
    return urls[0] if urls else None


def insert_leads(leads: list[dict], source: str = "secondary") -> tuple[int, int, int]:
    """Insert/update leads in the jds table (lead_status='pending').

    `source` is the caller identity (e.g. 'alex'), recorded on the row.
    Deduplicates by (company, role): new rows are inserted, existing rows are
    UPSERTed (score/url/summary/salary refreshed when the incoming value is present).

    Returns (imported, updated, skipped).
    """
    conn = get_conn()
    imported = updated = skipped = 0

    try:
        for lead in leads:
            company   = (lead.get("company") or "").strip()
            role      = (lead.get("role")    or "").strip()
            score     = lead.get("score")
            sal_min   = lead.get("salary_min")
            sal_max   = lead.get("salary_max")
            sal_curr  = lead.get("salary_currency", "USD")
            file_path = lead.get("file_path")
            eval_at   = lead.get("evaluated_at")
            skills    = lead.get("required_skills") or []
            url       = _first_url(lead)
            summary   = lead.get("summary")
            src_urls  = lead.get("source_urls") or []

            if not company or not role:
                skipped += 1
                continue

            existing = conn.execute(
                "SELECT id FROM jds WHERE company=? AND role=?", (company, role)
            ).fetchone()

            if existing:
                jd_id = existing["id"]
                # UPSERT: refresh fields only when a new value is supplied (COALESCE
                # keeps prior data rather than nulling it out on a partial re-push).
                conn.execute(
                    """UPDATE jds SET
                           score           = COALESCE(?, score),
                           url             = COALESCE(?, url),
                           summary         = COALESCE(?, summary),
                           salary_min      = COALESCE(?, salary_min),
                           salary_max      = COALESCE(?, salary_max),
                           salary_currency = COALESCE(?, salary_currency),
                           evaluated_at    = COALESCE(?, evaluated_at)
                       WHERE id=?""",
                    (score, url, summary, sal_min, sal_max, sal_curr, eval_at, jd_id),
                )
                updated += 1
            else:
                conn.execute(
                    """INSERT INTO jds
                       (company, role, file_path, score, evaluated_at,
                        salary_min, salary_max, salary_currency, url, summary,
                        source, lead_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (company, role, file_path, score, eval_at,
                     sal_min, sal_max, sal_curr, url, summary, source),
                )
                jd_id = conn.execute(
                    "SELECT id FROM jds WHERE company=? AND role=? ORDER BY id DESC LIMIT 1",
                    (company, role),
                ).fetchone()[0]
                imported += 1

            for skill_label in skills:
                conn.execute(
                    "INSERT OR IGNORE INTO jd_required_skills (jd_id, skill_label) VALUES (?, ?)",
                    (jd_id, skill_label),
                )

            if file_path:
                register_file(
                    file_path=file_path,
                    file_type="jd",
                    summary=f"Job description: {company} – {role}",
                    jd_id=jd_id,
                    source="sync",
                    source_urls=src_urls or None,
                )
            conn.commit()

    finally:
        conn.close()

    return imported, updated, skipped
