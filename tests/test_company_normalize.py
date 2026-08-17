from best_foot_forward.utils.company_normalize import (
    alnum_key, canonical_company, classify_row, company_slug,
)


def _row(company, role="Role", file_path=None, id=1):
    return {"id": id, "company": company, "role": role, "file_path": file_path}


def test_alnum_key():
    assert alnum_key("College Board") == "collegeboard"
    assert alnum_key("Go-Guardian!") == "goguardian"


def test_company_slug():
    assert company_slug("GoGuardian") == "goguardian"
    assert company_slug("Teaching Strategies") == "teaching-strategies"
    assert company_slug("College Board") == "college-board"


def test_canonical_explicit_alias():
    assert canonical_company("Perforce Software") == "Perforce"
    assert canonical_company("Edia Learning") == "Edia"


def test_canonical_display_fold():
    assert canonical_company("brightwheel") == "Brightwheel"
    assert canonical_company("CollegeBoard") == "College Board"


def test_clean_company():
    c = classify_row(_row(
        "GoGuardian",
        file_path="/x/data/applications/GoGuardian/Staff_SWE/GoGuardianJobDesc.txt"))
    assert c.kind == "clean"
    assert c.canonical_company == "GoGuardian"
    assert c.org_slug == "goguardian"


def test_alias_company():
    c = classify_row(_row("brightwheel"))
    assert c.kind == "alias"
    assert c.canonical_company == "Brightwheel"


def test_junk_token():
    c = classify_row(_row(
        "Research-and-Prep",
        file_path="/x/data/applications/Amazon/SDM/Research-and-Prep/notes.txt"))
    assert c.kind == "quarantine"


def test_junk_path_fragment():
    c = classify_row(_row(
        "Outschool",
        file_path="/x/data/applications/Outschool/DoE/research/glassdoor.txt"))
    assert c.kind == "quarantine"


def test_role_placeholder_recovered():
    # company == role dir, a different real company sits above under /applications/,
    # and the file is a JobDesc -> recover the true company from the path
    c = classify_row(_row(
        "Software_Engineering_Manager",
        file_path="/x/data/applications/Hasbro/Software_Engineering_Manager/HasbroJobDesc.txt"))
    assert c.kind == "recovered"
    assert c.canonical_company == "Hasbro"


def test_role_placeholder_misregistered_artifact():
    # same shape but the file is NOT a JobDesc -> quarantine (real JD row exists elsewhere)
    c = classify_row(_row(
        "Software_Engineering_Manager",
        file_path="/x/data/applications/Hasbro/Software_Engineering_Manager/HasbroThankYou.txt"))
    assert c.kind == "quarantine"


def test_flat_layout_not_a_placeholder():
    # old v6 layout: company == its own dir but there is no differing
    # /applications/ parent, so it's a legit company, not a placeholder
    c = classify_row(_row(
        "Andiamo",
        file_path="/x/JobSearch2026/v6/Andiamo/AndiamoJobDesc.txt"))
    assert c.kind == "clean"
    assert c.canonical_company == "Andiamo"
