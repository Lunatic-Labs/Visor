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
specs/, docs/          spec-driven docs and ADRs
```
