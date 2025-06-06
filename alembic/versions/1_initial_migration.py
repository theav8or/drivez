from alembic import op
import sqlalchemy as sa


"""
Initial migration

Revision ID: 1
Revises: None
Create Date: 2025-05-28 12:08:00

"""
# revision identifiers, used by Alembic.
revision = '1'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('car_brands',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('normalized_name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('normalized_name')
    )
    op.create_index('ix_car_brands_id', 'car_brands', ['id'], unique=False)
    op.create_table('car_models',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('normalized_name', sa.String(), nullable=False),
    sa.Column('brand_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['brand_id'], ['car_brands.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('normalized_name')
    )
    op.create_index('ix_car_models_id', 'car_models', ['id'], unique=False)
    op.create_table('car_listings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('mileage', sa.Integer(), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'source_id', name='uq_car_listings_source_id')
    )
    op.create_index('ix_car_listings_id', 'car_listings', ['id'], unique=False)
    op.create_index('ix_car_listings_source', 'car_listings', ['source'], unique=False)
    op.create_index('ix_car_listings_source_id', 'car_listings', ['source_id'], unique=False)
    op.create_index('ix_car_listings_url', 'car_listings', ['url'], unique=False)
    op.create_table('car_listing_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_id', sa.Integer(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('mileage', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_id'], ['car_listings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_car_listing_history_id', 'car_listing_history', ['id'], unique=False)
    # ### end Alembic commands ###

def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_car_listing_history_id', table_name='car_listing_history')
    op.drop_table('car_listing_history')
    op.drop_index('ix_car_listings_url', table_name='car_listings')
    op.drop_index('ix_car_listings_source_id', table_name='car_listings')
    op.drop_index('ix_car_listings_source', table_name='car_listings')
    op.drop_index('ix_car_listings_id', table_name='car_listings')
    op.drop_table('car_listings')
    op.drop_index('ix_car_models_id', table_name='car_models')
    op.drop_table('car_models')
    op.drop_index('ix_car_brands_id', table_name='car_brands')
    op.drop_table('car_brands')
    # ### end Alembic commands ###

