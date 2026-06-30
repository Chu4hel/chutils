import threading
import time

import pytest

from chutils import rate_limit, RateLimitExceededError
from chutils.decorators import clear_limiters, TokenBucket, LeakyBucket


@pytest.fixture(autouse=True)
def cleanup():
    clear_limiters()


def test_token_bucket_refill():
    bucket = TokenBucket(capacity=2, period=1.0)

    assert bucket.acquire() == 0.0
    assert bucket.acquire() == 0.0
    assert bucket.acquire() is None

    time.sleep(0.5)
    assert bucket.acquire() == 0.0
    assert bucket.acquire() is None


def test_leaky_bucket_smoothing():
    bucket = LeakyBucket(capacity=2, period=1.0)

    assert bucket.acquire() == 0.0
    assert bucket.acquire() == 0.0
    assert bucket.acquire() is None

    time.sleep(0.5)
    assert bucket.acquire() == 0.0
    assert bucket.acquire() is None


def test_sync_rate_limit_fail_fast():
    calls = 0

    @rate_limit(max_calls=2, period=1.0, wait=False)
    def my_func():
        nonlocal calls
        calls += 1
        return calls

    assert my_func() == 1
    assert my_func() == 2

    with pytest.raises(RateLimitExceededError):
        my_func()


def test_sync_rate_limit_wait():
    calls = 0

    @rate_limit(max_calls=2, period=0.5, wait=True)
    def my_func():
        nonlocal calls
        calls += 1
        return calls

    start = time.monotonic()
    assert my_func() == 1
    assert my_func() == 2

    assert my_func() == 3
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2


@pytest.mark.asyncio
async def test_async_rate_limit_fail_fast():
    calls = 0

    @rate_limit(max_calls=2, period=1.0, wait=False)
    async def my_func():
        nonlocal calls
        calls += 1
        return calls

    assert await my_func() == 1
    assert await my_func() == 2

    with pytest.raises(RateLimitExceededError):
        await my_func()


@pytest.mark.asyncio
async def test_async_rate_limit_wait():
    calls = 0

    @rate_limit(max_calls=2, period=0.5, wait=True)
    async def my_func():
        nonlocal calls
        calls += 1
        return calls

    start = time.monotonic()
    assert await my_func() == 1
    assert await my_func() == 2

    assert await my_func() == 3
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2


def test_rate_limit_key_func():
    calls = {}

    @rate_limit(max_calls=1, period=1.0, key_func=lambda user_id: f"user_{user_id}")
    def test_func(user_id):
        calls[user_id] = calls.get(user_id, 0) + 1

    test_func(user_id=1)
    test_func(user_id=2)

    with pytest.raises(RateLimitExceededError):
        test_func(user_id=1)

    with pytest.raises(RateLimitExceededError):
        test_func(user_id=2)


def test_thread_safety():
    calls = 0
    errors = []

    @rate_limit(max_calls=10, period=1.0, wait=False)
    def my_func():
        nonlocal calls
        calls += 1

    def worker():
        try:
            my_func()
        except RateLimitExceededError:
            errors.append(1)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == 10
    assert len(errors) == 10
