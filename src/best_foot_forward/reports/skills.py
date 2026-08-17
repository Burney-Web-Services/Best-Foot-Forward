def hr(char="─", width=60):
    print(char * width)


# COALESCE(canonical_label, lower(skill_label)): rows written before the
# canonicalization migration (or never backfilled) still group sanely on the
# raw lowercase label; rows with a canonical_label (the normal case going
# forward) group on the alias-normalized form, which is what lets "k8s" and
# "kubernetes" mentions across different JDs collapse into one real count
# instead of staying two singletons a demand-threshold filter throws away.
_GROUP_KEY = "COALESCE(canonical_label, lower(skill_label))"


def view_frequency(conn, limit=30):
    print(f"\n{'TOP DEMANDED SKILLS':^60}")
    hr()
    rows = conn.execute(f"""
        SELECT MAX(skill_label) as skill_label, {_GROUP_KEY} as grp,
               COUNT(*) as demand, MAX(skill_id) as skill_id
        FROM jd_required_skills
        GROUP BY grp
        ORDER BY demand DESC, grp
        LIMIT ?
    """, (limit,)).fetchall()

    total_jds = conn.execute("SELECT COUNT(*) FROM jds WHERE file_path IS NOT NULL").fetchone()[0]
    print(f"  Across {total_jds} scanned JDs\n")

    for i, r in enumerate(rows, 1):
        pct = int(r["demand"] / total_jds * 100) if total_jds else 0
        in_taxonomy = "✓" if r["skill_id"] else " "
        print(f"  {i:2}. [{in_taxonomy}] {r['grp']:<35} {r['demand']:>3} JDs  ({pct}%)")

    print(f"\n  [✓] = matched a group in your own skills library."
          f"\n        A blank row is demanded by employers but not claimed in your"
          f"\n        profile — see the skill gaps report.")


def vocabulary_health(conn) -> dict:
    """What fraction of indexed skill terms lie OUTSIDE the profile's own
    skills/bullets vocabulary? This is the only thing that distinguishes "you
    have no gaps" from "gaps were filtered out before the query ran" — a gap
    report built on a vocabulary derived from the profile it measures can
    return plausible-looking rows and no error, which is exactly what
    happened before this fix (of every label the old extractor ever produced,
    all but one were already in the profile or a small hardcoded list)."""
    profile_terms = set()
    for row in conn.execute("SELECT content FROM skills"):
        for term in row["content"].split(","):
            profile_terms.add(term.strip().lower())
    for row in conn.execute("SELECT text FROM bullets"):
        profile_terms.update(row["text"].lower().split())

    all_labels = [r[0] for r in conn.execute(f"SELECT DISTINCT {_GROUP_KEY} FROM jd_required_skills")]
    total = len(all_labels)
    if total == 0:
        return {"total": 0, "outside": 0, "outside_fraction": None}

    outside = 0
    for label in all_labels:
        label_lower = label.lower()
        if label_lower in profile_terms:
            continue
        if any(label_lower in t or t in label_lower for t in profile_terms if len(t) > 3):
            continue
        outside += 1

    return {"total": total, "outside": outside, "outside_fraction": outside / total}


def view_gaps(conn, min_demand=2):
    print(f"\n{'SKILL GAPS — demanded but thin or absent in profile':^60}")
    hr()

    health = vocabulary_health(conn)
    if health["total"] and health["outside_fraction"] is not None and health["outside_fraction"] < 0.10:
        print(f"  ⚠  Skill-gap vocabulary looks closed: {health['total'] - health['outside']} of "
              f"{health['total']} indexed terms are already in your skills profile.")
        print(f"     That can mean gaps were filtered out before this query ran — not that")
        print(f"     you don't have any. If these JDs were indexed before the canonicalization")
        print(f"     fix, re-index them:")
        print(f"       python3 -m best_foot_forward.utils.reindex_jd_skills --all")
        print()

    profile_terms = set()
    for row in conn.execute("SELECT content FROM skills"):
        for term in row["content"].split(","):
            profile_terms.add(term.strip().lower())

    for row in conn.execute("SELECT text FROM bullets"):
        profile_terms.update(row["text"].lower().split())

    rows = conn.execute(f"""
        SELECT MAX(skill_label) as skill_label, {_GROUP_KEY} as grp,
               COUNT(*) as demand, MAX(skill_id) as skill_id
        FROM jd_required_skills
        GROUP BY grp
        ORDER BY demand DESC
    """).fetchall()

    gaps, seen_once = [], []
    for r in rows:
        label_lower = r["grp"].lower()
        if label_lower in profile_terms:
            continue
        if any(label_lower in t or t in label_lower for t in profile_terms if len(t) > 3):
            continue
        if r["demand"] >= min_demand:
            gaps.append(r)
        elif r["demand"] == 1:
            seen_once.append(r)

    total_jds = conn.execute("SELECT COUNT(*) FROM jds WHERE file_path IS NOT NULL").fetchone()[0]

    if not gaps and not seen_once:
        print("  No significant gaps found.")
        return

    if gaps:
        for r in gaps:
            pct = int(r["demand"] / total_jds * 100) if total_jds else 0
            print(f"  {r['grp']:<40} {r['demand']:>3} JDs  ({pct}%)")
    else:
        print(f"  No gaps demanded by {min_demand}+ JDs.")

    # A requirement seen in exactly one role you actually applied to is still
    # a real gap — the old demand>=2 filter made these structurally invisible.
    if seen_once:
        print(f"\n  Seen once (below the {min_demand}-JD threshold, still worth knowing about):")
        for r in seen_once[:15]:
            print(f"    {r['grp']}")


def view_by_company(conn):
    print(f"\n{'SKILLS BY COMPANY':^60}")
    hr()

    jds = conn.execute("SELECT id, company, role FROM jds ORDER BY company").fetchall()
    for jd in jds:
        skills = conn.execute(
            "SELECT skill_label FROM jd_required_skills WHERE jd_id = ? ORDER BY skill_label",
            (jd["id"],)
        ).fetchall()
        if not skills:
            continue
        print(f"\n  {jd['company']} — {jd['role']}")
        print(f"    {', '.join(r['skill_label'] for r in skills)}")


def view_salaries(conn):
    print(f"\n{'SALARY RANGES BY ROLE':^60}")
    hr()

    rows = conn.execute("""
        SELECT company, role, salary_min, salary_max
        FROM jds
        ORDER BY salary_max DESC NULLS LAST, company
    """).fetchall()

    has_any = False
    for r in rows:
        if r["salary_min"] or r["salary_max"]:
            has_any = True
            lo = f"${r['salary_min']:,}" if r["salary_min"] else "?"
            hi = f"${r['salary_max']:,}" if r["salary_max"] else "?"
            print(f"  {r['company']:<25} {lo} – {hi}")

    if not has_any:
        print("  No salary data found. Run scan_jds.py --rescan to extract from JD files.")

    no_salary = [r for r in rows if not r["salary_min"] and not r["salary_max"]]
    if no_salary:
        print(f"\n  No salary listed ({len(no_salary)}): {', '.join(r['company'] for r in no_salary)}")
