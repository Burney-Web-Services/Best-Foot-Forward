"""Persist a lead's JD text to disk at evaluation time, and index what it says.

Until now the JD file was only written during *tailoring*. A lead you evaluate and
pass on is never tailored, so its text was never saved — which meant every declined
lead had zero `jd_required_skills` rows and no salary unless the range happened to
be captured by hand. The declined pile could be counted and ranked but never asked
"what do the jobs I turn down have in common?", because the answer lives in the JD
text nobody kept.

This writes that text once, when the lead is scored, and extracts from it the same
two things `scan_jds.py` extracts: the posted salary range and the required-skills
terms. It deliberately does *not* go through `scan_jds.scan()`, which has two
behaviours that are right for a directory sweep and wrong here:

  1. It skips any file whose `file_path` already has a `jds` row — and the
     evaluate-job stub creates exactly that row, so a plain scan does nothing.
     Working around it with `--rescan` re-walks the whole asset tree.
  2. `--rescan` overwrites `evaluated_at` with the scan time. That column means
     "when this lead was scored"; `lead_decided_at` exists precisely because
     conflating a scoring date with a later date misleads the reports.

So the extractors are reused directly and the row is updated narrowly.

Usage:
    python3 -m best_foot_forward.utils.save_lead_jd --company 'Affirm' \\
        --role 'Software Engineer II, Backend (Test Infra)' \\
        --url 'https://...' --text-file /tmp/jd.txt

Prints the jd_id, which the caller uses for the score/summary UPDATE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from best_foot_forward.db import (
    DATA_DIR,
    _root,
    get_conn,
    register_file,
    resolve_jd_path,
    resolve_or_create_jd,
)
from best_foot_forward.utils.audit_log import log_event
from best_foot_forward.utils.jd_skills import extract_terms
from best_foot_forward.utils.scan_jds import extract_salary
from best_foot_forward.utils.slugify import slugify

ASSET_BASE = os.path.join(DATA_DIR, "BestFootForward", "assets")


def jd_paths(company: str, role: str) -> tuple[str, str]:
    """(asset_dir, jd_file_path) for a company/role, both absolute.

    The role slug is computed with `slugify()`, never by hand — a one-character
    difference between this path and the one resume-tailor later uses is the same
    silent-duplicate-row failure that recurred three times on relative paths.
    The *filename* carries the role slug too: Logseq indexes every .md in the graph
    by filename alone, so two roles at one company sharing a bare
    `{Company}JobDesc.md` collide as duplicate pages.
    """
    role_slug = slugify(role)
    asset_dir = os.path.join(ASSET_BASE, company, role_slug)
    return asset_dir, os.path.join(asset_dir, f"{company}_{role_slug}JobDesc.md")


def render_jd_file(company: str, role: str, text: str, url: str | None = None) -> str:
    """The JD file body: a Logseq property block, then the posting verbatim."""
    props = [
        "type:: #JobDescription",
        f"company:: [[{company}]]",
        f"role:: {role}",
    ]
    if url:
        props.append(f"url:: {url}")
    return "\n".join(props) + "\n\n" + text.strip() + "\n"


def save_lead_jd(conn, company: str, role: str, text: str, url: str | None = None,
                 overwrite: bool = False, llm_labels: list[str] | None = None) -> dict:
    """Write the JD file, resolve its `jds` row, and index salary + skills.

    Does not write `score`, `summary` or `evaluated_at` — those belong to
    evaluate-job, which owns the scoring pass. Salary is only *filled in*, never
    overwritten: a range read off a posting's sidebar by hand (the Inductive
    Automation case) must survive a later re-parse that finds nothing in the body.

    llm_labels: optional `required_skills` list from evaluate-job's scoring
    subagent (which has already read the full JD for the Gap-risk dimension),
    unioned with the lexicon/profile extraction in jd_skills.extract_terms —
    see that module's docstring for why an open vocabulary needs both tiers.
    """
    asset_dir, file_path = jd_paths(company, role)
    file_path = resolve_jd_path(file_path)

    existed = os.path.exists(file_path)
    if existed and not overwrite:
        # A file already on disk may have been hand-corrected, or written by a
        # tailoring session with more in it than the posting text. Keep it and
        # index what is there rather than clobbering.
        with open(file_path, encoding="utf-8") as f:
            text = f.read()
        wrote = False
    else:
        os.makedirs(asset_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(render_jd_file(company, role, text, url))
        wrote = True

    jd_id, action = resolve_or_create_jd(conn, company, role, file_path)

    if action == "created":
        # Name lead_status explicitly on insert, as scan_jds.py does. The schema
        # DEFAULT is still 'approved' (the flip to 'pending' is parked on an
        # unmerged branch), so a brand-new lead would otherwise land pre-approved
        # and skip the triage inbox entirely. Only on 'created' — a found or
        # adopted row already carries a real decision that must not be reset.
        conn.execute("UPDATE jds SET lead_status = 'pending' WHERE id = ?", (jd_id,))

    salary_min, salary_max = extract_salary(text)
    conn.execute(
        "UPDATE jds SET salary_min = COALESCE(salary_min, ?), "
        "salary_max = COALESCE(salary_max, ?), output_dir = COALESCE(output_dir, ?) "
        "WHERE id = ?",
        (salary_min, salary_max, asset_dir, jd_id),
    )
    if url:
        conn.execute("UPDATE jds SET url = COALESCE(url, ?) WHERE id = ?", (url, jd_id))

    skills = extract_terms(text, conn, llm_labels=llm_labels)
    conn.execute("DELETE FROM jd_required_skills WHERE jd_id = ?", (jd_id,))
    for term in skills:
        conn.execute(
            "INSERT INTO jd_required_skills (jd_id, skill_label, skill_id, canonical_label, source) "
            "VALUES (?,?,?,?,?)",
            (jd_id, term.label, term.skill_id, term.canonical, term.source),
        )
    conn.commit()

    # JD files have never been auto-registered despite the docs saying they are;
    # registering here closes that gap for every evaluated lead.
    register_file(
        file_path, "jd",
        summary=f"JD for {company} — {role}",
        jd_id=jd_id,
        source="evaluate-job",
        source_urls=[url] if url else None,
    )

    return {
        "jd_id": jd_id, "action": action, "file_path": file_path,
        "wrote_file": wrote, "file_existed": existed,
        "salary_min": salary_min, "salary_max": salary_max,
        "skills_found": len(skills),
    }


def main():
    p = argparse.ArgumentParser(
        description="Save a lead's JD text and index its salary + required skills.")
    p.add_argument("--company", required=True)
    p.add_argument("--role", required=True, help="full role title, punctuation intact")
    p.add_argument("--url", help="canonical posting URL, if known")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text-file", help="file holding the raw JD text ('-' for stdin)")
    src.add_argument("--text", help="raw JD text (prefer --text-file for long postings)")
    p.add_argument("--overwrite", action="store_true",
                   help="replace an existing JD file instead of indexing what's there")
    p.add_argument("--skills-json", help="JSON array of required-skill labels from "
                                          "evaluate-job's scoring subagent (its "
                                          "required_skills field), or '-' for stdin. "
                                          "Unioned with lexicon/profile extraction.")
    args = p.parse_args()

    if args.text_file == "-":
        text = sys.stdin.read()
    elif args.text_file:
        with open(args.text_file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.text

    if not text.strip():
        print("[save_lead_jd] refusing to write an empty JD", file=sys.stderr)
        sys.exit(1)

    llm_labels = None
    if args.skills_json:
        raw = sys.stdin.read() if args.skills_json == "-" else args.skills_json
        llm_labels = json.loads(raw)

    conn = get_conn()
    try:
        r = save_lead_jd(conn, args.company, args.role, text, args.url, args.overwrite, llm_labels)
    finally:
        conn.close()

    # Named explicitly rather than splatting `r`: its "action" key (from
    # resolve_or_create_jd) collides with log_event's own `action` parameter.
    log_event("save-lead-jd", "save",
              company=args.company, role=args.role,
              jd_id=r["jd_id"], jd_action=r["action"], file_path=r["file_path"],
              wrote_file=r["wrote_file"], skills_found=r["skills_found"],
              salary_min=r["salary_min"], salary_max=r["salary_max"])

    verb = "wrote" if r["wrote_file"] else "kept existing"
    print(f"[save_lead_jd] {verb} {os.path.relpath(r['file_path'], _root)}")
    print(f"  jd_id: {r['jd_id']} ({r['action']})")
    if r["salary_min"] or r["salary_max"]:
        print(f"  salary parsed: {r['salary_min']}–{r['salary_max']} (only filled if empty)")
    else:
        print("  salary: none found in the body text "
              "(many boards put the range in a sidebar widget — set it by hand if you want it)")
    print(f"  required skills indexed: {r['skills_found']}")


if __name__ == "__main__":
    main()
