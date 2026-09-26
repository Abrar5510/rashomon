from __future__ import annotations

import ast
from typing import Any

from . import WITNESS_PERSONAS


def _parse(value: Any) -> Any:
    if not isinstance(value, str):
        return ("raw", value)
    s = value.strip()
    if not s:
        return ("empty", "")
    try:
        return ("lit", ast.literal_eval(s))
    except Exception:
        return ("str", " ".join(s.split()))


def same(a: Any, b: Any) -> bool:
    pa, pb = _parse(a), _parse(b)
    if pa[0] == "empty" or pb[0] == "empty":
        return False
    if pa[0] == "lit" and pb[0] == "lit":
        va, vb = pa[1], pb[1]
        if isinstance(va, bool) or isinstance(vb, bool):
            return type(va) is type(vb) and va == vb
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            return float(va) == float(vb)
        return type(va) is type(vb) and va == vb
    if pa[0] == "str" and pb[0] == "str":
        return pa[1] == pb[1]
    # one literal, one bare string: compare literal vs the raw string form
    left = repr(pa[1]) if pa[0] == "lit" else pa[1]
    right = repr(pb[1]) if pb[0] == "lit" else pb[1]
    return left == right


def canon(value: Any) -> str:
    p = _parse(value)
    if p[0] == "lit":
        return repr(p[1])
    if p[0] == "empty":
        return ""
    return str(p[1])


# A function is only called confusing when the *lower* bound of its Wilson
# interval clears this: with 15 graded predictions that means >= 7 wrong.
CONFUSING_LOWER_BOUND = 0.20
Z_95 = 1.96


def wilson_interval(wrong: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion (no scipy needed)."""
    if total <= 0:
        return (0.0, 1.0)
    n = float(total)
    p = wrong / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    margin = z * ((p * (1.0 - p) / n + z2 / (4.0 * n * n)) ** 0.5) / denom
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def label(wrong: int, total: int, consensus_wrong: int = 0) -> str:
    """Clear / Scattered / Confusing / Consensus misread, from the interval."""
    lo, _ = wilson_interval(wrong, total)
    if lo > CONFUSING_LOWER_BOUND:
        return "Consensus misread" if consensus_wrong >= 3 else "Confusing"
    return "Clear" if wrong == 0 else "Scattered"


def score_function(
    key: str,
    probe_entry: dict,
    answers: dict[str, dict[str, str]],
    personas: list[str] | None = None,
) -> dict:
    personas = personas or WITNESS_PERSONAS
    probes = [p for p in probe_entry.get("probes", []) if p.get("ok")]
    summaries = answers.get("__summaries__", {}).get(key, {})
    cards = []
    total = wrong = consensus = 0
    disagreements = []
    witnesses_clean = {p: True for p in personas}

    for idx, probe in enumerate(probes):
        actual = probe.get("repr")
        per_probe = answers.get(key, {}).get(str(idx), {})
        row = {"input": {"args": probe.get("args"), "kwargs": probe.get("kwargs")},
               "label": probe.get("label"), "actual": actual, "cards": []}
        seen: set[str] = set()
        probe_wrong = 0
        for persona in personas:
            pred = per_probe.get(persona, "")
            is_right = bool(pred) and same(pred, actual)
            total += 1
            if not is_right:
                wrong += 1
                probe_wrong += 1
                witnesses_clean[persona] = False
            if pred:
                seen.add(canon(pred))
            row["cards"].append(
                {
                    "witness": persona,
                    "prediction": pred,
                    "correct": is_right,
                    "summary": summaries.get(persona, ""),
                }
            )
        n_distinct = len(seen) if seen else 1
        disagreements.append(n_distinct)
        row["distinct_answers"] = n_distinct
        row["wrong"] = probe_wrong
        consensus = max(consensus, probe_wrong)
        cards.append(row)

    n_probes = len(probes)
    misread_rate = (wrong / total) if total else 0.0
    disagreement_mean = (sum(disagreements) / len(disagreements)) if disagreements else 0.0
    clean = [p for p, ok in witnesses_clean.items() if ok]
    ci_lo, ci_hi = wilson_interval(wrong, total)
    verdict = label(wrong, total, consensus)
    return {
        "key": key,
        "n_probes": n_probes,
        "n_witnesses": len(personas),
        "predictions": total,
        "misreads": wrong,
        "misread_rate": round(misread_rate, 4),
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "consensus_wrong": consensus,
        "disagreement_mean": round(disagreement_mean, 3),
        "disagreement_max": max(disagreements) if disagreements else 0,
        "witnesses_correct": len(clean),
        "witnesses_correct_of": len(personas),
        "witnesses_clean": clean,
        "label": verdict,
        "verdict": "confusing" if verdict in ("Confusing", "Consensus misread")
        else ("scattered" if verdict == "Scattered" else "clear"),
        "probes": cards,
    }


def score_all(
    functions: list[dict],
    probe_entries: dict[str, dict],
    answers: dict[str, dict],
    personas: list[str] | None = None,
) -> list[dict]:
    out = []
    for fn in functions:
        key = fn["key"]
        if key not in probe_entries or key not in answers:
            continue
        res = score_function(key, probe_entries[key], answers, personas)
        res["path"] = fn.get("path")
        res["qualname"] = fn.get("qualname")
        res["signature"] = fn.get("signature")
        res["source"] = fn.get("source")
        res["docstring"] = fn.get("docstring")
        res["n_lines"] = fn.get("n_lines")
        out.append(res)
    out.sort(key=lambda r: (-r["misread_rate"], -r["disagreement_max"], r["key"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
