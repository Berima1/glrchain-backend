"""Create hash-chained audit event storage.

Revision ID: 0003_audit_events
Revises: 0002_reports_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_audit_events"
down_revision = "0002_reports_evidence"
branch_labels = None
depends_on = None

ZERO_HASH = "0" * 64


def upgrade() -> None:
    op.create_table(
        "audit_heads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", sa.String(length=100), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False, unique=True),
    )
    op.create_index("ix_audit_events_event_id", "audit_events", ["event_id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"])
    op.execute(
        sa.text("INSERT INTO audit_heads (id, last_hash) VALUES (1, :zero_hash)")
        .bindparams(zero_hash=ZERO_HASH)
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_hash", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("audit_heads")
