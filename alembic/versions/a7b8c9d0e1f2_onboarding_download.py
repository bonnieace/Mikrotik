"""Encrypted, single-use onboarding script downloads.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("routers", sa.Column("onboarding_download_hash", sa.String(64), nullable=True))
    op.add_column("routers", sa.Column("onboarding_script_encrypted", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("routers", "onboarding_script_encrypted")
    op.drop_column("routers", "onboarding_download_hash")
