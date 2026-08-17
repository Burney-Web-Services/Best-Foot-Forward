"""Export BFF's company/application/prep/notes layer from SQLite to a Logseq
graph (Markdown-as-master), per the BFF -> Sevo-format migration.

Layout (namespaces stored on disk with ``___``):
  * ``{Company}``                     -> #Company entity page (org: reference)
  * ``{Company}/{Role}/Application``  -> pipeline master (one per jds row)
  * ``{Company}/{Role}/Prep``         -> interview prep (only when content exists)
  * ``{Company}/{Role}/Notes``        -> role-specific research (only when content)
  * ``{Company}/Notes``               -> company-wide research

Markdown is master for the pipeline fields; the DB library (bullets/skills/
stories) stays DB-master and is only *displayed* here as a regenerated block.
Company grouping / dedup / quarantine is delegated to ``company_normalize``.

Artifact links point at the post-relocation asset path
``../assets/{Company}/{Role_dir}/{file}`` (see relocate_assets.py). During the
Phase 1 dry-run the files are not there yet; the links go live after Phase 2.

Usage:
  python -m best_foot_forward.utils.export_graph --out DIR [--only COMPANY] [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import markdown_graph_kit as mgk

# Re-export for backward compatibility with existing code/tests
title_to_filename = mgk.title_to_filename

from best_foot_forward.utils.company_normalize import (
    canonical_company, classify_row, company_slug,
)
from best_foot_forward.utils.slugify import slugify

# --- helpers ---------------------------------------------------------------

def _role_title(role: str) -> str:
    """Namespace-safe role segment for a page title (only '/' is illegal)."""
    return re.sub(r"\s+", " ", (role or "Role").replace("/", "-")).strip()


def company_title(name: str) -> str:
    """Title-safe company name: '/' is the namespace separator, so a company
    like 'Mandiant / Google Cloud' must not create a bogus namespace."""
    return re.sub(r"\s*/\s*", " - ", (name or "").strip())


def asset_target(company: str, path: str, role: str) -> str:
    """A file's post-relocation home *relative to the graph root*:
    ``assets/{Company}/{role_dir}/{basename}``. Shared by export_graph (to build
    page links) and relocate_assets (to physically place files) so the two agree
    exactly. ``company`` = canonical title; ``role_dir`` = the file's current role
    segment under ``applications/``, else ``slugify(role)``."""
    p = (path or "").replace("\\", "/")
    base = os.path.basename(p)
    parts = p.split("/")
    role_dir = None
    if "applications" in parts:
        i = parts.index("applications")
        if i + 2 < len(parts):
            role_dir = parts[i + 2]
    if not role_dir:
        role_dir = slugify(role or "role")
    return f"assets/{company}/{role_dir}/{base}"


def _md_url(url: str) -> str:
    """Encode the chars that break a Markdown ``](url)`` — parentheses in a
    filename close the link early. Spaces are left literal (Logseq handles them)."""
    return url.replace("(", "%28").replace(")", "%29")


def _asset_link(path: str, company: str, role: str) -> str:
    """Relative link from pages/ to a file's home in assets/.

    If the DB path is already relocated into the graph
    (``data/BestFootForward/assets/…``), link it *directly* at its real
    location. Only when a path is still pre-move (under ``applications/``) do we
    predict its target via ``asset_target`` — which is what relocate_assets uses
    to place it. This keeps page links correct both before and after Phase 2."""
    p = (path or "").replace("\\", "/")
    if "BestFootForward/assets/" in p:
        return _md_url("../" + p[p.index("assets/"):])
    return _md_url("../" + asset_target(company, path, role))


_APP_SUFFIX = "___Application"


def _add_related_links(pages_dir, companies):
    """Add a '## Related' section to each Application page linking its namespace
    siblings (Prep, Notes, Application Questions, converted doc pages) so they're
    discoverable from the Application page — not only via Logseq's namespace tree.
    Inserted right after the property block. Idempotent: the Application page is
    regenerated fresh each run, so this appends exactly once per run."""
    for app_path in glob.glob(os.path.join(pages_dir, "*" + _APP_SUFFIX + ".md")):
        stem = os.path.basename(app_path)[:-3]
        if not stem.endswith(_APP_SUFFIX):
            continue
        if stem.split("___", 1)[0] not in companies:
            continue
        prefix = stem[:-len(_APP_SUFFIX)]          # Company___Role
        sibs = []
        for sib in sorted(glob.glob(os.path.join(pages_dir, glob.escape(prefix) + "___*.md"))):
            ss = os.path.basename(sib)[:-3]
            if ss == stem:                          # skip the Application page itself
                continue
            sibs.append(ss.replace("___", "/"))     # namespaced title
        if not sibs:
            continue
        lines = open(app_path).read().splitlines()
        i = 0                                        # find first body bullet (end of props)
        while i < len(lines) and not lines[i].lstrip().startswith(("- ", "* ")):
            i += 1
        block = ["- ## Related"] + [f"\t- [[{t}]]" for t in sibs]
        lines[i:i] = block
        with open(app_path, "w") as f:
            f.write("\n".join(lines) + "\n")


def _project_link(rel_path: str) -> str:
    """Link from pages/ to a file kept at its project-root-relative location
    (e.g. a recording left in data/media/). pages/ is <root>/data/BestFootForward/
    pages, so the project root is three levels up."""
    return _md_url("../../../" + (rel_path or "").replace("\\", "/").lstrip("/"))


def _rel_project(path: str) -> str:
    """Absolute BFF path -> project-root-relative (data/...)."""
    p = (path or "").replace("\\", "/")
    marker = "/BestFootForward/"
    if marker in p:
        return p.split(marker, 1)[1]
    return p


def _one_line(text: str) -> str:
    return re.sub(r"\s*\n\s*", " ", (text or "").strip())


def _prop(key, value):
    return f"{key}:: {value}" if value not in (None, "") else None


def _date_ref(value):
    """ISO date/datetime -> [[YYYY/MM/DD]] Logseq link (matches the graph's
    `yyyy/MM/dd` journal format so dates plug into the Year/Month/Day namespace
    index), else raw."""
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    return f"[[{m.group(1)}/{m.group(2)}/{m.group(3)}]]" if m else str(value)


# --- data access -----------------------------------------------------------

class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row

    def q(self, sql, args=()):
        return self.c.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        r = self.c.execute(sql, args).fetchone()
        return r


def _is_old_knowledge(path: str) -> bool:
    return "data/knowledge/" in (path or "").replace("\\", "/")


# file types the Prep page owns (kept off the Application ## Artifacts list).
PREP_FILE_TYPES = {"screen_prep", "interview_prep", "star_prep", "questions", "transcript", "recording"}


# --- page builders ---------------------------------------------------------

def build_company_page(company, jds_rows, role_of, page_kind):
    variants = sorted({r["company"] for r in jds_rows if r["company"] != company})
    props = [
        "type:: #Company",
        f"mistoria-reference:: org:{company_slug(company)}",
        "visibility:: private",
    ]
    if variants:
        props.append("aliases:: " + ", ".join(variants))
    body = ["", "- ## Roles"]
    for r in jds_rows:
        role = role_of[r["id"]]
        kind = page_kind[r["id"]]  # "Lead" or "Application"
        body.append(f"\t- [[{company}/{role}/{kind}]] — {r['_status']}")
    return "\n".join(props) + "\n" + "\n".join(body) + "\n"


def build_application_page(db, company, jd, app, apps_count):
    role = _role_title(jd["role"])
    props = [
        "type:: #Application",
        f"company:: [[{company}]]",
        _prop("role", jd["role"]),
        _prop("bff-jd-id", jd["id"]),
    ]
    if app:
        props.append(_prop("bff-application-id", app["id"]))
    props += [
        _prop("status", jd["_status"]),
        _prop("stage", app["stage"] if app else None),
        _prop("lead-status", jd["lead_status"]),
        _prop("lead-decided", _date_ref(jd["lead_decided_at"])),
        _prop("score", jd["score"]),
        _prop("source", jd["source"]),
        _prop("salary-min", jd["salary_min"]),
        _prop("salary-max", jd["salary_max"]),
        _prop("salary-target", jd["salary_target"]),
        _prop("salary-currency", jd["salary_currency"]),
        _prop("url", jd["url"]),
    ]
    if jd["file_path"]:
        props.append(_prop("jd-file", _asset_link(jd["file_path"], company, jd["role"])))
    props.append(_prop("evaluated", _date_ref(jd["evaluated_at"])))
    if app:
        props += [
            _prop("applied", _date_ref(app["applied_at"])),
            _prop("concluded", _date_ref(app["concluded_at"])),
            _prop("follow-up", _date_ref(app["follow_up_date"])),
            _prop("follow-up-count", app["follow_up_count"]),
            _prop("created", app["created_at"]),
        ]
        if app["source_application_id"]:
            src = db.one(
                "SELECT j.company, j.role FROM applications a JOIN jds j ON a.jd_id=j.id "
                "WHERE a.id=?", (app["source_application_id"],))
            if src:
                sc = company_title(canonical_company(src["company"]))
                props.append(f"source-application:: [[{sc}/{_role_title(src['role'])}/Application]]")
    props = [p for p in props if p]

    body = []

    def section(title, lines):
        if lines:
            body.append(f"- ## {title}")
            body.extend(f"\t- {ln}" for ln in lines)

    if app:
        section("Summary", [_one_line(app["resume_summary"])] if app["resume_summary"] else [])
        section("Tailoring notes", [_one_line(app["tailoring_notes"])] if app["tailoring_notes"] else [])
        section("Notes", [_one_line(app["notes"])] if app["notes"] else [])
        paras = db.q("SELECT body FROM application_letter_paragraphs "
                     "WHERE application_id=? ORDER BY position", (app["id"],))
        if paras or app["letter_salutation"] or app["letter_closing"]:
            lines = []
            if app["letter_salutation"]:
                lines.append(f"*{_one_line(app['letter_salutation'])}*")
            lines += [_one_line(p["body"]) for p in paras]
            if app["letter_closing"]:
                lines.append(f"*{_one_line(app['letter_closing'])}*")
            section("Cover letter", lines)

    contacts = db.q("SELECT name,title,role,interview_stage,interview_date,email,notes "
                    "FROM contacts WHERE jd_id=? ORDER BY id", (jd["id"],))
    if contacts:
        body.append("- ## Contacts")
        body.append("\t- | Name | Title | Role | Stage | Date | Email | Notes |")
        body.append("\t  | --- | --- | --- | --- | --- | --- | --- |")
        for c in contacts:
            row = " | ".join(_one_line(str(c[k] or "")) for k in
                             ("name", "title", "role", "interview_stage",
                              "interview_date", "email", "notes"))
            body.append(f"\t  | {row} |")

    if app:
        assess = db.q("SELECT type,description,url,deadline,submitted_at,notes "
                      "FROM assessments WHERE application_id=? ORDER BY id", (app["id"],))
        if assess:
            body.append("- ## Assessments")
            for a in assess:
                body.append(f"\t- **{a['type']}** — {_one_line(a['description'])}")
                meta = [f"url: {a['url']}" if a["url"] else "",
                        f"deadline: {a['deadline']}" if a["deadline"] else "",
                        f"submitted: {a['submitted_at']}" if a["submitted_at"] else ""]
                meta = [m for m in meta if m]
                if meta:
                    body.append("\t\t- " + " · ".join(meta))

    # Artifacts from file_registry (exclude old knowledge-page 'notes' and the
    # prep/interview/media types, which the Prep page owns).
    files = db.q(
        "SELECT file_path,file_type,summary FROM file_registry "
        "WHERE (jd_id=? OR application_id=?) ORDER BY file_type,file_path",
        (jd["id"], app["id"] if app else -1))
    files = [f for f in files if not _is_old_knowledge(f["file_path"])
             and f["file_type"] not in PREP_FILE_TYPES]
    if files:
        body.append("- ## Artifacts")
        for f in files:
            link = _asset_link(f["file_path"], company, jd["role"])
            label = f["summary"] or os.path.basename(f["file_path"])
            body.append(f"\t- [{_one_line(label)}]({link}) `{f['file_type']}`")

    # Selected bullets/skills — DB-master, shown as a regenerated block.
    if app:
        abul = db.q("SELECT ab.position, coalesce(ab.text_override,b.text) t "
                    "FROM application_bullets ab JOIN bullets b ON ab.bullet_id=b.id "
                    "WHERE ab.application_id=? ORDER BY ab.position", (app["id"],))
        askl = db.q("SELECT ask.position, s.label, coalesce(ask.content_override,s.content) c "
                    "FROM application_skills ask JOIN skills s ON ask.skill_id=s.id "
                    "WHERE ask.application_id=? ORDER BY ask.position", (app["id"],))
        if abul or askl:
            body.append("- ## Selected bullets / skills")
            body.append("\t- > generated from best_foot_forward.db (DB-master) — do not hand-edit")
            for b in abul:
                body.append(f"\t- {_one_line(b['t'])}")
            for s in askl:
                body.append(f"\t- **{s['label']}:** {_one_line(s['c'])}")

    if apps_count > 1:
        body.append("- ## Prior applications")
        body.append(f"\t- This role has {apps_count} application records in the DB; "
                    f"the most recent is shown above (bff-application-id "
                    f"{app['id'] if app else 'n/a'}).")

    return "\n".join(props) + "\n\n" + "\n".join(body) + "\n"


def build_lead_page(db, company, jd):
    """A #Lead page: a scored JD not turned into an application — pending, approved,
    or declined. Simpler sibling of the #Application page; promoted to one on tailoring."""
    props = [
        "type:: #Lead",
        f"company:: [[{company}]]",
        _prop("role", jd["role"]),
        _prop("bff-jd-id", jd["id"]),
        _prop("lead-status", jd["lead_status"]),
        _prop("lead-decided", _date_ref(jd["lead_decided_at"])),
        _prop("decline-category", jd["decline_category"]),
        _prop("decline-reason", jd["decline_reason"]),
        _prop("score", jd["score"]),
        _prop("source", jd["source"]),
        _prop("salary-min", jd["salary_min"]),
        _prop("salary-max", jd["salary_max"]),
        _prop("salary-target", jd["salary_target"]),
        _prop("salary-currency", jd["salary_currency"]),
        _prop("url", jd["url"]),
    ]
    if jd["file_path"]:
        props.append(_prop("jd-file", _asset_link(jd["file_path"], company, jd["role"])))
    props.append(_prop("evaluated", _date_ref(jd["evaluated_at"])))
    props = [p for p in props if p]

    body = []
    if jd["summary"]:
        body.append("- ## Summary")
        body.append(f"\t- {_one_line(jd['summary'])}")

    skills = db.q("SELECT skill_label FROM jd_required_skills WHERE jd_id=? ORDER BY id",
                  (jd["id"],))
    if skills:
        body.append("- ## Required skills")
        body.append("\t- " + ", ".join(_one_line(s["skill_label"]) for s in skills))

    if jd["url"]:
        body.append("- ## Posting")
        body.append(f"\t- [Open posting]({_md_url(jd['url'])})")

    return "\n".join(props) + ("\n\n" + "\n".join(body) if body else "") + "\n"


def _remove_generated(pages_dir, title, dry_run):
    """Delete one specific generated page by exact title (e.g. a stale
    ``Company/Role/Application`` when that JD is now a #Lead, or a stale
    ``Company/Role/Lead`` after promotion to an application). Targets a single
    known file — never a blanket ``rm pages/*.md``."""
    fn = os.path.join(pages_dir, mgk.title_to_filename(title) + ".md")
    if os.path.exists(fn):
        if not dry_run:
            os.remove(fn)
        return True
    return False


def build_prep_page(db, company, jd, app):
    files = db.q("SELECT file_path,file_type,summary FROM file_registry "
                 "WHERE (jd_id=? OR application_id=?)", (jd["id"], app["id"] if app else -1))
    files = [f for f in files if not _is_old_knowledge(f["file_path"])]
    prep = [f for f in files if f["file_type"] in ("screen_prep", "interview_prep", "star_prep")]
    ques = [f for f in files if f["file_type"] == "questions"]
    media = [f for f in files if f["file_type"] in ("transcript", "recording")]
    contacts = db.q("SELECT name,title,interview_stage,interview_date FROM contacts "
                    "WHERE jd_id=? AND (interview_stage IS NOT NULL OR interview_date IS NOT NULL) "
                    "ORDER BY id", (jd["id"],))
    stories = db.q("SELECT s.title, siu.question_prompt FROM story_interview_use siu "
                   "JOIN stories s ON siu.story_id=s.id WHERE siu.application_id=?",
                   (app["id"] if app else -1,))
    if not (prep or ques or media or contacts or stories):
        return None

    props = ["type:: #Prep", f"company:: [[{company}]]", _prop("role", jd["role"]),
             _prop("bff-jd-id", jd["id"])]
    if app:
        props.append(_prop("bff-application-id", app["id"]))
    props = [p for p in props if p]
    body = []

    def link(f):
        label = _one_line(f["summary"] or os.path.basename(f["file_path"]))
        # Raw recordings stay in data/media/ (too heavy for the graph); link them
        # at their real project-relative location. Everything else moves to assets/.
        url = (_project_link(f["file_path"]) if f["file_type"] == "recording"
               else _asset_link(f["file_path"], company, jd["role"]))
        return f"[{label}]({url})"

    if contacts:
        body.append("- ## Interview process")
        for c in contacts:
            who = " — ".join(x for x in (c["name"], c["title"]) if x)
            when = c["interview_date"] or ""
            body.append(f"\t- {c['interview_stage'] or 'stage'}: {who} {when}".rstrip())
    if prep:
        body.append("- ## Prep notes")
        body.extend(f"\t- {link(f)}" for f in prep)
    if ques:
        body.append("- ## Questions")
        body.extend(f"\t- {link(f)}" for f in ques)
    if stories:
        body.append("- ## Stories to use")
        for s in stories:
            body.append(f"\t- {s['title']}" + (f" — {_one_line(s['question_prompt'])}"
                                               if s["question_prompt"] else ""))
    if media:
        body.append("- ## Transcripts & recordings")
        body.extend(f"\t- {link(f)}" for f in media)
    return "\n".join(props) + "\n\n" + "\n".join(body) + "\n"


def build_thankyou_page(db, company, jd, app):
    """A #ThankYouNote page: thank you email sent after an interview.
    Only emitted if a 'thankyou' file exists in file_registry."""
    if not app:
        return None
    files = db.q("SELECT file_path, summary FROM file_registry "
                 "WHERE (application_id=?) AND file_type='thankyou'",
                 (app["id"],))
    if not files:
        return None
    f = files[0]  # Should only be one; take the first if multiple exist

    # Read email content from file
    try:
        with open(f["file_path"], "r", encoding="utf-8") as fh:
            email_body = fh.read()
    except FileNotFoundError:
        return None

    # Get recipient info from contacts
    contact = db.one("SELECT name, title, interview_date FROM contacts "
                     "WHERE jd_id=? ORDER BY id LIMIT 1", (jd["id"],))

    props = ["type:: #ThankYouNote", f"company:: [[{company}]]",
             _prop("role", jd["role"]), _prop("bff-jd-id", jd["id"]),
             _prop("bff-application-id", app["id"])]
    if contact:
        props.append(_prop("recipient", contact["name"]))
        props.append(_prop("recipient-title", contact["title"]))
        props.append(_prop("interview-date", _date_ref(contact["interview_date"])))
    props.append(_prop("thank-you-sent", _date_ref(app["concluded_at"])))
    props = [p for p in props if p]

    body = []
    body.append("- ## Thank You Email")
    body.append(f"\t- {_one_line(email_body)}")

    return "\n".join(props) + "\n\n" + "\n".join(body) + "\n"


def build_company_notes_page(db, company, jds_rows):
    # Seed from employers.notes when this company is also a past employer.
    emp = db.one("SELECT notes FROM employers WHERE lower(name)=lower(?)", (company,))
    research = db.q(
        "SELECT DISTINCT fr.file_path, fr.file_type, fr.summary FROM file_registry fr "
        "JOIN jds j ON fr.jd_id=j.id WHERE j.company IN "
        "(SELECT company FROM jds WHERE id IN (%s)) AND fr.file_type IN ('research','notes')"
        % ",".join(str(r["id"]) for r in jds_rows))
    research = [r for r in research if not _is_old_knowledge(r["file_path"])]
    if not (emp and emp["notes"]) and not research:
        return None
    props = ["type:: #CompanyNotes", f"company:: [[{company}]]"]
    body = []
    if emp and emp["notes"]:
        body.append("- ## Background")
        body.append(f"\t- {_one_line(emp['notes'])}")
    if research:
        body.append("- ## Research")
        for r in research:
            body.append(f"\t- [{_one_line(r['summary'] or os.path.basename(r['file_path']))}]"
                        f"({_asset_link(r['file_path'], company, 'research')}) `{r['file_type']}`")
    return "\n".join(props) + "\n\n" + "\n".join(body) + "\n"


# --- orchestration ---------------------------------------------------------

def export(db_path, out_dir, only=None, dry_run=False):
    db = DB(db_path)
    rows = db.q("SELECT * FROM jds ORDER BY id")

    # Group kept rows by canonical company; attach a resolved _status.
    by_company = defaultdict(list)
    for r in rows:
        cls = classify_row(r)
        if cls.kind == "quarantine":
            continue
        company = cls.canonical_company
        d = dict(r)
        d["_status"] = _resolve_status(db, r)
        by_company[company].append(_Row(d))

    if only:
        by_company = {k: v for k, v in by_company.items()
                      if k.lower() == only.lower()}

    pages_dir = os.path.join(out_dir, "pages")
    if not dry_run:
        os.makedirs(pages_dir, exist_ok=True)

    written = defaultdict(int)
    dup_report = []
    generated_titles = set()
    for company in sorted(by_company, key=str.lower):
        jds_rows = sorted(by_company[company], key=lambda r: r["id"])
        ctitle = company_title(company)
        generated_titles.add(ctitle)

        # Disambiguate the role segment only when two jds rows collide on it,
        # so no Application page overwrites another (lossless).
        base_counts = defaultdict(list)
        for jd in jds_rows:
            base_counts[_role_title(jd["role"])].append(jd["id"])
        role_of = {}
        for jd in jds_rows:
            base = _role_title(jd["role"])
            if len(base_counts[base]) > 1:
                role_of[jd["id"]] = f"{base} [jd{jd['id']}]"
                dup_report.append((company, base, base_counts[base]))
            else:
                role_of[jd["id"]] = base

        def emit(title, content):
            if content is None:
                return
            written[title.split("/")[-1] if "/" in title else "Company"] += 1
            if dry_run:
                return
            fn = os.path.join(pages_dir, mgk.title_to_filename(title) + ".md")
            with open(fn, "w") as f:
                f.write(content)

        # First pass: fetch applications + decide page type (Lead vs Application)
        # per JD, so the company page can link to the right page.
        apps_of = {}
        page_kind = {}
        for jd in jds_rows:
            apps = db.q("SELECT * FROM applications WHERE jd_id=? "
                        "ORDER BY datetime(created_at) DESC", (jd["id"],))
            apps_of[jd["id"]] = apps
            # 'declined' stays a Lead: the seeker passed on it, so there is no
            # application to render, and the page has to keep being regenerated or
            # its lead-status/decline-reason props freeze at their pre-decline
            # values and reconcile_graph reverts the decline from the stale page.
            is_lead = (not apps) and (jd["lead_status"] in ("pending", "approved", "declined"))
            page_kind[jd["id"]] = "Lead" if is_lead else "Application"

        emit(ctitle, build_company_page(ctitle, jds_rows, role_of, page_kind))
        emit(f"{ctitle}/Notes", build_company_notes_page(db, ctitle, jds_rows))
        for jd in jds_rows:
            apps = apps_of[jd["id"]]
            app = apps[0] if apps else None
            role = role_of[jd["id"]]
            if page_kind[jd["id"]] == "Lead":
                emit(f"{ctitle}/{role}/Lead", build_lead_page(db, ctitle, jd))
                # Drop any stale generated Application/Prep pages for this JD
                # (e.g. from before #Lead pages existed).
                if _remove_generated(pages_dir, f"{ctitle}/{role}/Application", dry_run):
                    written["removed"] += 1
                _remove_generated(pages_dir, f"{ctitle}/{role}/Prep", dry_run)
            else:
                emit(f"{ctitle}/{role}/Application",
                     build_application_page(db, ctitle, jd, app, len(apps)))
                emit(f"{ctitle}/{role}/Prep", build_prep_page(db, ctitle, jd, app))
                emit(f"{ctitle}/{role}/ThankYou", build_thankyou_page(db, ctitle, jd, app))
                # Drop a stale Lead page after promotion to an application.
                if _remove_generated(pages_dir, f"{ctitle}/{role}/Lead", dry_run):
                    written["removed"] += 1

    if not dry_run:
        _add_related_links(pages_dir, generated_titles)

    total = sum(written.values())
    print(f"{'[dry-run] ' if dry_run else ''}companies: {len(by_company)}  "
          f"pages: {total}  " + "  ".join(f"{k}={v}" for k, v in sorted(written.items())))
    if dup_report:
        seen = set()
        print(f"\nDuplicate (company, role) rows disambiguated with [jdN] — "
              f"candidates for DB dedup:")
        for company, role, ids in dup_report:
            key = (company, role)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {company} / {role}: jds {ids}")
    return written


def _resolve_status(db, jd):
    app = db.one("SELECT status FROM applications WHERE jd_id=? "
                 "ORDER BY datetime(created_at) DESC LIMIT 1", (jd["id"],))
    return (app["status"] if app and app["status"] else jd["lead_status"]) or "unknown"


class _Row(dict):
    """dict that also supports r['key'] like sqlite3.Row (already does)."""
    __getitem__ = dict.__getitem__


def main():
    from best_foot_forward.db import DATA_DIR as data_dir
    default_db = os.path.join(data_dir, "best_foot_forward.db")
    default_out = os.path.join(data_dir, "BestFootForward")
    ap = argparse.ArgumentParser(description="Export BFF pipeline data to a Logseq graph.")
    ap.add_argument("--db", default=default_db)
    ap.add_argument("--out", default=default_out,
                    help="Graph root (pages/ written under it). Defaults to the bff graph.")
    ap.add_argument("--only", default=None, help="Limit to one canonical company.")
    ap.add_argument("--dry-run", action="store_true", help="Count only, write nothing.")
    args = ap.parse_args()
    export(args.db, args.out, only=args.only, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
