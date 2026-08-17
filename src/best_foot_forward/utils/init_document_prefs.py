"""Initialize document preferences (color and font for generated .docx files).

Ensures the document_prefs table has exactly one row with defaults or user choices.
Run at the start of onboarding or resume-tailor to ensure prefs are initialized.

    python3 -m best_foot_forward.utils.init_document_prefs
"""
import os
import sqlite3

from best_foot_forward.db import DATA_DIR


def ensure_document_prefs(accent_color_hex: str = "50938A", font_name: str = "Calibri") -> None:
    """Ensure the document_prefs table has a row with the given (or default) preferences.

    Called at startup to initialize if not present. Idempotent.
    """
    db_path = os.path.join(DATA_DIR, "best_foot_forward.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Insert or replace (idempotent): id is always 1, so this overwrites if present
    conn.execute(
        "INSERT OR REPLACE INTO document_prefs (id, accent_color_hex, font_name) VALUES (1, ?, ?)",
        (accent_color_hex, font_name),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    ensure_document_prefs()
    print("✓ document_prefs initialized")
