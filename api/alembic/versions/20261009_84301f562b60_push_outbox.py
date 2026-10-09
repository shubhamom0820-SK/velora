"""push outbox

Revision ID: 84301f562b60
Revises: 18fc99762f2a
Create Date: 2026-10-09 12:00:01.000000

`push_outbox` (T-9.4, D-850): a push waiting to be sent, written in the
transaction that makes it true, so a rollback sends nothing. The worker claims
rows (`claimed_at`), sends them with no row lock held, and deletes each once
it is sent, skipped or given up on (`attempts`, 3). A claim older than five
minutes is a worker that died mid-send, and is taken again.

Nothing here is a record moderation needs (rule 12): each row lives seconds,
and what it announced is kept where it happened (the message, the match, the
in-app notification). The erasure deletes a user's rows (D-503).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84301f562b60"
down_revision: str | Sequence[str] | None = "18fc99762f2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "push_outbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_push_outbox_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_outbox")),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_push_outbox_attempts_not_negative")
        ),
    )
    op.create_index("ix_push_outbox_created_at", "push_outbox", ["created_at"])
    op.create_index("ix_push_outbox_user_id", "push_outbox", ["user_id"])


def downgrade() -> None:
    """Downgrade schema. A push still waiting is dropped: it was never a record."""
    op.drop_index("ix_push_outbox_user_id", table_name="push_outbox")
    op.drop_index("ix_push_outbox_created_at", table_name="push_outbox")
    op.drop_table("push_outbox")
