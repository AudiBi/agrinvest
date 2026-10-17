"""contributions fees not null

Le modèle déclare ces colonnes NOT NULL (défaut 0) mais la migration initiale les avait laissées
nullables : une valeur NULL fait échouer le calcul du montant net à la confirmation d'un paiement.

Revision ID: 5b7e1c9a2f40
Revises: dfb4d54b5a66
Create Date: 2026-10-17 14:17:27.847377

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b7e1c9a2f40'
down_revision = 'dfb4d54b5a66'
branch_labels = None
depends_on = None

FEE_COLUMNS = {
    'gateway_fee': sa.Numeric(precision=10, scale=2),
    'conversion_fee': sa.Numeric(precision=10, scale=2),
    'platform_fee': sa.Numeric(precision=10, scale=2),
    'platform_commission_amount': sa.Numeric(precision=12, scale=2),
}


def upgrade():
    # Les lignes existantes sans valeur sont complétées avant d'imposer la contrainte
    for column in FEE_COLUMNS:
        op.execute(f'UPDATE contributions SET {column} = 0 WHERE {column} IS NULL')
    with op.batch_alter_table('contributions') as batch:
        for column, type_ in FEE_COLUMNS.items():
            batch.alter_column(column, existing_type=type_, nullable=False)


def downgrade():
    with op.batch_alter_table('contributions') as batch:
        for column, type_ in FEE_COLUMNS.items():
            batch.alter_column(column, existing_type=type_, nullable=True)
