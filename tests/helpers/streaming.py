#!/usr/bin/env python3
"""
Helper functions for streaming tests.

These helpers ensure that mocked API calls properly stream output
when the ResponseProcessor pipeline is bypassed.
"""

from artist_bio_gen.core.output import append_jsonl_response
from artist_bio_gen.models import ApiResponse


def create_streaming_mock(original_mock):
    """
    Wraps a mock function to add streaming behavior.

    This is needed when mocking call_openai_api because the real function
    now uses ResponseProcessor which handles streaming, but mocks bypass that.

    Args:
        original_mock: The original mock function

    Returns:
        Wrapped function that streams output
    """
    def streaming_wrapper(*args, **kwargs):
        # call_openai_api signature:
        # (client, artist, prompt_id, version, worker_id, db_pool,
        #  skip_existing, test_mode, quota_monitor, pause_controller, output_path)
        # output_path is the 11th positional argument (index 10)

        # Get output_path from positional args or kwargs
        output_path = None
        if len(args) > 10:
            output_path = args[10]
        elif 'output_path' in kwargs:
            output_path = kwargs['output_path']

        # Get prompt_id and version
        prompt_id = args[2] if len(args) > 2 else kwargs.get('prompt_id', 'test')
        version = args[3] if len(args) > 3 else kwargs.get('version')

        # Call the original mock
        result = original_mock(*args, **kwargs)

        # If it returns a tuple (ApiResponse, duration), extract the response
        if isinstance(result, tuple) and len(result) == 2:
            api_response, duration = result
        else:
            api_response = result
            duration = 0.01

        # Stream to output file if path provided
        if output_path and isinstance(api_response, ApiResponse):
            try:
                append_jsonl_response(api_response, output_path, prompt_id, version)
            except Exception as e:
                # Log but don't fail tests
                print(f"Warning: Failed to stream to {output_path}: {e}")

        # Return the original result
        return result if isinstance(result, tuple) else (api_response, duration)

    return streaming_wrapper