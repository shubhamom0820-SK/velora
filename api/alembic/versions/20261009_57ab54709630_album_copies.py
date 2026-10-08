"""album copies

Revision ID: 57ab54709630
Revises: b53383c8e9b6
Create Date: 2026-10-09 01:37:59.956158

`album_copies` (T-8.4, D-730): one row per private photo watermarked for one
granted album request's viewer, naming the file in the private bucket. The row
is written only once its file is, and deleted only once its file is gone, so a
revoke, the erasure (D-503) and an under-18 refusal (D-078) find every copy by
its `file_key`, as their tests require of every `*_key` column. The request's
two people are on the row, so either one's erasure finds it. Rows only, so a
plain table with the app role's default grants.

**The downgrade refuses while any copy is recorded**, since the row is the only
record of where a watermarked copy of someone's private photo is stored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57ab54709630"
down_revision: str | Sequence[str] | None = "b53383c8e9b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_album_copies_{column}_{target}"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "album_copies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _fk("request_id", "album_requests"),
        _fk("photo_id", "photos"),
        _fk("owner_id", "users"),
        _fk("viewer_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_album_copies")),
        sa.UniqueConstraint("file_key", name=op.f("uq_album_copies_file_key")),
        sa.UniqueConstraint(
            "request_id", "photo_id", name=op.f("uq_album_copies_request_id_photo_id")
        ),
    )
    op.create_index("ix_album_copies_owner_id", "album_copies", ["owner_id"])
    op.create_index("ix_album_copies_viewer_id", "album_copies", ["viewer_id"])


def downgrade() -> None:
    """Downgrade schema: refused while any copy is recorded."""
    held = op.get_bind().scalar(sa.text("select count(*) from album_copies"))
    if held:
        raise RuntimeError(
            f"{held} watermarked album copies are in storage, and without their "
            "rows no deletion would find them (D-730)"
        )
    op.drop_index("ix_album_copies_viewer_id", table_name="album_copies")
    op.drop_index("ix_album_copies_owner_id", table_name="album_copies")
    op.drop_table("album_copies")
