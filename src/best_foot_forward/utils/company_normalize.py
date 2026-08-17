"""Company-name normalization for the BFF -> Logseq migration.

`scan_jds.py` walked ``data/applications/`` and registered a ``jds`` row for
many files that are not job descriptions at all (prep notes, thank-you letters,
research snippets). Those rows carry a bogus ``company`` -- usually the *role*
directory name (e.g. ``Software_Engineering_Manager``) or a pipeline-artifact
folder (``Research-and-Prep``, ``research``, ``Not-Pursued``). This module
classifies every ``jds`` row so the migration can:

  * group real leads/applications under a single canonical company,
  * recover the true company from the file path for role-placeholder rows,
  * quarantine (never delete) the non-JD junk registrations.

Data-driven signal for a mis-registration: the stored ``company`` equals the
row's own *role directory* (``basename(dirname(file_path))``). For a real row
the company is the *parent* of the role directory. Junk rows additionally point
at a non-JobDesc file, which is how a real recovered role is told apart from a
mis-registered artifact in the same directory.

Public API used by ``export_graph.py``:
  * ``canonical_company(name)`` -> display name after alias folding
  * ``company_slug(name)``      -> hyphenated ``org:`` slug (e.g. ``college-board``)
  * ``classify_row(row)``       -> Classification namedtuple

Run directly to emit the human review report:
  ``python -m best_foot_forward.utils.company_normalize [--out PATH]``
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
from collections import defaultdict
from typing import NamedTuple, Optional

# --- configuration ---------------------------------------------------------

# 'company' strings that are really pipeline/directory artifacts, never orgs.
JUNK_COMPANIES = {
    "research", "Research-and-Prep", "Resumes-and-Letters", "Not-Pursued", "v2",
}

# Path fragments that mark a row as a mis-registered non-JD file. (A real
# company whose JD merely sits in an old "Not-Pursued" triage folder is NOT
# junk -- only the literal ``Not-Pursued`` company token is, see JUNK_COMPANIES.)
JUNK_PATH_FRAGMENTS = ("/Research-and-Prep/", "/research/")

# Hand-curated cross-spelling merges a pure alphanumeric key cannot catch.
# key = raw company string as stored, value = canonical display name.
EXPLICIT_ALIASES = {
    "Perforce Software": "Perforce",
    "Perforce_Software": "Perforce",
    "OneStream Software": "OneStream",
    "McGrawHill_Platform": "McGrawHill",
    "Edia Learning": "Edia",                          # confirmed same org (Paul, 2026-07-16)
    "Request Technology (Am Law 100 firm)": "Request Technology",  # same recruiter
}

# When variants share an alphanumeric key, prefer this display spelling.
CANONICAL_DISPLAY = {
    "babylist": "Babylist",
    "brightwheel": "Brightwheel",
    "collegeboard": "College Board",
    "parentsquare": "ParentSquare",
    "teachingstrategies": "Teaching Strategies",
    "wex": "WEX",
}

# Pairs a human should eyeball; we do NOT auto-merge these.
# (Edia/Edia Learning and Request Technology pair resolved -> EXPLICIT_ALIASES.)
REVIEW_CANDIDATES = []

_JOBDESC_RE = re.compile(r"job[\s_-]*desc", re.IGNORECASE)


# --- primitives ------------------------------------------------------------

def alnum_key(name: str) -> str:
    """Normalized comparison key: lowercase, alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def company_slug(name: str) -> str:
    """Hyphenated ``org:`` slug matching the existing convention (goguardian,
    college-board, teaching-strategies)."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def canonical_company(name: str) -> str:
    """Display name after explicit-alias and alnum-key canonicalization."""
    if name in EXPLICIT_ALIASES:
        name = EXPLICIT_ALIASES[name]
    return CANONICAL_DISPLAY.get(alnum_key(name), name)


def _role_dir(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    return os.path.basename(os.path.dirname(file_path)) or None


def _applications_company(file_path: Optional[str]) -> Optional[str]:
    """The directory segment immediately after ``/applications/`` (the true
    company in the BFF artifact tree), or None when the path is elsewhere."""
    if not file_path:
        return None
    parts = file_path.replace("\\", "/").split("/")
    if "applications" in parts:
        i = parts.index("applications")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def _is_jobdesc_file(file_path: Optional[str]) -> bool:
    if not file_path:
        return False
    return bool(_JOBDESC_RE.search(os.path.basename(file_path)))


# --- classification --------------------------------------------------------

class Classification(NamedTuple):
    jd_id: int
    orig_company: str
    role: str
    file_path: Optional[str]
    role_dir: Optional[str]
    canonical_company: Optional[str]
    org_slug: Optional[str]
    kind: str      # 'clean' | 'recovered' | 'alias' | 'quarantine'
    reason: str


def classify_row(row) -> Classification:
    """Classify one jds row (needs keys: id, company, role, file_path)."""
    jd_id = row["id"]
    company = row["company"]
    role = row["role"] or ""
    fp = row["file_path"]
    rdir = _role_dir(fp)

    def result(kind, canon, reason):
        return Classification(
            jd_id, company, role, fp, rdir,
            canon, company_slug(canon) if canon else None, kind, reason,
        )

    # 1. Non-JD junk: artifact folders or junk path fragments.
    if company in JUNK_COMPANIES:
        return result("quarantine", None,
                      f"junk company token '{company}' (pipeline/dir artifact, not a JD)")
    if fp and any(frag in fp.replace("\\", "/") for frag in JUNK_PATH_FRAGMENTS):
        return result("quarantine", None,
                      "file lives in a research/prep/not-pursued folder, not a JD")

    apps_company = _applications_company(fp)

    # 2. Role-placeholder: stored company == the row's own role directory AND a
    #    *different* real company sits above it under /applications/. (The old
    #    flat structure ``.../v6/Andiamo/AndiamofJobDesc.txt`` has company==rdir
    #    with no differing parent -- that is a legit company, not a placeholder.)
    if (rdir and apps_company
            and alnum_key(company) == alnum_key(rdir)
            and alnum_key(company) != alnum_key(apps_company)):
        if not _is_jobdesc_file(fp):
            return result("quarantine", canonical_company(apps_company),
                          f"mis-registered artifact under {apps_company}/{rdir} "
                          f"(file is not a JobDesc); real JD row exists separately")
        return result("recovered", canonical_company(apps_company),
                      f"role name used as company; recovered '{apps_company}' from path")

    # 3. Real company; fold spelling/casing variants.
    canon = canonical_company(company)
    if canon != company:
        return result("alias", canon, f"folded '{company}' -> '{canon}'")
    return result("clean", canon, "")


# --- report ----------------------------------------------------------------

def _load_rows(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT id, company, role, file_path FROM jds ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def build_report(db_path: str) -> str:
    rows = [classify_row(r) for r in _load_rows(db_path)]

    by_company = defaultdict(list)
    quarantined = []
    for c in rows:
        (quarantined if c.kind == "quarantine" else by_company[c.canonical_company]).append(c)

    # Unresolved alnum-key collisions among *kept* companies (potential merges
    # we did not auto-apply).
    key_groups = defaultdict(set)
    for name in by_company:
        key_groups[alnum_key(name)].add(name)
    collisions = {k: sorted(v) for k, v in key_groups.items() if len(v) > 1}

    lines = []
    lines.append("# BFF Company Normalization — Review Report")
    lines.append("")
    lines.append(f"- Source DB: `{db_path}`")
    lines.append(f"- Total jds rows: **{len(rows)}**")
    lines.append(f"- Distinct canonical companies: **{len(by_company)}**")
    kept = sum(len(v) for v in by_company.values())
    lines.append(f"- Rows kept (clean/recovered/alias): **{kept}**")
    lines.append(f"- Rows quarantined (non-JD junk): **{len(quarantined)}**")
    lines.append("")
    lines.append("Nothing here is applied to the DB — this is for sign-off. "
                 "Quarantined rows are excluded from page generation; their files "
                 "survive via `file_registry` and can be linked from the parent "
                 "company's Notes/Prep during the salvage sweep.")
    lines.append("")

    # Merges actually applied (alias + recovered folding into a canonical).
    lines.append("## Merges applied (variants folded into one company)")
    lines.append("")
    any_merge = False
    for company in sorted(by_company, key=lambda s: s.lower()):
        variants = sorted({c.orig_company for c in by_company[company]
                           if c.orig_company != company})
        if variants:
            any_merge = True
            lines.append(f"- **{company}** ⟵ " + ", ".join(f"`{v}`" for v in variants))
    if not any_merge:
        lines.append("_(none)_")
    lines.append("")

    # Recovered placeholders.
    recovered = [c for v in by_company.values() for c in v if c.kind == "recovered"]
    lines.append(f"## Recovered from path (role name used as company) — {len(recovered)}")
    lines.append("")
    for c in sorted(recovered, key=lambda c: (c.canonical_company.lower(), c.jd_id)):
        lines.append(f"- jd `{c.jd_id}`: `{c.orig_company}` → **{c.canonical_company}** "
                     f"(role dir `{c.role_dir}`)")
    if not recovered:
        lines.append("_(none)_")
    lines.append("")

    # Flags for human judgement.
    lines.append("## Flags — review, NOT auto-merged")
    lines.append("")
    if collisions:
        lines.append("**Same normalized key, kept separate (possible duplicate company):**")
        for k, names in sorted(collisions.items()):
            lines.append(f"- {' / '.join(names)}")
        lines.append("")
    present = {c.canonical_company for v in by_company.values() for c in v}
    cand = [(a, b) for a, b in REVIEW_CANDIDATES if a in present and b in present]
    if cand:
        lines.append("**Likely-same companies (left separate pending your call):**")
        for a, b in cand:
            lines.append(f"- `{a}`  vs  `{b}`")
        lines.append("")
    if not collisions and not cand:
        lines.append("_(none)_")
        lines.append("")

    # Quarantine detail.
    lines.append(f"## Quarantined rows — {len(quarantined)} (excluded from page gen)")
    lines.append("")
    q_by_reason = defaultdict(list)
    for c in quarantined:
        tag = ("misregistered-artifact" if c.reason.startswith("mis-registered")
               else "junk-token" if "junk company token" in c.reason
               else "junk-folder")
        q_by_reason[tag].append(c)
    for tag in sorted(q_by_reason):
        lines.append(f"### {tag} ({len(q_by_reason[tag])})")
        for c in sorted(q_by_reason[tag], key=lambda c: c.jd_id):
            fp = c.file_path or "(no file)"
            lines.append(f"- jd `{c.jd_id}` `{c.orig_company}` — {c.reason}")
            lines.append(f"  - `{fp}`")
        lines.append("")

    # Full canonical company roster (kept rows).
    lines.append("## Canonical company roster (kept)")
    lines.append("")
    for company in sorted(by_company, key=lambda s: s.lower()):
        members = by_company[company]
        lines.append(f"- **{company}** (`org:{company_slug(company)}`) — "
                     f"{len(members)} row(s)")
    lines.append("")

    return "\n".join(lines)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_db = os.path.abspath(os.path.join(here, "..", "..", "..",
                                              "data", "best_foot_forward.db"))
    ap = argparse.ArgumentParser(description="Emit the company normalization review report.")
    ap.add_argument("--db", default=default_db)
    ap.add_argument("--out", default=None, help="Write report to this path (else stdout).")
    args = ap.parse_args()

    report = build_report(args.db)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
        print(f"Wrote report to {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
