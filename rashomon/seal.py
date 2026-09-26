"""Sealed held-out probes (P'): frozen with sha256 before any witness runs.

The Clarifier sees the scored probes — that is the point: it rewrites the
confusing function until the readers stop disagreeing.  It must NOT be able to
tune that rewrite to the inputs the re-measurement will use.  So P' is drawn
from a value table disjoint from the scored probes, executed for ground truth,
and frozen under a sha256 manifest *before* the witnesses are asked anything.
`verify()` recomputes the hashes: edit P' after the freeze and verification
fails, so `equiv --sealed` refuses to trust it.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import time
from typing import Any, Iterable

from .astx import FunctionInfo, load_function
from .probes import _NAME_HINTS, _default_value, _params, materialise
from .store import read_json, write_json

ALGORITHM = "rashomon.seal/1"

# Deliberately disjoint from probes._BY_TYPE: none of these values appear in
# the scored probe table, so P' exercises inputs the Clarifier never saw.
# Only JSON-round-trip-stable values (str/int/float/bool/list/dict/None) so a
# stored probe re-runs as exactly the input that produced its ground truth.
_PRIME_BY_TYPE: dict[str, list[Any]] = {
    "str": ["bob", "42", "a\tb", "\nstart", "end.", "..", "RASHOMON", "0x1f"],
    "int": [2, 3, 5, 11, 99, -7, 65536, 254],
    "float": [2.5, -0.5, 3.14159, 1e-9, 100.0],
    "bool": [False, True],
    "list": [[2], [1, 1, 1], ["bob"], [0, None], ["held", "out"]],
    "dict": [{"bob": 1}, {"": ""}, {"x": None}, {"held": [1, 2]}],
    "NoneType": [None],
}
_PRIME_GENERIC = [2, "held", [2], {"held": 1}, None, -3, 0.5, False]

_ANN_TABLE = {
    "str": "str", "int": "int", "float": "float", "bool": "bool",
    "list": "list", "List": "list", "dict": "dict", "Dict": "dict",
    "set": "list", "Set": "list", "tuple": "list", "Tuple": "list",
    "bytes": "str", "Sequence": "list", "Iterable": "list",
    "Mapping": "dict", "Optional": "generic", "Any": "generic",
    "Union": "generic", "None": "NoneType",
}


def case_signature(case: dict) -> str:
    return json.dumps(
        [case.get("args", []), case.get("kwargs", {})],
        sort_keys=True,
        ensure_ascii=False,
    )


def entry_hash(entry: dict) -> str:
    blob = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def file_hash(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _prime_value(annotation: str | None, name: str, slot: int) -> Any:
    ann = (annotation or "").strip()
    if ann:
        base = ann.replace("typing.", "").split("[")[0].split("|")[0].strip()
        kind = _ANN_TABLE.get(base)
        if kind == "generic" or (kind is None and base[:1].islower()):
            kind = _NAME_HINTS.get(name, "generic")
        if kind in _PRIME_BY_TYPE:
            vals = _PRIME_BY_TYPE[kind]
            return vals[slot % len(vals)]
        if kind == "generic":
            return _PRIME_GENERIC[slot % len(_PRIME_GENERIC)]
    hint = _NAME_HINTS.get(name)
    if hint in _PRIME_BY_TYPE:
        return _PRIME_BY_TYPE[hint][slot % len(_PRIME_BY_TYPE[hint])]
    return _PRIME_GENERIC[slot % len(_PRIME_GENERIC)]


def prime_cases(
    fn: FunctionInfo,
    count: int = 9,
    avoid: Iterable[str] = (),
) -> list[dict]:
    """Held-out call cases from the signature alone, disjoint from `avoid`.

    Slot 0 is a coherent "typical" call with every parameter at its benign
    held-out value (or its declared default). Later slots vary ONE parameter
    at a time, rotating through the signature, so the input distribution is
    genuinely different from heuristic_cases (which only ever varies the last
    parameter) while still producing runnable calls.
    """
    if not fn.source:
        return []
    try:
        tree = ast.parse(fn.source)
    except SyntaxError:
        return []
    node = next(
        (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )
    if node is None:
        return []
    specs = _params(fn, node)
    if not specs:
        case = {"args": [], "kwargs": {}, "label": "held0"}
        return [] if case_signature(case) in set(avoid) else [case]

    salt = int(hashlib.sha256(fn.key.encode("utf-8")).hexdigest()[:8], 16)
    seen = set(avoid)
    cases: list[dict] = []

    def value_for(spec: dict, index: int) -> Any:
        if spec["default"] is not None and index == 0:
            return _default_value(spec["default"])
        return _prime_value(spec["ann"], spec["name"], index)

    slot = 0
    while len(cases) < count and slot < count * 6:
        vary = slot % len(specs)
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for i, spec in enumerate(specs):
            if slot == 0 or i != vary:
                value = value_for(spec, 0)
            else:
                vals_len = len(_PRIME_GENERIC)
                value = value_for(spec, 1 + (salt + slot) % max(1, vals_len - 1))
            if spec["posonly"]:
                args.append(value)
            else:
                kwargs[spec["name"]] = value
        case = {"args": args, "kwargs": kwargs, "label": f"held{len(cases)}"}
        sig = case_signature(case)
        if sig not in seen:
            seen.add(sig)
            cases.append(case)
        slot += 1
    return cases


def primes_path(out_dir: str) -> str:
    return os.path.join(out_dir, "sealed", "primes.json")


def manifest_path(out_dir: str) -> str:
    return os.path.join(out_dir, "sealed", "manifest.json")


def is_sealed(out_dir: str) -> bool:
    return os.path.isfile(primes_path(out_dir)) and os.path.isfile(manifest_path(out_dir))


def seal(
    root: str,
    out_dir: str,
    functions: list[dict],
    scored: dict[str, dict] | None = None,
    count: int = 9,
    keep: int = 3,
    timeout: float = 10.0,
) -> list[dict]:
    """Generate, execute and freeze P'. Rewrites any previous freeze."""
    scored = scored or {}
    entries: list[dict] = []
    for d in functions:
        fn = load_function(root, d["key"])
        if fn is None:
            continue
        avoid = [
            case_signature(p)
            for p in scored.get(d["key"], {}).get("probes", [])
            if p.get("ok")
        ]
        cases = prime_cases(fn, count=count, avoid=avoid)
        if not cases:
            continue
        entry = materialise(root, fn, cases, timeout=timeout, keep=keep)
        if entry["n_runnable"]:
            entries.append(entry)

    os.makedirs(os.path.join(out_dir, "sealed"), exist_ok=True)
    p_path = primes_path(out_dir)
    write_json(p_path, entries)

    scored_file = os.path.join(out_dir, "probes.json")
    manifest = {
        "algorithm": ALGORITHM,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_functions": len(entries),
        "count": count,
        "keep": keep,
        "entries": {e["key"]: entry_hash(e) for e in entries},
        "file_sha256": file_hash(p_path),
        "disjoint_with": file_hash(scored_file) if os.path.isfile(scored_file) else None,
    }
    write_json(manifest_path(out_dir), manifest)
    return entries


def verify(out_dir: str) -> tuple[bool, list[str]]:
    """Recompute every hash in the manifest. Empty problems == freeze intact."""
    p_path = primes_path(out_dir)
    m_path = manifest_path(out_dir)
    if not os.path.isfile(p_path) or not os.path.isfile(m_path):
        return False, [f"no sealed probes under {os.path.join(out_dir, 'sealed')}; run `make seal` first"]
    problems: list[str] = []
    manifest = read_json(m_path)
    if manifest.get("algorithm") != ALGORITHM:
        problems.append(f"unknown seal algorithm {manifest.get('algorithm')!r}")
    actual = file_hash(p_path)
    if actual != manifest.get("file_sha256"):
        problems.append(
            f"primes.json sha256 mismatch: manifest {str(manifest.get('file_sha256'))[:12]}…, "
            f"file {actual[:12]}…"
        )
    entries = read_json(p_path)
    per_entry = manifest.get("entries", {})
    present = set()
    for e in entries:
        key = e.get("key", "?")
        present.add(key)
        want = per_entry.get(key)
        if want is None:
            problems.append(f"entry not in manifest: {key}")
        elif entry_hash(e) != want:
            problems.append(f"entry changed after the freeze: {key}")
    for key in per_entry:
        if key not in present:
            problems.append(f"entry missing from primes.json: {key}")
    return (not problems), problems
