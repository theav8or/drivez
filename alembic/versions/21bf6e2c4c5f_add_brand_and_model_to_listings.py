from alembic import op
import sqlalchemy as sa



"""add_brand_and_model_to_listings

Revision ID: 21bf6e2c4c5f
Revises: 1
Create Date: 2025-05-28 19:37:08.118689

"""
# revision identifiers, used by Alembic.
revision = '21bf6e2c4c5f'
down_revision = '1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add brand_id column with foreign key constraint
    op.add_column('car_listings', 
        sa.Column('brand_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_car_listings_brand_id',
        'car_listings', 'car_brands',
        ['brand_id'], ['id']
    )
    
    # Add model_id column with foreign key constraint
    op.add_column('car_listings', 
        sa.Column('model_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_car_listings_model_id',
        'car_listings', 'car_models',
        ['model_id'], ['id']
    )
    
    # Add other missing columns
    op.add_column('car_listings',
        sa.Column('yad2_id', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('fuel_type', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('transmission', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('body_type', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('color', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('status', sa.String(), nullable=True)
    )
    op.add_column('car_listings',
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create indexes for the new columns
    op.create_index('ix_car_listings_brand_id', 'car_listings', ['brand_id'])
    op.create_index('ix_car_listings_model_id', 'car_listings', ['model_id'])
    op.create_index('ix_car_listings_yad2_id', 'car_listings', ['yad2_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_car_listings_yad2_id', table_name='car_listings')
    op.drop_index('ix_car_listings_model_id', table_name='car_listings')
    op.drop_index('ix_car_listings_brand_id', table_name='car_listings')
    
    # Drop columns
    op.drop_column('car_listings', 'last_scraped_at')
    op.drop_column('car_listings', 'status')
    op.drop_column('car_listings', 'color')
    op.drop_column('car_listings', 'body_type')
    op.drop_column('car_listings', 'transmission')
    op.drop_column('car_listings', 'fuel_type')
    op.drop_column('car_listings', 'yad2_id')
    
    # Drop foreign key constraints and columns
    op.drop_constraint('fk_car_listings_model_id', 'car_listings', type_='foreignkey')
    op.drop_column('car_listings', 'model_id')
    op.drop_constraint('fk_car_listings_brand_id', 'car_listings', type_='foreignkey')
    op.drop_column('car_listings', 'brand_id')
