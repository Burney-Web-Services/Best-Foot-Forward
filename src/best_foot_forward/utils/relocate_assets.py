"""Phase 2 of the BFF -> Logseq migration: relocate the artifact tree into the
graph's assets/ and repoint the DB paths, so the graph is self-contained and
`file_registry` stays the single catalog.

Moves (into ``data/BestFootForward/assets/``):
  * the whole ``data/applications/`` tree, **canonicalizing the company dir**
    (raw ``brightwheel`` -> canonical ``Brightwheel``) so files land exactly
    where the pages link them, and preserving any deeper sub-dirs;
  * ``data/media/`` files that are catalogued in ``file_registry`` (transcripts/
    recordings), placed under their jd's ``{Company}/{slug(role)}/`` folder;
  * external JD files referenced by ``jds.file_path`` (e.g. old
    ``PERSONAL/JobSearch2026`` paths) are **copied** in (self-contained graph).

Then rewrites three DB columns to the new locations:
  * ``file_registry.file_path`` (project-root-relative),
  * ``jds.file_path`` and ``jds.output_dir`` (absolute).

Target paths come from the shared ``export_graph.asset_target()`` so the physical
move and the page links agree exactly. Idempotent / re-runnable; ``--dry-run``
prints the full plan and asserts there are no target collisions before touching
anything.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from collections import defaultdict

from best_foot_forward.db import _root as PROJECT_ROOT, DB_PATH
from best_foot_forward.utils.company_normalize import canonical_company
from best_foot_forward.utils.export_graph import asset_target, company_title
from best_foot_forward.utils.slugify import slugify

GRAPH_REL = "data/BestFootForward"
GRAPH_ROOT = os.path.normpath(os.path.join(PROJECT_ROOT, GRAPH_REL))
ASSETS_ABS = os.path.join(GRAPH_ROOT, "assets")
APPLICATIONS_ABS = os.path.normpath(os.path.join(PROJECT_ROOT, "data", "applications"))
MEDIA_ABS = os.path.normpath(os.path.join(PROJECT_ROOT, "data", "media"))


def _norm(p):
    return os.path.normpath(os.path.abspath(p))


def _ctitle(company_raw):
    return company_title(canonical_company(company_raw))


def build_plan(conn):
    """Return (moves, copies, collisions).
    moves/copies: list of (old_abs, new_abs). collisions: {new_abs: [olds]}.
    Also stashes jd metadata used for the DB rewrite on the returned dict."""
    conn.row_factory = sqlite3.Row
    # jd_id -> (ctitle, role) for media/external target computation
    jd_meta = {}
    for r in conn.execute("SELECT id, company, role FROM jds"):
        jd_meta[r["id"]] = (_ctitle(r["company"]), r["role"] or "role")

    moves = {}   # old_abs -> new_abs (internal move)
    copies = {}  # old_abs -> new_abs (external copy)

    # 1. whole applications tree, canonicalizing the top-level company dir.
    if os.path.isdir(APPLICATIONS_ABS):
        for root, _dirs, files in os.walk(APPLICATIONS_ABS):
            for fn in files:
                old = _norm(os.path.join(root, fn))
                rel = os.path.relpath(old, APPLICATIONS_ABS)          # C/R/.../file
                parts = rel.split(os.sep)
                company_raw = parts[0]
                rest = parts[1:] if len(parts) > 1 else [parts[0]]
                new = _norm(os.path.join(ASSETS_ABS, _ctitle(company_raw), *rest))
                moves[old] = new

    # 2. media TRANSCRIPTS catalogued in file_registry -> jd's asset folder.
    #    Raw recordings (WAV, ~154 MB) stay in data/media/ and are linked in
    #    place from the Prep pages (too heavy for the graph).
    for r in conn.execute(
        "SELECT file_path, jd_id, application_id FROM file_registry "
        "WHERE file_path LIKE 'data/media/%' AND file_type = 'transcript'"
    ):
        jd_id = r["jd_id"]
        if jd_id is None and r["application_id"] is not None:
            row = conn.execute("SELECT jd_id FROM applications WHERE id=?",
                               (r["application_id"],)).fetchone()
            jd_id = row["jd_id"] if row else None
        meta = jd_meta.get(jd_id)
        if not meta:
            continue  # unresolvable jd -> leave media file in place
        ctitle, role = meta
        old = _norm(os.path.join(PROJECT_ROOT, r["file_path"]))
        if not os.path.exists(old):
            continue
        new = _norm(os.path.join(GRAPH_ROOT, asset_target(ctitle, old, role)))
        moves[old] = new

    # 3. external JD files (jds.file_path outside data/applications) -> copy in.
    for r in conn.execute("SELECT id, file_path FROM jds WHERE file_path IS NOT NULL"):
        fp = r["file_path"]
        old = _norm(fp)
        if old.startswith(APPLICATIONS_ABS + os.sep):
            continue  # covered by the tree walk
        if not os.path.exists(old):
            continue
        ctitle, role = jd_meta[r["id"]]
        new = _norm(os.path.join(GRAPH_ROOT, asset_target(ctitle, old, role)))
        copies[old] = new

    # collision check across everything landing in the graph
    landing = defaultdict(list)
    for old, new in list(moves.items()) + list(copies.items()):
        landing[new].append(old)
    collisions = {new: olds for new, olds in landing.items() if len(olds) > 1}

    # jds.file_path is UNIQUE — two jds rewriting to the same target would abort
    # the DB update mid-flight (leaving files moved but DB stale). Catch it here
    # so --dry-run fails loudly *before* anything is touched.
    jds_targets = defaultdict(list)
    for r in conn.execute("SELECT id, file_path FROM jds WHERE file_path IS NOT NULL"):
        old = _norm(r["file_path"])
        new = moves.get(old) or copies.get(old)
        if new:
            jds_targets[new].append(f"jd{r['id']}:{old}")
    for new, who in jds_targets.items():
        if len(who) > 1:
            collisions.setdefault(new, []).extend(who)
    return moves, copies, collisions, jd_meta


def rewrite_db(conn, path_map, jd_meta):
    """Rewrite file_registry.file_path, jds.file_path, jds.output_dir using the
    old_abs -> new_abs map. Returns a counts dict."""
    counts = defaultdict(int)
    # file_registry (stored project-relative)
    for r in conn.execute("SELECT id, file_path FROM file_registry").fetchall():
        old = _norm(os.path.join(PROJECT_ROOT, r["file_path"]))
        if old in path_map:
            new_rel = os.path.relpath(path_map[old], PROJECT_ROOT)
            conn.execute("UPDATE file_registry SET file_path=? WHERE id=?",
                         (new_rel, r["id"]))
            counts["file_registry"] += 1
    # jds.file_path (absolute)
    for r in conn.execute("SELECT id, file_path, output_dir FROM jds").fetchall():
        if r["file_path"]:
            old = _norm(r["file_path"])
            if old in path_map:
                conn.execute("UPDATE jds SET file_path=? WHERE id=?",
                             (path_map[old], r["id"]))
                counts["jds.file_path"] += 1
        # jds.output_dir (absolute directory under data/applications)
        od = r["output_dir"]
        if od:
            od_abs = _norm(od)
            if od_abs.startswith(APPLICATIONS_ABS + os.sep):
                rel = os.path.relpath(od_abs, APPLICATIONS_ABS)   # C/R[/...]
                parts = rel.split(os.sep)
                new_od = _norm(os.path.join(ASSETS_ABS, _ctitle(parts[0]), *parts[1:]))
                conn.execute("UPDATE jds SET output_dir=? WHERE id=?",
                             (new_od, r["id"]))
                counts["jds.output_dir"] += 1
    return counts


def execute_moves(moves, copies):
    for old, new in moves.items():
        if not os.path.exists(old):
            continue
        os.makedirs(os.path.dirname(new), exist_ok=True)
        shutil.move(old, new)
    for old, new in copies.items():
        if not os.path.exists(old):
            continue
        os.makedirs(os.path.dirname(new), exist_ok=True)
        shutil.copy2(old, new)
    # prune now-empty dirs under applications
    if os.path.isdir(APPLICATIONS_ABS):
        for root, dirs, files in os.walk(APPLICATIONS_ABS, topdown=False):
            if not os.listdir(root):
                os.rmdir(root)


def main():
    ap = argparse.ArgumentParser(description="Relocate BFF artifacts into the graph's assets/.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default=None, help="Write the full move list here.")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys=ON")
    moves, copies, collisions, jd_meta = build_plan(conn)

    print(f"Plan: {len(moves)} moves, {len(copies)} copies (external), "
          f"{len(collisions)} collisions.")
    if args.report:
        with open(args.report, "w") as f:
            for old, new in sorted(moves.items()):
                f.write(f"MOVE  {os.path.relpath(old, PROJECT_ROOT)}  ->  "
                        f"{os.path.relpath(new, PROJECT_ROOT)}\n")
            for old, new in sorted(copies.items()):
                f.write(f"COPY  {old}  ->  {os.path.relpath(new, PROJECT_ROOT)}\n")
            for new, olds in collisions.items():
                f.write(f"COLLISION {os.path.relpath(new, PROJECT_ROOT)} <- {olds}\n")
        print(f"Wrote move report to {args.report}")

    if collisions:
        print("ABORT: target collisions detected (see report):")
        for new, olds in list(collisions.items())[:10]:
            print(f"  {os.path.relpath(new, PROJECT_ROOT)} <- "
                  f"{[os.path.relpath(o, PROJECT_ROOT) for o in olds]}")
        sys.exit(2)

    if args.dry_run:
        print("[dry-run] no files moved, no DB changes.")
        return

    path_map = {**moves, **copies}
    execute_moves(moves, copies)
    try:
        counts = rewrite_db(conn, path_map, jd_meta)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"DB rewrite FAILED ({e}); reversing file moves to restore state...")
        for old, new in moves.items():          # move survivors back
            if os.path.exists(new) and not os.path.exists(old):
                os.makedirs(os.path.dirname(old), exist_ok=True)
                shutil.move(new, old)
        for _old, new in copies.items():         # copies: originals intact, drop the copy
            if os.path.exists(new):
                os.remove(new)
        raise
    conn.close()
    print("DB rewrite:", dict(counts))
    print("Done.")


if __name__ == "__main__":
    main()
