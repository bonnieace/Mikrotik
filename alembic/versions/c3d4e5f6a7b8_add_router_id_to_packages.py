"""add_router_id_to_packages

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-02 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_ROUTER_ID = 2


def upgrade() -> None:
    op.add_column('packages', sa.Column('router_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_packages_router_id', 'packages', 'routers', ['router_id'], ['id']
    )
    op.execute(f'UPDATE packages SET router_id = {BACKFILL_ROUTER_ID} WHERE router_id IS NULL')


def downgrade() -> None:
    op.drop_constraint('fk_packages_router_id', 'packages', type_='foreignkey')
    op.drop_column('packages', 'router_id')
