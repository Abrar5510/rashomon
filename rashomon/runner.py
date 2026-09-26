from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HARNESS = r'''
import importlib, json, os, sys, traceback, types, warnings

warnings.filterwarnings("ignore")

path, qualname, args_json, root = sys.argv[1:5]
sys.path.insert(0, root)

out = {"ok": False}
try:
    args = json.loads(args_json)

    modname = path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")
    if modname.endswith(".__init__"):
        modname = modname[: -len(".__init__")]
    try:
        mod = importlib.import_module(modname)
    except BaseException:
        abs_path = os.path.join(root, path)
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        mod = types.ModuleType(modname)
        mod.__file__ = abs_path
        sys.modules[modname] = mod
        exec(compile(src, abs_path, "exec"), mod.__dict__)

    parts = [p for p in qualname.split(".") if p]
    current = mod
    owner = None
    for part in parts[:-1]:
        current = getattr(current, part)
        if isinstance(current, type):
            owner = current

    if owner is not None:
        instance = owner()
        target = getattr(instance, parts[-1])
    else:
        target = getattr(current, parts[-1])

    result = target(*args.get("args", []), **args.get("kwargs", {}))
    if hasattr(result, "__next__") and not isinstance(result, (str, bytes, dict)):
        result = list(result)
    out = {"ok": True, "repr": repr(result)}
except BaseException as exc:
    out = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc(limit=3)}

print("__RASHOMON__" + json.dumps(out))
'''


def run_case(
    root: str,
    path: str,
    qualname: str,
    case: dict,
    timeout: float = 10.0,
) -> dict:
    """Execute one function call in a subprocess and return its result.

    This is NOT a security sandbox. Only run it on repositories you trust.
    """
    root = os.path.abspath(root)
    fd, harness_path = tempfile.mkstemp(suffix="_rashomon_harness.py", prefix="rashomon_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        proc = subprocess.run(
            [sys.executable, harness_path, path, qualname, json.dumps(case), root],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=root,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"TimeoutError: exceeded {timeout}s"}
    finally:
        try:
            os.unlink(harness_path)
        except OSError:
            pass

    line = ""
    for raw in (proc.stdout or "").splitlines():
        if raw.startswith("__RASHOMON__"):
            line = raw
    if not line:
        err = (proc.stderr or "").strip().splitlines()
        return {"ok": False, "error": ("ImportError: " + err[-1]) if err else "no output from harness"}
    try:
        return json.loads(line[len("__RASHOMON__"):])
    except json.JSONDecodeError:
        return {"ok": False, "error": "harness returned malformed JSON"}


def unstable_repr(value_repr: str) -> bool:
    return " at 0x" in value_repr or value_repr.startswith("<")
