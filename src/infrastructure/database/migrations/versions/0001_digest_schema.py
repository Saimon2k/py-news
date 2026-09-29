"""Create digest service schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_digest_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])
    op.create_table(
        "user_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("channel_username", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "channel_id"),
    )
    op.create_table(
        "channel_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("last_digest_date", sa.DateTime(), nullable=False),
        sa.Column("last_message_id", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "channel_id"),
    )
    op.create_table(
        "digest_queues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("active", "completed", name="queuestatus"), nullable=False),
        sa.Column("source_batch_path", sa.String(), nullable=False),
    )
    op.create_table(
        "digest_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digest_queue_id", sa.Integer(), sa.ForeignKey("digest_queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("channel_username", sa.String(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("message_url", sa.String(), nullable=False),
        sa.Column("type", sa.Enum("text", "media_with_caption", "media_without_text", name="messagetype"), nullable=False),
        sa.Column("preview_text", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("source_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("digest_items")
    op.drop_table("digest_queues")
    op.drop_table("channel_states")
    op.drop_table("user_channels")
    op.drop_index("ix_users_telegram_user_id", table_name="users")
    op.drop_table("users")
