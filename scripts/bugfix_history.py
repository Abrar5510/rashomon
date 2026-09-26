#!/usr/bin/env python3
"""Step 7 - how often has each function been touched by a bug-fix commit?"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["history", *sys.argv[1:]]))
