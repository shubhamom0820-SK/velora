"""private message threads never expire

Revision ID: ddf84381ef6c
Revises: fb0a7ce8dd16
Create Date: 2026-10-08 22:00:00.000000

A private message never expires (D-231), and is a Thread of origin `dm`
(T-7.1, D-550). `ck_threads_active_expires` said every active Thread expires;
from here it says every active Thread **from a match** does, and an active
private-message Thread carries no `expires_at`, so the expiry cron (T-7.6),
which reads `expires_at`, never reaches it. A Knot still never carries one.

The downgrade puts T-1.10's rule back, which an active private-message Thread
can't pass: it refuses, naming how many there are, rather than inventing an
expiry for a conversation both people were told never ends.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ddf84381ef6c"
down_revision: str | Sequence[str] | None = "fb0a7ce8dd16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# op.f() marks the name final, so the naming convention isn't applied twice.
NAME = "ck_threads_active_expires"
BEFORE = "status <> 'active' OR expires_at IS NOT NULL"
AFTER = "status <> 'active' OR expires_at IS NOT NULL OR origin = 'dm'"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f(NAME), "threads", type_="check")
    op.create_check_constraint(op.f(NAME), "threads", AFTER)


def downgrade() -> None:
    """Downgrade schema."""
    never_expiring = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM threads "
            "WHERE status = 'active' AND expires_at IS NULL"
        )
    )
    if never_expiring:
        raise RuntimeError(
            f"{never_expiring} active private-message Thread(s) never expire "
            "(D-231, D-550); T-1.10's rule can't hold them. Not downgrading."
        )
    op.drop_constraint(op.f(NAME), "threads", type_="check")
    op.create_check_constraint(op.f(NAME), "threads", BEFORE)
