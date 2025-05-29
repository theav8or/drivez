"""Add image_url to car_listings

Revision ID: 20240529_add_image_url_to_car_listings
Revises: 
Create Date: 2025-05-29 17:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240529_add_image_url_to_car_listings'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add image_url column to car_listings table
    op.add_column('car_listings', sa.Column('image_url', sa.String(), nullable=True))
    op.create_index(op.f('ix_car_listings_image_url'), 'car_listings', ['image_url'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_car_listings_image_url'), table_name='car_listings')
    op.drop_column('car_listings', 'image_url')
