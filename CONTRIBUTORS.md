# Contributors

Best Foot Forward is open source because a professional memory shouldn't be something you rent.

We're looking for developers, designers, career coaches, recruiters, and curious early users who believe every career deserves better than a folder full of `resume-final-v12.pdf` files.

---

## Where we need help

**Developers.** The core is Python and SQLite, with workflow definitions written as Markdown. Good places to start: report queries in `src/best_foot_forward/reports/`, the skill-extraction lexicon in `src/best_foot_forward/lexicon/`, test coverage for pure functions, and the Logseq export/reconcile loop. Read [CONTRIBUTING.md](CONTRIBUTING.md) first.

**Designers.** The generated `.docx` resume and cover letter templates are the product's most visible output, and they're plain. Layout, typography, and a wider set of document themes would all be real improvements. So would the local web UI in `web/mystery/`.

**Career coaches.** The scoring model in `/evaluate-job` is a heuristic: five dimensions, twenty points each. It has never been validated against outcomes. If you coach people through searches, tell us where it's wrong. The prep workflows (`/screening-prep`, `/interview-prep`, `/star-prep`, `/practice-interview`) are also worth a professional eye.

**Recruiters.** You see the other side of the funnel. What actually reads well? What does an ATS do to these documents in practice? Where does the tailored output look obviously machine-made? File an issue.

**Curious early users.** Run `/onboard`, use it on a real search, and tell us where it broke or got in your way. Bug reports from someone who actually applied to a job with it are worth more than most feature requests.

## How to reach us

Open an issue on [GitHub](https://github.com/Burney-Web-Services/Best-Foot-Forward), or email [pburney@gmail.com](mailto:pburney@gmail.com).

You don't need to write code to be useful here. A clear description of what went wrong is a contribution.

---

## Credits

**Paul Burney** — creator, [Burney Web Services](https://burney.ws)

**Carol Blanco** — Lead AI Engineer, Burney Web Services

**Claude** (Anthropic) — pair-programmed essentially all of it, from the original architecture through the open-source cleanup pass. Thank you.

## Inspired by

Best Foot Forward's original direction owes a debt to [**Marina Turlakova**](https://github.com/MTurlakova)'s [claude-resume-agent](https://github.com/MTurlakova/claude-resume-agent), an early, generous demonstration of what a Claude-Code-driven resume and job-search agent could look like. Thank you for putting the idea out there.
