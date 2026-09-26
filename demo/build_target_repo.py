#!/usr/bin/env python3
"""Build demo/target_repo (a small library with a real bug-fix history).

Run: python3 demo/build_target_repo.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "target_repo")

PARSING = '''"""Duration and HTTP header parsing."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_duration(text):
    """Parse a compact duration such as '1h30m' into whole seconds."""
    units = {"s": 1, "m": 60, "h": 3600}
    total = 0
    pending = ""
    for ch in text:
        if ch.isdigit():
            pending += ch
        else:
            total += int(pending) * units[ch]
            pending = ""
    return total


def parse_retry_after(headers):
    """Seconds a client should wait, read from a Retry-After header."""
    raw = str(headers.get("Retry-After", "0")).strip()
    if raw.isdigit():
        return int(raw)
    when = parsedate_to_datetime(raw)
    delta = when - datetime.now(timezone.utc)
    return int(delta.total_seconds())
'''

PARSING_FIX_DAYS = PARSING.replace(
    'units = {"s": 1, "m": 60, "h": 3600}',
    'units = {"s": 1, "m": 60, "h": 3600, "d": 86400}',
)

PARSING_FIX_DATE = PARSING_FIX_DAYS.replace(
    "    return int(delta.total_seconds())",
    "    return max(0, int(delta.total_seconds()))",
)

TEXT = '''"""String helpers."""


def slugify(text):
    """Turn arbitrary text into a url-safe slug."""
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return "".join(out).strip("-")


def is_palindrome(text):
    """True when the text reads the same forwards and backwards."""
    return text.lower() == text.lower()[::-1]
'''

TEXT_FIX_SLUG = TEXT.replace(
    """        else:
            out.append("-")
    return "".join(out).strip("-")""",
    """        else:
            if out and out[-1] != "-":
                out.append("-")
    return "".join(out).strip("-")""",
)

TEXT_FIX_PALIN = TEXT_FIX_SLUG.replace(
    """    return text.lower() == text.lower()[::-1]""",
    """    clean = [ch for ch in text.lower() if ch.isalnum()]
    return clean == clean[::-1]""",
)

SEQ = '''"""Sequence helpers."""


def chunk(seq, size):
    """Split a sequence into consecutive blocks of `size`."""
    out = []
    for i in range(0, len(seq), size):
        out.append(seq[i:i + size])
    return out


def flatten(nested):
    """Flatten arbitrarily nested lists into a single list."""
    out = []
    for item in nested:
        if isinstance(item, (list, str)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out


def merge_intervals(intervals):
    """Merge overlapping [start, end] intervals."""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [tuple(pair) for pair in merged]
'''

SEQ_FIX_FLATTEN = SEQ.replace(
    "        if isinstance(item, (list, str)):",
    "        if isinstance(item, list):",
)

SEQ_FIX_CHUNK = SEQ_FIX_FLATTEN.replace(
    """    out = []
    for i in range(0, len(seq), size):""",
    """    if size <= 0:
        raise ValueError("size must be positive")
    out = []
    for i in range(0, len(seq), size):""",
)

SEQ_FIX_MERGE = SEQ_FIX_CHUNK.replace(
    "        if start < merged[-1][1]:",
    "        if start <= merged[-1][1]:",
)

NUM = '''"""Numeric helpers."""


def clamp(value, low, high):
    """Force a value into the inclusive range [low, high]."""
    return min(high, value)


def mean(values):
    """Arithmetic mean of a list of numbers."""
    return sum(values) / len(values)
'''

NUM_FIX_CLAMP = NUM.replace(
    "    return min(high, value)",
    "    return max(low, min(high, value))",
)

NUM_FIX_MEAN = NUM_FIX_CLAMP.replace(
    "    return sum(values) / len(values)",
    """    if not values:
        return 0.0
    return sum(values) / len(values)""",
)

TESTS = '''import pytest

from chronex.num import clamp, mean
from chronex.parsing import parse_duration, parse_retry_after
from chronex.seq import chunk, flatten, merge_intervals
from chronex.text import is_palindrome, slugify


def test_parse_duration():
    assert parse_duration("45s") == 45
    assert parse_duration("1h30m") == 5400
    assert parse_duration("2d4h") == 187200


def test_parse_duration_unknown_unit():
    with pytest.raises(KeyError):
        parse_duration("5w")


def test_parse_retry_after_seconds():
    assert parse_retry_after({"Retry-After": "120"}) == 120


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  a  --  b  ") == "a-b"


def test_is_palindrome():
    assert is_palindrome("A man, a plan, a canal: Panama")
    assert not is_palindrome("python")


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    with pytest.raises(ValueError):
        chunk([1], 0)


def test_flatten():
    assert flatten([[1, [2, [3]]], 4]) == [1, 2, 3, 4]


def test_merge_intervals():
    assert merge_intervals([(1, 3), (2, 6), (8, 10)]) == [(1, 6), (8, 10)]
    assert merge_intervals([(1, 2), (2, 3)]) == [(1, 3)]


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-3, 0, 10) == 0
    assert clamp(99, 0, 10) == 10


def test_mean():
    assert mean([1, 2, 3, 4]) == 2.5
    assert mean([]) == 0.0
'''

README = """# chronex

Small, deliberately ordinary helpers. Used as the Rashomon demo target.
"""

STAGES: list[tuple[str, dict[str, str]]] = [
    ("feat: initial chronex helpers", {
        "chronex/__init__.py": '"""chronex - tiny duration, text and sequence helpers."""\n',
        "chronex/parsing.py": PARSING,
        "chronex/text.py": TEXT,
        "chronex/seq.py": SEQ,
        "chronex/num.py": NUM,
        "README.md": README,
    }),
    ("fix: parse_duration ignored the 'd' suffix", {"chronex/parsing.py": PARSING_FIX_DAYS}),
    ("fix: clamp ignored the lower bound", {"chronex/num.py": NUM_FIX_CLAMP}),
    ("fix: flatten recursed into strings", {"chronex/seq.py": SEQ_FIX_FLATTEN}),
    ("fix: slugify produced repeated dashes", {"chronex/text.py": TEXT_FIX_SLUG}),
    ("fix: chunk blew the stack on size=0", {"chronex/seq.py": SEQ_FIX_CHUNK}),
    ("fix: merge_intervals split adjacent ranges", {"chronex/seq.py": SEQ_FIX_MERGE}),
    ("fix: is_palindrome choked on punctuation", {"chronex/text.py": TEXT_FIX_PALIN}),
    ("fix: parse_retry_after returned a negative delay", {"chronex/parsing.py": PARSING_FIX_DATE}),
    ("fix: mean raised ZeroDivisionError on empty input", {"chronex/num.py": NUM_FIX_MEAN}),
    ("test: cover the helpers", {"tests/test_chronex.py": TESTS}),
]


def git(*args: str) -> None:
    subprocess.run(
        ["git", "-C", REPO, *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "Rashomon Demo", "GIT_AUTHOR_EMAIL": "demo@example.com",
             "GIT_COMMITTER_NAME": "Rashomon Demo", "GIT_COMMITTER_EMAIL": "demo@example.com"},
    )


def main() -> int:
    if os.path.isdir(REPO):
        shutil.rmtree(REPO)
    os.makedirs(REPO)
    git("init", "-q", "-b", "main")
    for message, files in STAGES:
        for rel, content in files.items():
            abs_path = os.path.join(REPO, rel)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as fh:
                fh.write(content)
        git("add", "-A")
        git("commit", "-q", "-m", message)
    print(f"built {REPO} with {len(STAGES)} commits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
