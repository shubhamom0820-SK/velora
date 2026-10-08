"""Real time — the ticket (04-API.md, T-7.4)."""

from __future__ import annotations

from pydantic import BaseModel


class WsTicket(BaseModel):
    """Opens one socket, once, within 30 seconds: `/ws?ticket=`."""

    ticket: str
