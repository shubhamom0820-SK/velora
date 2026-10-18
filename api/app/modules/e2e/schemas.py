from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.core.enums import Role
from app.core.providers.payments import Outcome
from app.modules.auth.schemas import PHONE_INPUT_MAX


class LastCodeQuery(BaseModel):
    # In the body, never the path or query: the request logger binds the path,
    # and uvicorn's access log prints path and query (rule 15).
    phone: Annotated[str, StringConstraints(max_length=PHONE_INPUT_MAX)]


class LastCode(BaseModel):
    """The code the fake provider last sent the number, or null if it never did."""

    code: str | None


class SimulateWebhook(BaseModel):
    """Which payment's webhook to send, and how it ended. `amount_paise` fakes
    an amount other than the order's, for T-8.2's mismatch."""

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    outcome: Outcome
    amount_paise: Annotated[int, Field(gt=0)] | None = None


class SimulatedWebhook(BaseModel):
    """The HTTP status the API's own webhook route answered the delivery with."""

    delivered_status: int


class ExpiredThread(BaseModel):
    """When the Thread's hour ended: the moment it was asked (D-930)."""

    expires_at: AwareDatetime


class MakeStaff(BaseModel):
    """The staff role to give (D-963): moderator or admin, never user."""

    model_config = ConfigDict(extra="forbid")

    role: Literal[Role.MODERATOR, Role.ADMIN]


class Staff(BaseModel):
    """The role the account now has."""

    role: Role
