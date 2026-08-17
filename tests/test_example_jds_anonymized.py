"""Guard the committed Leia Organa example JDs against identity leaks.

`docs/example/LeiaOrgana/jds/*.odt` are real job postings with the employer's identity
replaced by an in-universe one (see `scripts/anonymize_example_jds.py`). This repo is
intended to go public, so a regression that reintroduces a real company name, an ATS
URL, or the original page thumbnail is a disclosure bug, not a cosmetic one.

The checks run over *all* XML in each ODF zip rather than the visible text, because the
leaks that actually occurred were invisible when reading the document: linked logo
images on a recruiting CDN, ATS bookmarks storing real cities in an attribute name, and
`Thumbnails/thumbnail.png` still rendering the original company's page.
"""
import importlib.util
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
JDS = REPO / "docs" / "example" / "LeiaOrgana" / "jds"
SCRIPT = REPO / "scripts" / "anonymize_example_jds.py"


def _load_anonymizer():
    """Import the script by path — `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location("anonymize_example_jds", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


anon = _load_anonymizer()
JD_FILES = sorted(anon.SPECS)


def _all_xml(path):
    z = zipfile.ZipFile(path)
    return "".join(z.read(n).decode("utf-8", "ignore")
                   for n in z.namelist() if n.endswith((".xml", ".rdf")))


@pytest.mark.parametrize("name", JD_FILES)
def test_jd_present(name):
    assert (JDS / name).is_file(), f"{name} missing from the example corpus"


@pytest.mark.parametrize("name", JD_FILES)
def test_no_real_employer_identifiers(name):
    hits = sorted({m.group(0) for m in anon.LEAK_RE.finditer(_all_xml(JDS / name))})
    assert not hits, f"{name} leaks real-world identifiers: {hits}"


@pytest.mark.parametrize("name", JD_FILES)
def test_no_collision_with_leias_own_history(name):
    """The jobs Leia applies TO must not reuse the employers she worked AT."""
    hits = sorted({m.group(0) for m in anon.COLLIDE_RE.finditer(_all_xml(JDS / name))})
    assert not hits, f"{name} reuses names from Leia's resume: {hits}"


@pytest.mark.parametrize("name", JD_FILES)
def test_no_external_references(name):
    """No live fetches. Only the keep-list (stack links) may survive."""
    blob = _all_xml(JDS / name)
    refs = sorted({u for u in anon.HREF_RE.findall(blob)
                   if not u.startswith(("../", "#"))
                   and not any(k in u for k in anon.IGNORE_HREF)
                   and not any(k in u for k in anon.KEEP_LINKS)})
    assert not refs, f"{name} still references external hosts: {refs}"


@pytest.mark.parametrize("name", JD_FILES)
def test_thumbnail_removed(name):
    """The page-1 preview renders the ORIGINAL company name, so it must not ship."""
    names = zipfile.ZipFile(JDS / name).namelist()
    assert not any("thumbnail" in n.lower() for n in names), \
        f"{name} still contains a page thumbnail"


@pytest.mark.parametrize("name", JD_FILES)
def test_still_a_valid_odf_document(name):
    """Rebuilding the zip by hand breaks ODF unless mimetype is first and stored."""
    z = zipfile.ZipFile(JDS / name)
    first = z.infolist()[0]
    assert z.testzip() is None, f"{name} is a corrupt zip"
    assert first.filename == "mimetype"
    assert first.compress_type == zipfile.ZIP_STORED
    assert z.read("mimetype") == b"application/vnd.oasis.opendocument.text"
