from alembic import op
import sqlalchemy as sa



"""merge migrations

Revision ID: af189eff3e7e
Revises: 20240529_add_image_url_to_car_listings, 21bf6e2c4c5f
Create Date: 2025-05-29 17:13:48.908911

"""
# revision identifiers, used by Alembic.
revision = 'af189eff3e7e'
down_revision = ('20240529_add_image_url_to_car_listings', '21bf6e2c4c5f')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
