#!/usr/bin/env python3
"""Record the offline demo session: probe inputs + five witness readings.

The probe inputs are hand-picked (the kind an LLM would propose). The witness
answers are a *recorded* session: every prediction is authored against the real
source, with the disagreements written down explicitly in CONFUSIONS.

Run: python3 demo/fixtures/make_fixtures.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.join(ROOT, "target_repo")
sys.path.insert(0, os.path.dirname(ROOT))

from rashomon import WITNESS_PERSONAS  # noqa: E402
from rashomon.astx import PickFilters, extract_from_files  # noqa: E402
from rashomon.runner import run_case  # noqa: E402

REPO = os.path.abspath(REPO)

PROBES: dict[str, list[dict]] = {
    "chronex/parsing.py::parse_duration": [
        {"args": ["1h30m"], "kwargs": {}, "label": "typical"},
        {"args": ["45s"], "kwargs": {}, "label": "simple"},
        {"args": ["2d4h"], "kwargs": {}, "label": "day-suffix"},
    ],
    "chronex/parsing.py::parse_retry_after": [
        {"args": [{"Retry-After": "120"}], "kwargs": {}, "label": "seconds"},
        {"args": [{}], "kwargs": {}, "label": "header-missing"},
        {"args": [{"Retry-After": " 5 "}], "kwargs": {}, "label": "padded"},
    ],
    "chronex/text.py::slugify": [
        {"args": ["Hello, World!"], "kwargs": {}, "label": "punctuation"},
        {"args": ["  a  --  b  "], "kwargs": {}, "label": "repeats"},
        {"args": ["\u00dcn\u00efcode 42"], "kwargs": {}, "label": "unicode"},
    ],
    "chronex/text.py::is_palindrome": [
        {"args": ["A man, a plan, a canal: Panama"], "kwargs": {}, "label": "punctuated"},
        {"args": ["racecar"], "kwargs": {}, "label": "plain"},
        {"args": ["Was it a car or a cat I saw?"], "kwargs": {}, "label": "question"},
    ],
    "chronex/seq.py::chunk": [
        {"args": [[1, 2, 3, 4, 5], 2], "kwargs": {}, "label": "even-split"},
        {"args": [[], 3], "kwargs": {}, "label": "empty"},
        {"args": [[1, 2, 3], 10], "kwargs": {}, "label": "size>len"},
    ],
    "chronex/seq.py::flatten": [
        {"args": [[[1, [2, [3]]], 4]], "kwargs": {}, "label": "deep"},
        {"args": [[]], "kwargs": {}, "label": "empty"},
        {"args": [["ab", ["cd"]]], "kwargs": {}, "label": "strings"},
    ],
    "chronex/seq.py::merge_intervals": [
        {"args": [[(1, 3), (2, 6), (8, 10), (15, 18)]], "kwargs": {}, "label": "overlap"},
        {"args": [[]], "kwargs": {}, "label": "empty"},
        {"args": [[(1, 2), (2, 3), (4, 5)]], "kwargs": {}, "label": "adjacent"},
    ],
    "chronex/num.py::clamp": [
        {"args": [5, 0, 10], "kwargs": {}, "label": "inside"},
        {"args": [-3, 0, 10], "kwargs": {}, "label": "below"},
        {"args": [99, 0, 10], "kwargs": {}, "label": "above"},
    ],
    "chronex/num.py::mean": [
        {"args": [[1, 2, 3, 4]], "kwargs": {}, "label": "typical"},
        {"args": [[]], "kwargs": {}, "label": "empty"},
        {"args": [[0.5, 1.5]], "kwargs": {}, "label": "floats"},
    ],
}

# (function key, probe index, witness) -> a prediction that does NOT match the run.
CONFUSIONS: dict[tuple[str, int, str], str] = {
    # parse_duration: '1h30m' -> 5400, '45s' -> 45, '2d4h' -> 187200
    ("chronex/parsing.py::parse_duration", 0, "speed-reader"): "90",
    ("chronex/parsing.py::parse_duration", 0, "regex-allergic"): "3600",
    ("chronex/parsing.py::parse_duration", 0, "api-historian"): "'1h30m'",
    ("chronex/parsing.py::parse_duration", 1, "regex-allergic"): "0",
    ("chronex/parsing.py::parse_duration", 2, "api-historian"): "7200",
    ("chronex/parsing.py::parse_duration", 2, "speed-reader"): "14400",
    ("chronex/parsing.py::parse_duration", 2, "edge-case-hunter"): "0",
    # parse_retry_after: 120 / 0 / 5
    ("chronex/parsing.py::parse_retry_after", 0, "regex-allergic"): "'120'",
    ("chronex/parsing.py::parse_retry_after", 1, "api-historian"): "None",
    ("chronex/parsing.py::parse_retry_after", 2, "speed-reader"): "'5 '",
    ("chronex/parsing.py::parse_retry_after", 2, "edge-case-hunter"): "ValueError",
    # slugify
    ("chronex/text.py::slugify", 0, "api-historian"): "'hello_world'",
    ("chronex/text.py::slugify", 1, "speed-reader"): "'a--b'",
    # is_palindrome
    ("chronex/text.py::is_palindrome", 0, "speed-reader"): "False",
    # chunk
    ("chronex/seq.py::chunk", 1, "edge-case-hunter"): "None",
    ("chronex/seq.py::chunk", 2, "speed-reader"): "[]",
    # flatten
    ("chronex/seq.py::flatten", 2, "speed-reader"): "['a', 'b', 'c', 'd']",
    ("chronex/seq.py::flatten", 2, "regex-allergic"): "['a', 'b', 'c', 'd']",
    # merge_intervals
    ("chronex/seq.py::merge_intervals", 1, "edge-case-hunter"): "None",
    ("chronex/seq.py::merge_intervals", 2, "speed-reader"): "[(1, 2), (2, 3), (4, 5)]",
    # clamp
    ("chronex/num.py::clamp", 1, "speed-reader"): "-3",
    # mean: nobody misreads it
}

SUMMARIES: dict[str, dict[str, str]] = {
    "chronex/parsing.py::parse_duration": {
        "careful-stylist": "Splits a compact duration on unit letters and sums seconds.",
        "speed-reader": "Adds up numbers it finds in a string.",
        "regex-allergic": "Walks the string, accumulating a total whenever it hits a unit letter.",
        "api-historian": "Converts a friendly duration string into seconds.",
        "edge-case-hunter": "Converts units to seconds; unknown unit letters raise KeyError.",
    },
    "chronex/parsing.py::parse_retry_after": {
        "careful-stylist": "Reads Retry-After as delta-seconds, or parses it as an HTTP date.",
        "speed-reader": "Pulls a wait time out of a response header.",
        "regex-allergic": "Returns the header value if it is all digits, otherwise treats it as a date.",
        "api-historian": "Standard Retry-After handling: seconds or HTTP-date.",
        "edge-case-hunter": "Defaults to 0 when the header is absent; clamps negative delays to 0.",
    },
    "chronex/text.py::slugify": {
        "careful-stylist": "Lowercases, keeps alphanumerics, and joins runs with single dashes.",
        "speed-reader": "Turns text into a url slug.",
        "regex-allergic": "Emits a dash for every non-alphanumeric character.",
        "api-historian": "Classic slugify: lowercase, strip, dash-separate.",
        "edge-case-hunter": "Collapses runs of separators and strips leading/trailing dashes.",
    },
    "chronex/text.py::is_palindrome": {
        "careful-stylist": "Compares the lowercased string with its reverse.",
        "speed-reader": "Checks a string against its reverse.",
        "regex-allergic": "Strips everything but letters and digits first, then compares reversed.",
        "api-historian": "Palindrome test ignoring case and punctuation.",
        "edge-case-hunter": "Empty and single-character inputs trivially return True.",
    },
    "chronex/seq.py::chunk": {
        "careful-stylist": "Slices the sequence into blocks of `size` from index 0.",
        "speed-reader": "Groups a list into fixed-size batches.",
        "regex-allergic": "Raises ValueError when size is not positive, then steps through by size.",
        "api-historian": "Typical batching helper.",
        "edge-case-hunter": "A final short block is kept; size > length yields one block.",
    },
    "chronex/seq.py::flatten": {
        "careful-stylist": "Recurses through nested lists and extends a flat result.",
        "speed-reader": "Unwraps nested lists.",
        "regex-allergic": "Appends leaves, recursing only when the item is itself a list.",
        "api-historian": "Classic recursive flatten.",
        "edge-case-hunter": "Empty input gives []; strings stay as single elements.",
    },
    "chronex/seq.py::merge_intervals": {
        "careful-stylist": "Sorts intervals, merges any that overlap or touch, and returns tuples.",
        "speed-reader": "Combines overlapping ranges.",
        "regex-allergic": "Accumulates into a list of lists, merging when the next start is <= the current end.",
        "api-historian": "Interval merging as usually written.",
        "edge-case-hunter": "Empty input returns []; adjacency counts as overlap.",
    },
    "chronex/num.py::clamp": {
        "careful-stylist": "Bounds a value with max(low, min(high, value)).",
        "speed-reader": "Keeps a number inside a range.",
        "regex-allergic": "Clamps to the range, and rejects an inverted range.",
        "api-historian": "Standard clamp.",
        "edge-case-hunter": "Inclusive at both ends.",
    },
    "chronex/num.py::mean": {
        "careful-stylist": "Sums values and divides by the count; empty input returns 0.0.",
        "speed-reader": "Averages a list.",
        "regex-allergic": "Returns 0.0 for an empty list, otherwise sum/len.",
        "api-historian": "Arithmetic mean.",
        "edge-case-hunter": "Guarded against ZeroDivisionError.",
    },
}


def main() -> int:
    fns = {fn.key: fn for fn in extract_from_files(REPO, sorted(
        os.path.relpath(os.path.join(dp, f), REPO)
        for dp, dn, fs in os.walk(REPO) for f in fs if f.endswith(".py")
    ), PickFilters(max_lines=200))}

    missing = [k for k in PROBES if k not in fns]
    if missing:
        print(f"missing functions: {missing}", file=sys.stderr)
        return 1

    probe_fixture: dict[str, list[dict]] = {}
    for key, cases in PROBES.items():
        fn = fns[key]
        out_cases = []
        for case in cases:
            res = run_case(REPO, fn.path, fn.qualname, case, timeout=10.0)
            if not res.get("ok"):
                print(f"probe failed for {key}: {res.get('error')}", file=sys.stderr)
                return 1
            out_cases.append(
                {
                    "args": case["args"],
                    "kwargs": case["kwargs"],
                    "label": case["label"],
                    "ok": True,
                    "repr": res["repr"],
                    "error": None,
                }
            )
            print(f"  {key} {case['label']} -> {res['repr']}")
        probe_fixture[key] = out_cases

    witness_fixture: dict[str, str] = {}
    for key, cases in PROBES.items():
        for idx, case in enumerate(cases):
            actual = probe_fixture[key][idx]["repr"]
            for persona in WITNESS_PERSONAS:
                witness_fixture[f"{key}#{idx}#{persona}"] = CONFUSIONS.get(
                    (key, idx, persona), actual
                )
    witness_fixture["__summaries__"] = SUMMARIES

    with open(os.path.join(HERE, "probes.json"), "w", encoding="utf-8") as fh:
        json.dump(probe_fixture, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(HERE, "witnesses.json"), "w", encoding="utf-8") as fh:
        json.dump(witness_fixture, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")

    n_wrong = len(CONFUSIONS)
    n_total = sum(len(v) for v in PROBES.values()) * len(WITNESS_PERSONAS)
    print(f"wrote probes.json ({len(PROBES)} functions) and "
          f"witnesses.json ({n_total} predictions, {n_wrong} wrong)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
