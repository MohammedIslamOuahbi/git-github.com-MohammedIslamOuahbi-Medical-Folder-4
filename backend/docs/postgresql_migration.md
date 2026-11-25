# PostgreSQL Migration Guide

## Why PostgreSQL Is Required For All Runtime Modes

SQLite was used historically by earlier versions of the project, but it is not supported as a runtime database for the PostgreSQL-only architecture.

Use PostgreSQL in all runtime modes because it provides:

- reliable concurrent writes for multi-user activity
- connection pooling for the FastAPI API
- safer backup and restore workflows
- better recovery, observability, and server-side administration

Production rule:

- PostgreSQL may be installed on every PC, but only the selected Server PC uses it during a mission
- client PCs must connect only to the FastAPI backend API
- do not share a SQLite file between clinic PCs

## Supported Environments

### Development / Local Testing

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder_dev
API_BASE_URL=http://localhost:8000/api/v1
```

### Production LAN / Clinic

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder
API_BASE_URL=http://192.168.0.136:8000/api/v1
BACKEND_CORS_ORIGINS=http://192.168.0.136:5173,http://192.168.0.137:5173
```

## PostgreSQL Installation

1. Install PostgreSQL on every machine that may run the backend or desktop application.
2. Make sure the PostgreSQL service is running.
3. Create the production database and the application account.
4. Keep PostgreSQL local to the active Server PC; client PCs do not need direct PostgreSQL LAN access.

Example SQL:

```sql
CREATE DATABASE medical_folder;
CREATE USER clinic_user WITH ENCRYPTED PASSWORD 'change-me';
GRANT ALL PRIVILEGES ON DATABASE medical_folder TO clinic_user;
```

If you use the built-in `postgres` user instead, update `DATABASE_URL` accordingly.

## Backend Configuration

Set the environment variables on the server:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder
API_BASE_URL=http://192.168.0.136:8000/api/v1
```

The backend rejects SQLite URLs at startup. SQLite should be used only as an input source for the one-time import script when migrating old data.

## Schema Migration Steps

1. Back up the current SQLite file if you are importing historical data.
2. Back up the PostgreSQL server if the target database already exists.
3. Install backend dependencies:

```bash
pip install -r requirements.txt
```

4. Apply Alembic migrations to PostgreSQL:

```bash
alembic upgrade head
```

5. Run the SQLite to PostgreSQL data copy:

```bash
python migrate_sqlite_to_postgres.py --sqlite-url sqlite:///./medical_clinic.db --postgres-url postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder
```

6. Start the FastAPI backend and verify login, users, campaigns, workers, visits, certificates, prescriptions, PDFs, signatures, sync, and reports.

## Data Migration Script

The project includes `migrate_sqlite_to_postgres.py`.

What it does:

- connects to SQLite and PostgreSQL
- verifies the target schema
- copies rows in foreign-key-safe order
- preserves IDs and timestamps
- carries JSON payloads as-is
- skips duplicates safely
- resets PostgreSQL sequences after import
- rolls back the PostgreSQL transaction on unexpected failure

Optional schema bootstrap:

```bash
python migrate_sqlite_to_postgres.py --sqlite-url sqlite:///./medical_clinic.db --postgres-url postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder --create-schema
```

## Backup Procedure

### SQLite Backup Before Migration

Copy the SQLite file to a safe location:

```powershell
Copy-Item .\medical_clinic.db .\medical_clinic.pre-postgres-backup.db
```

### PostgreSQL Backup

Use `pg_dump` on the server:

```bash
pg_dump -h localhost -U postgres -d medical_folder -F c -f medical_folder.backup
```

## Restore Procedure

Restore a PostgreSQL backup with `pg_restore`:

```bash
pg_restore -h localhost -U postgres -d medical_folder --clean --if-exists medical_folder.backup
```

For a full reset before re-running the migration, recreate the target database and then run:

```bash
alembic upgrade head
python migrate_sqlite_to_postgres.py --sqlite-url sqlite:///./medical_clinic.db --postgres-url postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder
```

## Verification Checklist

After migration, confirm:

- users, roles, and permissions load correctly
- companies, campaigns, branches, and drilling sites are present
- workers and medical folders open correctly
- medical visits, tests, and certificates keep their relationships
- prescriptions and attachments remain linked
- PDFs and signatures still resolve to the same file paths
- synchronization data and audit logs are intact
- search, pagination, and reports still work

## Important Runtime Note

SQLite is not a supported runtime database.
PostgreSQL is required for development, desktop, and production usage.
Even if PostgreSQL is installed on every PC, one active Server PC should be used during a mission and Client PCs should connect only to FastAPI.
