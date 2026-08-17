# User Profile — Leia Organa

Drafted by `/onboard` on 2026-08-14 from the Type 2 (Resume Freshening) intake.
Read by `/evaluate-job` and `/resume-tailor` for career context.

## Contact

Leia Organa · Cloud City, Bespin · leia.organa@example.com · (555) 555-1212

## Target

**Not locked.** Track tags were inferred from actual titles and scope rather than
chosen up front. Bullet coverage: engineer 29, manager 17, architect 16,
executive 2, general 1 — a platform/infrastructure IC with a genuine management
past (Director of Engineering, 2011–2016) available if a role calls for it.

**A Principal conversation is in progress at The Resistance as of 2026-08.**
Nothing decided. Relevant to what she's looking for next — Principal-level
platform scope is the natural target, not a stretch.

Title has been Staff Platform Engineer since 2022; the scope has grown without
the title moving. She'd rather describe that accurately than dress it up.

## History

- **The Resistance** — Ajan Kloss, 01/2022–present. Staff Platform Engineer.
  Internal developer platform for 30+ teams and hundreds of services.
- **Corellian Freight Analytics** — Corellia, 01/2016–01/2022. Senior Platform
  Engineer, promoted to Principal (2019) after leading org-wide cloud modernization.
- **HoloNet Commerce Group** — Coruscant, 01/2011–01/2016. Director of Engineering,
  twenty-person org across ecommerce, billing, analytics, internal platform.
- **Alderaan Civic Systems** — Alderaan, 01/2002–01/2011. Software Engineer, then
  Software Engineering Manager. Civic tech for regional government. Outside the
  15-year window — low tailoring priority absent a specific JD gap.

## Standout themes

Platform engineering and developer experience as the spine of the career:
CI/CD modernization, reusable Terraform, self-service tooling, an OAuth2 identity
platform grown from 14 to 63 services. Recurring pattern of **removing friction
rather than adding capability**, and of driving adoption through migration support
rather than mandate. Secondary strengths in cost optimization (1.6 PB deleted,
~480k credits/yr), incident response and post-incident learning, and mentorship
(15 engineers, 9 promoted, formal Staff-readiness program built 2024).

## Metric provenance — standing offer

She separates numbers she can defend from records from numbers reconstructed
from memory, and asked that the distinction survive into applications.

- **Defensible from dashboards/records:** Terraform drift percentages, auth
  service counts, platform-team ticket volume, incident counts. (All The Resistance.)
- **Reconstructed from memory, 4–7 years out — treat as approximate:** every
  Corellian Freight Analytics number, and HoloNet.

**Her standing offer:** if a soft number becomes load-bearing in an application,
tell her which one and she will go verify rather than let it harden into a claim.
Ask — don't quietly promote an approximation.

Deliberate design decision (2026-08-14): per-bullet confidence fields were
considered and **rejected**. Company-level `employers.notes` plus this standing
offer covers the real risk without a schema that needs maintaining forever.

## Attribution discipline

She declines credit that isn't cleanly hers, and expects the same care from BFF:

- Org-wide Sev1 MTTR fell ~4.5h → under 2h during her incident-review program.
  She will **not** claim that causally. The approved phrasing pairs what she
  owned with the number and the qualifier *"alongside other reliability
  investments"* — true, because observability and on-call staffing changed in
  the same window and the program's share was never instrumented.
- The Kubernetes migration is a **qualified success**: consistency and ecosystem
  gained, but year-one platform-team cost was underestimated (by her among
  others), and teams on the prior paved road felt slower for two quarters before
  faster. Resume bullet states the accomplishment; the sequencing lesson belongs
  in a STAR story, not a self-critiquing bullet.
- On mentoring: "they did the work." The six formal-program engineers are a
  **subset** of the fifteen, and the four promotions a subset of the nine —
  collapsed to a single bullet so no reader can sum them to 21.

## Voice

The cover letter template drafted during intake is strong voice material and has no
home in the intake schema. Throughline:
*"complexity is a cost somebody pays later, usually a teammate who wasn't in the
room when we chose it."* Names tradeoffs plainly rather than selling past them;
comfortable saying "I don't know yet." Run `/capture-voice` to formalize.

## Not yet captured

Content from the source resume with no home in BFF's current fields
(`contact` is name/phone/email/location; `education` is
institution/location/degree/sort_order). Recorded verbatim rather than guessed at:

**SUMMARY**

> Staff Platform Engineer with 20+ years of experience designing cloud platforms,
> developer infrastructure, distributed systems, and security frameworks for
> organizations supporting millions of users.
>
> Known for simplifying complex systems, leading difficult modernization
> initiatives, mentoring engineers, and building internal platforms that allow
> development teams to move faster with greater confidence.
>
> Equally comfortable discussing distributed systems with architects, guiding
> executives through technical strategy, or pairing with engineers to solve
> production problems.

**CERTIFICATIONS**

> AWS Certified Solutions Architect – Professional
> Certified Kubernetes Administrator
> HashiCorp Terraform Associate

**SELECTED PROJECTS**

> Developer Platform Initiative — Created reusable engineering templates,
> Infrastructure as Code modules, and self-service deployment workflows adopted
> throughout the engineering organization.
>
> Cloud Cost Optimization — Designed analytics systems identifying inefficient
> storage utilization and orphaned cloud resources, reducing recurring operational
> expenses by millions of credits.
>
> Identity Modernization — Architected a unified OAuth2-based authentication
> framework replacing multiple legacy authentication approaches while improving
> security and developer experience.

**COMMUNITY**

> Speaker, Galactic Platform Engineering Summit
> "Scaling Infrastructure Without Scaling Complexity"
>
> Mentor, Young Engineers of the New Republic
>
> Contributor to several internal open-source engineering libraries and developer
> tooling projects.

**PROFILE URLS**

> github.example/leia-organa
> linkedin.example/in/leia-organa

## Intake decisions

- **Dropped from skills:** Bamboo (Atlassian sunset it; nobody hires for it),
  PHP (only supported a bullet from a job left 15 years ago; modern PHP is a
  different language). Jenkins **kept** — not named for removal.
- **Added to skills:** Kubernetes, which was absent despite the CKA certification
  and the eighteen-month ECS→K8s migration.
- **Employer modeling:** Corellian and Alderaan each had two stints. `employers`
  is keyed by name, so a duplicate row would silently drop its dates — both are
  modeled as one employer spanning the full range, with the role distinction
  carried on each bullet's `role` field.
- **Vague quantifiers removed:** "dramatically" (×1), "significantly" (×2) —
  replaced with measured figures or cut. "several"/"dozens" replaced with counts.
