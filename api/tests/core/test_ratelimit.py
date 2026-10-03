"""The sliding window: counts, reopens on time, and says when (core/ratelimit.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType

from redis.asyncio import Redis

from app.core import ratelimit

START = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


async def _hits(redis: Redis, n: int, bucket: str = "203.0.113.7") -> list[bool]:
    return [
        (await ratelimit.hit(redis, "test", bucket, limit=5, window_s=60)).allowed
        for _ in range(n)
    ]


async def test_allows_up_to_the_limit_then_refuses(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)

    assert await _hits(test_redis, 6) == [True, True, True, True, True, False]


async def test_a_refusal_says_how_long_until_the_oldest_try_leaves(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _hits(test_redis, 1)
    clock.advance(timedelta(seconds=20))
    await _hits(test_redis, 4)

    verdict = await ratelimit.hit(
        test_redis, "test", "203.0.113.7", limit=5, window_s=60
    )

    assert verdict == ratelimit.Verdict(allowed=False, retry_after_s=40)


async def test_the_window_slides_rather_than_resetting(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _hits(test_redis, 1)
    clock.advance(timedelta(seconds=30))
    await _hits(test_redis, 4)

    # 61 s after the first try, only it has left the window: one place opens.
    clock.advance(timedelta(seconds=31))
    assert await _hits(test_redis, 2) == [True, False]


async def test_refused_tries_are_not_counted(
    test_redis: Redis, clock: ModuleType
) -> None:
    """Knocking on a closed window doesn't push its reopening further away."""
    clock.freeze(START)
    await _hits(test_redis, 5)
    assert await _hits(test_redis, 20) == [False] * 20

    clock.advance(timedelta(seconds=60))
    assert await _hits(test_redis, 5) == [True] * 5


async def test_each_bucket_and_scope_has_its_own_window(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _hits(test_redis, 5, bucket="203.0.113.7")

    assert await _hits(test_redis, 1, bucket="203.0.113.8") == [True]
    other_scope = await ratelimit.hit(
        test_redis, "another", "203.0.113.7", limit=5, window_s=60
    )
    assert other_scope.allowed


async def test_two_tries_in_the_same_millisecond_count_twice(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)  # frozen: every try lands on the same millisecond

    assert await _hits(test_redis, 6) == [True] * 5 + [False]


async def test_the_key_expires_with_its_window(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _hits(test_redis, 1)

    ttl_ms = await test_redis.pttl(ratelimit.key_for("test", "203.0.113.7"))
    assert 0 < ttl_ms <= 60_000


# --- peek: room left, recording nothing (D-066's wrong-code count) ------------


async def _peek(redis: Redis) -> ratelimit.Verdict:
    return await ratelimit.peek(redis, "test", "203.0.113.7", limit=5, window_s=60)


async def test_peek_records_nothing(test_redis: Redis, clock: ModuleType) -> None:
    clock.freeze(START)
    for _ in range(10):
        assert await _peek(test_redis) == ratelimit.Verdict(True, 0)

    assert await _hits(test_redis, 6) == [True, True, True, True, True, False]


async def test_peek_sees_a_full_window_and_when_it_opens(
    test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _hits(test_redis, 1)
    clock.advance(timedelta(seconds=20))
    await _hits(test_redis, 3)
    assert await _peek(test_redis) == ratelimit.Verdict(True, 0)

    await _hits(test_redis, 1)

    assert await _peek(test_redis) == ratelimit.Verdict(False, 40)
    clock.advance(timedelta(seconds=40))
    assert await _peek(test_redis) == ratelimit.Verdict(True, 0)
