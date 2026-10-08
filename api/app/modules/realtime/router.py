"""Real time (T-7.4): a ticket by REST, then the socket that uses it."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from redis.asyncio import Redis

from app.core.db import SessionOpener, session_opener
from app.core.deps import app_redis, onboarded_user, user_rate_limit
from app.modules.realtime import service
from app.modules.realtime.schemas import WsTicket
from app.modules.users.models import User

router = APIRouter(tags=["realtime"])
# The socket, at the root as §6 has it (`wss://api…/ws`), never under /v1.
gateway = APIRouter()

# A reconnect with backoff (T-7.12) asks for a few a minute; a script, more.
TICKETS_PER_MINUTE = 30


@router.post(
    "/ws/ticket",
    dependencies=[
        Depends(user_rate_limit("ws_ticket", limit=TICKETS_PER_MINUTE, window_s=60))
    ],
)
async def ticket(
    user: Annotated[User, Depends(onboarded_user)],
    redis: Annotated[Redis, Depends(app_redis)],
) -> WsTicket:
    return WsTicket(ticket=await service.issue(redis, user.id))


@gateway.websocket("/ws")
async def socket(
    websocket: WebSocket,
    open_session: Annotated[SessionOpener, Depends(session_opener)],
) -> None:
    await service.serve(websocket, open_session)
