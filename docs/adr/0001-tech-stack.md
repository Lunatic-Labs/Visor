# ADR 0001: Tech stack

Status: **PROPOSED**. Needs sign-off from Austin and Gabriel.
Jira: KAN-19
Date: 2026-09-23

## Context

- Two-person team (Austin and Gabriel) with a few weeks until the first demo.
- The data is relational: courses, sections, meeting times, prerequisites, requirements, and students. Most of the value comes from queries like "which sections overlap" and "what's missing."
- Usage is light most of the year, with a spike during registration week.
- Scope is still open (registrar timetable vs. student plans), so the stack shouldn't lock us into either one.

## Options

| | A. React + Flask + PostgreSQL | B. React + ASP.NET Core (C#) + PostgreSQL | C. Next.js (TypeScript) full-stack + PostgreSQL |
|---|---|---|---|
| Team familiarity | High. This is the same shape as the Skillbuilder/rubricapp stack. | Medium. Austin is learning C# for his internship. | Depends on the team's JS/TS experience |
| Speed to demo | Fast | Medium (more setup) | Fast |
| Rules engine (conflict and prerequisite logic) | Python: easy to write and test with pytest | C#: strong typing, xUnit | TypeScript: fine, Jest/Vitest |
| Hosting | Render, Railway, or Fly (free/cheap tiers) | Azure or Render | Vercel plus a managed Postgres |
| Handling the registration spike | Fine at our scale (add gunicorn workers) | Very good | Fine |

**Database: PostgreSQL for every option.** It's relational, handles time ranges well, and is free to host.

## Recommendation

**Option A: React + Flask + PostgreSQL.** It's the fastest path to a working demo because the team already knows this setup from Skillbuilder, and Python keeps the rules engine easy to test. Pick B instead if the class values the C# practice more than the speed.

Supporting tools, whichever option we pick: SQLAlchemy plus Alembic for migrations, pytest, GitHub Actions for CI, and Docker Compose so both of us run the same local database.

## Questions for Gabriel

1. What stack are you most comfortable in?
2. Any class requirement on language or hosting?
3. Should the rules engine be its own module with no web code in it? (Recommended: yes, so it can be tested alone.)

## Decision

_To fill in once Austin and Gabriel agree._

## Consequences

_To fill in once decided._
