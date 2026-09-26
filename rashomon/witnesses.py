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
) -> dict:
    """Return {key: {probe_idx: {persona: prediction}}}."""
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
        out: dict[str, dict] = {}
        summaries: dict[str, dict] = {}
        for fn in fns:
            entry = probes_by_key.get(fn.key, {})
            runnable = [p for p in entry.get("probes", []) if p.get("ok")]
            if not runnable:
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
                except Exception as exc:
                    parsed = {"summary": f"error: {exc}", "predictions": [""] * len(runnable)}
                summaries[fn.key][persona] = parsed["summary"]
                for i, pred in enumerate(parsed["predictions"]):
                    cols[i][persona] = pred
            out[fn.key] = {str(i): cols[i] for i in range(len(cols))}
        out["__summaries__"] = summaries
        return out

    raise ValueError(f"unknown witness backend {backend!r} (use 'file' or 'llm')")
