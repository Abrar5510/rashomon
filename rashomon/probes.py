from __future__ import annotations

import ast
import warnings
from typing import Any

from .astx import FunctionInfo
from .llm import LLMBackend, strip_fences
from .runner import run_case, unstable_repr

warnings.filterwarnings("ignore", category=SyntaxWarning)

_BY_TYPE: dict[str, list[Any]] = {
    "str": ["", "hello", "  padded  ", "a", "Hello, World!", "1h30m", "x" * 40,
            "ünïcode", "  ", "0", "true", "-1"],
    "int": [0, 1, -1, 7, 42, 1000, -100, 2**31],
    "float": [0.0, 1.5, -1.0, 0.1, 1e6, -0.001],
    "bool": [True, False],
    "list": [[], [1, 2, 3], [0], ["a"], list(range(10)), [None, 1]],
    "dict": [{}, {"a": 1}, {"k": "v"}, {"nested": {"x": 1}}, {1: "int key"}],
    "set": [set(), {1, 2}, {0}, {"a"}],
    "tuple": [(), (1, 2), (0,), ("a", "b"), (1, 2, 3)],
    "bytes": [b"", b"abc", b"\x00", b"ff"],
    "NoneType": [None, None, None, None],
}

# guesses for un-annotated parameters, keyed by the parameter's name
_NAME_HINTS: dict[str, str] = {
    "s": "str", "text": "str", "string": "str", "name": "str", "prefix": "str",
    "suffix": "str", "sep": "str", "char": "str", "word": "str", "line": "str",
    "path": "str", "url": "str", "host": "str", "title": "str", "fmt": "str",
    "format": "str", "pattern": "str", "key": "str", "label": "str", "tag": "str",
    "query": "str", "slug": "str", "cmd": "str", "glue": "str", "delim": "str",
    "n": "int", "num": "int", "count": "int", "size": "int", "limit": "int",
    "width": "int", "index": "int", "idx": "int", "pos": "int", "depth": "int",
    "level": "int", "base": "int", "year": "int", "timeout": "int", "max": "int",
    "minimum": "int", "maximum": "int", "decimals": "int", "precision": "int",
    "items": "list", "seq": "list", "lst": "list", "values": "list",
    "iterable": "list", "pairs": "list", "rows": "list", "args": "list",
    "mapping": "dict", "data": "dict", "kwargs_map": "dict", "cache": "dict",
    "mapping_kwargs": "dict", "obj": "dict", "config": "dict",
    "flag": "bool", "enabled": "bool", "strict": "bool", "ignore": "bool",
    "copy": "bool", "recursive": "bool",
    "default": "generic", "value": "generic", "val": "generic", "ret": "generic",
}

_GENERIC = [None, "", 0, 1, [], {}, 1.5, True, "x", [1], {"a": 1}, -1]
_LABELS = ["minimal", "typical", "edge", "odd", "odd2", "odd3"]


def _default_value(node: ast.expr | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _typed_value(annotation: str | None, name: str, slot: int) -> Any:
    ann = (annotation or "").strip()
    if ann:
        base = ann.replace("typing.", "").split("[")[0].split("|")[0].strip()
        table = {
            "str": "str", "int": "int", "float": "float", "bool": "bool",
            "list": "list", "List": "list", "dict": "dict", "Dict": "dict",
            "set": "set", "Set": "set", "tuple": "tuple", "Tuple": "tuple",
            "bytes": "bytes", "Sequence": "list", "Iterable": "list",
            "Mapping": "dict", "Optional": "generic", "Any": "generic",
            "Union": "generic", "None": "NoneType",
        }
        kind = table.get(base)
        if kind == "generic" or (kind is None and base[:1].islower()):
            kind = _NAME_HINTS.get(name, "generic")
        if kind:
            vals = _BY_TYPE.get(kind)
            if vals is not None:
                return vals[slot % len(vals)]
    hint = _NAME_HINTS.get(name)
    if hint and hint in _BY_TYPE:
        return _BY_TYPE[hint][slot % len(_BY_TYPE[hint])]
    if hint == "generic":
        return _GENERIC[slot % len(_GENERIC)]
    return _GENERIC[slot % len(_GENERIC)]


def _params(fn: FunctionInfo, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    a = node.args
    pos = list(a.posonlyargs) + list(a.args)
    defaults = list(a.defaults)
    offset = len(pos) - len(defaults)
    specs: list[dict] = []
    for i, arg in enumerate(pos):
        ann = ast.unparse(arg.annotation) if arg.annotation else None
        specs.append(
            {
                "name": arg.arg,
                "default": defaults[i - offset] if i >= offset else None,
                "ann": ann,
                "posonly": i < len(a.posonlyargs),
            }
        )
    for i, arg in enumerate(a.kwonlyargs):
        ann = ast.unparse(arg.annotation) if arg.annotation else None
        specs.append(
            {"name": arg.arg, "default": a.kw_defaults[i], "ann": ann, "posonly": False}
        )
    specs = [s for s in specs if s["name"] not in ("self", "cls")]
    return specs


def heuristic_cases(fn: FunctionInfo, count: int = 6) -> list[dict]:
    """Build candidate call cases from the signature alone (no LLM needed)."""
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
        # no-arg function: one probe is enough
        return [{"args": [], "kwargs": {}, "label": _LABELS[i]} for i in range(min(count, 1))]

    cases: list[dict] = []
    for slot in range(count):
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        vary_last = slot > 0
        for i, spec in enumerate(specs):
            is_last = i == len(specs) - 1
            if spec["default"] is not None and not (vary_last and is_last):
                value = _default_value(spec["default"])
            else:
                value = _typed_value(spec["ann"], spec["name"], slot if is_last else 0)
            if spec["posonly"]:
                args.append(value)
            else:
                kwargs[spec["name"]] = value
        cases.append({"args": args, "kwargs": kwargs, "label": _LABELS[slot % len(_LABELS)]})
    return cases


def llm_cases(backend: LLMBackend, fn: FunctionInfo, count: int = 3) -> list[dict]:
    system = (
        "You design test inputs. Reply with ONLY JSON: "
        '{"cases":[{"args":[...],"kwargs":{...},"label":"..."}]}'
    )
    user = (
        f"Function under test:\n\n```python\n{fn.source}\n```\n\n"
        f"Produce exactly {count} interesting input cases that exercise different branches. "
        "Values must be JSON-serialisable literals. No comments."
    )
    import json

    raw = strip_fences(backend.complete(system, user))
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON in probe response for {fn.key}")
    data = json.loads(raw[start : end + 1])
    cases = []
    for c in data.get("cases", [])[:count]:
        cases.append(
            {
                "args": list(c.get("args", [])),
                "kwargs": dict(c.get("kwargs", {})),
                "label": c.get("label", "llm"),
            }
        )
    return cases


def materialise(
    root: str,
    fn: FunctionInfo,
    cases: list[dict],
    timeout: float = 10.0,
    keep: int = 3,
) -> dict:
    """Run every candidate case, keep the ones that actually execute."""
    probes = []
    for case in cases:
        res = run_case(root, fn.path, fn.qualname, case, timeout=timeout)
        ok = bool(res.get("ok")) and not unstable_repr(str(res.get("repr") or ""))
        probes.append(
            {
                "args": case.get("args", []),
                "kwargs": case.get("kwargs", {}),
                "label": case.get("label", "?"),
                "ok": ok,
                "repr": res.get("repr") if ok else None,
                "error": None if ok else (res.get("error") or "unstable result repr"),
            }
        )
        if len([p for p in probes if p["ok"]]) >= keep:
            break
    return {
        "key": fn.key,
        "path": fn.path,
        "qualname": fn.qualname,
        "signature": fn.signature,
        "source": fn.source,
        "probes": probes,
        "n_runnable": len([p for p in probes if p["ok"]]),
    }
