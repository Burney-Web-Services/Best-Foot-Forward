"""Regression test for a real isolation gap tests/uat/ surfaced: generate_home's
write_sevo_pulse() stamps a line into BFF_SEVO_GLANCE, a real cross-graph hub
page that lives outside DATA_DIR entirely -- so unlike everything else
generate_home writes, db.py's DATA_DIR override never isolated it. A scripted
/evaluate-job UAT run reported it had leaked a fictional persona's pulse into
the real hub page (that specific incident didn't check out -- the real file
was verified byte-identical to its last real commit -- but the underlying gap
was real: nothing stopped it from happening under a live BFF_SEVO_GLANCE).
"""
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


@pytest.fixture
def glance_page(tmp_path):
    page = tmp_path / "Home.md"
    page.write_text("- ## Some Section\n\t- content\n")
    return page


def test_sevo_pulse_skipped_under_bff_data_dir(monkeypatch, tmp_path, glance_page):
    from best_foot_forward.utils import generate_home

    original = glance_page.read_text()
    monkeypatch.setenv("BFF_SEVO_GLANCE", str(glance_page))
    monkeypatch.setenv("BFF_DATA_DIR", str(tmp_path / "uat-data"))
    monkeypatch.setattr(generate_home, "SEVO_GLANCE", str(glance_page))

    conn = make_mem_db()
    generate_home.write_sevo_pulse(conn, active=0)
    conn.close()

    assert glance_page.read_text() == original, "write_sevo_pulse wrote despite BFF_DATA_DIR being set"


def test_sevo_pulse_writes_when_not_isolated(monkeypatch, glance_page):
    from best_foot_forward.utils import generate_home

    monkeypatch.setenv("BFF_SEVO_GLANCE", str(glance_page))
    monkeypatch.delenv("BFF_DATA_DIR", raising=False)
    monkeypatch.setattr(generate_home, "SEVO_GLANCE", str(glance_page))

    conn = make_mem_db()
    generate_home.write_sevo_pulse(conn, active=3)
    conn.close()

    updated = glance_page.read_text()
    assert "Job Search Pulse" in updated
    assert "**3** in motion" in updated


class TestEnsureDefaultFavorites:
    """generate_home.py's own docstring has claimed 'Favorited via
    logseq/config.edn :favorites [\"Home\"]' since before this function
    existed -- it never actually did anything until now. markdown_graph_kit's
    ensure_graph_config() deliberately doesn't touch :favorites (out of scope
    for a general-purpose graph-kit library), so this is BFF's own addition."""

    def test_adds_favorites_key_when_absent(self, tmp_path):
        from best_foot_forward.utils import generate_home

        graph_root = tmp_path / "BestFootForward"
        (graph_root / "logseq").mkdir(parents=True)
        cfg = graph_root / "logseq" / "config.edn"
        cfg.write_text('{:meta/version 1\n :file/name-format :triple-lowbar\n}\n')

        generate_home.ensure_default_favorites(str(graph_root))

        text = cfg.read_text()
        assert ':favorites ["home" "leads dashboard" "applications dashboard"]' in text
        assert ':file/name-format :triple-lowbar' in text, "must not clobber existing settings"

    def test_adds_missing_entries_without_disturbing_user_favorites(self, tmp_path):
        """A user favoriting an unrelated page in the Logseq UI writes into
        this same :favorites key -- must be additive, never replace or
        reorder what's already there."""
        from best_foot_forward.utils import generate_home

        graph_root = tmp_path / "BestFootForward"
        (graph_root / "logseq").mkdir(parents=True)
        cfg = graph_root / "logseq" / "config.edn"
        cfg.write_text('{:meta/version 1\n :favorites ["some other page" "home"]\n}\n')

        generate_home.ensure_default_favorites(str(graph_root))

        text = cfg.read_text()
        m = generate_home.re.search(r':favorites\s*\[([^\]]*)\]', text)
        items = generate_home.re.findall(r'"([^"]*)"', m.group(1))
        assert items == ["some other page", "home", "leads dashboard", "applications dashboard"]

    def test_noop_when_all_defaults_already_present(self, tmp_path):
        from best_foot_forward.utils import generate_home

        graph_root = tmp_path / "BestFootForward"
        (graph_root / "logseq").mkdir(parents=True)
        cfg = graph_root / "logseq" / "config.edn"
        original = '{:meta/version 1\n :favorites ["home" "leads dashboard" "applications dashboard"]\n}\n'
        cfg.write_text(original)

        generate_home.ensure_default_favorites(str(graph_root))

        assert cfg.read_text() == original

    def test_noop_when_config_edn_does_not_exist(self, tmp_path):
        from best_foot_forward.utils import generate_home

        graph_root = tmp_path / "BestFootForward"
        generate_home.ensure_default_favorites(str(graph_root))  # must not raise

        assert not (graph_root / "logseq" / "config.edn").exists()
