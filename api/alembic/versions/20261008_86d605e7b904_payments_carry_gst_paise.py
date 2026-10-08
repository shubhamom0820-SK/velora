"""payments carry gst_paise

Revision ID: 86d605e7b904
Revises: ed3028467a15
Create Date: 2026-10-08 12:00:00.000000

`payments.gst_paise` (D-450, T-8.1): the government's part of a payment's
GST-inclusive `amount_paise` (D-099). 0 while Velora is unregistered, which it is
until P-350; registration splits the amount, never moves it, so the check holds
it inside the amount.

The downgrade refuses once any payment carries GST: that is a record of tax
collected, and dropping the column would lose it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86d605e7b904"
down_revision: str | Sequence[str] | None = "ed3028467a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "payments",
        sa.Column(
            "gst_paise", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.create_check_constraint(
        "gst_within_amount",
        "payments",
        "gst_paise >= 0 AND gst_paise < amount_paise",
    )


def downgrade() -> None:
    """Downgrade schema, unless a payment carries GST."""
    carrying = op.get_bind().scalar(
        sa.text("select count(*) from payments where gst_paise <> 0")
    )
    if carrying:
        raise RuntimeError(
            f"{carrying} payment(s) carry GST: dropping gst_paise would lose a record "
            "of tax collected (D-450). Not downgrading."
        )
    op.drop_constraint(op.f("ck_payments_gst_within_amount"), "payments", type_="check")
    op.drop_column("payments", "gst_paise")
