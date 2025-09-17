#!/usr/bin/env python3
import builtins
import time as _time
import types
import unittest
from typing import Any, Dict

from artist_bio_gen.api.utils import (
    classify_error,
    compute_backoff,
    retry_with_exponential_backoff,
)


class DummyHTTPError(Exception):
    """A dummy exception simulating OpenAI SDK exceptions with flexible attrs."""

    def __init__(self, status=None, code=None, headers=None):
        super().__init__(f"status={status} code={code}")
        self.status_code = status
        self.status = status
        self.http_status = status
        self.code = code
        self.headers = headers or {}


class EnhancedBackoffTests(unittest.TestCase):
    def setUp(self) -> None:
        # Freeze random to deterministic midpoint so jitter factor = 1.0
        self._orig_random = __import__("random").random
        __import__("random").random = lambda: 0.5

        # Capture sleeps
        self.sleeps: list[float] = []
        self._orig_sleep = _time.sleep

        def _fake_sleep(x: float):
            self.sleeps.append(x)

        _time.sleep = _fake_sleep

    def tearDown(self) -> None:
        # Restore patched functions
        __import__("random").random = self._orig_random
        _time.sleep = self._orig_sleep

    def test_classify_rate_limit_with_retry_after(self):
        exc = DummyHTTPError(status=429, headers={"retry-after": "42"})
        c = classify_error(exc)
        self.assertEqual(c.kind, "rate_limit")
        self.assertTrue(c.should_retry)
        self.assertEqual(c.retry_after, 42)

    def test_classify_insufficient_quota(self):
        exc = DummyHTTPError(status=429, code="insufficient_quota")
        c = classify_error(exc)
        self.assertEqual(c.kind, "quota")
        self.assertTrue(c.should_retry)

    def test_classify_server_error_503(self):
        exc = DummyHTTPError(status=503, headers={"Retry-After": "7"})
        c = classify_error(exc)
        self.assertEqual(c.kind, "server")
        self.assertTrue(c.should_retry)
        self.assertEqual(c.retry_after, 7)

    def test_classify_network_timeout(self):
        exc = TimeoutError("timeout")
        c = classify_error(exc)
        self.assertEqual(c.kind, "network")
        self.assertTrue(c.should_retry)

    def test_compute_backoff_rate_limit_uses_retry_after_first_attempt(self):
        delay = compute_backoff(0, kind="rate_limit", retry_after=11)
        self.assertAlmostEqual(delay, 11.0, places=6)

    def test_compute_backoff_quota_caps(self):
        # attempt 0 => 300; 1 => 600; 2 => 1200; 3 => 2400; 4 => 3600 (cap)
        delays = [compute_backoff(i, kind="quota") for i in range(5)]
        expected = [300.0, 600.0, 1200.0, 2400.0, 3600.0]
        for got, exp in zip(delays, expected):
            self.assertAlmostEqual(got, exp, places=6)

    def test_retry_decorator_respects_rate_limit_backoff(self):
        # Function raises rate limit twice, then succeeds
        state = {"count": 0}

        @retry_with_exponential_backoff(max_retries=5)
        def flaky_fn():
            if state["count"] < 2:
                state["count"] += 1
                raise DummyHTTPError(status=429, headers={"retry-after": "5"})
            return "ok"

        result = flaky_fn()
        self.assertEqual(result, "ok")
        # With deterministic jitter, first delay uses retry-after 5, second uses 120 (base 60 x 2)
        self.assertGreaterEqual(len(self.sleeps), 2)
        self.assertAlmostEqual(self.sleeps[0], 5.0, places=6)
        self.assertAlmostEqual(self.sleeps[1], 120.0, places=6)


if __name__ == "__main__":
    unittest.main()
