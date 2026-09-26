#!/usr/bin/env python3
"""Step 1 - pick functions from a git diff, from churn, or from the tree."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["pick", *sys.argv[1:]]))
