"""Web Push notifications (T-9.4)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class PushSubscription:
    endpoint: str
    p256dh: str
    auth: str


# "gone": the browser dropped the subscription (HTTP 404/410), so delete it.
PushOutcome = Literal["sent", "gone"]


class PushProvider(Protocol):
    async def send(
        self, subscription: PushSubscription, payload: Mapping[str, object]
    ) -> PushOutcome: ...


class FakePush:
    """Records every notification. Endpoints in `gone_endpoints` answer "gone"."""

    def __init__(self) -> None:
        self.sent: list[tuple[PushSubscription, dict[str, object]]] = []
        self.gone_endpoints: set[str] = set()

    async def send(
        self, subscription: PushSubscription, payload: Mapping[str, object]
    ) -> PushOutcome:
        if subscription.endpoint in self.gone_endpoints:
            return "gone"
        self.sent.append((subscription, dict(payload)))
        return "sent"


class WebPush:
    """VAPID Web Push. Not built yet."""

    async def send(
        self, subscription: PushSubscription, payload: Mapping[str, object]
    ) -> PushOutcome:
        raise NotImplementedError("Web Push arrives with T-9.4.")
