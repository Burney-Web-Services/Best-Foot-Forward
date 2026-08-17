"""Durable, queryable history of UAT harness runs (tests/uat/run_uat.sh and
tests/uat/compare_eval_models.sh), so evaluate-job's behavior can be tracked
across BFF versions and model choices instead of living only in a session
transcript or a hand-updated CHECKLIST.md table.

The DB (tests/uat/uat_history.db, tracked in git) holds one row per live
`/evaluate-job` call a harness script drove — never raw reply text or any
fixture PII, just scoring/quality metrics plus enough provenance (git sha,
models used) to compare runs meaningfully later. Committing updates to this
file after a UAT pass is a normal commit like any other -- nothing here
auto-commits.

Usage:
    # called by the shell harnesses after a live run:
    python3 tests/uat/uat_history.py record --harness run_uat \\
        --fixture "Coruscant Systems Group" --outer-model sonnet \\
        --score 61 --cost-usd 1.62 --duration-ms 143000 --num-turns 9 \\
        --banned-phrase-hits "" --gaps-expected "GCP,ArgoCD,Snowflake" \\
        --gaps-named "GCP,ArgoCD,Snowflake"

    # human/CI-readable history:
    python3 tests/uat/uat_history.py report
    python3 tests/uat/uat_history.py report --fixture "Coruscant Systems Group" --limit 10
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "uat_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at              TEXT NOT NULL,               -- ISO 8601 UTC
    git_sha             TEXT,                        -- short sha of HEAD at run time
    harness             TEXT NOT NULL,                -- 'run_uat' | 'compare_eval_models'
    fixture             TEXT NOT NULL,                -- company name of the posting scored
    outer_model         TEXT,                          -- --model passed to the outer `claude -p` session
    eval_model          TEXT,                          -- BFF_EVAL_MODEL override; NULL = command's own default
    score               INTEGER,
    is_error            INTEGER NOT NULL DEFAULT 0,
    cost_usd            REAL,
    duration_ms         INTEGER,
    num_turns           INTEGER,
    banned_phrase_hits  TEXT NOT NULL DEFAULT '[]',   -- JSON array
    gaps_expected       TEXT NOT NULL DEFAULT '[]',   -- JSON array
    gaps_named          TEXT NOT NULL DEFAULT '[]',   -- JSON array, subset of gaps_expected
    notes               TEXT
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def _csv_to_list(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def record_run(
    db_path: Path,
    harness: str,
    fixture: str,
    outer_model: str | None = None,
    eval_model: str | None = None,
    score: int | None = None,
    is_error: bool = False,
    cost_usd: float | None = None,
    duration_ms: int | None = None,
    num_turns: int | None = None,
    banned_phrase_hits: list[str] | None = None,
    gaps_expected: list[str] | None = None,
    gaps_named: list[str] | None = None,
    notes: str | None = None,
    git_sha: str | None = None,
) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO runs (run_at, git_sha, harness, fixture, outer_model, eval_model, "
            "score, is_error, cost_usd, duration_ms, num_turns, banned_phrase_hits, "
            "gaps_expected, gaps_named, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                git_sha or _git_sha(),
                harness,
                fixture,
                outer_model,
                eval_model or None,
                score,
                1 if is_error else 0,
                cost_usd,
                duration_ms,
                num_turns,
                json.dumps(banned_phrase_hits or []),
                json.dumps(gaps_expected or []),
                json.dumps(gaps_named or []),
                notes,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def report_rows(db_path: Path, fixture: str | None = None, limit: int | None = None) -> list[sqlite3.Row]:
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        q = "SELECT * FROM runs"
        params: list = []
        if fixture:
            q += " WHERE fixture = ?"
            params.append(fixture)
        q += " ORDER BY run_at DESC"
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        return conn.execute(q, params).fetchall()
    finally:
        conn.close()


def _print_report(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("[uat_history] no runs recorded yet")
        return
    header = f"{'run_at':<20} {'sha':<8} {'harness':<20} {'fixture':<28} {'model':<8} {'score':>5} {'gaps':>7} {'banned':>7} {'cost':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        model = r["eval_model"] or r["outer_model"] or "-"
        gaps_named = json.loads(r["gaps_named"])
        gaps_expected = json.loads(r["gaps_expected"])
        gaps_col = f"{len(gaps_named)}/{len(gaps_expected)}" if gaps_expected else "-"
        banned = json.loads(r["banned_phrase_hits"])
        score_col = "ERROR" if r["is_error"] else (str(r["score"]) if r["score"] is not None else "-")
        cost_col = f"${r['cost_usd']:.2f}" if r["cost_usd"] is not None else "-"
        print(
            f"{r['run_at']:<20} {(r['git_sha'] or '-'):<8} {r['harness']:<20} {r['fixture'][:28]:<28} "
            f"{model:<8} {score_col:>5} {gaps_col:>7} {len(banned):>7} {cost_col:>7}"
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Override for testing; defaults to the tracked tests/uat/uat_history.db")
    sub = p.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Record one harness run")
    rec.add_argument(
        "--harness", required=True,
        # run_uat_custom: run_uat.sh driven by a non-Claude agent harness via
        # BFF_UAT_RUNNER=custom. Kept a distinct value rather than folded into
        # run_uat so a local-model run never silently averages in with the
        # hosted-model baseline it is meant to be compared against.
        choices=["run_uat", "run_uat_custom", "compare_eval_models"],
    )
    rec.add_argument("--fixture", required=True)
    rec.add_argument("--outer-model")
    rec.add_argument("--eval-model")
    rec.add_argument("--score", type=int)
    rec.add_argument("--is-error", action="store_true")
    rec.add_argument("--cost-usd", type=float)
    rec.add_argument("--duration-ms", type=int)
    rec.add_argument("--num-turns", type=int)
    rec.add_argument("--banned-phrase-hits", default="", help="comma-separated")
    rec.add_argument("--gaps-expected", default="", help="comma-separated")
    rec.add_argument("--gaps-named", default="", help="comma-separated")
    rec.add_argument("--notes")

    rep = sub.add_parser("report", help="Print run history")
    rep.add_argument("--fixture")
    rep.add_argument("--limit", type=int)

    args = p.parse_args()
    db_path = Path(args.db_path)

    if args.command == "record":
        row_id = record_run(
            db_path,
            harness=args.harness,
            fixture=args.fixture,
            outer_model=args.outer_model,
            eval_model=args.eval_model,
            score=args.score,
            is_error=args.is_error,
            cost_usd=args.cost_usd,
            duration_ms=args.duration_ms,
            num_turns=args.num_turns,
            banned_phrase_hits=_csv_to_list(args.banned_phrase_hits),
            gaps_expected=_csv_to_list(args.gaps_expected),
            gaps_named=_csv_to_list(args.gaps_named),
            notes=args.notes,
        )
        print(f"[uat_history] recorded run #{row_id} for {args.fixture!r} ({args.harness})")
    elif args.command == "report":
        _print_report(report_rows(db_path, fixture=args.fixture, limit=args.limit))


if __name__ == "__main__":
    main()
