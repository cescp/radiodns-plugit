"""Added type

Revision ID: 465e7dae3728
Revises: 1461ccb47bf0
Create Date: 2013-08-06 08:30:44.697000

"""

# revision identifiers, used by Alembic.
revision = '465e7dae3728'
down_revision = '1461ccb47bf0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('channel', sa.Column('type_id', sa.String(length=5), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('channel', 'type_id')
    ### end Alembic commands ###
