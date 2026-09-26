from __future__ import annotations

import ast
import os
import warnings
from dataclasses import dataclass, field, asdict

warnings.filterwarnings("ignore", category=SyntaxWarning)


@dataclass
class FunctionInfo:
    name: str
    qualname: str
    path: str
    module: str
    start: int
    end: int
    source: str
    signature: str
    docstring: str | None = None
    is_method: bool = False
    is_async: bool = False
    n_lines: int = 0
    key: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PickFilters:
    min_lines: int = 1
    max_lines: int = 60
    exclude_privates: bool = True
    exclude_nested: bool = True
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


def _module_name(relpath: str) -> str:
    rel = relpath[:-3] if relpath.endswith(".py") else relpath
    parts = [p for p in rel.split("/") if p not in (".", "")]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{node.name}({args}){ret}"


def extract_from_source(relpath: str, source: str) -> list[FunctionInfo]:
    relpath = relpath.replace(os.sep, "/")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    module = _module_name(relpath)
    out: list[FunctionInfo] = []

    def visit(body: list[ast.stmt], prefix: str, is_method: bool, inside_fn: bool) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{node.name}" if prefix else node.name
                nested = inside_fn
                if not nested:
                    src = ast.get_source_segment(source, node) or ""
                    start = node.lineno
                    end = getattr(node, "end_lineno", start) or start
                    out.append(
                        FunctionInfo(
                            name=node.name,
                            qualname=qual,
                            path=relpath,
                            module=module,
                            start=start,
                            end=end,
                            source=src,
                            signature=_sig(node),
                            docstring=ast.get_docstring(node),
                            is_method=is_method,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            n_lines=(src.count("\n") + 1) if src else end - start + 1,
                            key=f"{relpath}::{qual}",
                        )
                    )
                visit(node.body, qual + ".", is_method, True)
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".", True, inside_fn)
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for field_name in ("body", "orelse", "finalbody", "handlers"):
                    sub = getattr(node, field_name, None)
                    if isinstance(sub, list):
                        for item in sub:
                            if isinstance(item, ast.ExceptHandler):
                                visit(item.body, prefix, is_method, inside_fn)
                            elif isinstance(item, list):
                                visit(item, prefix, is_method, inside_fn)

    visit(tree.body, "", False, False)
    return out


def apply_filters(fns: list[FunctionInfo], f: PickFilters) -> list[FunctionInfo]:
    out = []
    for fn in fns:
        if fn.n_lines < f.min_lines or fn.n_lines > f.max_lines:
            continue
        if f.exclude_privates and fn.name.startswith("_"):
            continue
        if f.exclude_nested and "." in fn.qualname and fn.is_method is False:
            continue
        if f.include and not any(pat in fn.qualname or pat in fn.path for pat in f.include):
            continue
        if f.exclude and any(pat in fn.qualname or pat in fn.path for pat in f.exclude):
            continue
        out.append(fn)
    return out


def extract_from_files(root: str, relpaths: list[str], f: PickFilters | None = None) -> list[FunctionInfo]:
    f = f or PickFilters()
    found: list[FunctionInfo] = []
    for rel in relpaths:
        if not rel.endswith(".py"):
            continue
        abs_path = os.path.join(root, rel)
        if not os.path.isfile(abs_path):
            continue
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        found.extend(extract_from_source(rel, source))
    return apply_filters(found, f)


def load_function(root: str, key: str) -> FunctionInfo | None:
    path, _, qualname = key.partition("::")
    abs_path = os.path.join(root, path)
    if not os.path.isfile(abs_path):
        return None
    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
        source = fh.read()
    for fn in extract_from_source(path, source):
        if fn.qualname == qualname:
            return fn
    return None
