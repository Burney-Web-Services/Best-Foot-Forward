"""load_example_data.py: seeds a fresh, empty BFF database and Logseq graph
from a tracked fixture directory. Integration-style (real subprocesses, real
.docx generation) since the loader itself orchestrates real production
scripts rather than reimplementing their logic -- these tests exist to catch
exactly the class of bug found while building this (resolve_jd_path not
respecting BFF_DATA_DIR, generate_resume.py's bare imports breaking under -m
invocation) that a pure unit test wouldn't touch.

Every test runs against a throwaway BFF_DATA_DIR (never the real repo's
data/) and asserts the real repo's data/ and memory/ are untouched
afterward -- the isolation guarantee this whole mechanism exists for.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_fixture(fixture_dir: Path, with_tailored_application: bool = True) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "intake_data.py").write_text(
        'CONTACT = {"name": "Synthetic Persona", "phone": "555-0100", '
        '"email": "synth@example.com", "location": "Testville, TS"}\n'
        'EDUCATION = [{"institution": "Test University", "location": "Testville, TS", '
        '"degree": "BS Computer Science", "sort_order": 0}]\n'
        'EMPLOYERS = [{"name": "PriorCo", "location": "Remote", "start_date": "01/2018", '
        '"end_date": "12/2023", "sort_order": 0, "notes": ""}]\n'
        'BULLETS = [\n'
        '    {"id": None, "employer": "PriorCo", "role": "Engineer", '
        '"text": "Built a thing that scaled", "tracks": ["engineer"], "themes": []},\n'
        '    {"id": None, "employer": "PriorCo", "role": "Engineer", '
        '"text": "Used Python and Docker extensively", "tracks": ["engineer"], "themes": []},\n'
        ']\n'
        'SKILLS = [{"id": None, "label": "Backend:", "content": "Python, Docker, PostgreSQL", '
        '"tracks": ["engineer"], "themes": []}]\n'
    )
    (fixture_dir / "document_prefs.json").write_text(
        json.dumps({"accent_color_hex": "50938A", "font_name": "Calibri"})
    )
    (fixture_dir / "user_profile.md").write_text("# User Profile\nSynthetic Persona — test fixture only.\n")
    (fixture_dir / "voice_guide.md").write_text("# Voice Guide\nSynthetic Persona's voice — test fixture only.\n")

    lead_dir = fixture_dir / "applications" / "TestCorp" / "Staff_Engineer"
    lead_dir.mkdir(parents=True, exist_ok=True)
    (lead_dir / "JobDesc.md").write_text(
        "type:: #JobDescription\ncompany:: [[TestCorp]]\nrole:: Staff Engineer\n\n"
        "Requires production Kubernetes and ArgoCD experience.\n"
    )
    (lead_dir / "jd_eval.json").write_text(json.dumps({
        "score": 75, "summary": "Solid technical overlap, gap on Kubernetes/ArgoCD.",
        "url": "https://example.com/jobs/1", "salary_min": 150000, "salary_max": 190000,
        "salary_currency": "USD", "required_skills": ["Kubernetes", "ArgoCD", "Python"],
    }))

    if not with_tailored_application:
        return

    app_dir = fixture_dir / "applications" / "OtherCo" / "Engineer"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "JobDesc.md").write_text(
        "type:: #JobDescription\ncompany:: [[OtherCo]]\nrole:: Engineer\n\n"
        "Looking for a backend engineer with Python experience.\n"
    )
    (app_dir / "jd_eval.json").write_text(json.dumps({
        "score": 88, "summary": "Strong match on backend fundamentals.",
        "salary_min": 140000, "salary_max": 170000, "salary_currency": "USD",
        "required_skills": ["Python", "PostgreSQL"],
    }))
    (app_dir / "resume_data.py").write_text(
        'COMPANY = "OtherCo"\n'
        'ROLE = "Engineer"\n'
        'JD_FILE_PATH = "data/BestFootForward/assets/OtherCo/Engineer/OtherCo_EngineerJobDesc.md"\n'
        'RESUME = {\n'
        '    "summary": "Backend engineer with a track record of scaling systems.",\n'
        '    "skills": [{"id": "skills-backend", "label": "Backend:", "content": "Python, Docker, PostgreSQL"}],\n'
        '    "experience": [\n'
        '        {"employer": "PriorCo", "location": "Remote", "dates": "01/2018 - 12/2023",\n'
        '         "roles": [{"title": "Engineer", "bullets": [\n'
        '             {"id": "priorco-001", "text": "Built a thing that scaled"},\n'
        '             {"id": "priorco-002", "text": "Used Python and Docker extensively"},\n'
        '         ]}]},\n'
        '    ],\n'
        '}\n'
    )
    (app_dir / "letter_data.py").write_text(
        'COMPANY = "OtherCo"\n'
        'ROLE = "Engineer"\n'
        'JD_FILE_PATH = "data/BestFootForward/assets/OtherCo/Engineer/OtherCo_EngineerJobDesc.md"\n'
        'LETTER = {\n'
        '    "salutation": "Dear OtherCo Team,",\n'
        '    "paragraphs": ["I\'m excited to apply for the Engineer role.", '
        '"My background in backend systems aligns well with this position."],\n'
        '    "closing": "Sincerely,",\n'
        '}\n'
    )


def build_fixture_with_punctuation(fixture_dir: Path) -> None:
    """A tailored application whose directory name is underscored but whose
    real company/role (read back from JobDesc.md's property block) contain
    spaces and punctuation -- the exact shape that reproduced all 3 loader
    bugs documented in examples/leia-organa/README.md: duplicate `jds` rows
    (underscore-vs-space company mismatch once generate_resume.py re-reads
    JD_FILE_PATH), lost role punctuation, and a doubled JobDesc.md header.
    """
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "intake_data.py").write_text(
        'CONTACT = {"name": "Synthetic Persona", "phone": "555-0100", '
        '"email": "synth@example.com", "location": "Testville, TS"}\n'
        'EDUCATION = [{"institution": "Test University", "location": "Testville, TS", '
        '"degree": "BS Computer Science", "sort_order": 0}]\n'
        'EMPLOYERS = [{"name": "PriorCo", "location": "Remote", "start_date": "01/2018", '
        '"end_date": "12/2023", "sort_order": 0, "notes": ""}]\n'
        'BULLETS = [\n'
        '    {"id": None, "employer": "PriorCo", "role": "Engineer", '
        '"text": "Built a thing that scaled", "tracks": ["engineer"], "themes": []},\n'
        ']\n'
        'SKILLS = [{"id": None, "label": "Backend:", "content": "Python, Docker, PostgreSQL", '
        '"tracks": ["engineer"], "themes": []}]\n'
    )

    company_dir = "Multi_Word_Co"
    role_dir_name = "Director_VP_of_Software"
    company_display = "Multi Word Co"
    role_display = "Director/VP of Software"

    app_dir = fixture_dir / "applications" / company_dir / role_dir_name
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "JobDesc.md").write_text(
        f"type:: #JobDescription\ncompany:: [[{company_display}]]\nrole:: {role_display}\n\n"
        "Looking for a leader with Kubernetes and ArgoCD experience.\n"
    )
    (app_dir / "jd_eval.json").write_text(json.dumps({
        "score": 90, "summary": "Strong leadership fit.",
        "salary_min": 200000, "salary_max": 260000, "salary_currency": "USD",
        "required_skills": ["Kubernetes", "ArgoCD"],
    }))
    jd_file_path = (
        f"data/BestFootForward/assets/{company_display}/{role_dir_name}/"
        f"{company_display}_{role_dir_name}JobDesc.md"
    )
    (app_dir / "resume_data.py").write_text(
        f'COMPANY = "{company_display}"\n'
        f'ROLE = "{role_display}"\n'
        f'JD_FILE_PATH = "{jd_file_path}"\n'
        'RESUME = {\n'
        '    "summary": "Engineering leader with a track record of scaling orgs.",\n'
        '    "skills": [{"id": "skills-backend", "label": "Backend:", "content": "Python, Docker, PostgreSQL"}],\n'
        '    "experience": [\n'
        '        {"employer": "PriorCo", "location": "Remote", "dates": "01/2018 - 12/2023",\n'
        '         "roles": [{"title": "Engineer", "bullets": [\n'
        '             {"id": "priorco-001", "text": "Built a thing that scaled"},\n'
        '         ]}]},\n'
        '    ],\n'
        '}\n'
    )
    (app_dir / "letter_data.py").write_text(
        f'COMPANY = "{company_display}"\n'
        f'ROLE = "{role_display}"\n'
        f'JD_FILE_PATH = "{jd_file_path}"\n'
        'LETTER = {\n'
        '    "salutation": "Dear Hiring Team,",\n'
        '    "paragraphs": ["I would love to lead this team."],\n'
        '    "closing": "Sincerely,",\n'
        '}\n'
    )


def build_fixture_with_not_yet_loadable(fixture_dir: Path) -> None:
    """Same shape as build_fixture(), but both jd_eval.json files carry a
    `_not_yet_loadable` block -- a declined lead (category + reason + decision
    date) on the untailored one, a screen-stage + scheduled-interview contact
    on the tailored one. Mirrors examples/leia-organa's real Nar Shaddaa
    (decline) and Obroa-skai (screen stage + contact) provenance."""
    build_fixture(fixture_dir, with_tailored_application=True)

    lead_eval_path = fixture_dir / "applications" / "TestCorp" / "Staff_Engineer" / "jd_eval.json"
    lead_eval = json.loads(lead_eval_path.read_text())
    lead_eval["_not_yet_loadable"] = {
        "lead_status": "declined",
        "decline_category": "domain",
        "decline_reason": "Not a sector I want my name next to.",
        "lead_decided_at": "2026-08-14",
    }
    lead_eval_path.write_text(json.dumps(lead_eval))

    app_eval_path = fixture_dir / "applications" / "OtherCo" / "Engineer" / "jd_eval.json"
    app_eval = json.loads(app_eval_path.read_text())
    app_eval["_not_yet_loadable"] = {
        "application_stage": "screen",
        "contact": {
            "name": "Test Recruiter",
            "title": "Technical Recruiter",
            "role": "recruiter",
            "interview_date": "2026-08-21",
            "interview_time": "10:00 AM PT",
            "interview_stage": "screen",
            "notes": "Video call, link to follow",
        },
    }
    app_eval_path.write_text(json.dumps(app_eval))


def run_loader(fixture_dir: Path, data_dir: Path, force: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "BFF_DATA_DIR": str(data_dir), "BFF_UAT": "1"}
    cmd = [sys.executable, "-m", "best_foot_forward.utils.load_example_data", str(fixture_dir)]
    if force:
        cmd.append("--force")
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)


@pytest.fixture
def real_repo_snapshot():
    """Confirm the real repo's data/ and memory/ are untouched before and
    after -- the isolation guarantee under test."""
    data_existed = (REPO_ROOT / "data").exists()
    memory_existed = (REPO_ROOT / "memory").exists()
    yield
    assert (REPO_ROOT / "data").exists() == data_existed, "real repo data/ was touched"
    assert (REPO_ROOT / "memory").exists() == memory_existed, "real repo memory/ was touched"


class TestLoadExampleData:
    def test_full_load_scored_and_tailored(self, tmp_path, real_repo_snapshot):
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture(fixture_dir)

        result = run_loader(fixture_dir, data_dir)
        assert result.returncode == 0, result.stdout + result.stderr

        import sqlite3
        conn = sqlite3.connect(data_dir / "best_foot_forward.db")
        conn.row_factory = sqlite3.Row

        jds = {r["company"]: dict(r) for r in conn.execute("SELECT company, role, score FROM jds")}
        assert jds["TestCorp"]["score"] == 75
        assert jds["OtherCo"]["score"] == 88

        apps = conn.execute("SELECT status FROM applications").fetchall()
        assert len(apps) == 1
        assert apps[0]["status"] == "applied"

        # The Bug-1 regression check at the loader level: the fixture JD names
        # skills the persona doesn't have, and they must actually get indexed.
        canonicals = {r[0] for r in conn.execute(
            "SELECT canonical_label FROM jd_required_skills WHERE jd_id = "
            "(SELECT id FROM jds WHERE company='TestCorp')"
        )}
        assert {"Kubernetes", "ArgoCD"} <= canonicals

        conn.close()

        assert (data_dir / "memory" / "user_profile.md").exists()
        assert (data_dir / "memory" / "voice_guide.md").exists()

        resume_files = list((data_dir / "BestFootForward" / "assets" / "OtherCo" / "Engineer").glob("*Resume*"))
        assert resume_files, "no resume files generated for the tailored application"

        assert (data_dir / "BestFootForward" / "pages" / "Home.md").exists()

    def test_scored_only_lead_is_not_treated_as_applied(self, tmp_path, real_repo_snapshot):
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture(fixture_dir, with_tailored_application=False)

        result = run_loader(fixture_dir, data_dir)
        assert result.returncode == 0, result.stdout + result.stderr

        import sqlite3
        conn = sqlite3.connect(data_dir / "best_foot_forward.db")
        apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        assert apps == 0
        conn.close()

    def test_refuses_to_clobber_existing_real_data(self, tmp_path, real_repo_snapshot):
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture(fixture_dir, with_tailored_application=False)

        first = run_loader(fixture_dir, data_dir)
        assert first.returncode == 0, first.stdout + first.stderr

        second = run_loader(fixture_dir, data_dir)
        assert second.returncode != 0
        assert "refusing" in (second.stdout + second.stderr).lower()

    def test_force_overrides_the_safety_check(self, tmp_path, real_repo_snapshot):
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture(fixture_dir, with_tailored_application=False)

        run_loader(fixture_dir, data_dir)
        second = run_loader(fixture_dir, data_dir, force=True)
        assert second.returncode == 0, second.stdout + second.stderr

    def test_tailored_application_with_spaced_punctuated_name_loads_once(self, tmp_path, real_repo_snapshot):
        """Regression test for the 3 loader bugs found building the Leia
        fixture (examples/leia-organa/README.md): a directory name that's
        underscored but whose real company/role (in JobDesc.md's property
        block) have spaces and punctuation must not produce a duplicate
        `jds` row, must not lose the role's punctuation, and must not
        double the JobDesc.md header."""
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture_with_punctuation(fixture_dir)

        result = run_loader(fixture_dir, data_dir)
        assert result.returncode == 0, result.stdout + result.stderr

        import sqlite3
        conn = sqlite3.connect(data_dir / "best_foot_forward.db")
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT company, role, file_path FROM jds WHERE company = 'Multi Word Co'"
        ).fetchall()
        conn.close()

        # Bug 1: generate_resume.py re-reads JD_FILE_PATH (space-formatted,
        # per convention) after the loader's own insert -- if the two paths
        # don't agree, this comes back as 2 rows instead of 1.
        assert len(rows) == 1, f"expected exactly 1 jds row, got {len(rows)}: {[dict(r) for r in rows]}"

        # Bug 2: role must keep its punctuation, not the slugified directory form.
        assert rows[0]["role"] == "Director/VP of Software"

        # Bug 3: the written JD file must have exactly one property-block header.
        jd_text = Path(rows[0]["file_path"]).read_text(encoding="utf-8")
        assert jd_text.count("type:: #JobDescription") == 1, jd_text
        assert jd_text.count("company::") == 1, jd_text
        assert jd_text.count("role::") == 1, jd_text

    def test_missing_fixture_dir_fails_cleanly(self, tmp_path, real_repo_snapshot):
        result = run_loader(tmp_path / "does-not-exist", tmp_path / "uat-run")
        assert result.returncode != 0

    def test_not_yet_loadable_lead_state_replays(self, tmp_path, real_repo_snapshot):
        """jd_eval.json's `_not_yet_loadable` block (added 2026-08-16 to carry
        the real Leia fixture's decline/screen-stage outcomes) must replay
        through the documented write paths -- triage_lead.set_lead_status()
        for the decline, a direct applications.stage UPDATE for the stage,
        and a contacts insert -- not just sit unread in the JSON."""
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture_with_not_yet_loadable(fixture_dir)

        result = run_loader(fixture_dir, data_dir)
        assert result.returncode == 0, result.stdout + result.stderr

        import sqlite3
        conn = sqlite3.connect(data_dir / "best_foot_forward.db")
        conn.row_factory = sqlite3.Row

        lead = conn.execute(
            "SELECT lead_status, decline_category, decline_reason, lead_decided_at "
            "FROM jds WHERE company = 'TestCorp'"
        ).fetchone()
        assert lead["lead_status"] == "declined"
        assert lead["decline_category"] == "domain"
        assert lead["decline_reason"] == "Not a sector I want my name next to."
        assert lead["lead_decided_at"] == "2026-08-14"

        app = conn.execute(
            "SELECT a.stage FROM applications a JOIN jds j ON j.id = a.jd_id "
            "WHERE j.company = 'OtherCo'"
        ).fetchone()
        assert app["stage"] == "screen"

        contact = conn.execute(
            "SELECT c.name, c.title, c.role, c.interview_date, c.interview_stage "
            "FROM contacts c JOIN jds j ON j.id = c.jd_id WHERE j.company = 'OtherCo'"
        ).fetchone()
        assert contact is not None
        assert contact["name"] == "Test Recruiter"
        assert contact["role"] == "recruiter"
        assert contact["interview_date"] == "2026-08-21"

        conn.close()

    def test_not_yet_loadable_replay_is_idempotent_on_force_reload(self, tmp_path, real_repo_snapshot):
        """A second --force load over the same data_dir must not duplicate
        the contact row or clobber the decline decision with a fresh
        timestamp."""
        fixture_dir = tmp_path / "fixture"
        data_dir = tmp_path / "uat-run"
        build_fixture_with_not_yet_loadable(fixture_dir)

        first = run_loader(fixture_dir, data_dir)
        assert first.returncode == 0, first.stdout + first.stderr
        second = run_loader(fixture_dir, data_dir, force=True)
        assert second.returncode == 0, second.stdout + second.stderr

        import sqlite3
        conn = sqlite3.connect(data_dir / "best_foot_forward.db")
        contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        decided_at = conn.execute(
            "SELECT lead_decided_at FROM jds WHERE company = 'TestCorp'"
        ).fetchone()[0]
        conn.close()

        assert contact_count == 1
        assert decided_at == "2026-08-14"
