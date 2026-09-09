"""Add persistent public ISP registration attempt tracking.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registration_attempts_client_ip_hash", "registration_attempts", ["client_ip_hash"], unique=False)
    op.create_index("ix_registration_attempts_email_hash", "registration_attempts", ["email_hash"], unique=False)
    op.create_index("ix_registration_attempts_created_at", "registration_attempts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_registration_attempts_created_at", table_name="registration_attempts")
    op.drop_index("ix_registration_attempts_email_hash", table_name="registration_attempts")
    op.drop_index("ix_registration_attempts_client_ip_hash", table_name="registration_attempts")
    op.drop_table("registration_attempts")
