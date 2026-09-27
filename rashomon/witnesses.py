from __future__ import annotations

import json
from typing import Any

from . import WITNESS_PERSONAS
from .astx import FunctionInfo
from .llm import LLMBackend, strip_fences

PERSONA_TEXT = {
    "careful-stylist": "You read slowly and care about naming and structure.",
    "speed-reader": "You skim. You answer from shape and keywords, not careful tracing.",
    "regex-allergic": "You avoid pattern-matching; you reason about control flow only.",
    "api-historian": "You judge by what similar functions in this ecosystem usually do.",
    "edge-case-hunter": "You jump straight to boundaries and unusual inputs.",
}


def witness_prompt(fn: FunctionInfo, probes: list[dict], persona: str | None = None) -> tuple[str, str]:
    inputs = []
    for i, p in enumerate(probes):
        inputs.append(f"{i}: {fn.name}({json.dumps(p['args'])}"
                      + (", **" + json.dumps(p["kwargs"]) if p.get("kwargs") else "") + ")")
    system = (
        "You are one of several independent readers reviewing code you have never seen before. "
        "You cannot run it. Predict its exact return value.\n\n"
        'Reply with ONLY JSON: {"summary": "<one line: what this function does>", '
        '"predictions": ["<repr of return for input 0>", "<... input 1>", "<... input 2>"]}\n'
        "Each prediction must be a Python literal exactly as repr() would print it "
        "(strings single-quoted, booleans True/False). No prose, no markdown."
    )
    user = (
        (f"Reader persona: {PERSONA_TEXT.get(persona, persona or '')}\n\n" if persona else "")
        + f"```python\n{fn.source}\n```\n\n"
        + "Predict the return value for each input:\n" + "\n".join(inputs)
    )
    return system, user


def parse_witness_reply(text: str, n: int) -> dict:
    raw = strip_fences(text)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("witness reply contained no JSON object")
    data = json.loads(raw[start : end + 1])
    preds = list(data.get("predictions", []))
    while len(preds) < n:
        preds.append("")
    return {"summary": str(data.get("summary", "")), "predictions": preds[:n]}


def run_witnesses(
    fns: list[FunctionInfo],
    probes_by_key: dict[str, dict],
    backend: str = "file",
    source_path: str | None = None,
    llm: LLMBackend | None = None,
    personas: list[str] | None = None,
    checkpoint: str | None = None,
) -> dict:
    """Return {key: {probe_idx: {persona: prediction}}}.

    checkpoint: for backend=llm, a JSON path rewritten after every function so
    an interrupted run (quota, Ctrl-C) keeps its progress and a rerun resumes
    from the completed functions instead of starting over.
    """
    personas = personas or WITNESS_PERSONAS

    if backend == "file":
        if not source_path:
            raise ValueError("backend=file requires a recorded witness file")
        with open(source_path, "r", encoding="utf-8") as fh:
            recorded: dict[str, Any] = json.load(fh)
        out: dict[str, dict] = {}
        for fn in fns:
            n = len([p for p in probes_by_key.get(fn.key, {}).get("probes", []) if p.get("ok")])
            per_fn: dict[str, dict] = {}
            for i in range(n):
                answers = {}
                for persona in personas:
                    answers[persona] = recorded.get(f"{fn.key}#{i}#{persona}", "")
                per_fn[str(i)] = answers
            out[fn.key] = per_fn
        out["__summaries__"] = recorded.get("__summaries__", {})
        return out

    if backend == "llm":
        if llm is None:
            raise ValueError("backend=llm requires an LLM backend instance")
        import os
        import sys
        import time as _time

        out: dict[str, dict] = {}
        summaries: dict[str, dict] = {}
        prev: dict[str, Any] = {}
        if checkpoint and os.path.exists(checkpoint):
            with open(checkpoint, "r", encoding="utf-8") as fh:
                prev = json.load(fh)
            done = [k for k in prev if not str(k).startswith("__")]
            if done:
                print(f"  resuming: {len(done)} function(s) already answered", file=sys.stderr)

        def complete_fn(fn_key: str) -> bool:
            """True when a previous checkpoint already has every answer for fn_key."""
            prev_fn = prev.get(fn_key)
            if not isinstance(prev_fn, dict):
                return False
            return all(
                isinstance(by_persona, dict) and all(str(v) for v in by_persona.values())
                for by_persona in prev_fn.values()
            )

        t0 = _time.time()
        failures = 0
        for fn in fns:
            entry = probes_by_key.get(fn.key, {})
            runnable = [p for p in entry.get("probes", []) if p.get("ok")]
            if not runnable:
                continue
            if complete_fn(fn.key):
                out[fn.key] = prev[fn.key]
                summaries[fn.key] = (prev.get("__summaries__") or {}).get(fn.key, {})
                continue
            system, _ = witness_prompt(fn, runnable)
            cols: list[dict[str, str]] = [dict() for _ in runnable]
            summaries[fn.key] = {}
            for persona in personas:
                _, user = witness_prompt(fn, runnable, persona)
                try:
                    parsed = parse_witness_reply(
                        llm.complete(system, user), len(runnable)
                    )
                    failures = 0
                except Exception as exc:
                    parsed = {"summary": f"error: {exc}", "predictions": [""] * len(runnable)}
                    failures += 1
                    if failures >= 6:
                        out["__summaries__"] = summaries
                        if checkpoint:
                            with open(checkpoint, "w", encoding="utf-8") as fh:
                                json.dump(out, fh, indent=1, sort_keys=True)
                        raise ValueError(
                            f"aborting after {failures} consecutive witness failures "
                            f"({exc}). Partial answers saved to {checkpoint}; "
                            "rerun the same command later to resume."
                        )
                summaries[fn.key][persona] = parsed["summary"]
                for i, pred in enumerate(parsed["predictions"]):
                    cols[i][persona] = pred
            out[fn.key] = {str(i): cols[i] for i in range(len(cols))}
            if checkpoint:
                out["__summaries__"] = summaries
                with open(checkpoint, "w", encoding="utf-8") as fh:
                    json.dump(out, fh, indent=1, sort_keys=True)
            print(
                f"  [{len(out)}] {fn.key}: {len(personas)} readers on {len(runnable)} probe(s)"
                f" ({_time.time() - t0:.0f}s)",
                file=sys.stderr,
                flush=True,
            )
        out["__summaries__"] = summaries
        return out

    raise ValueError(f"unknown witness backend {backend!r} (use 'file' or 'llm')")
