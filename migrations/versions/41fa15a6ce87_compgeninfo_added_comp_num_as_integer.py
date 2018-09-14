"""CompGenInfo added comp num as integer

Revision ID: 41fa15a6ce87
Revises: eed6a6a11005
Create Date: 2018-09-13 22:59:29.109817

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41fa15a6ce87'
down_revision = 'eed6a6a11005'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('comp_gen_resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current_comp_num', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('comp_gen_resources', schema=None) as batch_op:
        batch_op.drop_column('current_comp_num')

    # ### end Alembic commands ###