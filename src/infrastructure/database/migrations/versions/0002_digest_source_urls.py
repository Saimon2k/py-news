"""Store source links for grouped digest items."""

from alembic import op
import sqlalchemy as sa


revision = "0002_digest_source_urls"
down_revision = "0001_digest_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "digest_items",
        sa.Column("source_urls", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("digest_items", "source_urls")
