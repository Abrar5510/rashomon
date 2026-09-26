"""Name-lift: score an anonymised copy of the same functions.

Misread rate conflates two things: how the code is *named* and how it is
*shaped*. The lift rewrites a function's identifiers — function name,
parameters, locals — to neutral `f_<hash>` / `p<n>` / `v<n>` tokens, leaving
structure, control flow and calls to other functions untouched, then re-runs
the exact same probes to prove behaviour is identical. Score the lifted copy
and the difference in misread rate is the naming effect:

    M(original) - M(lifted)  =  naming
    M(lifted)                ~= structure

Verification is mandatory: every probe must produce the same result (or the
same error type) on the lifted module, or `lift` exits non-zero and writes
nothing usable.
"""
from __future__ import annotations

import ast
import hashlib
import os
import re
import time
from typing import Any

from .astx import FunctionInfo, load_function
from .score import same as score_same
from .store import read_json, write_json

ALGORITHM = "rashomon.lift/1"

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_KEEP = ("self", "cls")


def _fresh(base: str, taken: set[str]) -> str:
    name = base
    while name in taken:
        name += "_"
    taken.add(name)
    return name


def _line_starts(src: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _off(starts: list[int], lineno: int, col: int) -> int:
    return starts[lineno - 1] + col


def _collect_bindings(root: ast.AST) -> tuple[set[str], dict[str, list[tuple[ast.AST, str | None]]]]:
    """Names bound inside the function.

    Returns (bindings, string_bound) where string_bound maps each name that is
    bound by a *string* on the AST (except-as, import aliases, match captures)
    to the nodes that carry it and the keyword that introduces it (`as`), so
    the binding token itself can be edited along with its references.
    """
    bindings: set[str] = set()
    declared: set[str] = set()
    string_bound: dict[str, list[tuple[ast.AST, str | None]]] = {}

    def bind_str(name: str, node: ast.AST, hint: str | None) -> None:
        bindings.add(name)
        string_bound.setdefault(name, []).append((node, hint))

    for node in ast.walk(root):
        if isinstance(node, ast.arg):
            if node.arg not in _KEEP:
                bindings.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not root:
                bindings.add(node.name)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                bind_str(node.name, node, "as")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for al in node.names:
                if al.asname:
                    bind_str(al.asname, al, "as")
                elif al.name.split(".")[0] != "*":
                    bind_str(al.name.split(".")[0], al, None)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
        elif hasattr(ast, "MatchAs") and isinstance(node, (ast.MatchAs, ast.MatchStar)):
            if getattr(node, "name", None):
                bind_str(node.name, node, None)
        elif hasattr(ast, "MatchMapping") and isinstance(node, ast.MatchMapping):
            if getattr(node, "rest", None):
                bind_str(node.rest, node, None)
    return bindings - declared, string_bound


def _find_binding_token(
    src: str, starts: list[int], node: ast.AST, name: str, hint: str | None
) -> tuple[int, int] | None:
    """Locate the literal token that binds `name` (its `as err`, `import x`, ...)."""
    s = _off(starts, node.lineno, node.col_offset)
    if getattr(node, "end_lineno", None):
        window = src[s:_off(starts, node.end_lineno, node.end_col_offset) + 1]
    else:
        line_end = src.find("\n", s)
        window = src[s: len(src) if line_end < 0 else line_end + 1]
    if hint:
        m = re.search(rf"\b{re.escape(hint)}\s+{re.escape(name)}\b", window)
        if not m:
            return None
        end = s + m.end()
        return (end - len(name), end)
    m = re.search(rf"\b{re.escape(name)}\b", window)
    if not m:
        return None
    return (s + m.start(), s + m.end())


def anonymise(fn: FunctionInfo) -> tuple[str, dict[str, str], str]:
    """Return (new_source, rename_map, new_function_name).

    Only identifiers are touched: names of the function, its parameters and
    its locals (plus nested defs' names/args and docstring mentions of them).
    Control flow, literals, attribute names and calls to other functions are
    left exactly as they were.
    """
    if not fn.source:
        raise ValueError(f"no source for {fn.key}")
    tree = ast.parse(fn.source)
    if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"{fn.key}: source does not start with its own def")
    root = tree.body[0]
    starts = _line_starts(fn.source)

    bindings, string_bound = _collect_bindings(root)
    bindings.add(root.name)
    # Resolve the literal binding tokens (except-as / import-as / match). A
    # name we cannot locate is dropped from the rename set entirely, so its
    # references keep the original spelling and behaviour stays consistent.
    string_tokens: dict[str, list[tuple[int, int]]] = {}
    for name, sites in string_bound.items():
        spans: list[tuple[int, int]] = []
        for node, hint in sites:
            tok = _find_binding_token(fn.source, starts, node, name, hint)
            if tok is None:
                break
            spans.append(tok)
        else:
            if name in bindings:
                string_tokens[name] = spans
            continue
        bindings.discard(name)

    taken = set(_IDENT.findall(fn.source))
    rename: dict[str, str] = {}

    # the function itself: unique, hash-derived so several lifted functions
    # can share a module without colliding
    digest = hashlib.sha256(fn.key.encode("utf-8")).hexdigest()[:6]
    rename[root.name] = _fresh(f"f_{digest}", taken)

    # root parameters first (p0, p1, ...), then every other local (v0, v1, ...)
    root_args = [
        a.arg
        for a in getattr(root.args, "posonlyargs", []) + list(root.args.args) + list(root.args.kwonlyargs)
        if a.arg not in _KEEP
    ]
    if root.args.vararg and root.args.vararg.arg not in _KEEP:
        root_args.append(root.args.vararg.arg)
    if root.args.kwarg and root.args.kwarg.arg not in _KEEP:
        root_args.append(root.args.kwarg.arg)
    for i, name in enumerate(root_args):
        if name in bindings:
            rename[name] = _fresh(f"p{i}", taken)
    for i, name in enumerate(n for n in sorted(bindings) if n not in rename):
        rename[name] = _fresh(f"v{i}", taken)

    # ---- collect edits (offsets are into fn.source) ----
    edits: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in rename:
            edits.append((_off(starts, node.lineno, node.col_offset),
                          _off(starts, node.end_lineno, node.end_col_offset),
                          rename[node.id]))
        elif isinstance(node, ast.arg) and node.arg in rename:
            edits.append((_off(starts, node.lineno, node.col_offset),
                          _off(starts, node.end_lineno, node.end_col_offset),
                          rename[node.arg]))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node is not root and node.name in rename:
            # the name token sits after `def ` / `class ` on the def line
            line_end = fn.source.find("\n", _off(starts, node.lineno, 0))
            line_end = len(fn.source) if line_end < 0 else line_end
            m = re.search(rf"\b(?:def|class)\s+({re.escape(node.name)})\b",
                          fn.source[_off(starts, node.lineno, node.col_offset):line_end])
            if m:
                base = _off(starts, node.lineno, node.col_offset)
                edits.append((base + m.start(1), base + m.end(1), rename[node.name]))

    # the root's own name token
    line_end = fn.source.find("\n", _off(starts, root.lineno, 0))
    line_end = len(fn.source) if line_end < 0 else line_end
    m = re.search(rf"\bdef\s+({re.escape(root.name)})\b",
                  fn.source[_off(starts, root.lineno, root.col_offset):line_end])
    if m:
        base = _off(starts, root.lineno, root.col_offset)
        edits.append((base + m.start(1), base + m.end(1), rename[root.name]))

    # recursive self-calls: keyword arguments must follow the renamed params
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == root.name:
            for kw in node.keywords:
                if kw.arg in rename and hasattr(kw, "lineno"):
                    s = _off(starts, kw.lineno, kw.col_offset)
                    edits.append((s, s + len(kw.arg), rename[kw.arg]))

    # string-bound tokens: `except E as err`, `import x as m`, match captures
    for name, spans in string_tokens.items():
        if name in rename:
            for s, e in spans:
                edits.append((s, e, rename[name]))

    # the docstring: word-boundary mentions of any renamed identifier
    if root.body and isinstance(root.body[0], ast.Expr) \
            and isinstance(root.body[0].value, ast.Constant) \
            and isinstance(root.body[0].value.value, str):
        lit = root.body[0].value
        s = _off(starts, lit.lineno, lit.col_offset)
        e = _off(starts, lit.end_lineno, lit.end_col_offset)
        text = fn.source[s:e]
        for old, new in rename.items():
            for m in re.finditer(rf"\b{re.escape(old)}\b", text):
                edits.append((s + m.start(), s + m.end(), new))

    # ---- apply, last-first so offsets stay valid; never overlap ----
    edits.sort(key=lambda t: (t[0], t[1]), reverse=True)
    new_source = fn.source
    last_start = len(fn.source) + 1
    for s, e, rep in edits:
        if e > last_start:  # overlaps an edit already applied
            continue
        new_source = new_source[:s] + rep + new_source[e:]
        last_start = s
    return new_source, rename, rename[root.name]


def _remap_kwargs(kwargs: dict, rename: dict[str, str]) -> dict:
    return {rename.get(k, k): v for k, v in kwargs.items()}


def _signature_of(source: str, new_name: str) -> str:
    node = ast.parse(source).body[0]
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{new_name}({ast.unparse(node.args)}){ret}"


def _splice(text: str, info: FunctionInfo, new_source: str) -> str:
    """Replace the function's line range in the module text.

    get_source_segment excludes the leading indent and any trailing comment,
    so both are preserved around the replacement block.
    """
    lines = text.splitlines(keepends=True)
    block = "".join(lines[info.start - 1:info.end])
    indent = block[: len(block) - len(block.lstrip())]
    if not block.lstrip().startswith(info.source[:30].rstrip()):
        raise ValueError(f"{info.key}: source segment does not match its line range")
    suffix = block[len(indent) + len(info.source):]
    new_block = indent + new_source + suffix
    head = "".join(lines[: info.start - 1])
    tail = "".join(lines[info.end:])
    return head + new_block + tail


def lifted_dir(out_dir: str) -> str:
    return os.path.join(out_dir, "lifted")


def _verify_function(
    lifted_root: str,
    rel: str,
    new_name: str,
    probes: list[dict],
    rename: dict[str, str],
    timeout: float,
) -> tuple[int, int, list[str]]:
    from .runner import run_case

    ok_count = 0
    total = 0
    failures: list[str] = []
    for p in probes:
        if not p.get("ok"):
            continue
        total += 1
        case = {"args": p.get("args", []), "kwargs": _remap_kwargs(p.get("kwargs", {}), rename)}
        res = run_case(lifted_root, rel, new_name, case, timeout=timeout)
        if res.get("ok"):
            good = score_same(res.get("repr"), p.get("repr"))
        else:
            good = (res.get("error") or "").split(":")[0] == (p.get("error") or "").split(":")[0]
        if good:
            ok_count += 1
        else:
            failures.append(
                f"{new_name}{case['args']} -> {res.get('repr') or res.get('error')!r}, "
                f"expected {p.get('repr') or p.get('error')!r}"
            )
    return ok_count, total, failures
