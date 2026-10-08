# Visor

A tool for Lipscomb's registrar's office to manage transfer course equivalencies, with degree-audit features to follow. Scope came from the 10/1 registrar meeting; see `CLAUDE.md` for the current state of the project and `specs/03-design-equivalencies.md` for the design.

**Using an AI assistant on this repo? Point it at `CLAUDE.md` first.**

Software Studio team project. Jira board: https://visor1.atlassian.net (project KAN, "The Visors").

## How we work: spec-driven development

Each spec is drafted, reviewed in a PR, and approved before the next one starts:

1. `specs/00-vision.md`: problem, users, goals, and what counts as success
2. `specs/01-requirements.md`: user stories with acceptance criteria
3. `specs/02-design.md`: architecture, data model, integrations, and scale
4. `specs/03-tasks.md`: implementation task breakdown (mirrored in Jira)

Other folders:

- `specs/open-questions.md`: decisions we still need to make
- `docs/adr/`: architecture decision records (one file per big decision)

## Running it

See **docs/dev-setup.md**. Short version: the backend runs with `flask --app wsgi seed` and `flask --app wsgi run`, and the frontend with `npm install` and `npm run dev`.

## Branches and PRs

- Name branches after their Jira key, e.g. `KAN-26-time-conflicts`.
- Never commit straight to `main`. Open a PR and get one review.
- Put the Jira key in the PR title.
