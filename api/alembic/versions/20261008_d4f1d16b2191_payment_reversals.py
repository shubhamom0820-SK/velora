"""payment reversals

Revision ID: d4f1d16b2191
Revises: 9a3d5384d962
Create Date: 2026-10-08 21:00:01.000000

P-420 closed (T-8.3, D-581): every refund and dispute the webhook handles is
recorded here, once, by its own Razorpay id (`rfnd_…`, `disp_…`), with what its
reversal took and what it couldn't. A reversal that found a balance of 0 writes
nothing to the ledger (an entry can't be 0), so before this a redelivery of
that refund, after he had bought Velas again, took from the new ones. Now the
record is the repeat check, whatever was taken.

Append-only, like the ledger it explains: UPDATE, DELETE and TRUNCATE are
refused by T-1.12's `refuse_change()`, and the app role has no UPDATE or DELETE
on it (`tests/test_app_role.py`). Keyed to `payments` only, never to `users`:
an erasure (D-500) neither takes it nor needs to.

The downgrade refuses while any row exists: the records are a payment's
(rule 12).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f1d16b2191"
down_revision: str | Sequence[str] | None = "9a3d5384d962"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "velora_app"

GUARDS = (
    # (trigger name, timing and events, level), T-1.12's pattern
    ("payment_reversals_no_update_delete", "before update or delete", "row"),
    ("payment_reversals_no_truncate", "before truncate", "statement"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_reversals",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("provider_ref", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("taken", sa.Integer(), nullable=False),
        sa.Column("shortfall", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('refund', 'dispute')",
            name=op.f("ck_payment_reversals_kind_known"),
        ),
        sa.CheckConstraint(
            "taken >= 0", name=op.f("ck_payment_reversals_taken_non_negative")
        ),
        sa.CheckConstraint(
            "shortfall >= 0", name=op.f("ck_payment_reversals_shortfall_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_reversals_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_reversals")),
        sa.UniqueConstraint(
            "provider_ref", name=op.f("uq_payment_reversals_provider_ref")
        ),
    )
    for name, when, level in GUARDS:
        op.execute(
            sa.text(
                f"create trigger {name} {when} on payment_reversals "
                f"for each {level} execute function refuse_change()"
            )
        )
    op.execute(sa.text(f"revoke update, delete on payment_reversals from {APP_ROLE}"))


def downgrade() -> None:
    """Downgrade schema: refused while any reversal is recorded."""
    recorded = op.get_bind().scalar(sa.text("select count(*) from payment_reversals"))
    if recorded:
        raise RuntimeError(
            f"{recorded} payment reversals are recorded, and a payment's records "
            "are never deleted (rule 12, D-581)"
        )
    op.drop_table("payment_reversals")
