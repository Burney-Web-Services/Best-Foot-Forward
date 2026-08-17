import os
import sqlite3

from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.text.run import Run
from docx.text.paragraph import Paragraph


# Module-level default root for testability
_ROOT = None


def _get_db_path():
    """Get the path to the BFF database."""
    global _ROOT
    if _ROOT:
        return os.path.join(_ROOT, "data", "best_foot_forward.db")
    try:
        from best_foot_forward.db import _root as ROOT
        return os.path.join(ROOT, "data", "best_foot_forward.db")
    except ImportError:
        return None


def get_accent_color() -> RGBColor:
    """Load the user's accent color preference from the DB, or use the default."""
    try:
        db_path = _get_db_path()
        if not db_path:
            return RGBColor(0x50, 0x93, 0x8A)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT accent_color_hex FROM document_prefs WHERE id = 1").fetchone()
        conn.close()
        if row and row["accent_color_hex"]:
            hex_str = row["accent_color_hex"].lstrip("#")
            return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    except Exception:
        pass
    return RGBColor(0x50, 0x93, 0x8A)  # default: teal


def get_font_name() -> str:
    """Load the user's font preference from the DB, or use the default."""
    try:
        db_path = _get_db_path()
        if not db_path:
            return "Calibri"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT font_name FROM document_prefs WHERE id = 1").fetchone()
        conn.close()
        if row and row["font_name"]:
            return row["font_name"]
    except Exception:
        pass
    return "Calibri"  # default


# Backward compatibility: export the default as ACCENT_COLOR
ACCENT_COLOR = get_accent_color()


def font(
    run: Run,
    size: float = 11,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor | None = None,
    font_name: str | None = None,
) -> None:
    if font_name is None:
        font_name = get_font_name()
    run.font.name = font_name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color


def _squash(text: str) -> str:
    """Lowercase and collapse all whitespace runs, for tolerant comparison."""
    return " ".join(text.lower().split())


def compose_signoff(closing: str | None, name: str | None) -> list[str]:
    """Return the letter sign-off as a list of paragraph strings.

    `closing` is authored per session in data/session/letter_data.py, and the
    convention for it has changed over time: it may be a bare valediction
    ("Sincerely,") or may already carry the full sign-off ("Sincerely,\\nJane Doe").
    Append `name` only when it is not already present, so a bare closing gets the
    name back while a closing that has it does not end up with it twice.

    Returns one string per paragraph: [closing] or [closing, name].
    """
    closing = (closing or "").strip()
    name = (name or "").strip()

    if not name:
        return [closing] if closing else []
    if not closing:
        return [name]
    if _squash(name) in _squash(closing):
        return [closing]
    return [closing, name]


def add_border(para: Paragraph) -> None:
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    pBdr.append(bottom)
    pPr.append(pBdr)
