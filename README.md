# Visor

A scheduling app for Lipscomb's registrar's office, and possibly for advisors and students (scope is being confirmed). The core job is to catch class time conflicts and prerequisite problems before registration.

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

## Branches and PRs

- Name branches after their Jira key, e.g. `KAN-26-time-conflicts`.
- Never commit straight to `main`. Open a PR and get one review.
- Put the Jira key in the PR title.
