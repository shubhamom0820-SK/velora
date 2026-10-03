"""otp sms daily cap

Revision ID: 89b155534dcf
Revises: 67e81c6c203d
Create Date: 2026-10-03 07:27:16.202063

`app_config.otp_sms_daily_cap`, seeded at 500 (T-3.2, D-066): the most Path B
sign-in codes the API sends in one day, across every number. At D-035's
unconfirmed ₹0.20 an SMS that is ₹100 a day, whatever an attacker rents; without
it, one cloud IPv6 /48 could spend ₹2.6 lakh an hour. Revisited at P-0.5, when
MSG91 goes live.

Same pattern as T-1.14's reference data: ON CONFLICT DO NOTHING, so running it
again never resets a value tuned since; written through an sa.table() stand-in,
not the model (rule 11); downgrade() deletes exactly this key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "89b155534dcf"
down_revision: str | Sequence[str] | None = "67e81c6c203d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY = "otp_sms_daily_cap"
VALUE = 500

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def reference_data() -> list[postgresql.Insert]:
    """The insert, shared by upgrade() and the test that runs it twice."""
    return [
        postgresql.insert(app_config)
        .values(key=KEY, value=VALUE)
        .on_conflict_do_nothing()
    ]


def upgrade() -> None:
    """Upgrade schema."""
    for statement in reference_data():
        op.execute(statement)


def downgrade() -> None:
    """Downgrade schema: remove exactly this key."""
    op.execute(sa.delete(app_config).where(app_config.c.key == KEY))
