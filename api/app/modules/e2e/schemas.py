from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.modules.auth.schemas import PHONE_INPUT_MAX


class LastCodeQuery(BaseModel):
    # In the body, never the path or query: the request logger binds the path,
    # and uvicorn's access log prints path and query (rule 15).
    phone: Annotated[str, StringConstraints(max_length=PHONE_INPUT_MAX)]


class LastCode(BaseModel):
    """The code the fake provider last sent the number, or null if it never did."""

    code: str | None
