"""Correlation statistics for the bug-history check. Pure Python, no scipy.

The script that prints these numbers is committed before the result is known, so
the correlation cannot be chosen after seeing it.
"""
from __future__ import annotations

import ast
import math
import random
from typing import Sequence

Number = float


def _pairs(x: Sequence[Number], y: Sequence[Number]) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in zip(x, y) if a is not None and b is not None]


def _ranks(values: Sequence[float]) -> list[float]:
    """Average ranks, 1-based, ties share the mean of the ranks they span."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    pts = _pairs(x, y)
    n = len(pts)
    if n < 2:
        return 0.0
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((a - mx) * (b - my) for a, b in pts)
    dx = math.sqrt(sum((a - mx) ** 2 for a, _ in pts))
    dy = math.sqrt(sum((b - my) ** 2 for _, b in pts))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    pts = _pairs(x, y)
    if len(pts) < 2:
        return 0.0
    return pearson(_ranks([p[0] for p in pts]), _ranks([p[1] for p in pts]))


def permutation_p(x: Sequence[float], y: Sequence[float], n: int = 10000,
                  seed: int = 0) -> float:
    """Two-sided p-value: how often does a shuffled y reach |rho| >= observed?"""
    pts = _pairs(x, y)
    if len(pts) < 3:
        return 1.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    observed = abs(spearman(xs, ys))
    if observed == 0.0:
        return 1.0
    rng = random.Random(seed)
    hits = 0
    for _ in range(n):
        rng.shuffle(ys)
        if abs(spearman(xs, ys)) >= observed:
            hits += 1
    return round((hits + 1) / (n + 1), 4)


def bootstrap_ci(x: Sequence[float], y: Sequence[float], n: int = 2000,
                 seed: int = 0) -> tuple[float, float]:
    """Percentile 95% CI for Spearman rho by resampling functions with replacement."""
    pts = _pairs(x, y)
    if len(pts) < 3:
        return (0.0, 0.0)
    rng = random.Random(seed)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n_pts = len(pts)
    stats: list[float] = []
    for _ in range(n):
        idx = [rng.randrange(n_pts) for _ in range(n_pts)]
        stats.append(spearman([xs[i] for i in idx], [ys[i] for i in idx]))
    stats.sort()
    lo = stats[int(0.025 * (n - 1))]
    hi = stats[int(0.975 * (n - 1))]
    return (round(lo, 3), round(hi, 3))


def branch_count(source: str) -> int:
    """AST decision points: the structural complexity a reader has to hold."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return 0
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp)):
            total += 1
        elif isinstance(node, ast.Try):
            total += len(node.handlers) + (1 if node.orelse else 0)
        elif isinstance(node, ast.BoolOp):
            total += max(1, len(node.values) - 1)
        elif isinstance(node, ast.Match):
            total += max(1, len(node.cases))
        elif isinstance(node, ast.comprehension):
            total += len(node.ifs) or 1
    return total
