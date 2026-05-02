"""add_router_id_to_logs_payments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_ROUTER_ID = 2


def upgrade() -> None:
    op.add_column('logs', sa.Column('router_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_logs_router_id', 'logs', 'routers', ['router_id'], ['id']
    )

    op.add_column('payments', sa.Column('router_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_payments_router_id', 'payments', 'routers', ['router_id'], ['id']
    )

    op.execute(f'UPDATE logs SET router_id = {BACKFILL_ROUTER_ID} WHERE router_id IS NULL')
    op.execute(f'UPDATE payments SET router_id = {BACKFILL_ROUTER_ID} WHERE router_id IS NULL')


def downgrade() -> None:
    op.drop_constraint('fk_logs_router_id', 'logs', type_='foreignkey')
    op.drop_column('logs', 'router_id')

    op.drop_constraint('fk_payments_router_id', 'payments', type_='foreignkey')
    op.drop_column('payments', 'router_id')
