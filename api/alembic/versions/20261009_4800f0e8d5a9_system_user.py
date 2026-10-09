"""system user

Revision ID: 4800f0e8d5a9
Revises: 086fa0402d0d
Create Date: 2026-10-09 18:00:00.000000

The system user (T-9.2, P-20, D-905): who `audit_log.actor_id` names when
nobody did it, as an automatic freeze. `actor_id` is never NULL (T-1.13): NULL
could not tell "the system did it" from "a bug forgot to set it".

Its row is shaped like an erased account, the one shape the checks allow with
no phone number: `deleted`, `anonymised_at` set, no `phone_enc`, no date of
birth, no PIN. So it never signs in (sign-in finds only rows not erased, by an
HMAC of a number, and `system` is no HMAC), never appears where people are
listed (every list asks for `active` and `done`), has no wallet, and its
referral code is outside the alphabet codes are made from, with an owner that
isn't `done`. The erasure skips it: nobody asked for its deletion.

Its id is `app.modules.admin.service.SYSTEM_USER_ID`, written out here rather
than imported, as migrations never import the app; `test_system_user.py` holds
the two to each other.

**The downgrade refuses while `audit_log` names it**: that log is append-only,
and the row it names can't go from under it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4800f0e8d5a9"
down_revision: str | Sequence[str] | None = "086fa0402d0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_USER_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            "insert into users (id, phone_hash, phone_enc, role, status, "
            "onboarding_step, referral_code, anonymised_at) "
            "values (cast(:id as uuid), 'system', null, 'user', 'deleted', 'dob', "
            "'system-user', now()) on conflict (id) do nothing"
        ).bindparams(id=SYSTEM_USER_ID)
    )


def downgrade() -> None:
    """Downgrade schema: refused while the audit log names the system user."""
    bind = op.get_bind()
    named = bind.execute(
        sa.text(
            "select exists (select 1 from audit_log where actor_id = cast(:id as uuid))"
        ).bindparams(id=SYSTEM_USER_ID)
    ).scalar()
    if named:
        raise RuntimeError(
            "audit_log names the system user (T-9.2): the log is append-only, "
            "so the row it names stays. Downgrade refused."
        )
    op.execute(
        sa.text("delete from users where id = cast(:id as uuid)").bindparams(
            id=SYSTEM_USER_ID
        )
    )
