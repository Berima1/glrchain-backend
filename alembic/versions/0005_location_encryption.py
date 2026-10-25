"""Add explicit encryption version for sensitive report locations.

Revision ID: 0005_location_encryption
Revises: 0004_firebase_uid
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_location_encryption"
down_revision = "0004_firebase_uid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical locations were stored as plaintext. Keep version 0 so the API
    # can return legacy values without trying to decrypt them.
    op.add_column(
        "reports",
        sa.Column(
            "location_encryption_key_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    # Fernet ciphertext is longer than source text; widen without rewriting legacy values.
    op.alter_column(
        "reports",
        "location",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Do not shrink location back to VARCHAR(500): encrypted values may be longer.
    # A safe downgrade requires a reviewed decryption/export step and is intentionally refused.
    raise RuntimeError(
        "Downgrade blocked: report locations may contain encrypted ciphertext longer than 500 characters. "
        "Restore a tested backup or write a reviewed forward migration."
    )
