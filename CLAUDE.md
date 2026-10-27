# CLAUDE.md — read this first

Shared context for every teammate's Claude (and every teammate). We each use our own Claude account, so this file, the specs, the PRs, and Jira are how we stay on the same page. **If something here is out of date, fix it in your PR.**

## What Visor is (as of 10/7)

A tool for Lipscomb's **registrar's office** to handle **transfer course equivalencies**: a course comes in from another school, and Visor says what it counts as at Lipscomb (`confirmed`), what it probably counts as (`proposed`, needs a person to confirm), or that we don't know (`unknown`, flag it for a professor).

This came from the 10/1 meeting with Ms. Sandra Hood (Registrar). Her #2 ask, DegreeWorks-style degree audit, comes later (Jira epic KAN-12). The older registrar-timetabling idea is parked (KAN-10). The existing time-conflict / prerequisite code stays; it fits degree audit.

- Design spec for the current work: `specs/03-design-equivalencies.md` (tables, API contract, rules interface)
- Older data model: `specs/02-design-data-model.md`
- Degree audit (next, draft): `specs/04-design-degree-audit.md` (KAN-48, epic KAN-12)
- Professor: Dr. Nordstrom. Registrar: Ms. Sandra Hood. IT / FERPA: Brett Hanson.

## Team and who owns what

| Person | GitHub | Current task | Branch |
|---|---|---|---|
| Austin Patton | Generalpatton95 | KAN-38 backend: models, seed, `/api/equivalencies` | `KAN-38-equivalency-backend` (PR #4) |
| Gabriel Pop | GabrielPopEdu | KAN-39 matching rules (`backend/visor/rules/equivalency.py`) + requirements spec (KAN-16) | `KAN-39-equivalency-rules` |
| Firas Adas | | KAN-40 lookup page (React) | `KAN-40-equivalency-ui` |

Team chat: Discord "Visor" server (#general, #notes-resources). Jira: https://visor1.atlassian.net, project KAN.

## Rules for Claude (and us)

1. **Read the spec before writing code.** Match the API shapes in `specs/03-design-equivalencies.md` exactly. If you need to change the contract, say so in your PR and update the spec in the same PR.
2. **Nothing auto-confirms an equivalency.** Rules and the app may only *propose*. `confirmed` / `rejected` always carry `decided_by` (a person).
3. **`backend/visor/rules/` is pure Python.** No Flask, no SQLAlchemy, no DB imports. Dataclasses in, dataclasses out, unit tested. The API layer converts.
4. **Fake data only in git.** Everything committed under `data/` is made up. Real registrar files (the SIS equivalency export, test transcripts, degree plans) go in `data/private/`, which is gitignored; the repo is public. Never commit real student data, real transcripts, or anything FERPA-covered. Official transcripts are Level 4 data and need IT sign-off.
5. **Never commit secrets.** `DATABASE_URL` and `VISOR_WRITE_TOKEN` live in Vercel env vars and your local `.env` (gitignored). No connection strings in code, commits, or PR text.
6. **Never push to `main`.** Work on your branch, open a PR, get one review. `main` deploys to production automatically.
7. **Keep PRs to your own task.** Don't edit another person's files on their branch; leave a PR comment instead.

## Workflow

- Branch: `KAN-<n>-short-name`. Commit messages start with `KAN-<n>:`. PR title starts with the Jira key. Use the PR template.
- Before pushing, run what CI runs:
  ```
  cd backend && ruff check . && pytest -q
  cd frontend && npm run build
  ```
- Every push gets a Vercel preview URL (posted on the PR by the Vercel bot). Put it in your PR description.
- **Log your hours in Jira** on your ticket (Log work) every session. The class tracks it. If Claude helped, say so in the worklog note.
- Move your Jira ticket: To Do → In Progress when you start → Done when your PR merges.
- Merge order for the equivalency work: KAN-39 rules → KAN-38 backend → KAN-40 UI. When rules land, wire `match()` into `_suggest()` in `backend/visor/equivalencies.py`.

## Running it

Full guide: `docs/dev-setup.md`. Short version (SQLite, no Docker):

```
cd backend && pip install -r requirements-dev.txt && flask --app wsgi seed && flask --app wsgi run --debug
cd frontend && npm install && npm run dev        # http://localhost:5173, /api proxied to :5000
```

## Where things are

| Path | What |
|---|---|
| `backend/visor/app.py` | Flask app factory, schedule/prereq endpoints |
| `backend/visor/equivalencies.py` | Equivalency API |
| `backend/visor/rules/` | Pure rules engine (conflicts, prereqs; equivalency matching coming) |
| `backend/visor/models.py`, `seed.py` | SQLAlchemy models, CSV loaders |
| `backend/visor/auth.py` | `@require_write_token`: every route that writes to the DB must use it (KAN-46) |
| `backend/visor/sis_import.py` | Importer for the registrar's SIS equivalency export (`flask import-sis`) |
| `data/sample/`, `data/equivalencies/` | Fake seed data; `data/equivalencies/README.md` lists the demo lookups |
| `frontend/src/` | React app |
| `api/index.py`, `vercel.json` | Vercel deploy layer (Flask as one serverless function) |
| `specs/`, `docs/adr/` | Specs and decision records |

Hosting: Vercel (frontend + API) and Neon Postgres. Production: https://visor-steel.vercel.app

## Open questions (don't build around these yet)

- ~~Top transfer schools~~ Answered 10/13 (her "Top Incoming Transfer Schools" doc, 14 schools): Nashville State, Vol State, Columbia State, UT Knoxville, UT Chattanooga, Harding, Tennessee State, MTSU, Belmont, Austin Peay, Pellissippi, Motlow, Trevecca, Samford. All 14 are in the SIS export.
- ~~SIS export format~~ Answered: see `specs/03-design-equivalencies.md`, "SIS import".
- The SIS export lists "Lipscomb University" itself as a transfer source, and UT Knoxville under two spellings. Ask Ms. Hood what the Lipscomb rows are.
- Who can confirm an equivalency: registrar only, or professors too? (KAN-29)
- One external course *does* map to two Lipscomb courses in the real SIS export (135 cases). For now: most-used is `confirmed`, the rest `proposed`. Need Ms. Hood to say what decides which applies.
