#!/usr/bin/env python3
"""
Enable execution of the artist_bio_gen package as a module.

This allows running the package with: python -m artist_bio_gen
"""

from .cli.main import main

if __name__ == "__main__":
    main()