from __future__ import annotations

import re
import subprocess

FIX_RE = re.compile(
    r"\b(fixes|fixed|fixing|fix|bugfix|bugs|bug|patched|patch|repairs|repair|"
    r"resolved|resolves|resolve|hotfix|regressions|regression|corrected|correct)\b",
    re.I,
)
NOT_FIX_RE = re.compile(
    r"\b(typo|typos|docstring|docstrings|docs?|lint|linting|pre-commit|readme|"
    r"whitespace|formatting|style)\b",
    re.I,
)


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def is_git_repo(root: str) -> bool:
    return _git(root, "rev-parse", "--is-inside-work-tree").returncode == 0


def _source_at(root: str, sha: str, path: str, qualname: str) -> str | None:
    proc = _git(root, "show", f"{sha}:{path}")
    if proc.returncode != 0:
        return None
    from .astx import extract_from_source

    for fn in extract_from_source(path, proc.stdout):
        if fn.qualname == qualname:
            return fn.source
    return None


def _touched_function(root: str, sha: str, path: str, qualname: str) -> bool:
    """True when this commit really changed the function, not just its neighbours."""
    cur = _source_at(root, sha, path, qualname)
    if cur is None:
        return False
    parent = _source_at(root, f"{sha}^", path, qualname)
    if parent is None:
        return True
    return cur != parent


def changed_files(root: str, base: str | None = None) -> list[str]:
    files: set[str] = set()
    if base:
        proc = _git(root, "diff", "--name-only", f"{base}...HEAD")
        if proc.returncode != 0:
            proc = _git(root, "diff", "--name-only", base)
    else:
        proc = _git(root, "diff", "--name-only", "HEAD")
        staged = _git(root, "diff", "--name-only", "--cached")
        files.update(staged.stdout.split())
    files.update(proc.stdout.split())
    return sorted(f for f in files if f.endswith(".py"))


def churned_files(root: str, limit: int = 10) -> list[tuple[str, int]]:
    proc = _git(root, "log", "--name-only", "--pretty=format:")
    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.endswith(".py"):
            counts[line] = counts.get(line, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:limit]


def function_history(
    root: str,
    path: str,
    qualname: str,
    start: int,
    end: int,
    signature: str = "",
) -> dict:
    """Commits touching a function, and how many of them look like bug fixes."""
    entries: list[tuple[str, str, str]] = []

    proc = _git(
        root,
        "log",
        "-L",
        f"{start},{end}:{path}",
        "--format=%H%x09%s%x09%ad",
        "--date=short",
    )
    if proc.returncode == 0 and proc.stdout.strip():
        for line in proc.stdout.splitlines():
            if re.fullmatch(r"[0-9a-f]{40}\t.*\t.*", line):
                h, subj, date = line.split("\t", 2)
                entries.append((h, subj, date))

    if not entries:
        seed = signature.split("(")[0] + "(" if signature else qualname.split(".")[-1] + "("
        proc = _git(
            root,
            "log",
            "-S",
            seed,
            "--format=%H%x09%s%x09%ad",
            "--date=short",
            "--",
            path,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "\t" in line and len(line.split("\t")[0]) == 40:
                    h, subj, date = line.split("\t", 2)
                    entries.append((h, subj, date))

    seen: dict[str, tuple] = {}
    for h, subj, date in entries:
        seen.setdefault(h, (h, subj, date))
    commits = [c for c in seen.values() if _touched_function(root, c[0], path, qualname)]
    fixes = [c for c in commits if FIX_RE.search(c[1]) and not NOT_FIX_RE.search(c[1])]
    return {
        "touching_commits": len(commits),
        "bug_fixes": len(fixes),
        "last_fix": max((c[2] for c in fixes), default=None),
        "fix_commits": [{"sha": c[0][:8], "subject": c[1], "date": c[2]} for c in fixes[:8]],
    }


def bugfix_history(root: str, functions: list[dict]) -> dict[str, dict]:
    if not is_git_repo(root):
        return {fn["key"]: {"touching_commits": 0, "bug_fixes": 0, "last_fix": None,
                            "fix_commits": [], "error": "not a git repository"}
                for fn in functions}
    out: dict[str, dict] = {}
    for fn in functions:
        try:
            out[fn["key"]] = function_history(
                root, fn["path"], fn["qualname"], fn.get("start", 1), fn.get("end", 1),
                fn.get("signature", ""),
            )
        except Exception as exc:
            out[fn["key"]] = {"touching_commits": 0, "bug_fixes": 0, "last_fix": None,
                              "fix_commits": [], "error": str(exc)}
    return out
