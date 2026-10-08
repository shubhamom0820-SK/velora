"""refund request kinds and status

Revision ID: 9a3d5384d962
Revises: 105ae9a99be1
Create Date: 2026-10-08 21:00:00.000000

T-8.3 defines the claim (D-580): T-1.12 left `refund_requests.status` free text
for this task. A claim is a broken payment, never a change of mind (D-050,
D-230):

- `reason`, now required: `missing_velas` (the money went through, no Velas
  came) or `duplicate_charge` (charged twice for one purchase).
- `status`: `open`, then `granted` (the missing Velas, through the webhook's
  own capture), `refunded` (a charge no Velas were ever granted for, returned in
  the gateway) or `rejected` (nothing broken: the admin's note says why).
- What an admin's resolution leaves: `resolved_at`; `note`, required on a
  rejection; on a refund, the gateway's payment and refund ids. The credited
  payment's row is never touched by a refund (D-580): the payment refunded has
  no row of its own, so turnover (D-483) stays right.
- One open claim per payment (`uq_refund_requests_open_per_payment`).

The downgrade refuses while any claim is resolved: its note and the gateway's
ids would go with the columns, and a refund's record is a payment's (rule 12).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a3d5384d962"
down_revision: str | Sequence[str] | None = "105ae9a99be1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = (
    (
        "ck_refund_requests_reason_known",
        "reason IN ('missing_velas', 'duplicate_charge')",
    ),
    (
        "ck_refund_requests_status_known",
        "status IN ('open', 'granted', 'refunded', 'rejected')",
    ),
    (
        "ck_refund_requests_resolved_when_closed",
        "(status = 'open') = (resolved_at IS NULL)",
    ),
    (
        "ck_refund_requests_refund_names_its_ids",
        (
            "status <> 'refunded' "
            "OR (provider_payment_id IS NOT NULL AND provider_refund_id IS NOT NULL)"
        ),
    ),
    (
        "ck_refund_requests_rejection_has_note",
        "status <> 'rejected' OR note IS NOT NULL",
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "refund_requests", "reason", existing_type=sa.Text(), nullable=False
    )
    op.add_column("refund_requests", sa.Column("note", sa.Text(), nullable=True))
    op.add_column(
        "refund_requests", sa.Column("provider_payment_id", sa.Text(), nullable=True)
    )
    op.add_column(
        "refund_requests", sa.Column("provider_refund_id", sa.Text(), nullable=True)
    )
    op.add_column(
        "refund_requests",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    for name, condition in CHECKS:
        op.create_check_constraint(op.f(name), "refund_requests", sa.text(condition))
    op.create_unique_constraint(
        op.f("uq_refund_requests_provider_refund_id"),
        "refund_requests",
        ["provider_refund_id"],
    )
    op.create_index(
        "uq_refund_requests_open_per_payment",
        "refund_requests",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    """Downgrade schema: refused while any claim is resolved."""
    resolved = op.get_bind().scalar(
        sa.text("select count(*) from refund_requests where status <> 'open'")
    )
    if resolved:
        raise RuntimeError(
            f"{resolved} refund requests are resolved, and their notes and the "
            "gateway's ids would be lost with these columns (D-580)"
        )
    op.drop_index("uq_refund_requests_open_per_payment", table_name="refund_requests")
    op.drop_constraint(
        op.f("uq_refund_requests_provider_refund_id"), "refund_requests", type_="unique"
    )
    for name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(name), "refund_requests", type_="check")
    op.drop_column("refund_requests", "resolved_at")
    op.drop_column("refund_requests", "provider_refund_id")
    op.drop_column("refund_requests", "provider_payment_id")
    op.drop_column("refund_requests", "note")
    op.alter_column("refund_requests", "reason", existing_type=sa.Text(), nullable=True)
