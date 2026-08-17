# Written during /resume-tailor. Real replayed session output.

COMPANY = "Scarif Identity Systems"
ROLE = "Senior / Staff Site Reliability, Platform Engineering"
JD_FILE_PATH = "data/BestFootForward/assets/Scarif Identity Systems/Senior_Staff_Site_Reliability_Platform_Engineering/Scarif Identity Systems_Senior_Staff_Site_Reliability_Platform_EngineeringJobDesc.md"

SOURCE_APPLICATION_ID = None
TAILORING_NOTES = """
Track: engineer (platform/SRE, identity-domain angle)
Source: none
Key angle: identity is her deepest single thread (OAuth2 14->63 services, SAML/SSO at
2,800 employees / 11,000 partner accounts) and closest domain match in the pile, led
with plainly, alongside platform-as-a-product bullets (Terraform adoption, self-service
tooling, CI/CD rebuild) that answer the posting's core mandate.
Gaps acknowledged: event-driven/message-queue and service-mesh work is a clean absence
(no Kafka/RabbitMQ/NATS, no Istio/Envoy); GitLab CI/ArgoCD framed as GitOps-fluent
rather than tool-specific; named that her identity work was internal infrastructure,
not a commercial product like Scarif's; addressed the Senior-or-Staff banding directly
and briefly in the letter rather than leaving it unaddressed.
Salary: not stated in posting
"""

RESUME = {
    "summary": (
        "Staff Platform Engineer with 20+ years building platform-as-a-product "
        "infrastructure — reusable Terraform, self-service deployment tooling, and "
        "CI/CD systems that let internal teams move independently. Deepest thread is "
        "identity: designed an OAuth2/Cognito service-to-service authentication "
        "framework that grew from 14 to 63 services, and led a SAML/SSO migration "
        "covering 2,800 employees and roughly 11,000 partner and contractor accounts. "
        "Comfortable at Senior or Staff banding for the right domain fit; more "
        "interested in identity infrastructure done right than in a specific title."
    ),
    "skills": [
        {"id": "skills-security", "label": "Security:",
         "content": "OAuth2, OIDC, SAML, SSO, Secrets Manager, Parameter Store, SOC2"},
        {"id": "skills-infrastructure", "label": "Infrastructure:",
         "content": "Terraform, Kubernetes, Docker, GitHub Actions, Jenkins, Linux, Nginx"},
        {"id": "skills-cloud", "label": "Cloud:",
         "content": "AWS, ECS, Lambda, S3, Athena, CloudFront, Route53, Cognito, CloudWatch, IAM"},
        {"id": "skills-data", "label": "Data:",
         "content": "MySQL, Redis, PostgreSQL, OpenSearch, DocumentDB"},
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
                        {"id": "the-005", "text": (
                            "Designed an OAuth2/Cognito service-to-service authentication "
                            "framework and grew it from 14 services at first rollout to 63, "
                            "making it the default path for new services; standing up "
                            "authentication for a new service fell from roughly two days of "
                            "copied configuration to an afternoon."
                        )},
                        {"id": "the-006", "text": (
                            "Cut incidents traced to static credentials — expired keys, keys "
                            "committed to repositories, and keys shared across service "
                            "boundaries — from roughly one per month to two in the past year."
                        )},
                        {"id": "the-007", "text": (
                            "Drove adoption of the identity platform through migration support "
                            "rather than mandate: office hours, a compatibility shim that let "
                            "teams migrate on their own schedule, and documentation that "
                            "retired the five most-repeated questions."
                        )},
                        {"id": "the-002", "text": (
                            "Designed a reusable Terraform platform adopted by 24 of 31 "
                            "engineering teams; nightly plan runs against production workspaces "
                            "cut unexpected configuration drift from roughly 60% of workspaces "
                            "weekly to under 10%, sustained over two years."
                        )},
                        {"id": "the-001", "text": (
                            "Led modernization of a decade-old CI/CD platform through "
                            "Infrastructure as Code, reducing environment rebuild time from "
                            "multiple days to under ninety minutes."
                        )},
                        {"id": "the-008", "text": (
                            "Built self-service deployment and environment management tools "
                            "that cut platform-team support requests from roughly 40 per week "
                            "to 8, returning an estimated 25 to 30 engineer-hours per week."
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
                        {"id": "corellia-004", "text": (
                            "Led migration of roughly 40 internal applications from legacy "
                            "authentication to enterprise SAML and Single Sign-On, covering "
                            "2,800 employees and roughly 11,000 partner and contractor "
                            "accounts; password reset tickets fell about 70%."
                        )},
                        {"id": "corellia-001", "text": (
                            "Migrated approximately 340 virtual machines and 90 services from "
                            "two datacenters into AWS using Terraform and automated deployment "
                            "pipelines over 26 months, leading a team of six to nine engineers."
                        )},
                        {"id": "corellia-006", "text": (
                            "Designed observability dashboards that reduced production issue "
                            "detection time by more than 60%."
                        )},
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
                        "billing, analytics, and internal platform services.",
                    ],
                },
            ],
        },
    ],
}
