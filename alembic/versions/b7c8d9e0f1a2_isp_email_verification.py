"""add ISP display name and email verification state

Revision ID: b7c8d9e0f1a2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "b7c8d9e0f1a2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns("admin_users")}


def upgrade() -> None:
    columns = _columns()
    if "isp_name" not in columns:
        op.add_column("admin_users", sa.Column("isp_name", sa.String(length=125), nullable=True))
    if "email_verified_at" not in columns:
        op.add_column("admin_users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    if "email_verification_token_hash" not in columns:
        op.add_column("admin_users", sa.Column("email_verification_token_hash", sa.String(length=64), nullable=True))
    if "email_verification_expires_at" not in columns:
        op.add_column("admin_users", sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True))
    if "email_verification_sent_at" not in columns:
        op.add_column("admin_users", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))

    # All accounts that existed before self-service signup are trusted existing operators.
    op.execute(sa.text("UPDATE admin_users SET email_verified_at = COALESCE(email_verified_at, created_at)"))

    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("admin_users")}
    if "ix_admin_users_email_verification_token_hash" not in indexes:
        op.create_index(
            "ix_admin_users_email_verification_token_hash",
            "admin_users",
            ["email_verification_token_hash"],
            unique=False,
        )


def downgrade() -> None:
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("admin_users")}
    if "ix_admin_users_email_verification_token_hash" in indexes:
        op.drop_index("ix_admin_users_email_verification_token_hash", table_name="admin_users")
    columns = _columns()
    for name in (
        "email_verification_sent_at",
        "email_verification_expires_at",
        "email_verification_token_hash",
        "email_verified_at",
        "isp_name",
    ):
        if name in columns:
            op.drop_column("admin_users", name)
