#!/usr/bin/env python3
"""BFF MCP Server — pure stdlib for stdio; aiohttp for Streamable HTTP.

Phase 1 (stdio): register in ~/.claude.json, zero new deps.
Phase 2 (Streamable HTTP): start with --serve [PORT] for a collaborator's LAN access.
  Single endpoint POST /mcp (bearer-token auth), the current MCP remote
  transport — replaced the deprecated HTTP+SSE two-endpoint transport.

Usage:
  stdio: /path/to/.venv/bin/python mcp_server.py
  HTTP:  /path/to/.venv/bin/python mcp_server.py --serve [PORT]   (default 8765)
"""

import asyncio
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import get_conn, DATA_DIR
from utils.config import BFF_ROLE
from utils.import_secondary import insert_leads

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_career_profile",
        "description": (
            "Get the career profile: contact info, education, and employer history. "
            "Reads from JSON caches — works on both primary and secondary machines."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_bullets",
        "description": (
            "Get achievement bullets from the career library. "
            "Reads from JSON caches — works on both primary and secondary machines. "
            "Optionally filter by track and/or theme keyword."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "track": {
                    "type": "string",
                    "description": "Filter by track — free text, matched against whatever track tags exist in the library (e.g. from job history or past tailoring). Omit for all bullets.",
                },
                "theme": {
                    "type": "string",
                    "description": "Filter by theme (e.g. 'cross-functional', 'scale', 'people-management').",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_skills",
        "description": (
            "Get skill groups from the skills library. "
            "Reads from JSON caches — works on both primary and secondary machines."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "track": {
                    "type": "string",
                    "description": "Filter by track — free text, matched against whatever track tags exist in the library.",
                },
                "theme": {
                    "type": "string",
                    "description": "Filter by theme keyword.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_profile_bundle",
        "description": (
            "Get the full raw grounding bundle (all JSON caches: bullets, conditional bullets, "
            "skills, contact, education, employers, plus user_profile.md) as a JSON "
            "string. Used by /secondary to seed a secondary machine's local caches so "
            "evaluate-job can score offline. Reads JSON caches — works on any machine."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_application_summary",
        "description": (
            "Get a summary of the job application pipeline: counts by status, active "
            "opportunities, and recent activity. Requires DB access (primary machine only)."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_stories",
        "description": (
            "Search STAR stories from the career corpus. Optionally filter by theme. "
            "Requires DB access (primary machine only)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "Filter by theme (e.g. 'people-management', 'scale', 'cross-functional').",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_salary_benchmarks",
        "description": (
            "Get salary range data from evaluated job descriptions. "
            "Requires DB access (primary machine only)."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_active_leads",
        "description": (
            "Get job leads with lead_status=pending or approved, sorted by score. "
            "Requires DB access (primary machine only)."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sync_leads",
        "description": (
            "Import evaluated leads into the primary DB (lead_status='pending'). "
            "Attributed to the authenticated caller's source (e.g. 'alex'). "
            "Deduplicates by (company, role): new leads are inserted, existing "
            "leads are updated (score/url/summary/salary refreshed). "
            "Requires DB access (primary machine only)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "leads": {
                    "type": "array",
                    "description": (
                        "Array of lead objects. Each object: {company, role, score, "
                        "salary_min, salary_max, salary_currency, url, summary, "
                        "file_path, required_skills, evaluated_at, source_urls, notes}. "
                        "`url` (or the first of `source_urls`) is the clickable posting link; "
                        "`summary` is the one-paragraph evaluate-job fit narrative."
                    ),
                    "items": {"type": "object"},
                },
            },
            "required": ["leads"],
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _data_path(filename):
    return Path(DATA_DIR) / filename


def _require_primary(tool_name):
    if BFF_ROLE == "secondary":
        return (
            f"[{tool_name}] Not available on secondary machine (BFF_ROLE=secondary). "
            "This tool requires direct DB access — run it from the primary machine."
        )
    return None


def _load_json(filename):
    p = _data_path(filename)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# --- HTTP/SSE bearer-token auth (Phase 2) ---------------------------------
# Token registry lives at data/mcp_tokens.json (gitignored). Shape:
#   { "tokens": { "<secret>": { "name": "alex", "source": "alex" } } }
# Mint entries with scripts/mint_token.py. Read fresh on each request so a
# newly-minted or revoked token takes effect without restarting the server.

def _load_tokens():
    data = _load_json("mcp_tokens.json")
    if not isinstance(data, dict):
        return {}
    tokens = data.get("tokens")
    return tokens if isinstance(tokens, dict) else {}


def _authenticate(request):
    """Validate the Authorization: Bearer header against the token registry.

    Returns (ok, source). Fails closed: no tokens configured, missing header,
    or an unknown token all return (False, None). Constant-time comparison
    avoids leaking valid-token prefixes via timing.
    """
    tokens = _load_tokens()
    if not tokens:
        return (False, None)
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return (False, None)
    presented = header[len("Bearer "):].strip()
    for token, entry in tokens.items():
        if secrets.compare_digest(presented, token):
            source = (entry or {}).get("source") or "secondary"
            return (True, source)
    return (False, None)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _get_profile_bundle(_args):
    import re as _re
    from datetime import datetime as _dt

    data_dir = Path(DATA_DIR)
    caches = {}
    # Every profile cache the secondary needs to score offline.
    names = sorted(p.name for p in data_dir.glob("_bullets*.json"))
    names += ["_skills.json", "_contact.json", "_education.json", "_employers.json"]
    for name in names:
        p = data_dir / name
        if p.exists():
            caches[name] = json.loads(p.read_text(encoding="utf-8"))

    # user_profile.md lives in the Claude Code memory dir: ~/.claude/projects/{sanitized-project-path}/memory/
    project_root = data_dir.parent
    sanitized = _re.sub(r"/", "-", str(project_root))
    memory_dir = Path.home() / ".claude" / "projects" / sanitized / "memory"
    profile_md = memory_dir / "user_profile.md"
    memory = {}
    if profile_md.exists():
        memory["user_profile.md"] = profile_md.read_text(encoding="utf-8")

    bundle = {
        "version": 1,
        "exported_at": _dt.now().isoformat(),
        "caches": caches,
        "memory": memory,
    }
    return json.dumps(bundle, indent=2)


def _get_career_profile(_args):
    contact_data = _load_json("_contact.json")
    edu_data     = _load_json("_education.json")
    emp_data     = _load_json("_employers.json")

    lines = ["# Career Profile\n"]

    if contact_data:
        c = contact_data.get("contact", {})
        lines.append("## Contact")
        lines.append(f"Name:     {c.get('name', 'N/A')}")
        lines.append(f"Email:    {c.get('email', 'N/A')}")
        lines.append(f"Location: {c.get('location', 'N/A')}")
        if c.get("phone"):
            lines.append(f"Phone:    {c['phone']}")
        if c.get("linkedin"):
            lines.append(f"LinkedIn: {c['linkedin']}")
        lines.append("")

    if edu_data:
        lines.append("## Education")
        for e in edu_data.get("education", []):
            lines.append(f"  {e.get('degree', '')} — {e.get('institution', '')} ({e.get('location', '')})")
        lines.append("")

    if emp_data:
        lines.append("## Employer History")
        for e in emp_data.get("employers", []):
            start = e.get("start_date", "")
            end   = e.get("end_date", "present") or "present"
            dates = f"{start}–{end}" if start else end
            lines.append(f"  {e.get('name', '')} ({dates})  {e.get('location', '')}")
    else:
        lines.append("(employer data unavailable)")

    return "\n".join(lines)


def _get_bullets(args):
    track = (args.get("track") or "").strip().lower()
    theme = (args.get("theme") or "").strip().lower()

    data = _load_json("_bullets.json")
    if data is None:
        return "Bullet library not found."

    bullets = data.get("bullets", [])

    if track:
        bullets = [
            b for b in bullets
            if track in [t.lower() for t in (b.get("tracks") or [])]
        ]
    if theme:
        bullets = [
            b for b in bullets
            if theme in [t.lower() for t in (b.get("themes") or [])]
        ]

    if not bullets:
        return f"No bullets found (track={track or 'all'}, theme={theme or 'all'})."

    label = f"track={track or 'all'}, theme={theme or 'all'}"
    lines = [f"# Bullets — {len(bullets)} results ({label})\n"]
    for b in bullets:
        lines.append(f"[{b['id']}] {b['text']}")
        themes_str = ", ".join(b.get("themes") or [])
        lines.append(f"  employer={b.get('employer','')!r}  tracks={b.get('tracks','')}  themes={themes_str}")
        lines.append("")

    return "\n".join(lines)


def _get_skills(args):
    track = (args.get("track") or "").strip().lower()
    theme = (args.get("theme") or "").strip().lower()

    data = _load_json("_skills.json")
    if data is None:
        return "Skills library not found."

    groups = data.get("skills", [])

    if track:
        groups = [g for g in groups if track in [t.lower() for t in (g.get("tracks") or [])]]
    if theme:
        groups = [g for g in groups if theme in [t.lower() for t in (g.get("themes") or [])]]

    if not groups:
        return f"No skill groups found (track={track or 'all'}, theme={theme or 'all'})."

    label = f"track={track or 'all'}, theme={theme or 'all'}"
    lines = [f"# Skills — {len(groups)} groups ({label})\n"]
    for g in groups:
        lines.append(f"## {g['label']}")
        lines.append(g.get("content", ""))
        tracks_str = ", ".join(g.get("tracks") or [])
        themes_str = ", ".join(g.get("themes") or [])
        lines.append(f"  tracks={tracks_str}  themes={themes_str}")
        lines.append("")

    return "\n".join(lines)


def _get_application_summary(_args):
    err = _require_primary("get_application_summary")
    if err:
        return err

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

        by_status = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM applications GROUP BY status ORDER BY cnt DESC"
        ).fetchall()

        active = conn.execute("""
            SELECT j.company, j.role, a.status, a.stage, date(a.applied_at) AS applied_at
            FROM applications a
            JOIN jds j ON a.jd_id = j.id
            WHERE a.status NOT IN ('rejected', 'declined', 'withdrawn', 'offer_declined')
            ORDER BY a.applied_at DESC
            LIMIT 20
        """).fetchall()

        recent = conn.execute("""
            SELECT j.company, j.role, a.status, a.stage, date(a.applied_at) AS applied_at
            FROM applications a
            JOIN jds j ON a.jd_id = j.id
            ORDER BY a.applied_at DESC
            LIMIT 5
        """).fetchall()
    finally:
        conn.close()

    lines = ["# Application Summary\n", f"Total applications: {total}\n"]

    lines.append("## By Status")
    for row in by_status:
        lines.append(f"  {row[0] or 'unknown'}: {row[1]}")
    lines.append("")

    if active:
        lines.append(f"## Active Pipeline ({len(active)})")
        for r in active:
            stage = r["stage"] or "application"
            lines.append(f"  {r['company']} — {r['role']} ({r['status']}, {stage})")
        lines.append("")

    lines.append("## Most Recent 5")
    for r in recent:
        lines.append(f"  {r['applied_at']}  {r['company']} — {r['role']} ({r['status']})")

    return "\n".join(lines)


def _search_stories(args):
    err = _require_primary("search_stories")
    if err:
        return err

    theme = (args.get("theme") or "").strip().lower()

    conn = get_conn()
    try:
        if theme:
            rows = conn.execute("""
                SELECT DISTINCT s.id, s.title, s.situation, s.task, s.action, s.result,
                       s.timeframe, s.readiness, s.lp_tags,
                       e.name AS employer_name
                FROM stories s
                LEFT JOIN employers e ON s.employer_id = e.id
                LEFT JOIN story_themes st ON st.story_id = s.id
                WHERE LOWER(st.theme) = ?
                ORDER BY s.id DESC
            """, (theme,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT s.id, s.title, s.situation, s.task, s.action, s.result,
                       s.timeframe, s.readiness, s.lp_tags,
                       e.name AS employer_name
                FROM stories s
                LEFT JOIN employers e ON s.employer_id = e.id
                ORDER BY s.id DESC
            """).fetchall()
    finally:
        conn.close()

    if not rows:
        label = f" (theme={theme})" if theme else ""
        return f"No stories found{label}."

    label = f"theme={theme or 'all'}"
    lines = [f"# Stories — {len(rows)} results ({label})\n"]
    for r in rows:
        lines.append(f"## [{r['id']}] {r['title']}")
        lines.append(
            f"Employer: {r['employer_name'] or 'N/A'}  |  "
            f"Timeframe: {r['timeframe'] or 'N/A'}  |  "
            f"Readiness: {r['readiness'] or 'draft'}"
        )
        if r["lp_tags"]:
            lines.append(f"LP/Competency: {r['lp_tags']}")
        lines.append(f"\n**Situation:** {r['situation'] or 'N/A'}")
        lines.append(f"**Task:** {r['task'] or 'N/A'}")
        lines.append(f"**Action:** {r['action'] or 'N/A'}")
        lines.append(f"**Result:** {r['result'] or 'N/A'}")
        lines.append("")

    return "\n".join(lines)


def _get_salary_benchmarks(_args):
    err = _require_primary("get_salary_benchmarks")
    if err:
        return err

    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT company, role, salary_min, salary_max, salary_currency, score,
                   date(evaluated_at) AS evaluated_at
            FROM jds
            WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL
            ORDER BY COALESCE(salary_max, salary_min) DESC
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No salary data found in job descriptions."

    lines = [f"# Salary Benchmarks — {len(rows)} JDs with salary data\n"]
    lines.append(f"  {'Company':<22} {'Role':<33} {'Min':>10} {'Max':>10} {'Score':>6}")
    lines.append("  " + "─" * 83)
    for r in rows:
        min_s   = f"${r['salary_min']:,}"  if r["salary_min"]  else "—"
        max_s   = f"${r['salary_max']:,}"  if r["salary_max"]  else "—"
        score_s = str(r["score"]) if r["score"] else "—"
        co  = (r["company"] or "")[:20]
        rol = (r["role"]    or "")[:31]
        lines.append(f"  {co:<22} {rol:<33} {min_s:>10} {max_s:>10} {score_s:>6}")

    return "\n".join(lines)


def _get_active_leads(_args):
    err = _require_primary("get_active_leads")
    if err:
        return err

    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT company, role, lead_status, source, score,
                   salary_min, salary_max, date(evaluated_at) AS evaluated_at
            FROM jds
            WHERE lead_status IN ('pending', 'approved')
            ORDER BY lead_status, score DESC
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No active leads (no JDs with lead_status=pending or approved)."

    lines = [f"# Active Leads — {len(rows)} total\n"]
    current_status = None
    for r in rows:
        if r["lead_status"] != current_status:
            current_status = r["lead_status"]
            lines.append(f"## {current_status.upper()}")
        score_s = str(r["score"]) if r["score"] else "—"
        sal_parts = []
        if r["salary_min"]:
            sal_parts.append(f"${r['salary_min']:,}")
        if r["salary_max"]:
            sal_parts.append(f"${r['salary_max']:,}")
        sal = " – ".join(sal_parts)
        source = r["source"] or "paul"
        co  = r["company"] or "?"
        rol = r["role"]    or "?"
        lines.append(f"  [{score_s:>3}] {co} — {rol}  (source: {source}){('  ' + sal) if sal else ''}")

    return "\n".join(lines)


def _sync_leads(args, source="secondary"):
    err = _require_primary("sync_leads")
    if err:
        return err

    leads = args.get("leads")
    if not isinstance(leads, list):
        return "[sync_leads] 'leads' must be an array of lead objects."

    if not leads:
        return "[sync_leads] Empty leads array — nothing to import."

    imported, updated, skipped = insert_leads(leads, source=source)
    parts = [f"[sync_leads] {imported} imported, {updated} updated, {skipped} skipped."]
    if imported or updated:
        parts.append("Run 'python3 src/best_foot_forward/cli.py leads' to review pending leads.")
    return "\n".join(parts)


HANDLERS = {
    "get_career_profile":      _get_career_profile,
    "get_profile_bundle":      _get_profile_bundle,
    "get_bullets":             _get_bullets,
    "get_skills":              _get_skills,
    "get_application_summary": _get_application_summary,
    "search_stories":          _search_stories,
    "get_salary_benchmarks":   _get_salary_benchmarks,
    "get_active_leads":        _get_active_leads,
    "sync_leads":              _sync_leads,
}

# ---------------------------------------------------------------------------
# JSON-RPC message handler — returns response dict or None (notifications)
# ---------------------------------------------------------------------------

def _handle(msg, source="secondary") -> dict | None:
    # `source` is the authenticated caller identity (from the bearer token) on
    # the HTTP/SSE path; stdio callers use the default. It is threaded into
    # sync_leads so imported leads are attributed to the actual sourcer (e.g. 'alex').
    method = msg.get("method", "")
    msg_id = msg.get("id")

    if msg_id is None:
        return None  # notification — no response

    if method == "initialize":
        # Echo the client's requested protocol version (falling back to the
        # baseline). Our message shapes are stable across these revisions, so
        # matching the client maximizes compatibility across transports.
        client_ver = (msg.get("params") or {}).get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": client_ver or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "best-foot-forward", "version": "1.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params    = msg.get("params", {})
        name      = params.get("name", "")
        arguments = params.get("arguments", {})
        handler   = HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name!r}"},
            }
        try:
            # sync_leads records the authenticated caller as the lead's `source`
            # (e.g. 'alex'); every other tool is read-only and ignores identity.
            if name == "sync_leads":
                text = handler(arguments, source=source)
            else:
                text = handler(arguments)
        except Exception as e:
            text = f"Error in {name!r}: {type(e).__name__}: {e}"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }

    return {
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method!r}"},
    }

# ---------------------------------------------------------------------------
# Transport 1 — stdio (Phase 1)
# ---------------------------------------------------------------------------

def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


async def serve_stdio():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    while True:
        try:
            line = await reader.readline()
        except Exception:
            break
        if not line:
            break
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = _handle(msg)
            if resp:
                _send(resp)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Transport 2 — Streamable HTTP (single endpoint, POST /mcp)
# ---------------------------------------------------------------------------
# The current MCP remote transport (2025-03-26 spec), replacing the deprecated
# HTTP+SSE two-endpoint transport. Our tools are stateless request/response, so
# we run session-less: each JSON-RPC request's response is returned directly as
# application/json on the same POST — no SSE stream, no session ids to track.

async def _mcp_post(request):
    from aiohttp import web

    ok, source = _authenticate(request)
    if not ok:
        return web.Response(status=401, text="Unauthorized")

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32700, "message": "Parse error"}},
            status=400,
        )

    # Body is a single JSON-RPC message (or, from older clients, a batch array).
    batch = isinstance(body, list)
    messages = body if batch else [body]
    responses = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        try:
            resp = _handle(msg, source=source)
        except Exception:
            resp = None
        if resp is not None:
            responses.append(resp)

    # Nothing to return (all notifications) → 202 with no body, per spec.
    if not responses:
        return web.Response(status=202)

    return web.json_response(responses if batch else responses[0])


async def _mcp_get(request):
    # We don't offer a server→client SSE stream on this endpoint. 405 is the
    # spec-sanctioned response when there's no GET stream to open.
    from aiohttp import web
    return web.Response(status=405, text="Method Not Allowed")


async def serve_http(port: int):
    from aiohttp import web

    # Fail closed: never bind an unauthenticated network port. The HTTP
    # transport is only meaningful once at least one bearer token exists.
    if not _load_tokens():
        print(
            "Refusing to start HTTP server: no tokens configured.\n"
            f"  Expected token registry at: {_data_path('mcp_tokens.json')}\n"
            "  Mint one first:  python3 scripts/mint_token.py --name <who>",
            file=sys.stderr, flush=True,
        )
        sys.exit(1)

    app = web.Application()
    app.router.add_post("/mcp", _mcp_post)
    app.router.add_get("/mcp", _mcp_get)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"BFF MCP server (Streamable HTTP) listening on http://0.0.0.0:{port}/mcp", file=sys.stderr, flush=True)
    print(f"  Configure clients with: http://YOUR_LAN_IP:{port}/mcp", file=sys.stderr, flush=True)

    try:
        await asyncio.Event().wait()  # run forever
    finally:
        await runner.cleanup()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    args = sys.argv[1:]
    if "--serve" in args:
        idx = args.index("--serve")
        port = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 8765
        await serve_http(port)
    else:
        await serve_stdio()


if __name__ == "__main__":
    asyncio.run(main())
