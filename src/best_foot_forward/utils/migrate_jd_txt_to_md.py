"""One-off migration: convert JD .txt files to .md with a Logseq property block,
so they open natively in Logseq (like the existing Research.md pattern) instead
of falling out to an OS text editor, and so markdown-graph-mcp can index them.

Only touches files matching scan_jds.is_jd_file() (e.g. "*JobDesc.txt") — never
the resume/letter .txt siblings, which are an intentional, separate pattern.

Usage:
    python3 src/best_foot_forward/utils/migrate_jd_txt_to_md.py data/BestFootForward/assets            # dry-run
    python3 src/best_foot_forward/utils/migrate_jd_txt_to_md.py data/BestFootForward/assets --apply
"""
import argparse
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_here, "..")))  # src/best_foot_forward/

from db import get_conn, resolve_jd_path
from scan_jds import is_jd_file


def build_page(company, role, url, body_text):
    lines = [
        "type:: #JobDescription",
        f"company:: [[{company}]]",
        f"role:: {role}",
    ]
    if url:
        lines.append(f"url:: {url}")
    return "\n".join(lines) + "\n\n" + body_text.strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root_dir")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root_dir = os.path.abspath(args.root_dir)
    conn = get_conn()

    txt_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith(".txt") and is_jd_file(fname):
                txt_files.append(os.path.join(dirpath, fname))

    print(f"Found {len(txt_files)} JD .txt file(s) under {root_dir}")

    plan = []       # (old_path, new_path, jd_id, company, role, url)
    unresolved = []

    for old_path in sorted(txt_files):
        abs_old = resolve_jd_path(old_path)
        row = conn.execute(
            "SELECT id, company, role, url FROM jds WHERE file_path = ?", (abs_old,)
        ).fetchone()
        if not row:
            unresolved.append((old_path, "no matching jds row"))
            continue
        jd_id, company, role, url = row
        new_path = os.path.splitext(old_path)[0] + ".md"
        if os.path.exists(new_path):
            unresolved.append((old_path, f"target already exists: {new_path}"))
            continue
        plan.append((old_path, new_path, jd_id, company, role, url))

    print(f"\n=== {len(plan)} files to convert ===")
    for old_path, new_path, jd_id, company, role, url in plan:
        print(f"  jd #{jd_id} [{company} / {role}]: {os.path.relpath(old_path, root_dir)} -> {os.path.basename(new_path)}"
              + (f"  (url: {url})" if url else "  (no url)"))

    if unresolved:
        print(f"\n=== {len(unresolved)} UNRESOLVED (skipped) ===")
        for path, reason in unresolved:
            print(f"  {os.path.relpath(path, root_dir)}: {reason}")

    if not args.apply:
        print("\n[dry-run] pass --apply to write .md files, remove .txt originals, and update the DB")
        return

    updated_registry = 0
    for old_path, new_path, jd_id, company, role, url in plan:
        with open(old_path, encoding="utf-8") as f:
            body = f.read()
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(build_page(company, role, url, body))
        os.remove(old_path)

        new_abs = resolve_jd_path(new_path)
        conn.execute("UPDATE jds SET file_path = ? WHERE id = ?", (new_abs, jd_id))

        old_rel = os.path.relpath(old_path, os.path.join(_here, "..", "..", ".."))
        new_rel = os.path.relpath(new_path, os.path.join(_here, "..", "..", ".."))
        cur = conn.execute(
            "UPDATE file_registry SET file_path = ? WHERE file_path = ?", (new_rel, old_rel)
        )
        updated_registry += cur.rowcount

    conn.commit()
    conn.close()
    print(f"\nApplied: {len(plan)} files converted, {updated_registry} file_registry row(s) updated")


if __name__ == "__main__":
    main()
