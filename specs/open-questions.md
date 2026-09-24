# Open questions

## BLOCKING: waiting on Dr. Nordstrom (Jira KAN-14)

**Update 9/24:** our registrar customer is **Ms. Sandra Hood**. Gabriel is working with Dr. Nordstrom to prepare for a meeting with her. The questions below are the agenda.

Visor may be mainly a **scheduling app for the registrar's office**, not a student/advisor planning tool. We emailed to ask:

- Who is the main user: registrar, students, or advisors?
- What does "scheduling" mean here: building the course timetable (sections, times, rooms), building each student's schedule, both, or booking appointments?
- What role, if any, do students and advisors have?
- What does the first demo need to show, and when is it due?
- Is real data available (catalog, requirements, section times), or should we use sample data?

## Needed before requirements (01)

1. **Time conflicts:** does Visor only warn when two classes overlap, or does it choose sections to avoid overlaps?
2. When two required classes always conflict, what should Visor do? Suggest a different semester, suggest a substitute, or flag it?
3. Should Visor account for outside commitments (work hours, family) when suggesting sections?
4. Does Visor register students for classes, or only plan? (Suggested: plan only for v1.)
5. Advisor visibility: only their own advisees, or everyone in the department?
6. Plan approval: required before registration, or optional?

## Needed before design (02). Proposed defaults, not decided.

- **Login:** school SSO eventually. Mock login for the v1 demo.
- **FERPA:** students see only their own records. Advisors see their advisees. Registrar sees all. Log every view or change of a student record.
- **Uptime:** high availability during registration weeks. Normal availability the rest of the year is fine.
- **Backups:** daily automated database backups, kept for at least 30 days, with a restore we've actually tested.
- **Integrations:** start with CSV import. Add a direct connection to the student information system later.

## Baseline numbers to get from an advisor

- How many advisees per advisor? Minutes per student per semester?
- How many students hit a time conflict or prerequisite problem each term?
