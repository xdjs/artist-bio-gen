#!/usr/bin/env python3
"""
Artist Bio Generator - Entry Point Wrapper

Simple wrapper script that maintains backward compatibility while
the main implementation is now in the artist_bio_gen package.
"""

import sys
from artist_bio_gen.main import *

if __name__ == "__main__":
    sys.exit(main())