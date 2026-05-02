"""add admin_users and router ownership

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _table_exists(name):
    return name in sa_inspect(op.get_bind()).get_table_names()


def _column_exists(table, column):
    cols = [c['name'] for c in sa_inspect(op.get_bind()).get_columns(table)]
    return column in cols


def _fk_exists(table, fk_name):
    fks = [fk['name'] for fk in sa_inspect(op.get_bind()).get_foreign_keys(table)]
    return fk_name in fks


def upgrade():
    # 1. Create admin_users table (idempotent)
    if not _table_exists('admin_users'):
        op.create_table(
            'admin_users',
            sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
            sa.Column('username', sa.String(125), nullable=False),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('role', sa.String(50), nullable=False, server_default='isp'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username'),
            sa.UniqueConstraint('email'),
        )

    # 2. Seed the "admin" user only if not already present
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT id FROM admin_users WHERE username = 'admin' LIMIT 1")).fetchone()
    if not existing:
        hashed_pw = _pwd_context.hash("secret")
        conn.execute(
            sa.text(
                "INSERT INTO admin_users (username, email, hashed_password, role, is_active, created_at) "
                "VALUES (:username, :email, :hashed_password, :role, :is_active, NOW())"
            ),
            {"username": "admin", "email": None, "hashed_password": hashed_pw, "role": "isp", "is_active": True},
        )

    # 3. Add nullable owner_id to routers (idempotent)
    if not _column_exists('routers', 'owner_id'):
        op.add_column('routers', sa.Column('owner_id', sa.Integer(), nullable=True))

    # 4. Add FK if not already there
    if not _fk_exists('routers', 'fk_routers_owner_id_admin_users'):
        op.create_foreign_key(
            'fk_routers_owner_id_admin_users',
            'routers', 'admin_users',
            ['owner_id'], ['id'],
        )

    # 5. Assign only router id=2 to the admin user (only if not already assigned)
    conn.execute(
        sa.text(
            "UPDATE routers SET owner_id = (SELECT id FROM admin_users WHERE username = 'admin' LIMIT 1) "
            "WHERE id = 2 AND owner_id IS NULL"
        )
    )

    # 6. Make owner_id NOT NULL
    op.alter_column('routers', 'owner_id', nullable=False)


def downgrade():
    op.drop_constraint('fk_routers_owner_id_admin_users', 'routers', type_='foreignkey')
    op.drop_column('routers', 'owner_id')
    op.drop_table('admin_users')
