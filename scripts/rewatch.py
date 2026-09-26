#!/usr/bin/env python3
"""Re-run probes, witnesses and scoring against the Clarifier's rewritten copy.

Usage: python3 scripts/rewatch.py --key chronex/parsing.py::parse_duration \
           [--root demo/target_repo] [--out rashomon_out] [--backend file ...]

With --sealed the re-measurement happens on the frozen held-out probes P'
(see `make seal`) instead of the scored probes: inputs the Clarifier never
saw, so the rewrite cannot be tuned to them. P' has no recorded answers, so
--sealed needs live witnesses (WITNESS_BACKEND=llm).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rashomon.cli import main  # noqa: E402


def run(argv: list[str]) -> int:
    rc = main(argv)
    if rc:
        print(f"step failed: {' '.join(argv)}", file=sys.stderr)
    return rc


def _compare(before_path: str, after_path: str, key: str) -> int:
    old = {r["key"]: r for r in json.load(open(before_path, encoding="utf-8"))}
    new = {r["key"]: r for r in json.load(open(after_path, encoding="utf-8"))}
    o, n = old.get(key), new.get(key)
    if not o or not n:
        print("could not compare old and new scores", file=sys.stderr)
        return 1
    print(f"{key}")
    print(f"  before: {o['misreads']}/{o['predictions']} misread "
          f"({o['misread_rate']:.0%}), {o['witnesses_correct']}/{o['n_witnesses']} clean, "
          f"{o['disagreement_mean']:.2f} distinct")
    print(f"  after:  {n['misreads']}/{n['predictions']} misread "
          f"({n['misread_rate']:.0%}), {n['witnesses_correct']}/{n['n_witnesses']} clean, "
          f"{n['disagreement_mean']:.2f} distinct")
    return 0


def _witness_args(a) -> list[str]:
    w_args = ["--backend", a._witness_backend]
    if a.witness_file:
        w_args += ["--witness-file", a.witness_file]
    if a.provider:
        w_args += ["--provider", a.provider]
    if a.model:
        w_args += ["--model", a.model]
    return w_args


def sealed_rewatch(a, row: dict, clar_root: str, clar_out: str) -> int:
    """Re-measure M on P' (frozen held-out inputs) before and after the rewrite."""
    from rashomon.seal import primes_path

    entry = next(
        (e for e in json.load(open(primes_path(a.out), encoding="utf-8")) if e["key"] == row["key"]),
        None,
    )
    if entry is None:
        print(f"no sealed probes for {row['key']}; run `make seal` first", file=sys.stderr)
        return 2

    # pass 1: the ORIGINAL source against P'
    sealed_out = os.path.join(a.out, "sealed_out")
    os.makedirs(sealed_out, exist_ok=True)
    json.dump([row], open(os.path.join(sealed_out, "functions.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump([entry], open(os.path.join(sealed_out, "probes.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    if run(["witness", "--root", a.root, "--out", sealed_out, *_witness_args(a)]):
        return 1
    if run(["score", "--root", a.root, "--out", sealed_out]):
        return 1

    # pass 2: the CLARIFIED copy against the same P'
    if run(["pick", "--root", clar_root, "--out", clar_out, "--files", row["path"],
            "--max-lines", "400"]):
        return 1
    json.dump([entry], open(os.path.join(clar_out, "probes.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    if run(["witness", "--root", clar_root, "--out", clar_out, *_witness_args(a)]):
        return 1
    if run(["score", "--root", clar_root, "--out", clar_out]):
        return 1

    print(f"held-out P' re-measurement ({row['key']}):")
    return _compare(os.path.join(sealed_out, "results.json"),
                    os.path.join(clar_out, "results.json"), row["key"])


def main_cli() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="rashomon_out")
    p.add_argument("--backend", default="heuristic", choices=["heuristic", "llm", "file"])
    p.add_argument("--witness-backend", default=None, choices=["llm", "file"])
    p.add_argument("--probes-file")
    p.add_argument("--witness-file")
    p.add_argument("--provider", default="anthropic")
    p.add_argument("--model")
    p.add_argument("--sealed", action="store_true",
                   help="re-measure on the frozen held-out probes P' (needs live witnesses)")
    a = p.parse_args()

    src = json.load(open(os.path.join(a.out, "functions.json"), encoding="utf-8"))
    row = next((r for r in src if r["key"] == a.key), None)
    if not row:
        print(f"unknown key {a.key!r}", file=sys.stderr)
        return 2

    clar_root = os.path.join(a.out, "clarified")
    clar_out = os.path.join(a.out, "clarified_out")
    a._witness_backend = a.witness_backend or ("file" if a.witness_file else "llm")

    if a.sealed:
        from rashomon.seal import verify

        ok, problems = verify(a.out)
        if not ok:
            for p in problems:
                print(f"  ! {p}", file=sys.stderr)
            print("sealed rewatch refused: the P' freeze does not verify", file=sys.stderr)
            return 2
        if a._witness_backend != "llm":
            print("sealed rewatch needs live witnesses: a recorded session has no answers "
                  "for P'. Use --witness-backend llm (needs an API key).", file=sys.stderr)
            return 2
        if not os.path.isfile(os.path.join(clar_root, row["path"])):
            print(f"no clarified copy for {a.key}; run `make clarify ID={a.key}` first",
                  file=sys.stderr)
            return 2
        return sealed_rewatch(a, row, clar_root, clar_out)

    if not os.path.isfile(os.path.join(clar_root, row["path"])):
        print(f"no clarified copy for {a.key}; run `make clarify ID={a.key}` first", file=sys.stderr)
        return 2

    if run(["pick", "--root", clar_root, "--out", clar_out, "--files", row["path"],
            "--max-lines", "400"]):
        return 1

    # Reuse the sealed probe inputs: the clarified function must behave identically,
    # so the same inputs give the same actuals and the scores stay comparable.
    original = json.load(open(os.path.join(a.out, "probes.json"), encoding="utf-8"))
    entry = next((p for p in original if p["key"] == a.key), None)
    if entry is None:
        print(f"no sealed probes for {a.key}", file=sys.stderr)
        return 2
    entry = dict(entry)
    entry["source"] = row["source"]
    os.makedirs(clar_out, exist_ok=True)
    json.dump([entry], open(os.path.join(clar_out, "probes.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    if run(["witness", "--root", clar_root, "--out", clar_out, *_witness_args(a)]):
        return 1
    if run(["score", "--root", clar_root, "--out", clar_out]):
        return 1

    return _compare(os.path.join(a.out, "results.json"),
                    os.path.join(clar_out, "results.json"), a.key)


if __name__ == "__main__":
    sys.exit(main_cli())
