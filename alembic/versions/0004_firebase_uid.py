"""Map GLRChain profiles to verified Firebase Auth UIDs.

Revision ID: 0004_firebase_uid
Revises: 0003_audit_events
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_firebase_uid"
down_revision = "0003_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("firebase_uid", sa.String(length=128), nullable=True))
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_column("users", "firebase_uid")
