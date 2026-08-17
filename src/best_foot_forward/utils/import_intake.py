"""
Imports intake data from data/session/intake_data.py into SQLite.
Written by the /onboard skill; safe to re-run (upsert throughout).

Usage:
    python3 src/best_foot_forward/utils/import_intake.py
"""

import sys as _sys, os as _os
_sys.path.insert(0, (_os.environ.get('BFF_DATA_DIR') or _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../../../data'))) + '/session')
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))
del _sys, _os

import re
import os
from db import get_conn, init_db
from utils.audit_log import log_event


def slugify(name: str) -> str:
    """'Kuat Design Systems' → 'kuat'  |  'Chandrila Data Collective' → 'chandril'"""
    first_word = name.strip().split()[0]
    return re.sub(r'[^a-z0-9]', '', first_word.lower())[:8]


def next_bullet_seq(conn, slug: str) -> int:
    """Return the next available sequence number for a given employer slug."""
    pattern = f"{slug}-%"
    rows = conn.execute(
        "SELECT id FROM bullets WHERE id LIKE ? ORDER BY id", (pattern,)
    ).fetchall()
    if not rows:
        return 1
    # Parse the highest trailing number found
    nums = []
    for row in rows:
        m = re.search(r'-(\d+)$', row["id"])
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


def skill_id_from_label(label: str) -> str:
    """'AI & Product Engineering:' → 'skills-ai-product-engineering'"""
    clean = label.lower().rstrip(':').strip()
    slug = re.sub(r'[^a-z0-9]+', '-', clean).strip('-')
    return f"skills-{slug}"


def run():
    import intake_data as d

    init_db()
    conn = get_conn()

    # ── Contact ───────────────────────────────────────────────────────────────
    c = d.CONTACT
    conn.execute(
        "INSERT OR REPLACE INTO contact (id, name, phone, email, location) VALUES (1, ?, ?, ?, ?)",
        (c["name"], c.get("phone", ""), c.get("email", ""), c.get("location", ""))
    )
    print(f"  Contact: {c['name']}")

    # ── Education ─────────────────────────────────────────────────────────────
    edu_count = 0
    for i, edu in enumerate(d.EDUCATION):
        existing = conn.execute(
            "SELECT id FROM education WHERE institution = ?", (edu["institution"],)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO education (institution, location, degree, sort_order) VALUES (?, ?, ?, ?)",
                (edu["institution"], edu.get("location", ""), edu.get("degree", ""), edu.get("sort_order", i))
            )
            edu_count += 1
    print(f"  Education: {edu_count} new record(s) (skipped existing)")

    # ── Employers ─────────────────────────────────────────────────────────────
    employer_id_map: dict[str, int] = {}
    emp_count = 0
    for emp in d.EMPLOYERS:
        existing = conn.execute(
            "SELECT id FROM employers WHERE name = ?", (emp["name"],)
        ).fetchone()
        if existing:
            employer_id_map[emp["name"]] = existing["id"]
        else:
            conn.execute(
                "INSERT INTO employers (name, location, start_date, end_date, sort_order, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    emp["name"],
                    emp.get("location", ""),
                    emp.get("start_date"),
                    emp.get("end_date"),
                    emp.get("sort_order", 0),
                    emp.get("notes", ""),
                )
            )
            row = conn.execute("SELECT id FROM employers WHERE name = ?", (emp["name"],)).fetchone()
            employer_id_map[emp["name"]] = row["id"]
            emp_count += 1
    print(f"  Employers: {emp_count} new, {len(d.EMPLOYERS) - emp_count} already existed")

    # ── Bullets ───────────────────────────────────────────────────────────────
    slug_seq: dict[str, int] = {}
    bullet_count = 0
    bullet_skipped = 0
    for b in d.BULLETS:
        emp_name = b["employer"]
        if emp_name not in employer_id_map:
            print(f"  WARNING: bullet employer '{emp_name}' not found in EMPLOYERS — skipping bullet: {b['text'][:60]}")
            continue

        # Auto-generate ID if not provided; check for content duplicates first
        bullet_id = b.get("id")
        if not bullet_id:
            dup = conn.execute(
                "SELECT id FROM bullets WHERE employer_id = ? AND text = ?",
                (employer_id_map[emp_name], b["text"])
            ).fetchone()
            if dup:
                bullet_skipped += 1
                continue
            slug = slugify(emp_name)
            if slug not in slug_seq:
                slug_seq[slug] = next_bullet_seq(conn, slug)
            bullet_id = f"{slug}-{slug_seq[slug]:03d}"
            slug_seq[slug] += 1
        else:
            existing = conn.execute("SELECT id FROM bullets WHERE id = ?", (bullet_id,)).fetchone()
            if existing:
                bullet_skipped += 1
                continue

        conn.execute(
            "INSERT INTO bullets (id, employer_id, role, text) VALUES (?, ?, ?, ?)",
            (bullet_id, employer_id_map[emp_name], b.get("role", ""), b["text"])
        )
        for track in b.get("tracks", []):
            conn.execute(
                "INSERT OR IGNORE INTO bullet_tracks (bullet_id, track) VALUES (?, ?)",
                (bullet_id, track)
            )
        for theme in b.get("themes", []):
            conn.execute(
                "INSERT OR IGNORE INTO bullet_themes (bullet_id, theme) VALUES (?, ?)",
                (bullet_id, theme)
            )
        bullet_count += 1

    print(f"  Bullets: {bullet_count} new, {bullet_skipped} already existed")

    # ── Skills ────────────────────────────────────────────────────────────────
    skill_count = 0
    skill_skipped = 0
    for s in d.SKILLS:
        skill_id = s.get("id") or skill_id_from_label(s["label"])

        existing = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if existing:
            skill_skipped += 1
            continue

        conn.execute(
            "INSERT INTO skills (id, label, content) VALUES (?, ?, ?)",
            (skill_id, s["label"], s["content"])
        )
        for track in s.get("tracks", []):
            conn.execute(
                "INSERT OR IGNORE INTO skill_tracks (skill_id, track) VALUES (?, ?)",
                (skill_id, track)
            )
        for theme in s.get("themes", []):
            conn.execute(
                "INSERT OR IGNORE INTO skill_themes (skill_id, theme) VALUES (?, ?)",
                (skill_id, theme)
            )
        skill_count += 1

    print(f"  Skills: {skill_count} new, {skill_skipped} already existed")

    conn.commit()
    conn.close()

    log_event(
        "onboard", "import_intake",
        contact=c["name"], education_new=edu_count, employers_new=emp_count,
        bullets_new=bullet_count, skills_new=skill_count,
    )

    print()
    print("Import complete. Run export_cache.py to regenerate JSON caches.")


if __name__ == "__main__":
    run()
