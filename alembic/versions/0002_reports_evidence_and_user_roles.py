"""Add report ownership, timestamps, roles, and evidence metadata.

Revision ID: 0002_reports_evidence
Revises: 0001_create_users_and_reports
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_reports_evidence"
down_revision = "0001_create_users_and_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), server_default="user", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Existing descriptions were encrypted with the historical SECRET_KEY setting.
    # Mark them as v1; new application writes explicitly use key version 2.
    op.add_column("reports", sa.Column("encryption_key_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("reports", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column(
        "reports",
        sa.Column("status", sa.String(length=32), server_default="submitted", nullable=False),
    )
    op.add_column(
        "reports",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_foreign_key(
        "fk_reports_user_id_users",
        "reports",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("object_name", sa.String(length=1024), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_records_report_id", "evidence_records", ["report_id"])
    op.create_index("ix_evidence_records_sha256", "evidence_records", ["sha256"])
    op.create_index("ix_evidence_records_uploaded_by", "evidence_records", ["uploaded_by"])


def downgrade() -> None:
    op.drop_index("ix_evidence_records_uploaded_by", table_name="evidence_records")
    op.drop_index("ix_evidence_records_sha256", table_name="evidence_records")
    op.drop_index("ix_evidence_records_report_id", table_name="evidence_records")
    op.drop_table("evidence_records")

    op.drop_constraint("fk_reports_user_id_users", "reports", type_="foreignkey")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_column("reports", "created_at")
    op.drop_column("reports", "status")
    op.drop_column("reports", "user_id")
    op.drop_column("reports", "encryption_key_version")
    op.drop_column("users", "created_at")
    op.drop_column("users", "role")
