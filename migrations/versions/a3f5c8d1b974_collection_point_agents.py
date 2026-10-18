"""collection point agents

Rattachement des agents aux points de collecte : un agent n'encaisse des espèces qu'aux points
auxquels un administrateur l'a rattaché.

Revision ID: a3f5c8d1b974
Revises: 7c2d9e4b1a63
Create Date: 2026-10-18 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f5c8d1b974'
down_revision = '7c2d9e4b1a63'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'collection_point_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collection_point_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['collection_point_id'], ['collection_points.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_collection_point_agents_collection_point_id'), 'collection_point_agents',
                    ['collection_point_id'], unique=False)
    op.create_index(op.f('ix_collection_point_agents_agent_id'), 'collection_point_agents',
                    ['agent_id'], unique=False)
    op.create_index('idx_collection_point_agent_unique', 'collection_point_agents',
                    ['collection_point_id', 'agent_id'], unique=True)


def downgrade():
    op.drop_index('idx_collection_point_agent_unique', table_name='collection_point_agents')
    op.drop_index(op.f('ix_collection_point_agents_agent_id'), table_name='collection_point_agents')
    op.drop_index(op.f('ix_collection_point_agents_collection_point_id'), table_name='collection_point_agents')
    op.drop_table('collection_point_agents')
