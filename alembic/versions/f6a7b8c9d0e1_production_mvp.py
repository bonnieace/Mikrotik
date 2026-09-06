"""production MVP schema and payment sessions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-06
"""

from __future__ import annotations

import re
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _index_names(table: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}


def _unique_names(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_unique_constraints(table) if item.get("name")}


def _fill_uuids(table: str, column: str) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"SELECT id FROM {table} WHERE {column} IS NULL")).fetchall()
    for (row_id,) in rows:
        conn.execute(sa.text(f"UPDATE {table} SET {column}=:value WHERE id=:id"), {"value": str(uuid.uuid4()), "id": row_id})


def _dedupe_with_suffix(table: str, value_column: str, scope_column: str = "router_id") -> None:
    """Preserve all legacy rows while making scoped names safe for a unique key."""
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            f"SELECT {scope_column}, {value_column} FROM {table} "
            f"WHERE {scope_column} IS NOT NULL GROUP BY {scope_column}, {value_column} HAVING COUNT(*) > 1"
        )
    ).fetchall()
    for scope, value in duplicates:
        rows = conn.execute(
            sa.text(
                f"SELECT id FROM {table} WHERE {scope_column}=:scope AND {value_column}=:value ORDER BY id"
            ),
            {"scope": scope, "value": value},
        ).fetchall()
        for (row_id,) in rows[1:]:
            renamed = f"{str(value)[:100]}-{row_id}"
            conn.execute(
                sa.text(f"UPDATE {table} SET {value_column}=:renamed WHERE id=:id"),
                {"renamed": renamed, "id": row_id},
            )


def upgrade() -> None:
    conn = op.get_bind()

    _add("admin_users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    _add("admin_users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    _add("admin_users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    _add("admin_users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    _add("routers", sa.Column("uid", sa.String(36), nullable=True))
    _add("routers", sa.Column("portal_slug", sa.String(80), nullable=True))
    _add("routers", sa.Column("portal_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add("routers", sa.Column("payment_provider", sa.String(32), nullable=False, server_default="mpesa"))
    _add("routers", sa.Column("connection_mode", sa.String(32), nullable=False, server_default="direct"))
    _add("routers", sa.Column("onboarding_status", sa.String(32), nullable=False, server_default="configured"))
    _add("routers", sa.Column("onboarding_token_hash", sa.String(64), nullable=True))
    _add("routers", sa.Column("onboarding_token_expires_at", sa.DateTime(), nullable=True))
    _add("routers", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    _add("routers", sa.Column("last_error", sa.String(255), nullable=True))
    _add("routers", sa.Column("routeros_version", sa.String(64), nullable=True))
    _fill_uuids("routers", "uid")
    rows = conn.execute(sa.text("SELECT id, name FROM routers WHERE portal_slug IS NULL")).fetchall()
    for row_id, name in rows:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "router").lower()).strip("-")[:50] or "router"
        conn.execute(sa.text("UPDATE routers SET portal_slug=:slug WHERE id=:id"), {"slug": f"{slug}-{row_id}", "id": row_id})
    with op.batch_alter_table("routers") as batch:
        batch.alter_column("uid", existing_type=sa.String(36), nullable=False)
        batch.alter_column("portal_slug", existing_type=sa.String(80), nullable=False)
        batch.alter_column("ip_address", existing_type=sa.String(125), type_=sa.String(255), nullable=False)
        batch.alter_column("password", existing_type=sa.String(125), type_=sa.Text(), nullable=False)
        batch.create_unique_constraint("uq_routers_uid", ["uid"])
        batch.create_unique_constraint("uq_routers_portal_slug", ["portal_slug"])
    if "ix_routers_owner_id" not in _index_names("routers"):
        op.create_index("ix_routers_owner_id", "routers", ["owner_id"])

    _add("packages", sa.Column("uid", sa.String(36), nullable=True))
    _add("packages", sa.Column("validity_minutes", sa.Integer(), nullable=True))
    _add("packages", sa.Column("router_profile", sa.String(125), nullable=False, server_default="default"))
    _add("packages", sa.Column("rate_limit", sa.String(64), nullable=True))
    _add("packages", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _fill_uuids("packages", "uid")
    conn.execute(sa.text("UPDATE packages SET validity_minutes=validity_days * 1440 WHERE validity_minutes IS NULL"))
    _dedupe_with_suffix("packages", "name")
    with op.batch_alter_table("packages") as batch:
        batch.alter_column("uid", existing_type=sa.String(36), nullable=False)
        batch.alter_column("validity_minutes", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_packages_uid", ["uid"])
        batch.create_unique_constraint("uq_package_router_name", ["router_id", "name"])

    _add("hotspot_users", sa.Column("uid", sa.String(36), nullable=True))
    _add("hotspot_users", sa.Column("password_encrypted", sa.Text(), nullable=True))
    _add("hotspot_users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _fill_uuids("hotspot_users", "uid")
    conn.execute(sa.text("UPDATE hotspot_users SET otp=CONCAT('legacy-', id) WHERE otp IS NULL"))
    _dedupe_with_suffix("hotspot_users", "otp")
    with op.batch_alter_table("hotspot_users") as batch:
        batch.alter_column("uid", existing_type=sa.String(36), nullable=False)
        batch.alter_column("otp", existing_type=sa.String(50), type_=sa.String(125), nullable=False)
        batch.create_unique_constraint("uq_hotspot_users_uid", ["uid"])
        batch.create_unique_constraint("uq_hotspot_router_username", ["router_id", "otp"])

    _add("ppp_users", sa.Column("uid", sa.String(36), nullable=True))
    _add("ppp_users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _fill_uuids("ppp_users", "uid")
    _dedupe_with_suffix("ppp_users", "pppoe_username")
    # Replace global uniqueness with tenant/router uniqueness.
    for constraint in inspect(conn).get_unique_constraints("ppp_users"):
        columns = set(constraint.get("column_names") or [])
        if columns in ({"email"}, {"pppoe_username"}) and constraint.get("name"):
            op.drop_constraint(constraint["name"], "ppp_users", type_="unique")
    with op.batch_alter_table("ppp_users") as batch:
        batch.alter_column("uid", existing_type=sa.String(36), nullable=False)
        batch.alter_column("email", existing_type=sa.String(125), nullable=True)
        batch.alter_column("profile", existing_type=sa.Text(), type_=sa.String(125), nullable=True)
        batch.alter_column("pppoe_password", existing_type=sa.String(125), type_=sa.Text(), nullable=False)
        batch.create_unique_constraint("uq_ppp_users_uid", ["uid"])
        batch.create_unique_constraint("uq_ppp_router_username", ["router_id", "pppoe_username"])

    _add("payments", sa.Column("uid", sa.String(36), nullable=True))
    _add("payments", sa.Column("provider", sa.String(32), nullable=False, server_default="mpesa"))
    _add("payments", sa.Column("provider_receipt", sa.String(125), nullable=True))
    _add("payments", sa.Column("status", sa.String(32), nullable=False, server_default="completed"))
    _fill_uuids("payments", "uid")
    duplicates = conn.execute(sa.text("SELECT invoice FROM payments GROUP BY invoice HAVING COUNT(*) > 1")).fetchall()
    for (invoice,) in duplicates:
        rows = conn.execute(sa.text("SELECT id FROM payments WHERE invoice=:invoice ORDER BY id"), {"invoice": invoice}).fetchall()
        for (row_id,) in rows[1:]:
            conn.execute(sa.text("UPDATE payments SET invoice=:invoice WHERE id=:id"), {"invoice": f"{invoice}-{row_id}", "id": row_id})
    with op.batch_alter_table("payments") as batch:
        batch.alter_column("uid", existing_type=sa.String(36), nullable=False)
        batch.create_unique_constraint("uq_payments_uid", ["uid"])
        batch.create_unique_constraint("uq_payments_invoice", ["invoice"])
        batch.create_unique_constraint("uq_payments_provider_receipt", ["provider_receipt"])

    _add("logs", sa.Column("level", sa.String(16), nullable=False, server_default="info"))
    _add("logs", sa.Column("event_type", sa.String(64), nullable=True))

    op.create_table(
        "payment_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("access_token_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("provider_receipt", sa.String(125), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("result_code", sa.String(32), nullable=True),
        sa.Column("result_description", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("phone_hash", sa.String(64), nullable=False),
        sa.Column("amount", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("service_type", sa.String(50), nullable=False),
        sa.Column("customer_reference", sa.String(125), nullable=True),
        sa.Column("client_ip_hash", sa.String(64), nullable=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("access_username", sa.String(125), nullable=True),
        sa.Column("access_password_encrypted", sa.Text(), nullable=True),
        sa.Column("credentials_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_payment_sessions_public_id"),
        sa.UniqueConstraint("provider_request_id", name="uq_payment_sessions_provider_request"),
        sa.UniqueConstraint("provider_receipt", name="uq_payment_sessions_receipt"),
        sa.UniqueConstraint("router_id", "idempotency_key", name="uq_payment_router_idempotency"),
    )
    op.create_index("ix_payment_sessions_status", "payment_sessions", ["status"])
    op.create_index("ix_payment_sessions_phone_hash", "payment_sessions", ["phone_hash"])
    op.create_index("ix_payment_sessions_client_ip_hash", "payment_sessions", ["client_ip_hash"])


def downgrade() -> None:
    op.drop_table("payment_sessions")
    # The remaining changes intentionally require a forward repair migration. Downgrading
    # encrypted credentials or restoring global PPP username uniqueness is data-destructive.
