"""empty message

Revision ID: 7ea53d9d888f
Revises: 88be74c0bf85
Create Date: 2018-06-01 23:07:27.919186

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7ea53d9d888f'
down_revision = '88be74c0bf85'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('competition_event', schema=None) as batch_op:
        batch_op.drop_column('scrambles')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('competition_event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scrambles', sa.TEXT(), nullable=True))

    # ### end Alembic commands ###
