"""create users and reports tables

Revision ID: 0001_create_users_and_reports
Revises: 
Create Date: 2025-09-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0001_create_users_and_reports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("username", sa.String, unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String, nullable=False),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("reporter", sa.String, nullable=False),
        sa.Column("location", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
    )


def downgrade():
    op.drop_table("reports")
    op.drop_table("users")
