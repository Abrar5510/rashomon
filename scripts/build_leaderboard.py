#!/usr/bin/env python3
"""Build web/data.json for the leaderboard."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["leaderboard", *sys.argv[1:]]))
