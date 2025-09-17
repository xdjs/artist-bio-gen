#!/usr/bin/env python3
import time
import unittest

from artist_bio_gen.api.operations import call_openai_api
from artist_bio_gen.api.quota import QuotaMonitor, PauseController
from artist_bio_gen.models import ArtistData


class DummyParsed:
    def __init__(self, text="Hello", rid="resp_1", created=1234567890, usage=None):
        self.output_text = text
        self.id = rid
        self.created_at = created
        self.usage = usage or {"total_tokens": 123}


class DummyRaw:
    def __init__(self, headers, parsed):
        self.headers = headers
        self._parsed = parsed

    def parse(self):
        return self._parsed


class DummyResponses:
    def __init__(self, headers, parsed):
        self._raw = DummyRaw(headers=headers, parsed=parsed)

        class _WithRaw:
            def __init__(self, raw):
                self._raw = raw

            def create(self, prompt):
                return self._raw

        self.with_raw_response = _WithRaw(self._raw)

    def create(self, prompt):
        # Fallback path: return parsed directly
        return self._raw.parse()


class DummyClient:
    def __init__(self, headers, parsed):
        self.responses = DummyResponses(headers=headers, parsed=parsed)


class TestOperationsQuotaIntegration(unittest.TestCase):
    def test_call_openai_api_updates_quota_monitor(self):
        headers = {
            'x-ratelimit-remaining-requests': '999',
            'x-ratelimit-limit-requests': '1000',
            'x-ratelimit-remaining-tokens': '4000000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60',
            'x-ratelimit-reset-tokens': '3600'
        }
        parsed = DummyParsed()
        client = DummyClient(headers=headers, parsed=parsed)

        monitor = QuotaMonitor(daily_limit_requests=1000, pause_threshold=0.8)
        controller = PauseController()

        artist = ArtistData(artist_id="00000000-0000-0000-0000-000000000000", name="Test", data="")

        api_resp, duration = call_openai_api(
            client=client,
            artist=artist,
            prompt_id="p-123",
            worker_id="W01",
            db_pool=None,
            skip_existing=True,
            test_mode=True,
            quota_monitor=monitor,
            pause_controller=controller,
        )

        self.assertEqual(api_resp.response_text, "Hello")
        self.assertGreater(duration, 0.0)
        # Quota monitor should have recorded the request
        self.assertEqual(monitor.requests_used_today, 1)
        self.assertIsNotNone(monitor.get_current_status())
        self.assertIsNotNone(monitor.get_current_metrics())


if __name__ == "__main__":
    unittest.main()

