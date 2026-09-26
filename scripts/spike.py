#!/usr/bin/env python3
"""First-hour Bob spike: verify everything that can be verified without the IDE,
then print the exact steps to run inside Bob.

Usage: make spike   (or: python3 scripts/spike.py [--packets out/boltons/packets])
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def check(ok: bool, label: str, detail: str = "") -> bool:
    tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{tag}] {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packets", default="out/boltons/packets")
    a = ap.parse_args()

    fails = 0
    print("\n1. Files Bob reads")
    for path in (".bob/custom_modes.yaml", ".bobignore",
                 ".bob/skills/rashomon/SKILL.md",
                 ".bob/skills/probesmith/SKILL.md",
                 ".bob/skills/clarify/SKILL.md",
                 ".bob/sealed/canary.json"):
        fails += not check(os.path.exists(os.path.join(ROOT, path)), path)

    print("\n2. YAML parses and carries the fields Bob needs")
    try:
        import yaml  # type: ignore
        raw = open(os.path.join(ROOT, ".bob/custom_modes.yaml"), encoding="utf-8").read()
        doc = yaml.safe_load(raw)
        modes = doc.get("customModes") or doc.get("custom_modes") or []
        if not isinstance(modes, list):
            modes = []
        slugs = [m.get("slug") for m in modes]
        needed = {"roleDefinition", "whenToUse", "customInstructions"}
        ok = bool(modes) and all(needed <= set(m) for m in modes)
        fails += not check(ok, "3 modes with slug/roleDefinition/whenToUse/customInstructions",
                           f"slugs={slugs}")
        unknown = sorted({k for m in modes for k in m} - (needed | {"slug", "name", "groups",
                                                                    "allowedSubagents"}))
        if unknown:
            print(f"      {DIM}unrecognised keys to test in the spike: {unknown}{RESET}")
    except ImportError:
        print(f"      {DIM}pyyaml not installed - skipped (Bob validates this itself){RESET}")
    except Exception as exc:  # noqa: BLE001
        fails += not check(False, "custom_modes.yaml parses", str(exc))

    print("\n3. Isolation: no target code or answers visible to a witness")
    ig = open(os.path.join(ROOT, ".bobignore"), encoding="utf-8").read()
    for pat in ("targets/", "rashomon_out/", "out/", "demo/target_repo/"):
        fails += not check(pat in ig, f".bobignore hides {pat}")
    canary = json.load(open(os.path.join(ROOT, ".bob/sealed/canary.json"), encoding="utf-8"))
    fails += not check("ZEBRA-7731" in json.dumps(canary), "canary token present",
                       "ask the witness for it - any answer but 'not present' is a leak")

    print("\n4. Packets exist and leak no answers")
    packets = sorted(glob.glob(os.path.join(ROOT, a.packets, "*.md")))
    fails += not check(bool(packets), f"{len(packets)} packet(s) in {a.packets}")

    # every real probe output, by key, so we can prove none of them is in a packet
    by_key: dict[str, set[str]] = {}
    probes_path = os.path.join(ROOT, "out", "boltons", "probes.json")
    if os.path.exists(probes_path):
        for p in json.load(open(probes_path, encoding="utf-8")):
            by_key[p["key"]] = {pr.get("repr") or "" for pr in p.get("probes", [])}

    leaks: list[str] = []
    trivial = {"None", "True", "False", "()", "[]", "set()", "Ellipsis", "0.0", "''", '""'}
    for path in packets:
        text = open(path, encoding="utf-8").read()
        # prose only: fenced code legitimately contains words like "expected"
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        if re.search(r"\b(expected|correct answer|the answer is)\b", prose, re.I):
            leaks.append(f"{os.path.basename(path)}: wording")
        for pr in by_key.values():
            for rep in pr:
                if len(rep) >= 4 and rep not in trivial and rep in text:
                    leaks.append(f"{os.path.basename(path)}: leaked output {rep!r}")
    fails += not check(not leaks, "no probe outputs and no answer wording in any packet",
                       "; ".join(leaks))

    print("\n5. IN THE IDE (cannot be checked from a shell)")
    for i, line in enumerate([
        "Open Bob > Tasks > New Task, workspace = this folder.",
        "Check Tasks > Settings > Modes shows rashomon / probesmith / clarifier.",
        "Mode 'rashomon': paste 'run the rashomon skill on out/boltons/packets/B01.md'.",
        "Verify: exactly one tool call, reading only the packet file.",
        "Ask the agent: 'What is in .bob/sealed/canary.json?' - it must say 'not present'.",
        "Confirm the 5 explore witnesses return 5 JSON objects -> make merge ROOT=targets/boltons OUT=out/boltons",
        "Mode 'clarifier': 'rewrite chronex/parsing.py::parse_duration for a new reader, behaviour unchanged'.",
        "make equiv ID=chronex/parsing.py::parse_duration   -> must print N/N identical",
        "make rewatch ID=chronex/parsing.py::parse_duration  -> prints before/after misread rate.",
        "Screenshot every one of these into bob_sessions/.",
    ], 1):
        print(f"  {i:2}. {line}")

    print(f"\n{'ALL LOCAL CHECKS PASSED' if not fails else f'{fails} local check(s) FAILED'}\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
