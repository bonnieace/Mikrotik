"""add admin_users and router ownership

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade():
    # 1. Create admin_users table
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

    # 2. Seed the existing "admin" user (role=isp, password="secret")
    hashed_pw = _pwd_context.hash("secret")
    op.execute(
        sa.text(
            "INSERT INTO admin_users (username, email, hashed_password, role, is_active, created_at) "
            "VALUES (:username, :email, :hashed_password, :role, :is_active, NOW())"
        ).bindparams(
            username="admin",
            email=None,
            hashed_password=hashed_pw,
            role="isp",
            is_active=True,
        )
    )

    # 3. Add nullable owner_id to routers
    op.add_column('routers', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_routers_owner_id_admin_users',
        'routers', 'admin_users',
        ['owner_id'], ['id'],
    )

    # 4. Assign only router id=2 to the admin user
    op.execute(
        sa.text("UPDATE routers SET owner_id = (SELECT id FROM admin_users WHERE username = 'admin' LIMIT 1) WHERE id = 2")
    )

    # 5. Make owner_id NOT NULL now that all rows are backfilled
    op.alter_column('routers', 'owner_id', nullable=False)


def downgrade():
    op.drop_constraint('fk_routers_owner_id_admin_users', 'routers', type_='foreignkey')
    op.drop_column('routers', 'owner_id')
    op.drop_table('admin_users')
