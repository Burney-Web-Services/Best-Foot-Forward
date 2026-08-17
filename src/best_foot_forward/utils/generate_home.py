"""Generate the bff graph's Home dashboard (data/BestFootForward/pages/Home.md).

Markdown is master for the pipeline, but a landing page benefits from a current
roll-up. This reads the DB (the index) and writes a linked summary + a couple of
live Logseq queries. Re-run any time (or from a hook) to refresh. Also ensures
Home + both dashboards are favorited in `logseq/config.edn` (see
`ensure_default_favorites()`) — Logseq's default landing page is Journals, and
without this there's no visible path from there to these pages.

    python -m best_foot_forward.utils.generate_home
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import date

from best_foot_forward.db import DATA_DIR
from best_foot_forward.utils.company_normalize import canonical_company
from best_foot_forward.utils.export_graph import company_title, _role_title
from best_foot_forward.utils.triage_lead import DECLINE_CATEGORIES

GRAPH_ROOT = os.path.join(DATA_DIR, "BestFootForward")
HOME = os.path.join(GRAPH_ROOT, "pages", "Home.md")

# Logseq's default landing page is Journals, with no visible path from there
# to Home or either dashboard -- a new user (or a demo) has to already know
# these pages exist to find them. markdown_graph_kit's ensure_graph_config()
# deliberately only writes settings it considers "required for correctness"
# (file/name-format, journal/page-title-format); :favorites is a genuine user
# preference, out of scope for a general-purpose graph-kit library, so BFF
# sets its own defaults here instead.
DEFAULT_FAVORITE_PAGES = ["home", "leads dashboard", "applications dashboard"]
# stages that mean "actively in an interview loop"
# offer_received belongs here: an offer under consideration is very much in
# motion, and its response deadline is the most time-sensitive thing on the board.
ACTIVE_STAGES = ("screen", "phone_screen", "interview_1", "interview_2",
                 "interview_3", "onsite", "final", "assessment_submitted",
                 "offer_received")
# Terminal *failures*. Left exactly as-is so anything reading it for a failure
# count keeps its meaning.
DEAD = ("rejected", "ghosted", "withdrawn", "not_pursued")
# Terminal *success* — the search worked. Deliberately not folded into DEAD:
# "how many searches end in an offer" needs to be countable separately from
# "how many ended in a pass".
WON = ("accepted",)
# Every terminal status, whatever the outcome. This is what "still open"
# filters actually want: turning an offer down is neither a failure nor a
# win, but it's over, same as the rest.
CLOSED = DEAD + WON + ("offer_declined",)


def app_link(company, role):
    return f"[[{company_title(canonical_company(company))}/{_role_title(role)}/Application]]"


def lead_link(company, role):
    return f"[[{company_title(canonical_company(company))}/{_role_title(role)}/Lead]]"


def dref(value):
    """ISO date -> [[YYYY/MM/DD]] link (matches the yyyy/MM/dd journal format)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    return f"[[{m.group(1)}/{m.group(2)}/{m.group(3)}]]" if m else str(value or "")


def ensure_default_favorites(graph_root):
    """Add Home + both dashboards to logseq/config.edn's :favorites, without
    ever removing or reordering anything already there -- whether a user
    favorited something else in the Logseq UI (which appends to the same
    key) or a prior run of this function already added ours. Idempotent;
    no-ops if config.edn doesn't exist yet (bootstrap_graph() hasn't run)."""
    cfg_path = os.path.join(graph_root, "logseq", "config.edn")
    if not os.path.exists(cfg_path):
        return
    with open(cfg_path, encoding="utf-8") as f:
        text = f.read()

    m = re.search(r":favorites\s*\[([^\]]*)\]", text)
    if m:
        existing = re.findall(r'"([^"]*)"', m.group(1))
        existing_lower = {e.lower() for e in existing}
        missing = [p for p in DEFAULT_FAVORITE_PAGES if p not in existing_lower]
        if not missing:
            return
        new_vec = "[" + " ".join(f'"{i}"' for i in existing + missing) + "]"
        text = text[:m.start()] + ":favorites " + new_vec + text[m.end():]
    else:
        brace = text.find("{")
        if brace == -1:
            return  # not a recognizable EDN map; don't touch it
        vec = "[" + " ".join(f'"{p}"' for p in DEFAULT_FAVORITE_PAGES) + "]"
        text = text[:brace + 1] + f"\n :favorites {vec}\n" + text[brace + 1:]

    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    conn = sqlite3.connect(os.path.join(DATA_DIR, "best_foot_forward.db"))
    conn.row_factory = sqlite3.Row
    q = lambda sql, a=(): conn.execute(sql, a).fetchall()
    today = date.today().isoformat()

    total = q("SELECT count(*) c FROM applications")[0]["c"]
    active = q(f"SELECT count(*) c FROM applications WHERE stage IN "
               f"({','.join('?'*len(ACTIVE_STAGES))}) AND status NOT IN {CLOSED} "
               f"AND concluded_at IS NULL", ACTIVE_STAGES)[0]["c"]
    wk_applied = q("SELECT count(*) c FROM applications WHERE applied_at >= date('now','-7 day')")[0]["c"]
    wk_rej = q("SELECT count(*) c FROM applications WHERE status='rejected' "
               "AND concluded_at >= date('now','-7 day')")[0]["c"]

    L = []
    L.append("type:: #Dashboard")
    L.append("visibility:: private")
    L.append("")
    L.append(f"- # Best Foot Forward — Home")
    L.append(f"- **{total}** applications · **{active}** in motion · "
             f"**{wk_applied}** applied this week · **{wk_rej}** passes this week "
             f"· _updated {dref(today)}_")

    # 🔥 In motion
    rows = q(f"SELECT j.company,j.role,a.stage,a.status FROM applications a "
             f"JOIN jds j ON a.jd_id=j.id WHERE a.stage IN "
             f"({','.join('?'*len(ACTIVE_STAGES))}) AND a.status NOT IN {CLOSED} "
             f"AND a.concluded_at IS NULL ORDER BY a.stage DESC", ACTIVE_STAGES)
    L.append("- ## 🔥 In motion")
    L += [f"\t- {app_link(r['company'],r['role'])} — {r['stage']}" for r in rows] or ["\t- _none_"]

    # 🎉 Offers — the one thing the whole board exists to produce. Guarded by
    # `if rows:` so a search with none yet renders nothing rather than an
    # empty "_none_" sitting there as a daily reminder.
    rows = q("SELECT j.company,j.role,a.stage,a.offer_title,a.offer_salary,"
             "a.offer_currency,a.offer_start_date,a.offer_deadline "
             "FROM applications a JOIN jds j ON a.jd_id=j.id "
             "WHERE a.status IN ('accepted') OR a.stage='offer_received' "
             "ORDER BY a.concluded_at DESC, a.offer_received_at DESC")
    if rows:
        L.append("- ## 🎉 Offers")
        for r in rows:
            verb = "accepted" if r["stage"] == "offer_accepted" else "received"
            line = f"\t- {app_link(r['company'],r['role'])} — **{verb}**"
            if r["offer_title"]:
                line += f" · {r['offer_title']}"
            if r["offer_salary"]:
                line += f" · {r['offer_currency'] or 'USD'} {r['offer_salary']:,}"
            if r["offer_start_date"]:
                line += f" · starts {dref(r['offer_start_date'])}"
            if verb == "received" and r["offer_deadline"]:
                line += f" · **respond by {dref(r['offer_deadline'])}**"
            L.append(line)

    # 📅 Upcoming interviews
    rows = q("SELECT j.company,j.role,c.name,c.interview_date,c.interview_stage "
             "FROM contacts c JOIN jds j ON c.jd_id=j.id "
             "WHERE c.interview_date >= date('now') ORDER BY c.interview_date")
    L.append("- ## 📅 Upcoming interviews")
    L += [f"\t- {dref(r['interview_date'])} — {app_link(r['company'],r['role'])} "
          f"({r['interview_stage'] or 'interview'}{', '+r['name'] if r['name'] else ''})"
          for r in rows] or ["\t- _none scheduled_"]

    # 📮 Recently applied (5)
    rows = q("SELECT j.company,j.role,a.applied_at FROM applications a "
             "JOIN jds j ON a.jd_id=j.id WHERE a.applied_at IS NOT NULL "
             "ORDER BY a.applied_at DESC LIMIT 5")
    L.append("- ## 📮 Recently applied")
    L += [f"\t- {dref((r['applied_at'] or '')[:10])} — {app_link(r['company'],r['role'])}" for r in rows]

    # ⏰ Follow-ups due
    rows = q(f"SELECT j.company,j.role,a.follow_up_date FROM applications a "
             f"JOIN jds j ON a.jd_id=j.id WHERE a.follow_up_date IS NOT NULL "
             f"AND a.follow_up_date <= date('now') AND a.status NOT IN {CLOSED} "
             f"ORDER BY a.follow_up_date")
    L.append("- ## ⏰ Follow-ups due")
    L += [f"\t- {dref(r['follow_up_date'])} — {app_link(r['company'],r['role'])}" for r in rows] or ["\t- _none due_"]

    # 🎯 Top open leads (not yet applied)
    rows = q("SELECT company,role,score FROM jds WHERE lead_status IN ('approved','pending') "
             "AND id NOT IN (SELECT jd_id FROM applications WHERE jd_id IS NOT NULL) "
             "AND score IS NOT NULL ORDER BY score DESC LIMIT 8")
    L.append("- ## 🎯 Top open leads to pursue")
    L += [f"\t- **{r['score']}** — {app_link(r['company'],r['role'])}" for r in rows] or ["\t- _none_"]

    # 🚫 Recently declined (5) — timestamped Lead links, mirroring "Recently applied".
    # Date shown and sorted on is when the lead was *declined* (lead_decided_at), falling
    # back to the eval date for leads triaged before that column existed. Links target the
    # .../Lead pages export_graph keeps generating for declined leads.
    rows = q("SELECT j.company,j.role,"
             "date(COALESCE(j.lead_decided_at,j.evaluated_at)) AS decided FROM jds j "
             "LEFT JOIN applications a ON a.jd_id=j.id "
             "WHERE j.lead_status='declined' AND a.id IS NULL "
             "ORDER BY COALESCE(j.lead_decided_at,j.evaluated_at) DESC LIMIT 5")
    L.append("- ## 🚫 Recently declined")
    L += [f"\t- {dref(r['decided'])} — {lead_link(r['company'],r['role'])}" for r in rows] or ["\t- _none_"]

    # small live query (fast) — the big open-leads query lives on Leads Dashboard
    L.append("- ## 🔎 Live views")
    L.append("\t- Currently interviewing")
    L.append("\t\t- {{query (property status \"interviewing\")}}")

    # quick links
    L.append("- ## 🔗 Reference")
    for p in ["Leads Dashboard", "Applications Dashboard", "Declined Leads",
              "Job Board and Leads", "Personal Value Proposition",
              "Interview Questions", "Tailoring Resumes, Letters, and Applications"]:
        L.append(f"\t- [[{p}]]")

    with open(HOME, "w") as f:
        f.write("\n".join(L) + "\n")
    write_leads_dashboard(conn)
    write_declined_dashboard(conn)
    write_applications_dashboard(conn)
    write_sevo_pulse(conn, active)
    ensure_default_favorites(GRAPH_ROOT)
    print(f"wrote {HOME} + Leads Dashboard + Declined Leads + Applications Dashboard + Sèvo pulse")
    print(f"  {total} apps, {active} in motion, {wk_applied} applied this week")


# Optional cross-graph pulse: set BFF_SEVO_GLANCE to a hub page (e.g. a Sèvo
# "at a Glance" page) to stamp a one-line job-search summary into it. Unset →
# skipped. This is a personal-hub integration; most users leave it off.
SEVO_GLANCE = os.environ.get("BFF_SEVO_GLANCE")
PULSE_HEADER = "- ## 🎯 Job Search Pulse"


def write_sevo_pulse(conn, active):
    """Stamp a one-line job-search pulse into the hub page named by
    BFF_SEVO_GLANCE (pointer, not a copy — full board stays in the bff graph).
    Idempotent: replaces its own block. Skips silently if unset/missing.

    Also skips whenever BFF_DATA_DIR is set (an isolated/UAT run, per
    CLAUDE.md's "Execution context awareness"): BFF_SEVO_GLANCE points at a
    real cross-graph hub page that lives outside DATA_DIR entirely, so
    db.py's DATA_DIR override doesn't isolate it the way it isolates
    everything else this module writes. Found via tests/uat/ actually
    running /evaluate-job end to end against a real BFF_SEVO_GLANCE-bearing
    settings.local.json -- a scripted persona's fictional pulse has no
    business landing on a real hub page."""
    if os.environ.get("BFF_DATA_DIR"):
        return
    if not SEVO_GLANCE or not os.path.exists(SEVO_GLANCE):
        return
    nxt = conn.execute(
        "SELECT j.company,c.interview_stage,c.interview_date FROM contacts c "
        "JOIN jds j ON c.jd_id=j.id WHERE c.interview_date >= date('now') "
        "ORDER BY c.interview_date LIMIT 1").fetchone()
    fu = conn.execute("SELECT count(*) c FROM applications WHERE follow_up_date IS NOT NULL "
                      "AND follow_up_date <= date('now') AND status NOT IN "
                      f"{CLOSED}").fetchone()["c"]
    nxt_txt = (f"{nxt['company']} {nxt['interview_stage'] or 'interview'} {dref(nxt['interview_date'])}"
               if nxt else "none scheduled")
    line = (f"\t- **{active}** in motion · next: {nxt_txt} · {fu} follow-ups due · "
            f"full board → bff `Home` _(updated {dref(date.today().isoformat())})_")
    block = [PULSE_HEADER, line]

    lines = open(SEVO_GLANCE, encoding="utf-8").read().splitlines()
    # remove an existing pulse block (header + its indented children)
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip() == PULSE_HEADER.strip():
            i += 1
            while i < len(lines) and not lines[i].startswith("- "):
                i += 1
            continue
        out.append(lines[i]); i += 1
    # insert before the first "- ## " section (top of the dashboard)
    pos = next((k for k, l in enumerate(out) if l.startswith("- ## ")), len(out))
    out[pos:pos] = block
    with open(SEVO_GLANCE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def write_leads_dashboard(conn):
    """Full open-leads board (its own page so the big query doesn't slow Home)."""
    out = os.path.join(os.path.dirname(HOME), "Leads Dashboard.md")
    # active_leads is the shared SQL view (same source as the web Leads report).
    rows = conn.execute("SELECT * FROM active_leads").fetchall()
    L = ["type:: #Dashboard", "visibility:: private", "",
         "- # Leads Dashboard",
         f"- Open leads not yet applied ({len(rows)}), by evaluate-job score. "
         "Generated list (fast); live query below for a Logseq-native view.",
         "- ## 🎯 Open leads by score"]
    for r in rows:
        sc = r["score"] if r["score"] is not None else "—"
        line = (f"\t- **{sc}** {lead_link(r['company'], r['role'])} "
                f"· {r['lead_status']}" + (f" · {r['source']}" if r["source"] else ""))
        if r["url"]:
            line += f" · [posting]({r['url']})"
        L.append(line)
    L += ["- ## 🔎 Live view (Logseq query — slower to load)",
          "\t- {{query (property type \"#Lead\")}}"]
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


def write_declined_dashboard(conn):
    """Full declined-leads board — leads the seeker evaluated and passed on, kept
    with their score and fit summary so the 'why not a fit' reasoning stays visible.
    Each declined lead also keeps its own #Lead page (export_graph); this board is the
    roll-up across them. Mirrors write_leads_dashboard; reads straight from the DB."""
    out = os.path.join(os.path.dirname(HOME), "Declined Leads.md")
    rows = conn.execute(
        "SELECT j.company, j.role, j.score, j.salary_min, j.salary_max, "
        "       j.url, j.summary, j.decline_reason, j.decline_category, "
        "       date(j.evaluated_at) AS evaluated, "
        "       date(COALESCE(j.lead_decided_at,j.evaluated_at)) AS declined "
        "FROM jds j LEFT JOIN applications a ON a.jd_id=j.id "
        "WHERE j.lead_status='declined' AND a.id IS NULL "
        "ORDER BY (j.score IS NULL), j.score DESC, j.company"
    ).fetchall()
    L = ["type:: #Dashboard", "visibility:: private", "",
         "- # Declined Leads",
         f"- Leads evaluated and passed on ({len(rows)}), kept with their fit analysis. "
         "A declined lead is the seeker's own decision — distinct from a company "
         "rejection, which lives on the application (status='rejected')."]

    # Why-tally first: the roll-up is the reason to open this board, and it renders
    # from the same DECLINE_CATEGORIES glosses the CLI report and the triage prompt
    # use, so the vocabulary reads identically wherever it appears.
    tally = {}
    for r in rows:
        tally[r["decline_category"]] = tally.get(r["decline_category"], 0) + 1
    if tally:
        L.append("- ## 🧭 Why they were passed on")
        for slug, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0] or "zz")):
            if slug:
                L.append(f"\t- **{n}** {slug} — {DECLINE_CATEGORIES.get(slug, '')}")
            else:
                L.append(f"\t- **{n}** _uncategorized_")

    L.append("- ## 🚫 Declined by score")
    for r in rows:
        sc = r["score"] if r["score"] is not None else "—"
        line = f"\t- **{sc}** {r['company']} · {r['role']}"
        if r["salary_min"] and r["salary_max"]:
            line += f" · ${r['salary_min']//1000}K–${r['salary_max']//1000}K"
        # Both dates only when they differ — a lead scored weeks before it was
        # declined is exactly the case the decision timestamp exists to show.
        if r["evaluated"] and r["evaluated"] != r["declined"]:
            line += f" · evaluated {dref(r['evaluated'])}"
        if r["declined"]:
            line += f" · declined {dref(r['declined'])}"
        if r["url"]:
            line += f" · [posting]({r['url']})"
        L.append(line)
        if r["decline_category"]:
            L.append(f"\t\t- **Why:** {r['decline_category']} — "
                     f"{DECLINE_CATEGORIES.get(r['decline_category'], '')}")
        if r["decline_reason"]:
            L.append(f"\t\t- **Passed because:** {r['decline_reason']}")
        if r["summary"]:
            L.append(f"\t\t- **Fit analysis:** {r['summary']}")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


def write_applications_dashboard(conn):
    """Full applications board — every application, grouped by status. The Home
    'Recently applied' glance shows only the latest 5; this is the complete roster.
    Applications DO have graph pages (export_graph), so entries link out."""
    out = os.path.join(os.path.dirname(HOME), "Applications Dashboard.md")
    rows = conn.execute(
        "SELECT j.company, j.role, a.status, a.stage, "
        "       date(a.applied_at) AS applied, date(a.concluded_at) AS concluded "
        "FROM applications a JOIN jds j ON a.jd_id=j.id "
        "ORDER BY a.applied_at DESC"
    ).fetchall()
    by_status = {}
    for r in rows:
        by_status.setdefault(r["status"] or "unknown", []).append(r)
    L = ["type:: #Dashboard", "visibility:: private", "",
         "- # Applications Dashboard",
         f"- Every application ({len(rows)}), grouped by status. "
         "The Home dashboard shows only the 5 most recent."]
    for status in sorted(by_status):
        items = by_status[status]
        L.append(f"- ## {status} ({len(items)})")
        for r in items:
            line = f"\t- {app_link(r['company'], r['role'])}"
            if r["stage"]:
                line += f" · {r['stage']}"
            if r["applied"]:
                line += f" · applied {dref(r['applied'])}"
            if r["concluded"]:
                line += f" · concluded {dref(r['concluded'])}"
            L.append(line)
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
