"""BFF_DATA_DIR: the structural fix for sandbox contamination. Before this,
the only way to run BFF against a throwaway data directory was a separate
repo clone -- and a clone whose `origin` happened to point at the real GitHub
repo is exactly what let a real roleplay session get mistaken for a real
working copy and used for real applications, with a real-PII stash left
behind. DATA_DIR is read once at import time (a module-level constant, same
as _root always was), so this has to run as a subprocess with the env var
already set -- reloading the module in-process wouldn't exercise the same
code path a real script invocation does.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(code: str, env_overrides: dict) -> str:
    import os
    env = {**os.environ, **env_overrides}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return result.stdout.strip()


class TestBffDataDirOverride:
    def test_default_data_dir_is_repo_relative(self, tmp_path):
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import DATA_DIR; print(DATA_DIR)",
            env_overrides={"BFF_DATA_DIR": ""},
        )
        assert out.endswith("/data") or out.endswith("\\data")
        assert str(REPO_ROOT) in out

    def test_bff_data_dir_env_var_overrides_default(self, tmp_path):
        override = str(tmp_path / "uat-run")
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import DATA_DIR; print(DATA_DIR)",
            env_overrides={"BFF_DATA_DIR": override},
        )
        assert out == override

    def test_db_path_is_derived_from_the_override(self, tmp_path):
        override = str(tmp_path / "uat-run")
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import DB_PATH; print(DB_PATH)",
            env_overrides={"BFF_DATA_DIR": override},
        )
        assert out == str(Path(override) / "best_foot_forward.db")

    def test_get_conn_creates_a_missing_data_dir(self, tmp_path):
        """DATA_DIR is entirely gitignored -- a genuinely fresh clone has no
        data/ directory at all, and sqlite3.connect() can create the DB file
        but not a missing parent directory. Confirmed 2026-08-16 testing a
        clean-clone setup: init_db() raised sqlite3.OperationalError on a
        brand-new checkout's very first call, which would have hit every new
        user on first setup. get_conn() must create DATA_DIR itself rather
        than relying on every one of its several dozen callers to mkdir
        first."""
        override = tmp_path / "does-not-exist-yet" / "uat-run"
        assert not override.exists()
        run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import init_db; init_db()",
            env_overrides={"BFF_DATA_DIR": str(override)},
        )
        assert (override / "best_foot_forward.db").exists()


class TestResolveJdPathRespectsOverride:
    """A relative JD path always looks like 'data/BestFootForward/assets/...'
    (the convention every command and every fixture uses). Before this fix,
    resolve_jd_path anchored that at _root regardless of BFF_DATA_DIR, so an
    isolated/UAT run's JD files all resolved inside the real checkout's data/
    -- exactly backwards for isolation, and the kind of bug that would have
    silently written real-looking files into the real repo during a test run."""

    def test_data_relative_path_anchors_at_the_override(self, tmp_path):
        override = str(tmp_path / "uat-run")
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import resolve_jd_path; "
            "print(resolve_jd_path('data/BestFootForward/assets/Acme/Engineer/JobDesc.md'))",
            env_overrides={"BFF_DATA_DIR": override},
        )
        assert out == str(Path(override) / "BestFootForward" / "assets" / "Acme" / "Engineer" / "JobDesc.md")

    def test_bare_data_path_anchors_at_the_override(self, tmp_path):
        override = str(tmp_path / "uat-run")
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import resolve_jd_path; "
            "print(resolve_jd_path('data'))",
            env_overrides={"BFF_DATA_DIR": override},
        )
        assert out == override

    def test_default_behavior_unchanged_with_no_override(self, tmp_path):
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import resolve_jd_path, _root; "
            "import os; print(resolve_jd_path('data/BestFootForward/assets/Acme/Engineer/JobDesc.md') "
            "== os.path.normpath(os.path.join(_root, 'data/BestFootForward/assets/Acme/Engineer/JobDesc.md')))",
            env_overrides={"BFF_DATA_DIR": ""},
        )
        assert out == "True"

    def test_absolute_path_is_unaffected(self, tmp_path):
        override = str(tmp_path / "uat-run")
        out = run_python(
            "import sys; sys.path.insert(0, 'src'); from best_foot_forward.db import resolve_jd_path; "
            "print(resolve_jd_path('/some/absolute/JobDesc.md'))",
            env_overrides={"BFF_DATA_DIR": override},
        )
        assert out == "/some/absolute/JobDesc.md"
