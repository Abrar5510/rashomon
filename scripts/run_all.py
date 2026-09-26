#!/usr/bin/env python3
"""End-to-end: pick -> probes -> witnesses -> score -> history -> leaderboard.

Use --backend-file to replay a recorded session (no API key required).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["run-all", *sys.argv[1:]]))
