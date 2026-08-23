# SaaS Backend — Multi-Tenant Project Management Platform

Milestone 1 (Project Bootstrap) scaffold. See `saas-backend-architecture.md` (your
architecture doc) for the full design and the rest of the milestones.

## Stack
- Python 3.12, managed with **uv**
- Django 6 + Django REST Framework
- PostgreSQL, Redis, Celery (worker + beat)
- Docker / Docker Compose for local dev
- pytest + pytest-django, ruff for lint/format
- GitHub Actions CI

## Project layout
```
.
├── src/
│   ├── config/
│   │   ├── settings/{base,dev,prod,test}.py
│   │   ├── celery.py
│   │   ├── urls.py
│   │   ├── wsgi.py / asgi.py
│   ├── apps/            # domain apps land here starting Milestone 2
│   ├── common/
│   │   ├── models.py     # BaseModel, TenantScopedModel, TenantManager
│   │   └── permissions.py
│   └── manage.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml / uv.lock
├── .env.example
└── .github/workflows/ci.yml
```

## Local setup (with Docker — recommended)

```bash
# 1. clone / cd into the repo
cp .env.example .env
# .env's DATABASE_URL/REDIS_URL already point at the "postgres"/"redis"
# service names, which is correct for Docker Compose networking.

# 2. build and start everything (web, worker, beat, postgres, redis)
docker compose up --build

# App is now at http://localhost:8000/health/
```

Migrations run automatically on `web` container start (see `docker-compose.yml`'s
`command:`). To run other management commands inside the container:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

## Local setup (without Docker, using uv directly)

Useful for fast iteration; you'll still want Postgres/Redis running somewhere
(either via `docker compose up postgres redis` and nothing else, or installed
natively).

```bash
# 1. install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. install dependencies (creates .venv automatically)
uv sync

# 3. copy env and point DATABASE_URL/REDIS_URL at localhost instead of
#    the docker service names
cp .env.example .env
sed -i 's/@postgres:/@localhost:/; s/redis:\/\/redis:/redis:\/\/localhost:/' .env

# 4. start just the infra containers
docker compose up -d postgres redis

# 5. run Django
cd src
uv run python manage.py migrate
uv run python manage.py runserver
```

## Tests & lint

```bash
uv run pytest                 # uses config.settings.test, real Postgres required
uv run pytest --cov           # with coverage
uv run ruff check .           # lint
uv run ruff format .          # format
```

## Git

```bash
git init
git add .
git commit -m "Milestone 1: project bootstrap (uv, Docker, settings split, base models)"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, then
`pytest` against real Postgres/Redis service containers on every push/PR to `main`.

## What's NOT here yet (by design)

This is Milestone 1 only — infrastructure, no features. No `User` model, no
`Organization`, no auth. Those start at Milestone 2 per the architecture doc's
recommended implementation order. `common/models.py` and
`common/permissions.py` exist now specifically so every domain app built from
Milestone 2 onward inherits tenant-safety from day one instead of it being
retrofitted later.
