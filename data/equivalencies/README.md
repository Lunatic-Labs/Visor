# Sample transfer-equivalency data (FAKE)

Made up for development and the 10/8 demo. **Not real Lipscomb equivalencies.** School names are real Tennessee community colleges so the data reads naturally, but every course, mapping, and decision here is invented. Replace with the SIS export from the registrar when it arrives (KAN-36).

Loaded by `flask seed` after `data/sample/`, via `visor.seed.load_equivalencies`. Loading is idempotent.

| File | One row per | Notes |
|---|---|---|
| `schools.csv` | school | |
| `external_courses.csv` | course at another school | `catalog_year` is part of the key |
| `equivalencies.csv` | mapping | `external` = `SUBJ NUM` at that school; `lipscomb` blank for `elective` / `none` |
| `reviews.csv` | professor review request | matched to an equivalency by school + external + lipscomb |

## What the demo can hit

| Lookup | Result |
|---|---|
| Nashville State `CISP 1010` | confirmed → CS 1113 |
| Nashville State `ENGL 1010` | confirmed → general elective |
| Vol State `PHED 1110` | confirmed → does not transfer |
| Columbia State `CSCI 1020` | proposed → CS 1213 (0.78), one pending review |
| Vol State `CIS 2350` | proposed → CS 2113 (0.71) |
| Columbia State `CSCI 2020` | rejected row only → unknown |
| Vol State `CIS 1010`, `MATH 1920`, `COMM 2025`; Columbia State `ENGL 1010`; Nashville State `HIST 2010` | no row → unknown |
