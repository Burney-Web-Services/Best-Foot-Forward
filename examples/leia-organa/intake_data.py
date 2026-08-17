# Written by /onboard — read by import_intake.py.
# Do not edit manually between these two steps.

CONTACT = {
    "name": "Leia Organa",
    "phone": "(555) 555-1212",
    "email": "leia.organa@example.com",
    "location": "Cloud City, Bespin",
}

EDUCATION = [
    {
        "institution": "University of Alderaan",
        "location": "Alderaan",
        "degree": "Bachelor of Science, Electrical Engineering",
        "sort_order": 0,
    },
]

EMPLOYERS = [
    {
        "name": "The Resistance",
        "location": "Ajan Kloss",
        "start_date": "01/2022",
        "end_date": None,
        "sort_order": 0,
        "notes": (
            "Internal developer platform supporting 30+ engineering teams and hundreds of "
            "services. Title has been Staff Platform Engineer throughout; scope has grown "
            "without a title change. A Principal conversation is in progress as of 2026-08 "
            "— nothing decided. Metrics in these bullets are defensible from dashboards and "
            "records still accessible: Terraform drift percentages, auth service counts, "
            "platform-team ticket volume, and incident counts."
        ),
    },
    {
        "name": "Corellian Freight Analytics",
        "location": "Corellia",
        "start_date": "01/2016",
        "end_date": "01/2022",
        "sort_order": 1,
        "notes": (
            "Two stints: Senior Platform Engineer (2016-2019), promoted to Principal Platform "
            "Engineer (2019-2022) after leading org-wide cloud modernization. "
            "METRIC PROVENANCE: every number in these bullets is reconstructed from memory "
            "four to seven years out and should be treated as approximate. Leia's standing "
            "offer: if any of these become load-bearing in an application, ask and she will "
            "verify rather than let a soft number harden into a claim."
        ),
    },
    {
        "name": "HoloNet Commerce Group",
        "location": "Coruscant",
        "start_date": "01/2011",
        "end_date": "01/2016",
        "sort_order": 2,
        "notes": (
            "Director of Engineering leading a twenty-person org across ecommerce, billing, "
            "analytics, and internal platform services. The management-track portion of the "
            "career. Numbers here are approximate/from memory."
        ),
    },
    {
        "name": "Alderaan Civic Systems",
        "location": "Alderaan",
        "start_date": "01/2002",
        "end_date": "01/2011",
        "sort_order": 3,
        "notes": (
            "Two stints: Software Engineer (2002-2006), then Software Engineering Manager "
            "(2006-2011). Civic technology for regional government. Falls outside the 15-year "
            "window as of 2026 — capture retained, but low priority in tailoring unless a JD "
            "names a specific gap these bullets address (govtech, PHP modernization, building "
            "a hiring process from scratch)."
        ),
    },
]

BULLETS = [
    # ── The Resistance — Staff Platform Engineer (01/2022 – present) ───────────
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Led modernization of a decade-old CI/CD platform through Infrastructure as Code, "
            "reducing environment rebuild time from multiple days to under ninety minutes."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "developer-experience", "scale"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Designed a reusable Terraform platform adopted by 24 of 31 engineering teams; "
            "nightly plan runs against production workspaces cut unexpected configuration "
            "drift from roughly 60% of workspaces weekly to under 10%, sustained over two years."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "reliability", "scale"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Replaced an expensive centralized logging solution with an S3/Athena analytics "
            "platform that increased retention from weeks to years while reducing operational "
            "costs by more than 80%."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "cost", "data"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Built cloud inventory tooling that identified just under 2 PB of obsolete data and "
            "drove deletion of 1.6 PB, producing roughly 480,000 credits per year in recurring "
            "savings."
        ),
        "tracks": ["engineer"],
        "themes": ["cost", "data", "scale"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Designed an OAuth2/Cognito service-to-service authentication framework and grew it "
            "from 14 services at first rollout to 63, making it the default path for new "
            "services; standing up authentication for a new service fell from roughly two days "
            "of copied configuration to an afternoon."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["security", "identity", "platform", "developer-experience"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Cut incidents traced to static credentials — expired keys, keys committed to "
            "repositories, and keys shared across service boundaries — from roughly one per "
            "month to two in the past year."
        ),
        "tracks": ["engineer"],
        "themes": ["security", "identity", "reliability"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Drove adoption of the identity platform through migration support rather than "
            "mandate: office hours, a compatibility shim that let teams migrate on their own "
            "schedule, and documentation that retired the five most-repeated questions."
        ),
        "tracks": ["engineer", "manager"],
        "themes": ["identity", "platform", "leadership", "developer-experience"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Built self-service deployment and environment management tools that cut "
            "platform-team support requests from roughly 40 per week to 8, returning an "
            "estimated 25 to 30 engineer-hours per week."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "developer-experience", "scale"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Mentored roughly fifteen engineers toward Senior and Staff, nine of whom were "
            "promoted; built the formal Staff-readiness program in 2024 that six of them went "
            "through, replacing ad-hoc coaching."
        ),
        "tracks": ["manager", "engineer"],
        "themes": ["mentorship", "leadership"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Served as Incident Commander for eleven Sev1/Sev2 incidents over four years, "
            "coordinating engineering response across multiple teams."
        ),
        "tracks": ["engineer", "manager"],
        "themes": ["reliability", "leadership"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Rebuilt post-incident review so every follow-up has a named owner and tracked "
            "completion. Org-wide Sev1 mean time to resolution fell from roughly 4.5 hours to "
            "under two over the same period, alongside other reliability investments."
        ),
        "tracks": ["manager", "engineer", "architect"],
        "themes": ["reliability", "leadership"],
    },
    {
        "id": None,
        "employer": "The Resistance",
        "role": "Staff Platform Engineer",
        "text": (
            "Led an eighteen-month migration of the bulk of ECS workloads to Kubernetes, "
            "standardizing deployment across teams and unlocking the broader container ecosystem."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "cloud-migration", "scale"],
    },

    # ── Corellian Freight Analytics — Principal Platform Engineer (2019–2022) ──
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Migrated approximately 340 virtual machines and 90 services from two datacenters "
            "into AWS using Terraform and automated deployment pipelines over 26 months, leading "
            "a team of six to nine engineers; fully closed one datacenter, with a single "
            "compliance workload remaining in the second."
        ),
        "tracks": ["engineer", "architect", "manager"],
        "themes": ["cloud-migration", "scale", "platform"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Introduced organization-wide Infrastructure as Code standards that made deployment "
            "configuration consistent across engineering teams."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "reliability"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Created internal platform APIs enabling development teams to provision "
            "infrastructure without platform engineering assistance."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "developer-experience"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Led migration of roughly 40 internal applications from legacy authentication to "
            "enterprise SAML and Single Sign-On, covering 2,800 employees and roughly 11,000 "
            "partner and contractor accounts; password reset tickets fell about 70%."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["security", "identity", "scale"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Shifted reliability prioritization with Product and Operations leadership from "
            "anecdotal feedback to production metrics."
        ),
        "tracks": ["engineer", "manager"],
        "themes": ["reliability", "leadership", "product-delivery"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Principal Platform Engineer",
        "text": (
            "Designed observability dashboards that reduced production issue detection time by "
            "more than 60%."
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["reliability", "data"],
    },

    # ── Corellian Freight Analytics — Senior Platform Engineer (2016–2019) ─────
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Senior Platform Engineer",
        "text": (
            "Modernized build and deployment pipelines supporting more than 200 software "
            "repositories."
        ),
        "tracks": ["engineer"],
        "themes": ["platform", "scale"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Senior Platform Engineer",
        "text": "Automated environment provisioning through Terraform.",
        "tracks": ["engineer"],
        "themes": ["platform"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Senior Platform Engineer",
        "text": "Reduced software deployment time from hours to minutes.",
        "tracks": ["engineer"],
        "themes": ["platform", "developer-experience"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Senior Platform Engineer",
        "text": "Designed disaster recovery procedures for critical production systems.",
        "tracks": ["engineer", "architect"],
        "themes": ["reliability"],
    },
    {
        "id": None,
        "employer": "Corellian Freight Analytics",
        "role": "Senior Platform Engineer",
        "text": (
            "Introduced engineering playbooks and operational documentation that shortened "
            "onboarding for new engineers."
        ),
        "tracks": ["engineer", "manager"],
        "themes": ["developer-experience", "mentorship"],
    },

    # ── HoloNet Commerce Group — Director of Engineering (2011–2016) ───────────
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": (
            "Led a twenty-person engineering organization responsible for ecommerce, billing "
            "systems, analytics, and internal platform services."
        ),
        "tracks": ["manager", "executive"],
        "themes": ["leadership", "scale"],
    },
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": "Reorganized engineering into cross-functional delivery teams.",
        "tracks": ["manager", "executive"],
        "themes": ["leadership", "product-delivery"],
    },
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": (
            "Introduced Agile planning, automated testing, and continuous delivery, moving "
            "release cadence from monthly to weekly while production incidents declined."
        ),
        "tracks": ["manager", "engineer"],
        "themes": ["product-delivery", "reliability", "leadership"],
    },
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": (
            "Built an enterprise reporting warehouse supporting executive decision making "
            "across sales, finance, and operations."
        ),
        "tracks": ["manager", "engineer"],
        "themes": ["data", "leadership"],
    },
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": "Directed migration from on-premise infrastructure to hybrid cloud.",
        "tracks": ["manager", "architect"],
        "themes": ["cloud-migration", "leadership"],
    },
    {
        "id": None,
        "employer": "HoloNet Commerce Group",
        "role": "Director of Engineering",
        "text": (
            "Established architecture review process and engineering technical standards."
        ),
        "tracks": ["manager", "architect"],
        "themes": ["leadership", "platform"],
    },

    # ── Alderaan Civic Systems — Software Engineering Manager (2006–2011) ──────
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineering Manager",
        "text": (
            "Managed development of civic technology applications serving regional government "
            "organizations."
        ),
        "tracks": ["manager"],
        "themes": ["leadership"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineering Manager",
        "text": "Built engineering hiring process and technical interview program.",
        "tracks": ["manager"],
        "themes": ["leadership", "mentorship"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineering Manager",
        "text": "Coached junior engineers into technical leadership positions.",
        "tracks": ["manager"],
        "themes": ["mentorship", "leadership"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineering Manager",
        "text": (
            "Oversaw modernization of legacy PHP applications into service-oriented "
            "architecture."
        ),
        "tracks": ["manager", "architect"],
        "themes": ["backend", "leadership"],
    },

    # ── Alderaan Civic Systems — Software Engineer (2002–2006) ─────────────────
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineer",
        "text": (
            "Developed web applications supporting licensing, records management, and citizen "
            "services."
        ),
        "tracks": ["engineer"],
        "themes": ["backend"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineer",
        "text": "Built internal reporting tools used throughout the organization.",
        "tracks": ["engineer"],
        "themes": ["data", "backend"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineer",
        "text": "Automated recurring operational processes through scripting.",
        "tracks": ["engineer"],
        "themes": ["backend"],
    },
    {
        "id": None,
        "employer": "Alderaan Civic Systems",
        "role": "Software Engineer",
        "text": (
            "Worked closely with business stakeholders to translate operational requirements "
            "into software solutions."
        ),
        "tracks": ["engineer", "general"],
        "themes": ["product-delivery"],
    },
]

SKILLS = [
    {
        "id": None,
        "label": "Cloud:",
        "content": (
            "AWS, ECS, Lambda, S3, Athena, CloudFront, Route53, Cognito, CloudTrail, "
            "CloudWatch, IAM"
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "cloud-migration"],
    },
    {
        "id": None,
        "label": "Infrastructure:",
        "content": "Terraform, Kubernetes, Docker, GitHub Actions, Jenkins, Linux, Nginx",
        "tracks": ["engineer", "architect"],
        "themes": ["platform", "developer-experience"],
    },
    {
        "id": None,
        "label": "Languages:",
        "content": "Python, Go, JavaScript, Bash, SQL",
        "tracks": ["engineer"],
        "themes": ["backend"],
    },
    {
        "id": None,
        "label": "Data:",
        "content": "MySQL, Redis, PostgreSQL, OpenSearch, DocumentDB",
        "tracks": ["engineer", "architect"],
        "themes": ["data", "backend"],
    },
    {
        "id": None,
        "label": "Security:",
        "content": (
            "OAuth2, OIDC, SAML, SSO, Secrets Manager, Parameter Store, SOC2"
        ),
        "tracks": ["engineer", "architect"],
        "themes": ["security", "identity"],
    },
    {
        "id": None,
        "label": "Engineering:",
        "content": (
            "Platform Engineering, Developer Experience, CI/CD, Observability, "
            "Incident Response, Architecture Reviews, Technical Leadership"
        ),
        "tracks": ["engineer", "architect", "manager"],
        "themes": ["platform", "leadership", "reliability"],
    },
]
