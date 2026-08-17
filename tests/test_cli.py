"""cli.py: the reporting entry point docs/README.md and docs/reference.md tell
readers to run.

It shipped broken. `python3 src/best_foot_forward/cli.py <report>` — the exact
command in docs/README.md:44 and docs/reference.md:95 — died with
ModuleNotFoundError, because running the file as a script puts only
src/best_foot_forward/ on sys.path (enough for its own `from db import ...`)
while reports/applications.py imports `best_foot_forward.utils.triage_lead`,
which needs src/. Nobody caught it because every real invocation happened from
an agent session that already had PYTHONPATH=src set.

These tests run it as a subprocess with PYTHONPATH deliberately cleared, which
is the only way to exercise what a fresh clone actually does.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "src" / "best_foot_forward" / "cli.py"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
SCHEMA_PATH = REPO_ROOT / "src" / "best_foot_forward" / "schema.sql"


@pytest.fixture(scope="module")
def seeded_data_dir(tmp_path_factory):
    """An empty-but-initialized DATA_DIR. The tests must not read the developer's
    real database — CI has none, and a machine that does would make results
    depend on personal data."""
    import sqlite3
    d = tmp_path_factory.mktemp("cli-data")
    conn = sqlite3.connect(d / "best_foot_forward.db")
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()
    return d


def run_cli(*args, cwd=None, data_dir=None):
    """Invoke the CLI the way a new clone would: no PYTHONPATH, plain python3."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if data_dir is not None:
        env["BFF_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd or REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def menu_keys():
    """The command keys cli.py actually accepts, read out of its MENU table."""
    src = CLI.read_text()
    menu = src.split("MENU = [", 1)[1].split("\n]", 1)[0]
    return [m.group(1) for m in re.finditer(r'^\s*\("([a-z]+)"', menu, re.M)]


class TestDocumentedInvocationWorks:
    def test_bare_import_does_not_explode(self, seeded_data_dir):
        """The regression: this exited 1 on ModuleNotFoundError."""
        result = run_cli("skills", data_dir=seeded_data_dir)
        assert "ModuleNotFoundError" not in result.stderr, result.stderr
        assert result.returncode == 0, result.stderr

    def test_runs_from_an_unrelated_working_directory(self, tmp_path, seeded_data_dir):
        result = run_cli("gaps", cwd=tmp_path, data_dir=seeded_data_dir)
        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize("cmd", menu_keys())
    def test_every_menu_command_runs_on_an_empty_database(self, cmd, seeded_data_dir):
        """Every report must survive a database with no rows in it — that's the
        state a user is in immediately after onboarding."""
        result = run_cli(cmd, data_dir=seeded_data_dir)
        assert result.returncode == 0, f"{cmd} failed:\n{result.stderr}"


class TestUninitializedDatabase:
    def test_missing_database_explains_itself_instead_of_a_traceback(self, tmp_path):
        result = run_cli("skills", data_dir=tmp_path / "nonexistent")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr, result.stderr
        assert "No database yet" in result.stdout
        assert "onboard" in result.stdout

    def test_empty_database_file_is_also_caught(self, tmp_path):
        (tmp_path / "best_foot_forward.db").touch()
        result = run_cli("skills", data_dir=tmp_path)
        assert result.returncode == 1
        assert "no tables yet" in result.stdout
        assert "sqlite3.OperationalError" not in result.stderr


class TestDispatch:
    def test_unknown_command_exits_nonzero_and_lists_the_real_ones(self, seeded_data_dir):
        result = run_cli("bogus", data_dir=seeded_data_dir)
        assert result.returncode == 1
        assert "Unknown command" in result.stdout
        for key in ("skills", "gaps", "salaries"):
            assert key in result.stdout


class TestDocsStayInSync:
    def test_module_docstring_lists_the_commands_that_exist(self):
        """The docstring used to advertise a `rejections` command that was never
        implemented, and omitted eight that were."""
        docstring = CLI.read_text().split('"""')[1]
        listed = set(re.findall(r"\b([a-z]+)\b", docstring.split("Commands:", 1)[1]))
        actual = set(menu_keys())
        missing = actual - listed
        invented = {w for w in listed if w not in actual} & {
            "rejections", "companies", "salaries", "weekly", "skills", "gaps",
        }
        assert not missing, f"docstring omits real commands: {sorted(missing)}"
        assert not invented, f"docstring lists commands that don't exist: {sorted(invented)}"

    def test_docs_index_table_matches_the_menu(self):
        table = DOCS_INDEX.read_text()
        documented = set(re.findall(r"^\|\s*`([a-z]+)`\s*\|", table, re.M))
        actual = set(menu_keys())
        assert actual <= documented, (
            f"docs/README.md's report table is missing: {sorted(actual - documented)}"
        )
