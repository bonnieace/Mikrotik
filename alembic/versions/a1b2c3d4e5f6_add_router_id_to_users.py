"""add_router_id_to_users

Revision ID: a1b2c3d4e5f6
Revises: 78fdbc06c3bf
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '78fdbc06c3bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ID of the router all existing users belong to
BACKFILL_ROUTER_ID = 2


def upgrade() -> None:
    op.add_column('hotspot_users', sa.Column('router_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_hotspot_users_router_id', 'hotspot_users', 'routers', ['router_id'], ['id']
    )

    op.add_column('ppp_users', sa.Column('router_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_ppp_users_router_id', 'ppp_users', 'routers', ['router_id'], ['id']
    )

    # Backfill existing rows to the known router
    op.execute(f'UPDATE hotspot_users SET router_id = {BACKFILL_ROUTER_ID} WHERE router_id IS NULL')
    op.execute(f'UPDATE ppp_users SET router_id = {BACKFILL_ROUTER_ID} WHERE router_id IS NULL')


def downgrade() -> None:
    op.drop_constraint('fk_hotspot_users_router_id', 'hotspot_users', type_='foreignkey')
    op.drop_column('hotspot_users', 'router_id')

    op.drop_constraint('fk_ppp_users_router_id', 'ppp_users', type_='foreignkey')
    op.drop_column('ppp_users', 'router_id')
