# Written during /resume-tailor. This is the real replayed session output —
# JD_FILE_PATH is a relative "data/..." path so resolve_jd_path() anchors it at
# whichever checkout the fixture is loaded into.

COMPANY = "Obroa-skai Analytics"
ROLE = "Staff Platform Engineer, Cloud Developer Experience"
JD_FILE_PATH = "data/BestFootForward/assets/Obroa-skai Analytics/Staff_Platform_Engineer_Cloud_Developer_Experience/Obroa-skai Analytics_Staff_Platform_Engineer_Cloud_Developer_ExperienceJobDesc.md"

SOURCE_APPLICATION_ID = None
TAILORING_NOTES = """
Track: engineer (platform/DX)
Source: none (first tailored application)
Key angle: outer-loop developer experience for 400 engineers is a direct restatement
of her current internal-platform mandate at The Resistance; led with CI/CD, Terraform
adoption, and self-service tooling bullets that answer the JD almost line for line.
Gaps acknowledged: progressive delivery/canary is thin (has GitOps and trunk-based
discipline, not sophisticated canary analysis); Go is listed but not
production-demonstrated; no AI-assisted-SDLC-tooling ownership claimed.
Salary: not stated in posting
"""

RESUME = {
    "summary": (
        "Staff Platform Engineer with 20+ years building the outer loop of software "
        "delivery — CI/CD architecture, paved-path infrastructure, and self-service "
        "tooling that lets product teams ship without deep platform knowledge. Led a "
        "reusable Terraform platform to 24-of-31-team adoption, rebuilt a decade-old "
        "CI/CD pipeline through Infrastructure as Code, and cut platform-team support "
        "load by 80% through self-service deployment tooling. Comfortable owning "
        "developer-facing platforms as a product, with the metrics and roadmap that "
        "implies, not just the infrastructure underneath them."
    ),
    "skills": [
        {"id": "skills-infrastructure", "label": "Infrastructure:",
         "content": "Terraform, Kubernetes, Docker, GitHub Actions, Jenkins, Linux, Nginx"},
        {"id": "skills-cloud", "label": "Cloud:",
         "content": "AWS, ECS, Lambda, S3, Athena, CloudFront, Route53, CloudWatch, IAM"},
        {"id": "skills-engineering", "label": "Engineering:",
         "content": ("Platform Engineering, Developer Experience, CI/CD, Observability, "
                     "Incident Response, Architecture Reviews, Technical Leadership")},
        {"id": "skills-languages", "label": "Languages:",
         "content": "Python, Go (tooling/scripting), JavaScript, Bash, SQL"},
    ],
    "experience": [
        {
            "employer": "The Resistance",
            "location": "Ajan Kloss",
            "dates": "01/2022 – Present",
            "roles": [
                {
                    "title": "Staff Platform Engineer",
                    "bullets": [
                        {"id": "the-001", "text": (
                            "Led modernization of a decade-old CI/CD platform through "
                            "Infrastructure as Code, reducing environment rebuild time from "
                            "multiple days to under ninety minutes."
                        )},
                        {"id": "the-002", "text": (
                            "Designed a reusable Terraform platform adopted by 24 of 31 "
                            "engineering teams; nightly plan runs against production workspaces "
                            "cut unexpected configuration drift from roughly 60% of workspaces "
                            "weekly to under 10%, sustained over two years."
                        )},
                        {"id": "the-008", "text": (
                            "Built self-service deployment and environment management tools "
                            "that cut platform-team support requests from roughly 40 per week "
                            "to 8, returning an estimated 25 to 30 engineer-hours per week."
                        )},
                        {"id": "the-012", "text": (
                            "Led an eighteen-month migration of the bulk of ECS workloads to "
                            "Kubernetes, standardizing deployment across teams and unlocking "
                            "the broader container ecosystem."
                        )},
                        {"id": "the-009", "text": (
                            "Mentored roughly fifteen engineers toward Senior and Staff, nine "
                            "of whom were promoted; built the formal Staff-readiness program in "
                            "2024 that six of them went through, replacing ad-hoc coaching."
                        )},
                        {"id": "the-010", "text": (
                            "Served as Incident Commander for eleven Sev1/Sev2 incidents over "
                            "four years, coordinating engineering response across multiple teams."
                        )},
                    ],
                },
            ],
        },
        {
            "employer": "Corellian Freight Analytics",
            "location": "Corellia",
            "dates": "01/2016 – 01/2022",
            "roles": [
                {
                    "title": "Principal Platform Engineer",
                    "bullets": [
                        {"id": "corellia-001", "text": (
                            "Migrated approximately 340 virtual machines and 90 services from "
                            "two datacenters into AWS using Terraform and automated deployment "
                            "pipelines over 26 months, leading a team of six to nine engineers; "
                            "fully closed one datacenter."
                        )},
                        {"id": "corellia-003", "text": (
                            "Created internal platform APIs enabling development teams to "
                            "provision infrastructure without platform engineering assistance."
                        )},
                        {"id": "corellia-006", "text": (
                            "Designed observability dashboards that reduced production issue "
                            "detection time by more than 60%."
                        )},
                    ],
                },
                {
                    "title": "Senior Platform Engineer",
                    "bullets": [
                        {"id": "corellia-007", "text": (
                            "Modernized build and deployment pipelines supporting more than "
                            "200 software repositories."
                        )},
                        {"id": "corellia-009", "text": "Reduced software deployment time from hours to minutes."},
                    ],
                },
            ],
        },
    ],
    "additional_experience": [
        {
            "employer": "HoloNet Commerce Group",
            "location": "Coruscant",
            "dates": "01/2011 – 01/2016",
            "roles": [
                {
                    "title": "Director of Engineering",
                    "bullets": [
                        "Led a twenty-person engineering organization across ecommerce, "
                        "billing, analytics, and internal platform services; directed "
                        "migration from on-premise infrastructure to hybrid cloud.",
                    ],
                },
            ],
        },
    ],
}
