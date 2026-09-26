#!/usr/bin/env python3
"""Steps 2+4 - generate probe inputs and run the function for real."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["probes", *sys.argv[1:]]))
