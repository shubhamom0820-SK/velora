"""admin grant names its audit row

Revision ID: 7a758777affd
Revises: 688032b1dc7a
Create Date: 2026-10-16 09:00:02.000000

**Every reason names its ref, `admin_grant` included** (T-9.5, D-923).
97ddae55f597 left `admin_grant`'s ref optional while its only callers were the
seed and `make_user`; from T-9.5 an admin grants Velas, and a grant names the
`audit_log` row its call writes, or it is a grant nobody can trace (at the
direction of the advisor directing Sprint 5, 3 October 2026). The seed and the
tests' grants write a row as the system user (D-905) and name it.

**`NOT VALID`** (the founder on the advisor's recommendation, relayed, 16
October 2026: "never require an infra-reset"). Every new row is checked; the
rows already there are not. A dev
database holds the seed's earlier grants, with no ref, and the ledger refuses
UPDATE and DELETE (T-1.12), so a validated CHECK could never be added there
without dropping the database. Whatever earlier rows any database holds stay
as they were written. A later `VALIDATE CONSTRAINT` would fail wherever such a
row exists, so nothing runs one.

The downgrade puts 97ddae55f597's rule back, validated: the rows that passed the
stricter rule pass the looser one.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a758777affd"
down_revision: str | Sequence[str] | None = "688032b1dc7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_ledger_entries_ref_required"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f(NAME), "ledger_entries")
    op.execute(
        f'ALTER TABLE ledger_entries ADD CONSTRAINT "{NAME}" '
        "CHECK (ref_id IS NOT NULL) NOT VALID"
    )


def downgrade() -> None:
    """Downgrade schema: `admin_grant`'s ref optional again (97ddae55f597)."""
    op.drop_constraint(op.f(NAME), "ledger_entries")
    op.create_check_constraint(
        op.f(NAME), "ledger_entries", "reason = 'admin_grant' OR ref_id IS NOT NULL"
    )
