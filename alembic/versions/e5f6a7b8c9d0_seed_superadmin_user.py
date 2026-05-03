"""seed superadmin user

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import bcrypt

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM admin_users WHERE username = 'superadmin' LIMIT 1")
    ).fetchone()
    if not existing:
        hashed_pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            sa.text(
                "INSERT INTO admin_users (username, email, hashed_password, role, is_active, created_at) "
                "VALUES (:username, :email, :hashed_password, :role, :is_active, NOW())"
            ),
            {
                "username": "superadmin",
                "email": None,
                "hashed_password": hashed_pw,
                "role": "superadmin",
                "is_active": True,
            },
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM admin_users WHERE username = 'superadmin'"))
