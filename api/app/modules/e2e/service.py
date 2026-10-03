"""What the fake SMS provider has 'sent' (T-3.13). No database, no rules."""

from __future__ import annotations

from app.core.errors import AppError
from app.core.providers.sms import FakeSms, SmsProvider
from app.core.security import normalize_phone


def last_code(sms: SmsProvider, typed_phone: str) -> str | None:
    """The last code `sms` sent to the number, typed as a person would type it.

    The fake's own outbox, never the stored code: a number the API sent nothing
    to, a banned one (D-073), gets no code here, exactly as its phone wouldn't.
    """
    if not isinstance(sms, FakeSms):
        # create_app() mounts this only beside the fake; anything else is a bug.
        raise AppError("NOT_FOUND", "Not found.", status=404)
    return sms.last_code(normalize_phone(typed_phone))
