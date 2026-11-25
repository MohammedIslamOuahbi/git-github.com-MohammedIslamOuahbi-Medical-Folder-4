# Database Deployment Guide

## Why SQLite Should Not Be Used In The Clinic LAN

SQLite stores data in a single file and is not designed for a busy multi-user clinic setup with around 20 PCs working at the same time.

Main risks with SQLite in this environment:

- file-level locking becomes a bottleneck under concurrent writes
- backup and restore workflows are tied to a local file, not a managed server database
- reliability and recovery are weaker for central multi-user usage
- operational visibility is limited compared with a real database server

For this reason, PostgreSQL is the only supported runtime database for the application. SQLite may appear only as a historical source when importing old data into PostgreSQL.

## Required Production Topology

Use this architecture in the clinic:

1. One central server runs:
   - FastAPI backend
   - PostgreSQL database
2. Each PC may have PostgreSQL installed, but only the selected Server PC uses its local database during a mission.
3. Every client PC talks only to the FastAPI API over the LAN.
4. Client mode never connects to the local PostgreSQL installation.

## Environment Configuration

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
API_BASE_URL=http://192.168.1.10:8000/api/v1
BACKEND_CORS_ORIGINS=http://192.168.1.10:5173,http://192.168.1.20:5173
```

## Migration Procedure

1. Install PostgreSQL on every machine that will run the backend locally, including development machines.
2. On the selected Server PC only, create the production database and dedicated application user.
3. Set `DATABASE_URL` to the PostgreSQL connection string for the current environment.
4. Run:

```bash
alembic upgrade head
```

5. If you are migrating an existing SQLite dataset, run:

```bash
python migrate_sqlite_to_postgres.py --sqlite-url sqlite:///./medical_clinic.db --postgres-url postgresql+psycopg://medical_user:change-me@127.0.0.1:5432/medical_folder
```

6. Start the FastAPI backend.
7. Point all clinic client PCs to the FastAPI backend API.

## Notes About Existing Features

The PostgreSQL production path is intended to preserve:

- workers
- medical folders
- medical visits
- certificates
- prescriptions
- PDFs
- signatures
- users and permissions

## Operational Notes

- In every environment, use PostgreSQL-native backup and restore procedures.
- Do not share or run a SQLite file as an application database.
- Even when PostgreSQL is installed on every PC, use only one active Server PC during a mission.
