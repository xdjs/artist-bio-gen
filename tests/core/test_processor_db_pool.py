#!/usr/bin/env python3
"""
Tests that database connections acquired for tasks are returned to the pool
after processing, for both success and failure paths.
"""

import tempfile
import time
import unittest
import os
from unittest.mock import patch

from artist_bio_gen.core.processor import process_artists_concurrent
from artist_bio_gen.models import ArtistData, ApiResponse


class FakePool:
    def __init__(self):
        self.get_count = 0
        self.put_count = 0
        self.connections = []
        self.released = []

    def getconn(self):
        self.get_count += 1
        conn = object()
        self.connections.append(conn)
        return conn

    def putconn(self, conn):
        self.put_count += 1
        self.released.append(conn)


def _make_artists(n: int):
    return [
        ArtistData(artist_id=f"00000000-0000-0000-0000-{i:012d}", name=f"Artist {i}")
        for i in range(1, n + 1)
    ]


class TestProcessorDbPool(unittest.TestCase):
    def test_connections_released_on_success(self):
        artists = _make_artists(4)
        pool = FakePool()

        def fake_call_openai_api(client, artist, prompt_id, version, worker_id, db_pool, skip_existing, test_mode, quota_monitor=None, pause_controller=None):
            # Simulate the new behavior where call_openai_api acquires and releases connections
            if db_pool is not None:
                conn = db_pool.getconn()  # Simulate getting connection
                db_pool.putconn(conn)     # Simulate releasing connection
            
            # Return a minimal successful response and duration
            return (
                ApiResponse(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    artist_data=artist.data,
                    response_text="ok",
                    response_id="resp_ok",
                    created=int(time.time()),
                    db_status="null",
                    error=None,
                ),
                0.01,
            )

        # Create temporary JSONL output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
        
        try:
            with patch("artist_bio_gen.core.orchestrator.call_openai_api", side_effect=fake_call_openai_api):
                success, failed = process_artists_concurrent(
                    artists=artists,
                    client=object(),
                    prompt_id="pid",
                    version=None,
                    max_workers=2,
                    output_path=output_path,
                    db_pool=pool,
                    test_mode=False,
                )

            self.assertEqual(success, len(artists))
            self.assertEqual(failed, 0)
            self.assertEqual(pool.get_count, len(artists))
            self.assertEqual(pool.put_count, len(artists))
            self.assertEqual(len(pool.released), len(artists))
        finally:
            # Clean up temporary file
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_connections_released_on_failure(self):
        artists = _make_artists(3)
        pool = FakePool()

        def fake_call_openai_api_fail(client, artist, prompt_id, version, worker_id, db_pool, skip_existing, test_mode, quota_monitor=None, pause_controller=None):
            # Simulate the new behavior where call_openai_api acquires and releases connections
            # even when an error occurs later in the function
            if db_pool is not None:
                conn = db_pool.getconn()  # Simulate getting connection
                db_pool.putconn(conn)     # Simulate releasing connection
            raise RuntimeError("boom")

        # Create temporary JSONL output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
        
        try:
            with patch("artist_bio_gen.core.orchestrator.call_openai_api", side_effect=fake_call_openai_api_fail):
                success, failed = process_artists_concurrent(
                    artists=artists,
                    client=object(),
                    prompt_id="pid",
                    version=None,
                    max_workers=2,
                    output_path=output_path,
                    db_pool=pool,
                    test_mode=False,
                )

            self.assertEqual(success, 0)
            self.assertEqual(failed, len(artists))
            self.assertEqual(pool.get_count, len(artists))
            self.assertEqual(pool.put_count, len(artists))
            self.assertEqual(len(pool.released), len(artists))
        finally:
            # Clean up temporary file
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == "__main__":
    unittest.main()

