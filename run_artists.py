#!/usr/bin/env python3
"""
Artist Bio Generator - Entry Point Wrapper

Simple wrapper script that maintains backward compatibility while
the main implementation is now in the artist_bio_gen package.

This script provides the original run_artists.py interface while
delegating all functionality to the refactored package modules.
"""

import sys

def main():
    """Main entry point that delegates to the package CLI."""
    try:
        from artist_bio_gen.cli import main as cli_main
        cli_main()
    except KeyboardInterrupt:
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()