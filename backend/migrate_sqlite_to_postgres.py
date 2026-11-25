from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable

from sqlalchemy import JSON, MetaData, Table, and_, create_engine, func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import Base
from app.models import *  # noqa: F401,F403


def build_engine(url: str):
    engine_kwargs = {"future": True, "pool_pre_ping": True, "pool_recycle": 3600}
    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **engine_kwargs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate backend data from SQLite to PostgreSQL.")
    parser.add_argument("--sqlite-url", help="Source SQLite URL. Example: sqlite:///./medical_clinic.db")
    parser.add_argument(
        "--postgres-url",
        help="Target PostgreSQL URL. Example: postgresql+psycopg://postgres:password@localhost:5432/medical_folder",
    )
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Create missing tables in PostgreSQL from SQLAlchemy metadata before copying data.",
    )
    return parser.parse_args()


def resolve_urls(args: argparse.Namespace) -> tuple[str, str]:
    sqlite_url = args.sqlite_url or ""
    postgres_url = args.postgres_url or ""

    if not sqlite_url.startswith("sqlite"):
        raise ValueError("The --sqlite-url source argument is required and must be a SQLite URL.")
    if not postgres_url.startswith("postgresql"):
        raise ValueError("The --postgres-url target argument is required and must be a PostgreSQL URL.")

    return sqlite_url, postgres_url


def get_table_order(source_meta: MetaData, target_meta: MetaData) -> list[str]:
    ordered = [table.name for table in target_meta.sorted_tables if table.name in source_meta.tables]
    extras = sorted(name for name in source_meta.tables if name not in ordered and name in target_meta.tables)
    return ordered + extras


def table_count(connection: Connection, table: Table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def reset_postgres_sequence(connection: Connection, table: Table) -> None:
    pk_columns = list(table.primary_key.columns)
    if len(pk_columns) != 1:
        return

    pk_column = pk_columns[0]
    try:
        python_type = pk_column.type.python_type
    except NotImplementedError:
        return

    if python_type is not int:
        return

    quoted_table_name = '"' + table.name.replace('"', '""') + '"'
    quoted_column_name = '"' + pk_column.name.replace('"', '""') + '"'
    sequence_name = connection.execute(
        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": quoted_table_name, "column_name": pk_column.name},
    ).scalar_one_or_none()
    if not sequence_name:
        return

    sql = text(
        f"""
        SELECT setval(
            :sequence_name,
            COALESCE((SELECT MAX({quoted_column_name}) FROM {quoted_table_name}), 1),
            (SELECT COUNT(*) > 0 FROM {quoted_table_name})
        )
        """
    )
    connection.execute(sql, {"sequence_name": sequence_name})


def verify_target_schema(target_meta: MetaData) -> None:
    expected_tables = set(Base.metadata.tables.keys())
    actual_tables = set(target_meta.tables.keys())
    missing_tables = sorted(expected_tables - actual_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            "The PostgreSQL schema is missing required tables. Run 'alembic upgrade head' first "
            f"or use --create-schema. Missing: {missing}"
        )


def iter_rows(connection: Connection, table: Table, common_columns: Iterable[str]):
    columns = [table.c[column_name] for column_name in common_columns]
    statement = select(*columns)
    pk_columns = list(table.primary_key.columns)
    if pk_columns:
        statement = statement.order_by(*pk_columns)
    return connection.execute(statement).mappings()


def normalize_value(target_table: Table, column_name: str, value):
    if value is None:
        return None

    target_column = target_table.c[column_name]
    if isinstance(target_column.type, JSON) and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    return value


def copy_table(source_connection: Connection, target_connection: Connection, source_table: Table, target_table: Table) -> tuple[int, int, int]:
    source_column_names = set(source_table.columns.keys())
    target_column_names = [column.name for column in target_table.columns]
    common_columns = [column_name for column_name in target_column_names if column_name in source_column_names]

    total_rows = table_count(source_connection, source_table)
    inserted = 0
    updated = 0
    skipped = 0

    print(f"[{target_table.name}] {total_rows} rows detected")

    pk_columns = [column.name for column in target_table.primary_key.columns]

    for index, row in enumerate(iter_rows(source_connection, source_table, common_columns), start=1):
        payload = {
            column_name: normalize_value(target_table, column_name, row[column_name]) for column_name in common_columns
        }

        try:
            with target_connection.begin_nested():
                if pk_columns and all(payload.get(column_name) is not None for column_name in pk_columns):
                    pk_filter = and_(*(target_table.c[column_name] == payload[column_name] for column_name in pk_columns))
                    existing = target_connection.execute(select(target_table).where(pk_filter).limit(1)).mappings().first()
                    if existing is not None:
                        changed_payload = {
                            column_name: payload[column_name]
                            for column_name in common_columns
                            if existing.get(column_name) != payload[column_name]
                        }
                        if changed_payload:
                            target_connection.execute(target_table.update().where(pk_filter).values(**changed_payload))
                            updated += 1
                        else:
                            skipped += 1
                        continue

                target_connection.execute(target_table.insert().values(**payload))
                inserted += 1
        except IntegrityError:
            skipped += 1

        if index % 250 == 0 or index == total_rows:
            print(
                f"[{target_table.name}] progress {index}/{total_rows} | "
                f"inserted={inserted} updated={updated} skipped={skipped}"
            )

    reset_postgres_sequence(target_connection, target_table)
    return inserted, updated, skipped


def migrate(sqlite_url: str, postgres_url: str, create_schema: bool) -> None:
    source_engine = build_engine(sqlite_url)
    target_engine = build_engine(postgres_url)

    if create_schema:
        Base.metadata.create_all(bind=target_engine)

    source_meta = MetaData()
    target_meta = MetaData()
    source_meta.reflect(bind=source_engine)
    target_meta.reflect(bind=target_engine)

    verify_target_schema(target_meta)
    table_order = get_table_order(source_meta, target_meta)

    print("Source SQLite:", sqlite_url)
    print("Target PostgreSQL:", postgres_url)
    print("Tables scheduled:", ", ".join(table_order))

    try:
        with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
            total_inserted = 0
            total_updated = 0
            total_skipped = 0

            for table_name in table_order:
                source_table = source_meta.tables[table_name]
                target_table = target_meta.tables[table_name]
                inserted, updated, skipped = copy_table(source_connection, target_connection, source_table, target_table)
                total_inserted += inserted
                total_updated += updated
                total_skipped += skipped

            print(
                "Migration completed successfully. "
                f"inserted={total_inserted}, updated={total_updated}, skipped={total_skipped}"
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Migration failed and PostgreSQL changes were rolled back: {exc}") from exc
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> int:
    try:
        args = parse_args()
        sqlite_url, postgres_url = resolve_urls(args)
        migrate(sqlite_url=sqlite_url, postgres_url=postgres_url, create_schema=args.create_schema)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
