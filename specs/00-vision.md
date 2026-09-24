# Visor: Vision (DRAFT v0.1)

Status: ON HOLD. The main user and focus may change (see open-questions.md). Jira: KAN-15
Last updated: 2026-09-23

## Problem

- Advisors spend a lot of time on one-on-one appointments just to work out each student's schedule for the next semester.
- Tracking is manual. Some advisors keep each student's progress in an Excel spreadsheet.
- Students don't always know which classes to take or when to take them.
- **Time conflicts.** A student is supposed to take two required classes in the same semester, but they're scheduled at the same time. The plan breaks and graduation can slip. This happens often.

## One-line pitch

Visor builds each student's semester-by-semester plan from their degree requirements, flags time conflicts and missing prerequisites before registration, and adjusts the plan when something changes. Advisors then only need to review and approve.

## Success measures

| Goal | How we measure it |
|---|---|
| Less advising time | Fewer meetings per student per semester, or shorter ones |
| Fewer scheduling problems | Fewer students blocked by time conflicts or missing prerequisites at registration |
| Better graduation estimates | Visor's projected graduation date matches the actual one |

We still need baseline numbers from an advisor for each measure (see open-questions.md).

## Users and roles

| Role | Main job in Visor |
|---|---|
| Registrar's office | Maintain the catalog and schedule data. Possibly the main user (TBD). |
| Advisor | Review each student's suggested plan and approve it |
| Student | See their degree plan and what to take this semester and next. Adjust their own plan. |

- Students **can** edit their own plan. Advisor or registrar approval of changes is a likely feature.
- Advisor visibility (only their own advisees or all students) hasn't been decided.

## Core workflows (happy paths)

### Student: first login
1. Log in.
2. See their major, catalog year, and degree plan, with completed, in-progress, and remaining requirements.
3. See the current and upcoming semester, with the suggested classes for each.
4. See a full semester-by-semester plan through graduation, with a projected graduation date.

### Advisor: typical week
1. Get notified when student plans are ready for review.
2. Check each plan: are the suggestions accurate, and does the schedule fit the student's outside life?
3. Approve it, with a quick email or a short meeting at most. The approval sends the student an automatic email.

### When things change
If a class isn't offered, a student fails a course, or a student changes majors, Visor re-plans the remaining semesters and shows what changed.

## Key rules and data

- The course catalog, prerequisites, and degree requirements come from school files or systems, not manual entry.
- **Catalog year:** a student follows the requirements from the year they enrolled.
- Visor needs to know which semesters each course is offered, its capacity, and each section's meeting times.
- Transcript data can be imported, and grades can also be entered by hand.

## Scope and constraints

- One school (Lipscomb) for now.
- User count unknown. Several users at once normally, with a spike during registration week.
- Team project for Software Studio. Tech stack: see `docs/adr/0001-tech-stack.md` (proposed).
- Timeline: a few weeks to the first demo, with basic functions working end to end.
- Out of scope for v1: not decided yet.
