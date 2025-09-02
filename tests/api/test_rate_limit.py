#!/usr/bin/env python3
"""Tests for rate limiting and retry logic."""

import unittest
from unittest.mock import patch

import httpx
from openai import RateLimitError

from artist_bio_gen.api import RateLimiter, call_with_retry


class _DummyResponse:
    class Usage:
        total_tokens = 5

    usage = Usage()


def _build_rate_limit_error(seconds: int = 1) -> RateLimitError:
    response = httpx.Response(
        429,
        headers={"Retry-After": str(seconds)},
        request=httpx.Request("GET", "http://test"),
    )
    return RateLimitError("rate limit", response=response, body=None)


class TestRateLimiter(unittest.TestCase):
    def test_daily_cap_exceeded(self):
        limiter = RateLimiter(rpm=1000, tpm=100000, tpd=20)
        limiter.record(15)
        with self.assertRaises(RuntimeError):
            limiter.wait(tokens_estimate=10)


class TestCallWithRetry(unittest.TestCase):
    def test_retry_after_header(self):
        limiter = RateLimiter(rpm=1000, tpm=100000, tpd=1000000)
        attempts = {"count": 0}

        def func():
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise _build_rate_limit_error(1)
            return _DummyResponse()

        with patch("time.sleep") as sleep:
            result = call_with_retry(func, rate_limiter=limiter, worker_id="T")
            self.assertIsInstance(result, _DummyResponse)
            sleep.assert_any_call(1.0)
            self.assertEqual(attempts["count"], 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
