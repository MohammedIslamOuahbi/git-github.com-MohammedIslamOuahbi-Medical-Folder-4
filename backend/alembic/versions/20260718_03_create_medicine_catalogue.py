"""create medicine catalogue

Revision ID: 20260718_03
Revises: 20260718_02
Create Date: 2026-07-18 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260718_03"
down_revision = "20260718_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "medicine_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("import_mode", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deactivated_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_by_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mapping_json", sa.JSON(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medicine_imports_id"), "medicine_imports", ["id"], unique=False)
    op.create_index(op.f("ix_medicine_imports_file_hash"), "medicine_imports", ["file_hash"], unique=False)

    op.create_table(
        "medicines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registration_number", sa.String(length=255), nullable=True),
        sa.Column("national_code", sa.String(length=255), nullable=True),
        sa.Column("stable_identity_key", sa.String(length=128), nullable=False),
        sa.Column("international_nonproprietary_name", sa.String(length=500), nullable=True),
        sa.Column("brand_name", sa.String(length=500), nullable=False),
        sa.Column("full_name", sa.String(length=600), nullable=True),
        sa.Column("pharmaceutical_form", sa.String(length=255), nullable=True),
        sa.Column("source_pharmaceutical_form", sa.String(length=255), nullable=True),
        sa.Column("strength", sa.String(length=255), nullable=True),
        sa.Column("packaging", sa.String(length=500), nullable=True),
        sa.Column("list_category", sa.String(length=100), nullable=True),
        sa.Column("p1", sa.String(length=255), nullable=True),
        sa.Column("p2", sa.String(length=255), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("laboratory", sa.String(length=500), nullable=True),
        sa.Column("registration_holder", sa.String(length=500), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("medicine_type", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_prescribable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("source_file_name", sa.String(length=255), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("source_import_id", sa.Integer(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_brand_name", sa.String(length=500), nullable=True),
        sa.Column("normalized_generic_name", sa.String(length=500), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(length=20), nullable=False, server_default="synced"),
        sa.Column("local_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["source_import_id"], ["medicine_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_identity_key"),
        sa.UniqueConstraint("local_id"),
    )
    op.create_index(op.f("ix_medicines_id"), "medicines", ["id"], unique=False)
    op.create_index(op.f("ix_medicines_registration_number"), "medicines", ["registration_number"], unique=False)
    op.create_index(op.f("ix_medicines_national_code"), "medicines", ["national_code"], unique=False)
    op.create_index(op.f("ix_medicines_brand_name"), "medicines", ["brand_name"], unique=False)
    op.create_index(op.f("ix_medicines_international_nonproprietary_name"), "medicines", ["international_nonproprietary_name"], unique=False)
    op.create_index(op.f("ix_medicines_laboratory"), "medicines", ["laboratory"], unique=False)
    op.create_index(op.f("ix_medicines_is_active"), "medicines", ["is_active"], unique=False)
    op.create_index(op.f("ix_medicines_is_prescribable"), "medicines", ["is_prescribable"], unique=False)
    op.create_index(op.f("ix_medicines_normalized_brand_name"), "medicines", ["normalized_brand_name"], unique=False)
    op.create_index(op.f("ix_medicines_normalized_generic_name"), "medicines", ["normalized_generic_name"], unique=False)
    op.create_index(op.f("ix_medicines_source_import_id"), "medicines", ["source_import_id"], unique=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_medicines_search_text_trgm ON medicines USING gin (search_text gin_trgm_ops)"
    )

    op.create_table(
        "medicine_import_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("medicine_import_id", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=255), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["medicine_import_id"], ["medicine_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medicine_import_errors_id"), "medicine_import_errors", ["id"], unique=False)
    op.create_index(op.f("ix_medicine_import_errors_medicine_import_id"), "medicine_import_errors", ["medicine_import_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_medicine_import_errors_medicine_import_id"), table_name="medicine_import_errors")
    op.drop_index(op.f("ix_medicine_import_errors_id"), table_name="medicine_import_errors")
    op.drop_table("medicine_import_errors")
    op.execute("DROP INDEX IF EXISTS ix_medicines_search_text_trgm")
    op.drop_index(op.f("ix_medicines_source_import_id"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_normalized_generic_name"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_normalized_brand_name"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_is_prescribable"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_is_active"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_laboratory"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_international_nonproprietary_name"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_brand_name"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_national_code"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_registration_number"), table_name="medicines")
    op.drop_index(op.f("ix_medicines_id"), table_name="medicines")
    op.drop_table("medicines")
    op.drop_index(op.f("ix_medicine_imports_file_hash"), table_name="medicine_imports")
    op.drop_index(op.f("ix_medicine_imports_id"), table_name="medicine_imports")
    op.drop_table("medicine_imports")
