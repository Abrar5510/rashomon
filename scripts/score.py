#!/usr/bin/env python3
"""Steps 3+4 - ask the witnesses, then score their predictions against the run.

Pass --witness-file to replay a recorded session instead of calling a model.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402


def _drop(argv, *flags):
    out, i = [], 0
    while i < len(argv):
        if argv[i] in flags:
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out


if __name__ == "__main__":
    argv = sys.argv[1:]
    has_recorded = "--witness-file" in argv
    rc = main(["witness", *(["--backend", "file"] if has_recorded else []), *argv])
    if rc:
        raise SystemExit(rc)
    raise SystemExit(main(["score", *_drop(argv, "--witness-file", "--backend")]))
