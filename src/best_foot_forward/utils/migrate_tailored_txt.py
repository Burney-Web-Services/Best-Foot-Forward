"""
Migrate tailored .txt files from flat data/resumes/tailored/ and data/letters/tailored/
directories to live beside their .docx outputs in the JD asset directory.

This is a one-time migration for Phase 3 of the flexible-tracks refactor.

Run with: python3 src/best_foot_forward/utils/migrate_tailored_txt.py [--dry-run]

Outputs a match report showing:
- Source .txt file → target asset directory
- Match method (exact JD match, fuzzy domain match, or skipped)
- Confidence level for fuzzy matches

After reviewing the report, run without --dry-run to actually move files.
"""

import os
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Find directories
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.normpath(os.path.join(_here, '../../..'))
DATA_DIR = os.path.join(_project_root, 'data')
TAILORED_RESUME_DIR = os.path.join(DATA_DIR, 'resumes', 'tailored')
TAILORED_LETTER_DIR = os.path.join(DATA_DIR, 'letters', 'tailored')
ASSET_BASE = os.path.join(_project_root, 'data', 'BestFootForward', 'assets')

# Import helpers
sys.path.insert(0, os.path.join(_here, '..'))
from db import get_conn


def _slugify_role(role: str) -> str:
    """Convert role name to slug: spaces/slashes → underscores."""
    return role.replace('/', '_').replace('\\', '_').replace(' ', '_').replace('-', '_')


def _similarity(a: str, b: str) -> float:
    """Simple string similarity 0.0–1.0."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_target_directory(filename: str, file_type: str) -> tuple[str, str, float]:
    """
    Given a tailored filename (e.g. "Google_Senior_Engineer.txt"),
    find the best matching asset directory and return (path, match_method, confidence).

    Returns:
    - (target_dir, "exact_jd", 1.0) — exact JD match found
    - (target_dir, "fuzzy", 0.X) — fuzzy match above threshold
    - (None, "skipped", 0.0) — no suitable match
    """
    # Parse filename: {Company}_{Role}.txt
    stem = filename.replace('.txt', '')
    parts = stem.split('_', 1)
    if len(parts) != 2:
        return None, 'skipped', 0.0

    filename_company, filename_role = parts

    # Try exact match first: query JDs table for company/role pair
    conn = get_conn()
    try:
        jd_rows = conn.execute(
            """
            SELECT id, file_path FROM jds
            WHERE LOWER(company) = LOWER(?) AND LOWER(role) = LOWER(?)
            LIMIT 1
            """,
            (filename_company.replace('_', ' '), filename_role.replace('_', ' '))
        ).fetchall()

        if jd_rows:
            jd_path = jd_rows[0]['file_path']
            if jd_path:
                target_dir = os.path.dirname(jd_path)
                return target_dir, 'exact_jd', 1.0

        # Try fuzzy match: search all JDs for highest-scoring company/role combo
        all_jds = conn.execute("SELECT id, company, role, file_path FROM jds").fetchall()
        best_score = 0.0
        best_dir = None

        target_combined = f"{filename_company} {filename_role}".lower()

        for row in all_jds:
            company = row['company'] or ''
            role = row['role'] or ''
            combined = f"{company} {role}".lower()

            # Score: average similarity of company and role parts
            company_sim = _similarity(filename_company, company)
            role_sim = _similarity(filename_role, role)
            score = (company_sim + role_sim) / 2.0

            if score > best_score and score >= 0.5:  # threshold: 50% similarity
                best_score = score
                best_dir = os.path.dirname(row['file_path']) if row['file_path'] else None

        if best_dir:
            return best_dir, 'fuzzy', best_score

    finally:
        conn.close()

    return None, 'skipped', 0.0


def migrate(dry_run=True):
    """Run the migration. Returns a list of match records."""
    matches = []

    # Process resumes
    if os.path.exists(TAILORED_RESUME_DIR):
        for filename in os.listdir(TAILORED_RESUME_DIR):
            if not filename.endswith('.txt'):
                continue

            source_path = os.path.join(TAILORED_RESUME_DIR, filename)
            target_dir, method, confidence = _find_target_directory(filename, 'resume')

            if target_dir:
                target_path = os.path.join(target_dir, filename)
                matches.append({
                    'file': filename,
                    'type': 'resume',
                    'source': source_path,
                    'target': target_path,
                    'method': method,
                    'confidence': confidence,
                    'status': 'success' if not dry_run else 'dry-run',
                })
                if not dry_run:
                    os.makedirs(target_dir, exist_ok=True)
                    with open(source_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            else:
                matches.append({
                    'file': filename,
                    'type': 'resume',
                    'source': source_path,
                    'target': None,
                    'method': 'skipped',
                    'confidence': 0.0,
                    'status': 'skipped',
                })

    # Process letters
    if os.path.exists(TAILORED_LETTER_DIR):
        for filename in os.listdir(TAILORED_LETTER_DIR):
            if not filename.endswith('.txt'):
                continue

            source_path = os.path.join(TAILORED_LETTER_DIR, filename)
            target_dir, method, confidence = _find_target_directory(filename, 'letter')

            if target_dir:
                target_path = os.path.join(target_dir, filename)
                matches.append({
                    'file': filename,
                    'type': 'letter',
                    'source': source_path,
                    'target': target_path,
                    'method': method,
                    'confidence': confidence,
                    'status': 'success' if not dry_run else 'dry-run',
                })
                if not dry_run:
                    os.makedirs(target_dir, exist_ok=True)
                    with open(source_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            else:
                matches.append({
                    'file': filename,
                    'type': 'letter',
                    'source': source_path,
                    'target': None,
                    'method': 'skipped',
                    'confidence': 0.0,
                    'status': 'skipped',
                })

    return matches


def print_report(matches):
    """Print a human-readable migration report."""
    print("\n" + "=" * 80)
    print("MIGRATION REPORT: Tailored .txt files → Asset directory")
    print("=" * 80 + "\n")

    success_count = sum(1 for m in matches if m['method'] != 'skipped')
    skipped_count = sum(1 for m in matches if m['method'] == 'skipped')

    print(f"Total files processed: {len(matches)}")
    print(f"  Matched (will migrate): {success_count}")
    print(f"  Skipped (no match): {skipped_count}\n")

    # Print by method
    print("EXACT JD MATCHES (confidence 1.0):")
    exact = [m for m in matches if m['method'] == 'exact_jd']
    for m in exact:
        print(f"  ✓ {m['file']} ({m['type']})")
        print(f"    → {m['target']}")
    if not exact:
        print("  (none)\n")
    else:
        print()

    print("FUZZY DOMAIN MATCHES:")
    fuzzy = [m for m in matches if m['method'] == 'fuzzy']
    for m in fuzzy:
        conf = int(m['confidence'] * 100)
        print(f"  ~ {m['file']} ({m['type']}) — {conf}% confidence")
        print(f"    → {m['target']}")
    if not fuzzy:
        print("  (none)\n")
    else:
        print()

    print("SKIPPED (no match found):")
    skipped = [m for m in matches if m['method'] == 'skipped']
    for m in skipped:
        print(f"  ✗ {m['file']} ({m['type']})")
    if not skipped:
        print("  (none)\n")
    else:
        print()

    print("=" * 80)
    if skipped_count > 0:
        print(f"\nWARNING: {skipped_count} file(s) could not be matched and will need manual placement.")
    print("Review the matches above. If satisfied, run without --dry-run to apply.\n")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

    if dry_run:
        print("Running in DRY-RUN mode. No files will be moved.\n")

    matches = migrate(dry_run=dry_run)
    print_report(matches)

    if not dry_run:
        print(f"\n✓ Migration complete. {sum(1 for m in matches if m['method'] != 'skipped')} files moved.")
