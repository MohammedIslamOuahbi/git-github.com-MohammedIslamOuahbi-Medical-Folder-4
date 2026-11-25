# Medical Clinic Management System Backend

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

## Database Environments

The application uses PostgreSQL in every environment:

- `development`: PostgreSQL for local development and tests
- `production`: PostgreSQL for the clinic LAN / multi-user deployment

Important deployment rule:

- Client PCs must connect only to the FastAPI backend API.
- The PostgreSQL database must run only on the central server.
- Do not install or use a separate database on each client PC.

Legacy SQLite note:

- SQLite is not a supported runtime database anymore.
- If you have historical SQLite data, use it only as a one-time migration source into PostgreSQL.

See [docs/database-deployment.md](./docs/database-deployment.md) for the deployment overview and [docs/postgresql_migration.md](./docs/postgresql_migration.md) for the full migration runbook.

## Environment Variables

- `APP_ENV`
- `DATABASE_URL`
- `API_BASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `BACKEND_CORS_ORIGINS`
- `APP_NAME`

### Development example

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder_dev
API_BASE_URL=http://localhost:8000/api/v1
```

### Production LAN / clinic example

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg2://postgres:change-me@192.168.1.10:5432/medical_folder
API_BASE_URL=http://192.168.1.10:8000/api/v1
BACKEND_CORS_ORIGINS=http://192.168.1.10:5173,http://192.168.1.20:5173
```

## Alembic

Use Alembic for schema management, especially in PostgreSQL production.

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
alembic downgrade -1
```

Notes:

- Run `alembic upgrade head` before starting the API in every environment.
- Use `python migrate_sqlite_to_postgres.py --sqlite-url ... --postgres-url ...` only when importing historical SQLite data into PostgreSQL.

## Seed

```bash
python -m app.seed.seed_permissions
python -m app.seed.seed_admin
python -m app.seed.seed_tests
python -m app.seed.seed_demo_data
```

Seeded platform accounts:

- `super_admin`: `babzizsaleh@ibnsina.com` / `babziz saleh`
- `admin`: `babzizmostafa@ibnsina.com` / `babziz mostafa`
- `admin`: `ouahbimohammedislam@ibnsina.com` / `mohammed islam`

`seed_demo_data` creates a realistic Algerian oil and gas test dataset with:

- `20` companies
- `100` branches
- `200` drilling sites
- `500` workers
- `10` medical tests
- `4` doctors
- `8` assistants

## Feature Coverage

The PostgreSQL migration path is intended to preserve existing backend features, including:

- workers
- medical folders
- medical visits
- certificates
- prescriptions
- PDFs
- signatures
- users and permissions

## API Overview

- Auth: `/api/v1/auth`
- Users: `/api/v1/users`
- Companies: `/api/v1/companies`
- Branches: `/api/v1/branches`
- Drilling Sites: `/api/v1/drilling-sites`
- Workers: `/api/v1/workers`
- Campaigns: `/api/v1/campaigns`
- Medical Tests: `/api/v1/medical-tests`
- Medical Visits: `/api/v1/medical-visits`
- Prescriptions: `/api/v1/prescriptions`
- Worker Tests: `/api/v1/worker-tests`
- Imports: `/api/v1/imports`
- Reports: `/api/v1/reports`
- Dashboard: `/api/v1/dashboard`
- Sync: `/api/v1/sync`
- Audit Logs: `/api/v1/audit-logs`
