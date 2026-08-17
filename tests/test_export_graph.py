from best_foot_forward.utils.export_graph import (
    asset_target, company_title, title_to_filename, _role_title, _date_ref,
)


def test_company_title_slash_sanitized():
    # '/' is the namespace separator, so a company with '/' must not create one
    assert company_title("Mandiant / Google Cloud") == "Mandiant - Google Cloud"
    assert company_title("GoGuardian") == "GoGuardian"


def test_role_title_slash_sanitized():
    assert _role_title("Senior Solution Architect (Data/Integration)") == \
        "Senior Solution Architect (Data-Integration)"


def test_title_to_filename():
    assert title_to_filename("GoGuardian/Staff SWE/Application") == \
        "GoGuardian___Staff SWE___Application"


def test_asset_target_from_applications_path():
    t = asset_target("GoGuardian",
                     "data/applications/GoGuardian/Staff_SWE/GoGuardianJobDesc.txt",
                     "Staff SWE")
    assert t == "assets/GoGuardian/Staff_SWE/GoGuardianJobDesc.txt"


def test_asset_target_fallbacks_to_role_slug():
    # a path with no 'applications' segment (e.g. media) uses slugify(role)
    t = asset_target("Acme", "data/media/transcripts/call.md", "Senior Engineer")
    assert t == "assets/Acme/Senior_Engineer/call.md"


def test_date_ref_slash_format():
    assert _date_ref("2026-07-16T19:10:49") == "[[2026/07/16]]"
    assert _date_ref(None) is None
