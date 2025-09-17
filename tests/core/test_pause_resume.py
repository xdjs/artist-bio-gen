#!/usr/bin/env python3
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta

from artist_bio_gen.api.quota import (
    QuotaMonitor,
    PauseController,
    parse_rate_limit_headers,
)


class TestPauseResume(unittest.TestCase):
    def test_quota_monitor_persistence_roundtrip(self):
        qm = QuotaMonitor(daily_limit_requests=100, pause_threshold=0.8)

        # Simulate an update from response
        headers = {
            'x-ratelimit-remaining-requests': '95',
            'x-ratelimit-limit-requests': '100',
            'x-ratelimit-remaining-tokens': '3999000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60s',
            'x-ratelimit-reset-tokens': '60s',
        }
        qm.update_from_response(headers, usage_stats={'total_tokens': 100})

        # Persist and reload
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'quota_state.json')
            qm.persist_state(path)

            qm2 = QuotaMonitor()
            ok = qm2.load_state(path)
            self.assertTrue(ok)
            self.assertEqual(qm2.daily_limit_requests, 100)
            self.assertAlmostEqual(qm2.pause_threshold, 0.8)
            self.assertGreaterEqual(qm2.requests_used_today, 1)
            self.assertIsNotNone(qm2.get_current_status())
            self.assertIsNotNone(qm2.get_current_metrics())

    def test_pause_controller_pause_resume(self):
        pc = PauseController()
        self.assertFalse(pc.is_paused())

        pc.pause("Testing pause")
        self.assertTrue(pc.is_paused())
        self.assertEqual(pc.get_pause_reason(), "Testing pause")

        # wait_if_paused should block until resumed; simulate with a thread
        unblock = []
        def waiter():
            pc.wait_if_paused(timeout=0.2)
            unblock.append(True)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)
        pc.resume("Done")
        t.join(timeout=1.0)
        self.assertTrue(unblock)
        self.assertFalse(pc.is_paused())

    def test_pause_controller_auto_resume(self):
        pc = PauseController()
        pc.pause("Auto", resume_at=time.time() + 0.1)
        self.assertTrue(pc.is_paused())

        # wait_if_paused should auto-resume shortly
        pc.wait_if_paused(timeout=0.5)
        self.assertFalse(pc.is_paused())

    def test_pause_controller_schedule_resume(self):
        pc = PauseController()
        pc.pause("Schedule")
        ts = time.time() + 0.05
        pc.resume_at(ts)
        # It should auto-resume by time
        pc.wait_if_paused(timeout=0.5)
        self.assertFalse(pc.is_paused())


if __name__ == "__main__":
    unittest.main()

