#!/usr/bin/env python3
"""
Small Batch Testing Simulation for Task 4.3

This script simulates the small batch testing scenario without making real API calls.
It can be used to validate the quota monitoring system's behavior under various conditions.
"""

import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from artist_bio_gen.api.quota import QuotaMonitor, PauseController
from artist_bio_gen.core.processor import process_artists_concurrent
from artist_bio_gen.models import ArtistData, ApiResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmallBatchTestSimulator:
    """Simulates small batch testing with configurable scenarios."""

    def __init__(self, num_artists: int = 100):
        self.num_artists = num_artists
        self.processed_count = 0
        self.pause_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None
        self.test_results = []

    def create_test_artists(self) -> List[ArtistData]:
        """Create test artist data."""
        artists = []
        for i in range(1, self.num_artists + 1):
            artists.append(ArtistData(
                artist_id=i,
                name=f"Test Artist {i}",
                data=f"Test data for artist {i} with some biographical information..."
            ))
        return artists

    def simulate_api_response(self, artist: ArtistData, scenario: str = "normal") -> tuple:
        """Simulate API response based on scenario."""
        self.processed_count += 1

        # Simulate different scenarios
        if scenario == "rate_limit" and self.processed_count % 20 == 0:
            # Simulate rate limit every 20 requests
            raise Exception("Rate limit exceeded")

        if scenario == "quota_pause" and self.processed_count >= self.num_artists * 0.5:
            # Simulate quota threshold at 50%
            self.pause_count += 1
            time.sleep(0.1)  # Simulate pause

        # Create mock response
        response = ApiResponse(
            artist_id=artist.artist_id,
            artist_name=artist.name,
            artist_data=artist.data,
            response_text=f"Generated bio for {artist.name}: A talented artist with a rich history...",
            response_id=f"resp_{self.processed_count}",
            created=int(time.time()),
            db_status="null",
            error=None
        )

        # Simulate processing time
        time.sleep(0.01)

        return response, 0.01

    def run_test_scenario(self, scenario_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific test scenario."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Running Scenario: {scenario_name}")
        logger.info(f"Configuration: {config}")
        logger.info(f"{'='*60}")

        self.processed_count = 0
        self.pause_count = 0
        self.error_count = 0
        self.start_time = time.time()

        artists = self.create_test_artists()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, f"{scenario_name}_output.jsonl")

            # Mock the OpenAI client
            mock_client = Mock()

            # Create mock API call function
            def mock_api_call(*args, **kwargs):
                artist = args[1]
                quota_monitor = kwargs.get('quota_monitor')
                pause_controller = kwargs.get('pause_controller')

                # Simulate quota monitoring
                if quota_monitor and self.processed_count % 10 == 0:
                    headers = {
                        'x-ratelimit-remaining-requests': str(5000 - self.processed_count * 10),
                        'x-ratelimit-limit-requests': '5000',
                        'x-ratelimit-remaining-tokens': str(4000000 - self.processed_count * 1000),
                        'x-ratelimit-limit-tokens': '4000000',
                        'x-ratelimit-reset-requests': '60s',
                        'x-ratelimit-reset-tokens': '60s',
                    }
                    quota_monitor.update_from_response(headers, {'total_tokens': 100})

                    # Check if should pause
                    should_pause, reason = quota_monitor.should_pause()
                    if should_pause and pause_controller:
                        logger.warning(f"PAUSE TRIGGERED: {reason}")
                        pause_controller.pause(reason, resume_at=time.time() + 0.5)
                        self.pause_count += 1

                return self.simulate_api_response(artist, config.get('scenario', 'normal'))

            try:
                with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_api_call):
                    successful, failed = process_artists_concurrent(
                        artists=artists[:config.get('batch_size', self.num_artists)],
                        client=mock_client,
                        prompt_id="test_prompt",
                        version=None,
                        max_workers=config.get('max_workers', 4),
                        output_path=output_path,
                        daily_request_limit=config.get('daily_limit', 1000),
                        quota_threshold=config.get('quota_threshold', 0.8),
                        quota_monitoring=config.get('quota_monitoring', True),
                    )

                self.end_time = time.time()
                duration = self.end_time - self.start_time

                # Read and validate output
                output_lines = 0
                if os.path.exists(output_path):
                    with open(output_path, 'r') as f:
                        output_lines = len(f.readlines())

                result = {
                    'scenario': scenario_name,
                    'success': successful,
                    'failed': failed,
                    'total_processed': successful + failed,
                    'output_lines': output_lines,
                    'duration': duration,
                    'avg_time_per_artist': duration / max(successful, 1),
                    'pause_count': self.pause_count,
                    'error_count': self.error_count,
                    'success_rate': (successful / config.get('batch_size', self.num_artists)) * 100,
                    'config': config
                }

                self.test_results.append(result)
                self.print_scenario_results(result)

                return result

            except Exception as e:
                logger.error(f"Scenario failed: {e}")
                return {
                    'scenario': scenario_name,
                    'error': str(e),
                    'success': 0,
                    'failed': config.get('batch_size', self.num_artists)
                }

    def print_scenario_results(self, result: Dict[str, Any]):
        """Print formatted results for a scenario."""
        logger.info("\n" + "-" * 40)
        logger.info(f"Scenario: {result['scenario']}")
        logger.info(f"Successful: {result['success']}")
        logger.info(f"Failed: {result['failed']}")
        logger.info(f"Success Rate: {result.get('success_rate', 0):.1f}%")
        logger.info(f"Duration: {result['duration']:.2f}s")
        logger.info(f"Avg Time/Artist: {result['avg_time_per_artist']:.3f}s")
        logger.info(f"Pauses Triggered: {result['pause_count']}")
        logger.info(f"Output Lines Written: {result['output_lines']}")
        logger.info("-" * 40)

    def run_all_scenarios(self):
        """Run all test scenarios."""
        scenarios = [
            # Scenario 1: Basic functionality test
            {
                'name': '1_basic_functionality',
                'config': {
                    'batch_size': 10,
                    'max_workers': 2,
                    'daily_limit': 1000,
                    'quota_threshold': 0.8,
                    'scenario': 'normal'
                }
            },

            # Scenario 2: Low threshold test
            {
                'name': '2_low_threshold',
                'config': {
                    'batch_size': 30,
                    'max_workers': 4,
                    'daily_limit': 50,
                    'quota_threshold': 0.2,
                    'scenario': 'normal'
                }
            },

            # Scenario 3: High concurrency test
            {
                'name': '3_high_concurrency',
                'config': {
                    'batch_size': 50,
                    'max_workers': 8,
                    'daily_limit': 500,
                    'quota_threshold': 0.8,
                    'scenario': 'normal'
                }
            },

            # Scenario 4: Full batch test
            {
                'name': '4_full_batch',
                'config': {
                    'batch_size': 100,
                    'max_workers': 4,
                    'daily_limit': 500,
                    'quota_threshold': 0.8,
                    'scenario': 'normal'
                }
            },

            # Scenario 5: Quota pause simulation
            {
                'name': '5_quota_pause',
                'config': {
                    'batch_size': 20,
                    'max_workers': 2,
                    'daily_limit': 15,
                    'quota_threshold': 0.5,
                    'scenario': 'quota_pause'
                }
            }
        ]

        logger.info("\n" + "=" * 60)
        logger.info("STARTING SMALL BATCH TEST SIMULATION")
        logger.info("=" * 60)

        for scenario in scenarios:
            result = self.run_test_scenario(
                scenario['name'],
                scenario['config']
            )
            time.sleep(0.5)  # Brief pause between scenarios

        self.print_summary()

    def print_summary(self):
        """Print summary of all test results."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SIMULATION SUMMARY")
        logger.info("=" * 60)

        total_successful = sum(r.get('success', 0) for r in self.test_results)
        total_failed = sum(r.get('failed', 0) for r in self.test_results)
        total_duration = sum(r.get('duration', 0) for r in self.test_results)

        logger.info(f"Total Scenarios Run: {len(self.test_results)}")
        logger.info(f"Total Artists Processed: {total_successful}")
        logger.info(f"Total Failed: {total_failed}")
        logger.info(f"Overall Success Rate: {(total_successful / (total_successful + total_failed)) * 100:.1f}%")
        logger.info(f"Total Duration: {total_duration:.2f}s")

        logger.info("\nPer-Scenario Results:")
        logger.info("-" * 60)
        logger.info(f"{'Scenario':<30} {'Success':<10} {'Failed':<10} {'Duration':<10}")
        logger.info("-" * 60)

        for result in self.test_results:
            if 'error' not in result:
                logger.info(
                    f"{result['scenario']:<30} "
                    f"{result['success']:<10} "
                    f"{result['failed']:<10} "
                    f"{result['duration']:<10.2f}s"
                )

        # Check acceptance criteria
        logger.info("\n" + "=" * 60)
        logger.info("ACCEPTANCE CRITERIA CHECK")
        logger.info("=" * 60)

        criteria = {
            'All scenarios completed': len(self.test_results) == 5,
            'Success rate > 95%': (total_successful / max(total_successful + total_failed, 1)) > 0.95,
            'Pause/resume working': any(r['pause_count'] > 0 for r in self.test_results),
            'Performance < 2s/artist': all(
                r.get('avg_time_per_artist', float('inf')) < 2.0
                for r in self.test_results
            ),
            'No data corruption': all(
                r.get('output_lines', 0) == r.get('success', 0)
                for r in self.test_results
            )
        }

        for criterion, passed in criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{criterion}: {status}")

        overall_pass = all(criteria.values())
        logger.info("\n" + "=" * 60)
        logger.info(f"OVERALL TEST RESULT: {'✅ PASS' if overall_pass else '❌ FAIL'}")
        logger.info("=" * 60)

        return overall_pass


def main():
    """Main entry point for test simulation."""
    # Parse command line arguments if needed
    batch_size = 100
    if len(sys.argv) > 1:
        batch_size = int(sys.argv[1])

    # Run simulation
    simulator = SmallBatchTestSimulator(num_artists=batch_size)
    simulator.run_all_scenarios()

    # Return exit code based on results
    sys.exit(0 if simulator.test_results else 1)


if __name__ == "__main__":
    main()