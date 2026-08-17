#!/usr/bin/env python3
"""Rebuild the fictional example JDs in `docs/example/LeiaOrgana/jds/` from real postings.

This is how the Leia Organa example corpus was produced, kept so the provenance of
that dataset is auditable and so the mapping can be re-run or extended rather than
re-derived by hand. Every posting Leia "applies to" is a real job description with
the employer's identity replaced by an in-universe one.

**The real source postings are deliberately NOT in this repo.** They live outside it
(originally `~/Desktop/originals/`) and must stay outside — committing them would
defeat the point. Pass their location with `--src`; the default is a path that will
simply not exist on most checkouts, which is the intended failure mode.

Why it edits `content.xml` in the ODF zip directly rather than round-tripping through
pandoc/LibreOffice: a round-trip rebuilds the document and degrades its formatting.
Substituting inside the zip preserves the original layout exactly. Company names were
verified to sit as contiguous text (no `<text:span>` splits), which is what makes the
literal token swaps safe.

Four kinds of edit, because a naive find-and-replace over the visible text leaks:

 1. whole-paragraph drops   — ATS/legal boilerplate (privacy notices, EEO, scam
                              warnings, `#LI-` tags, "Back to jobs" chrome)
 2. whole-paragraph rewrites — prose needing restatement, and any paragraph whose text
                              is fragmented across spans by an embedded hyperlink
 3. literal token swaps     — company/product/place names
 4. structural removals     — see below; these are the ones that bite

The non-obvious leaks, all invisible when reading the document:

 * **Linked logo images.** Three postings referenced `<draw:image xlink:href="https://
   s*-recruiting.cdn.greenhouse.io/.../<Company>_Logo.png">` — a *live external fetch*,
   with the company name in the URL path and in an `<svg:title>` alt-text.
 * **ATS location bookmarks.** `<text:bookmark text:name="secondary-additional-location-
   Milpitas, California"/>` stores real cities in an *attribute name*. These survive any
   amount of visible-text rewriting.
 * **Page thumbnails.** `Thumbnails/thumbnail.png` is a rendered preview of page 1 and
   still shows the original company name. Dropped, along with its manifest entry.
 * **Hyperlink hrefs** generally — ATS board URLs (Greenhouse *and* Ashby, so the pass is
   driven by "strip every href not on the keep-list" rather than by host), tracking
   tokens, press coverage, LinkedIn, investor and careers pages.

`--verify` re-checks output for all of the above. Run it after any spec change.
"""
import argparse
import html
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "Desktop" / "originals"
DEFAULT_OUT = REPO / "docs" / "example" / "LeiaOrgana" / "jds"

SRC = DEFAULT_SRC
OUT = DEFAULT_OUT

PARA_RE = re.compile(r"<text:(p|h)\b[^>]*>.*?</text:\1>", re.S)
LINK_RE = re.compile(r"<text:a\b[^>]*>(.*?)</text:a>", re.S)
FRAME_RE = re.compile(r"<draw:frame\b(?:(?!</draw:frame>).)*?<draw:image\b[^>]*?"
                      r"greenhouse\.io.*?</draw:frame>", re.S)
# ATS bookmarks embed the real city names in their text:name attribute, e.g.
# <text:bookmark text:name="secondary-additional-location-Milpitas, California"/>
BOOKMARK_RE = re.compile(r"<text:bookmark\b[^>]*location[^>]*/>")

KEEP_LINKS = ("github.com/go-gitea/gitea",)


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace("'", "&apos;"))


def plain(fragment):
    """Visible text of an XML fragment."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ").strip()


def apply_paras(xml, drops, drops_exact, rewrites, stats):
    def handle(m):
        frag = m.group(0)
        text = plain(frag)
        if not text:
            return frag
        if text in drops_exact:
            stats["dropped"].append(text)
            return ""
        for marker in drops:
            if marker in text:
                stats["dropped"].append(text)
                return ""
        for marker, replacement in rewrites:
            if marker in text:
                stats["rewritten"].append(text)
                tag = m.group(1)
                open_tag = re.match(r"<text:%s\b[^>]*>" % tag, frag).group(0)
                span = re.search(r'<text:span text:style-name="[^"]*">', frag)
                body = esc(replacement)
                if span:
                    body = span.group(0) + body + "</text:span>"
                return open_tag + body + "</text:%s>" % tag
        return frag
    return PARA_RE.sub(handle, xml)


def unwrap_links(xml, stats):
    def handle(m):
        whole = m.group(0)
        if any(k in whole for k in KEEP_LINKS):
            return whole
        stats["unlinked"] += 1
        return m.group(1)          # keep the anchor text, drop the href
    return LINK_RE.sub(handle, xml)


def scrub(name, spec):
    src = SRC / name
    zin = zipfile.ZipFile(src)
    xml = zin.read("content.xml").decode("utf-8")
    stats = {"dropped": [], "rewritten": [], "unlinked": 0, "frames": 0, "bookmarks": 0}

    xml, n = FRAME_RE.subn("", xml)
    stats["frames"] = n
    xml, nb = BOOKMARK_RE.subn("", xml)
    stats["bookmarks"] = nb

    xml = apply_paras(xml, spec.get("drops", []), spec.get("drops_exact", []),
                      spec.get("rewrites", []), stats)
    xml = unwrap_links(xml, stats)

    for old, new in spec.get("tokens", []):
        for o, n2 in ((old, new), (esc(old), esc(new))):
            if o in xml:
                xml = xml.replace(o, n2)

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / name
    with zipfile.ZipFile(dst, "w") as zout:
        # mimetype MUST be first and stored uncompressed for ODF recognition
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zout.writestr(zi, zin.read("mimetype"))
        for item in zin.infolist():
            if item.filename in ("mimetype", "Thumbnails/thumbnail.png"):
                continue          # thumbnail still renders the ORIGINAL company name
            data = zin.read(item.filename)
            if item.filename == "content.xml":
                data = xml.encode("utf-8")
            elif item.filename == "META-INF/manifest.xml":
                m = data.decode("utf-8")
                m = re.sub(r"\s*<manifest:file-entry[^>]*Thumbnails/thumbnail\.png[^>]*/>", "", m)
                data = m.encode("utf-8")
            zout.writestr(item, data)

    print(f"\n=== {name} -> {spec['company']}")
    print(f"    logo frames removed : {stats['frames']}")
    print(f"    location bookmarks  : {stats['bookmarks']}")
    print(f"    hyperlinks stripped : {stats['unlinked']}")
    print(f"    paragraphs dropped  : {len(stats['dropped'])}")
    for d in stats["dropped"]:
        print(f"        - {d[:70]}")
    print(f"    paragraphs rewritten: {len(stats['rewritten'])}")
    for d in stats["rewritten"]:
        print(f"        ~ {d[:70]}")
    missing = [m for m, _ in spec.get("rewrites", [])
               if not any(m in x for x in stats["rewritten"])]
    if missing:
        print(f"    !! REWRITE MARKERS NEVER MATCHED: {missing}")
    missing_d = [m for m in spec.get("drops", [])
                 if not any(m in x for x in stats["dropped"])]
    if missing_d:
        print(f"    !! DROP MARKERS NEVER MATCHED: {missing_d}")


SPECS = {}

# ---------------------------------------------------------------- one.odt
SPECS["one.odt"] = {
    "company": "Chandrila Data Collective",
    "drops": [
        "Back to jobs",
        "Links to more information",
        "External Handbook",
        "Youtube",
        "Privacy Statement",
        # orphaned link-chrome once their hyperlinks are stripped
        "Benefits",
        "Website",
    ],
    "rewrites": [],
    "tokens": [
        ("Prolific  Logo", "Chandrila Data Collective Logo"),
        ("Why Prolific", "Why Chandrila Data Collective"),
        ("JoinProlific", "JoinChandrila"),
        ("Prolific", "Chandrila Data Collective"),
        ("Remote, UK", "Remote, Chandrila"),
    ],
}

# ---------------------------------------------------------------- two.odt
SPECS["two.odt"] = {
    "company": "Nar Shaddaa Exchange Group",
    "drops": [
        "Back to jobs",
        "Depending on the role, your interview and onboarding",
        "#LI-Remote",
        "#LI-AL1",
        "By submitting your application, you agree to our terms of service",
    ],
    "rewrites": [
        ("Fanatics is building a leading global digital sports platform",
         "Nar Shaddaa Exchange Group is building the leading prediction and trading "
         "platform in the Outer Rim. We ignite the passions of sports and entertainment "
         "audiences across the galaxy and maximize reach for our partners by offering "
         "products and services across Exchange Commerce, Exchange Collectibles, and "
         "Exchange Betting & Gaming, allowing fans to Buy, Collect, and Bet. Through the "
         "Exchange platform, fans can buy licensed fan gear, apparel, and hardgoods; "
         "collect physical and digital trading cards, memorabilia, and other digital "
         "assets; and bet as the company builds its Sportsbook and iGaming platform. "
         "Nar Shaddaa Exchange Group has an established database of over 40 million "
         "registered participants; a partner network of approximately 600 sporting "
         "properties, including major sector leagues, teams, academies, and retail "
         "partners, 1,200 athletes and celebrities, and 90 exclusive athletes; and over "
         "800 retail locations across Hutt Space. Our more than 9,000 employees are "
         "committed to relentlessly enhancing the fan experience galaxy-wide."),
        ("Ready to build the future of sports betting",
         "Ready to build the future of prediction markets? If you possess some of these "
         "skills but not all of them, we still encourage you to apply! We are open to "
         "fully remote candidates based in Hutt Space. Remote employees may also be "
         "eligible for a home office setup stipend."),
    ],
    "tokens": [
        ("Fanatics Betting &amp; Gaming Logo", "Nar Shaddaa Exchange Group Logo"),
        ("Fanatics Markets", "Nar Shaddaa Markets"),
        ("Fanatics Betting &amp; Gaming", "Nar Shaddaa Exchange Group"),
        ("Fanatics", "Nar Shaddaa Exchange Group"),
        ("Staff Platform Engineer, Nar Shaddaa Markets - UK",
         "Staff Platform Engineer, Nar Shaddaa Markets"),
        ("Edinburgh, Scotland, United Kingdom; Leeds, England, United Kingdom; "
         "London, England, United Kingdom",
         "Duros Sector, Nar Shaddaa; Promenade District, Nar Shaddaa; "
         "Lower Levels, Nar Shaddaa"),
        ("United Kingdom", "Hutt Space"),
    ],
}

# ---------------------------------------------------------------- three.odt
SPECS["three.odt"] = {
    "company": "Scarif Identity Systems",
    "drops": [
        "We may use artificial intelligence (AI) tools to support parts of the hiring process",
    ],
    "rewrites": [
        # fragmented by ATS location bookmarks, so rewrite the whole paragraph
        ("Atlanta", "Citadel Station / Stardust Annex / Coastal Works"),
    ],
    "tokens": [
        ("Saviynt’s", "Scarif Identity Systems’"),   # avoid "Systems’s"
        ("Saviynt", "Scarif Identity Systems"),
    ],
}

# ---------------------------------------------------------------- four.odt
SPECS["four.odt"] = {
    "company": "Obroa-skai Analytics",
    "drops": [
        "Back to jobs",
        "AlphaSense is an equal-opportunity employer",
        "In addition, it is the policy of AlphaSense to provide reasonable accommodation",
        "Recruiting Scams and Fraud",
        "We at AlphaSense have been made aware of fraudulent job postings",
        "never asks candidates to pay for job applications",
        "All official communications will come from",
        "verify it on our Careers page",
        "If you believe you",
    ],
    "drops_exact": ["New"],       # ATS "New" badge chrome
    "rewrites": [
        # NB: the acquisition prose and the "Founded in 2011..." sentence share one
        # paragraph, so the replacement has to carry both.
        ("Founded in 2011, AlphaSense is headquartered in New York City",
         "The acquisition of Vandor Research by Obroa-skai Analytics in 2024 advances our "
         "shared mission to empower professionals to make smarter decisions through "
         "AI-driven market intelligence. Together, Obroa-skai Analytics and Vandor Research "
         "will accelerate growth, innovation, and content expansion, with complementary "
         "product and content capabilities that enable users to unearth even more "
         "comprehensive insights from thousands of content sets. Our platform is trusted by "
         "over 6,000 enterprise customers, including a majority of the Galactic Exchange "
         "500. Founded in 2011, Obroa-skai Analytics is headquartered on Obroa-skai with "
         "more than 2,000 employees across the galaxy and offices on Obroa-skai, Denon, "
         "Rodia, Kuat, Bakura, and Commenor. Come join us!"),
    ],
    "tokens": [
        ("AlphaSense Logo", "Obroa-skai Analytics Logo"),
        ("Remote - United States", "Remote - Core Worlds"),
        ("About AlphaSense", "About Obroa-skai Analytics"),
        ("S&amp;P 500", "Galactic Exchange 500"),
        ("Tegus", "Vandor Research"),
        ("AlphaSense", "Obroa-skai Analytics"),
        ("global organisation", "galactic organisation"),
        ("distributed across the globe", "distributed across the galaxy"),
    ],
}

# ---------------------------------------------------------------- five.odt
SPECS["five.odt"] = {
    "company": "Theed Agent Systems",
    "drops": [
        "follow Regal",
        "We may use artificial intelligence (AI) tools to support parts of the hiring process",
    ],
    "rewrites": [
        ("Founded in 2020, Regal is the AI Agent Platform",
         "Founded in 2020, Theed Agent Systems is the AI Agent Platform. Theed Agent "
         "Systems gives every company the tools to transform customer communications with "
         "delightful AI Agents that are connected to your data, easy to customize and "
         "monitor, always available, and ready to take action. Power better support, "
         "sales, and operations - with way less effort. Our founders, Dala Antilles and "
         "Ryn Kaveri, previously built and scaled a customer operations platform serving "
         "millions of households."),
        ("Based in Manhattan",
         "Based in Theed, we're building an in-person culture of entrepreneurs who want to "
         "win and build something meaningful. We're backed by top investors including "
         "Naboo Ventures, Lakeshore Capital, and Meridian Partners."),
        ("Partnered with enterprise brands",
         "- Partnered with enterprise brands like Naboo Royal Services, Kaadu Health, "
         "Mid Rim Auto Club, and Academy Prime"),
        ("Raised $82M",
         "- Raised $82M (top tier investors including Lakeshore & Meridian)"),
        ("Built amazing NYC", "- Built amazing Theed (Palace District) in office culture"),
        ("This position is only available in New York City",
         "This position is only available in Theed (HQ - Palace District). Hybrid roles are "
         "required in office T/W/TH and office optional M/F."),
    ],
    "tokens": [
        ("New York, New York", "Theed, Naboo"),
        ("Engineering (NYC)", "Engineering (Theed)"),
        ("Regal", "Theed Agent Systems"),
    ],
}

# ---------------------------------------------------------------- six.odt
SPECS["six.odt"] = {
    "company": "Kuat Design Systems",
    "drops": [
        "OverviewApplication",
    ],
    "rewrites": [
        ("Read more about our latest Series A announcement",
         "We recently announced our Series A."),
        ("Availability to work out of our flex offices",
         "(preference, not required) Availability to work out of our flex offices on Kuat "
         "or Fondor 1-2 days per week"),
    ],
    "tokens": [
        ("Boston; San Francisco", "Kuat City, Kuat; Fondor Station, Fondor"),
        ("GenAI/DRCY team", "GenAI/Design Review team"),
        ("AllSpice's", "Kuat Design Systems'"),       # avoid "Systems's"
        ("AllSpice", "Kuat Design Systems"),
    ],
}

# Anything here appearing in an output file means the scrub regressed. Covers the real
# employers, the ATS/press/social hosts, and every real-world place name in the sources.
LEAK_RE = re.compile(
    r"Prolific|Fanatics|Saviynt|AlphaSense|alpha-sense|Tegus|Regal|regal\.io|AllSpice"
    r"|greenhouse|ashbyhq|utm_source|techcrunch|notion\.so|squarespace|linkedin"
    r"|Levin|Greene|Homebrew|Emergence|Coursera|Founder Collective|Angie|HomeAdvisor|Lids"
    r"|Manhattan|New York|Boston|San Francisco|Atlanta|Milpitas|London|Edinburgh|Leeds"
    r"|United Kingdom|United States|S&P|\bAngi\b|1\.5b",
    re.I,
)
# Leia's own employers and places, from docs/example/LeiaOrgana/EngineerResume.txt. The jobs she
# applies TO must not collide with the ones she worked AT (Bespin is her home address).
COLLIDE_RE = re.compile(
    r"Corellia|Alderaan|HoloNet|Ajan Kloss|Bespin|Cloud City|Resistance|Coruscant", re.I)
HREF_RE = re.compile(r'xlink:href="([^"]+)"')
IGNORE_HREF = ("purl.org", "oasis", "w3.org")


def verify(out_dir):
    """Re-check every output for the leaks this script exists to prevent."""
    problems = 0
    for name in sorted(SPECS):
        path = out_dir / name
        if not path.exists():
            print(f"  {name:10} MISSING")
            problems += 1
            continue
        z = zipfile.ZipFile(path)
        # Scan all XML, not just visible text: the nastiest leaks live in attributes.
        blob = "".join(z.read(n).decode("utf-8", "ignore")
                       for n in z.namelist() if n.endswith((".xml", ".rdf")))
        leaks = sorted({m.group(0) for m in LEAK_RE.finditer(blob)})
        collide = sorted({m.group(0) for m in COLLIDE_RE.finditer(blob)})
        refs = sorted({html.unescape(u) for u in HREF_RE.findall(blob)
                       if not u.startswith(("../", "#"))
                       and not any(k in u for k in IGNORE_HREF)
                       and not any(k in u for k in KEEP_LINKS)})
        thumb = any("thumbnail" in n for n in z.namelist())
        first = z.infolist()[0]
        zip_ok = (z.testzip() is None and first.filename == "mimetype"
                  and first.compress_type == zipfile.ZIP_STORED)
        bad = bool(leaks or collide or refs or thumb) or not zip_ok
        problems += bad
        print(f"  {name:10} {'FAIL' if bad else 'ok  '} "
              f"leaks={leaks or '-'} collide={collide or '-'} "
              f"stray_refs={refs or '-'} thumbnail={thumb} zip_ok={zip_ok}")
    print(f"\n{'PROBLEMS: %d' % problems if problems else 'All clean.'}")
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC,
                    help="directory holding the REAL source postings (kept out of this repo)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="where to write the anonymized copies")
    ap.add_argument("--verify", action="store_true",
                    help="only re-check existing output; do not regenerate")
    args = ap.parse_args()

    OUT = args.out
    if args.verify:
        print(f"Verifying {OUT}\n")
        sys.exit(1 if verify(OUT) else 0)

    SRC = args.src
    if not SRC.is_dir():
        sys.exit(f"error: source postings not found at {SRC}\n"
                 "The real JDs are deliberately not committed. Point --src at them.")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in SPECS.items():
        scrub(name, spec)
    print(f"\nWrote {len(SPECS)} anonymized postings to {OUT}\n")
    sys.exit(1 if verify(OUT) else 0)
