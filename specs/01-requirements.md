# Visor: requirements (user stories)

Scope: **transfer course equivalencies** (`specs/03-design-equivalencies.md`). Degree audit stories come later (KAN-12).

Each of us writes two stories (KAN-16). Format:

- **As a** [role], **I want** [action], **so that** [benefit].
- **Acceptance criteria** as Given / When / Then. Each one should be something a test can check. Where a test already exists, it's named in brackets.

Roles: **Registrar** (Ms. Hood and her office), **Professor** (a faculty member asked to weigh in), **Admin** (us, running imports and the deployment).

---

## Austin (KAN-43)

### US-1: Load the SIS equivalency export

**As the** registrar's office, **I want** Visor to load the transfer equivalencies we've already approved in the SIS, **so that** every known answer is there without anyone re-typing it.

Acceptance criteria:

1. **Given** the SIS export (`.xlsx` or `.csv`) with the standard columns, **when** an admin imports it, **then** each school, transfer course, and Lipscomb course is created once, and each transfer course gets exactly one `confirmed` equivalency (its most-used pairing) with `decided_by = "Registrar's office (SIS)"`. [`test_load_into_db`, `test_only_one_confirmed_per_external_course`]
2. **Given** a transfer course the SIS approved as more than one Lipscomb course, **when** it's imported, **then** the other pairings are saved as `proposed` with `confidence` = their share of transfers, for the registrar to sort out. [`test_load_into_db`, `test_plan_groups_and_ranks`]
3. **Given** a Lipscomb placeholder code like `EN2XXT`, `PH1XXX`, or `TRACC`, **when** it's imported, **then** it's saved as elective credit (`kind = elective`, no Lipscomb course) with the code in the notes. [`test_load_into_db`, `test_elective_codes_and_school_kind`]
4. **Given** codes written different ways (`ENGL 1010`, `ENGL1010`, `AR-2201-0399-03`) or fractional credits (`2.67`), **when** they're imported, **then** the same course is matched once and the credits are kept as-is. [`test_split_code`, `test_plan_groups_and_ranks`]
5. **Given** the same file is imported twice, **when** the second import runs, **then** nothing new is added. [`test_import_is_idempotent`]
6. **Given** a file missing a required column, **when** it's imported, **then** the import stops, names the missing column, and saves nothing. [`test_missing_column_is_an_error`]
7. **Given** `--dry-run`, **when** the import runs, **then** it prints a summary and writes nothing. *(Gap: covered only through `build_plan().summary()`, not the CLI flag itself.)*
8. **Given** the real export, **then** it is never committed to the repo (public); it lives in `data/private/`, which is gitignored. *(Checked by review, not a test.)*

### US-2: Look up a transfer course

**As** someone in the registrar's office, **I want** to enter a transfer course's school and course code and see what it counts as at Lipscomb, **so that** I can answer a student without digging through catalogs and old files.

Acceptance criteria:

1. **Given** a course with a confirmed direct equivalency, **when** I look it up, **then** I get `confirmed`, the Lipscomb course, and who decided it. [`test_lookup_confirmed_direct`]
2. **Given** a course confirmed as elective credit or as not transferring, **when** I look it up, **then** I get `confirmed` with kind `elective` or `none`. [`test_lookup_confirmed_elective_and_none`]
3. **Given** a course with only proposed matches, **when** I look it up, **then** I get `proposed` and the candidates ranked by confidence, plus how many professor reviews are pending. [`test_lookup_proposed_has_candidates_and_pending_review`]
4. **Given** a course with no match (or only rejected ones), **when** I look it up, **then** I get `unknown`, and the course is recorded so it can be flagged for review. [`test_lookup_rejected_only_is_unknown`, `test_lookup_new_course_is_recorded_as_unknown`]
5. **Given** I type `engl` and ` 1010 `, **when** I look it up, **then** I get the same answer as `ENGL` / `1010`. [`test_lookup_case_and_whitespace_insensitive`]
6. **Given** a missing field or a school that doesn't exist, **when** I look it up, **then** I get a clear error (`400` / `404`) and nothing is recorded. [`test_lookup_validation`, `test_lookup_unknown_school_404`]
7. **Given** any lookup, **then** nothing is ever confirmed automatically; only a person sets `confirmed`. [`test_confirm_requires_a_person`]
8. **Given** the lookup page, **when** I submit a course, **then** the result shows within a couple of seconds. *(Gap: no frontend tests yet; see Firas's stories.)*

---

## Gabriel (KAN-44)

_Two stories go here. Suggested: rules proposing likely matches without ever confirming (KAN-39), and flagging a course for professor review._

## Firas (KAN-45)

_Two stories go here. Suggested: using the lookup page, and confirming or rejecting a proposed match with your name recorded._

---

## Non-functional requirements

- **Privacy:** no real student data or transcripts in the repo. Official transcripts are FERPA Level 4 and need IT sign-off (Brett Hanson). Real registrar files stay in `data/private/`.
- **Safety:** until login exists (KAN-30), every route that changes data needs the write token (KAN-46).
- **Hosting:** runs on Vercel + Neon free tiers; the lookup should feel instant for one office's worth of traffic.
