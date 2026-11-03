# Dev setup (KAN-22)

Stack: React (Vite) + Flask + PostgreSQL. See `docs/adr/0001-tech-stack.md`.

## Option A: Docker (closest to production)

Needs Docker Desktop.

```
docker compose up --build
docker compose exec backend flask seed     # load data/sample
```

- App: http://localhost:5173
- API: http://localhost:5000/api/health

## Option B: No Docker (fastest to start)

Needs Python 3.11+ and Node 20+. The backend uses a local SQLite file when `DATABASE_URL` isn't set.

**Backend** (terminal 1):
```
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
flask --app wsgi seed
flask --app wsgi run --debug
```

**Frontend** (terminal 2):
```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. You should see 3 time conflicts for Spring 2027 (they're planted in `data/sample`).

## Loading the registrar's real equivalencies

Ms. Hood's SIS export is **real Lipscomb data** and the repo is public, so it never gets committed. Get it from #notes-resources on Discord, put it in `data/private/` (gitignored), then:

```
cd backend
flask --app wsgi import-sis --dry-run "../data/private/Lipscomb University Transfer Courses and Equivalents.xlsx"
flask --app wsgi import-sis "../data/private/Lipscomb University Transfer Courses and Equivalents.xlsx"
```

Running it twice is safe. To see only real data locally, use a fresh database and skip `flask seed`'s fake equivalencies. Don't load it into the shared Neon database without checking with the team first (it shows up on the public site). Details: `specs/03-design-equivalencies.md`, "SIS import".

## Loading the real class schedule (and the full list of Lipscomb courses)

Lipscomb's public class-schedule page has Export > CSV. Save that file in `data/private/` (gitignored), then:

```
cd backend
flask --app wsgi import-schedule --dry-run "../data/private/2027 Spring Semester Class Schedule  Lipscomb University.csv"
flask --app wsgi import-schedule "../data/private/2027 Spring Semester Class Schedule  Lipscomb University.csv"
```

The registrar does the same without a terminal: Import tab > Class schedule > choose the CSV > Upload (it has a "check only" box too). Either way, the load time is recorded and shown on the Schedule tab as "last updated", turning amber after a day.

One row per section becomes a course (if new), a section, and its meeting times. Running it twice is safe, and courses already in the database (e.g. from the SIS import) are never overwritten. Rows it can't use fully (a section code over 4 characters, meetings listed as calendar dates, an end time before the start) are listed at the end. It reads only this export's format, not the four-file format below. The export has no prerequisites. Details: `backend/visor/schedule_import.py`.

To see only real data locally, import the SIS file and the schedule into a fresh database and skip `flask seed`.

## Loading the registrar's catalog and section schedule

Same idea, for `terms.csv` / `courses.csv` / `prereqs.csv` / `sections.csv` (format: `data/sample/README.md`):

```
cd backend
flask --app wsgi import-csv --dry-run path/to/her/csvs
flask --app wsgi import-csv path/to/her/csvs
```

Each row is checked on its own — a bad row (bad number, unknown course, overlapping end/start time, ...) is skipped and printed as `file line N: reason`; every valid row in the same files still loads. Running it twice is safe: an unchanged row is left alone, a changed one (e.g. updated enrollment) is updated, nothing is duplicated.

## Tests and lint

```
cd backend
pytest -q
ruff check .
```

CI runs the same checks plus a frontend build on every PR (`.github/workflows/ci.yml`).

## Layout

```
backend/visor/rules/   pure scheduling logic (no Flask/DB imports)
backend/visor/         Flask app, models, CSV seed/import
backend/tests/         pytest
frontend/src/          React UI
data/sample/           FAKE sample data (see its README)
data/private/          real registrar files, gitignored, never committed
specs/, docs/          spec-driven docs and ADRs
```
