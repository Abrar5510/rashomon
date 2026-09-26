from __future__ import annotations

import json
import os

HEADER = """# Witness packet {batch}

You are one of several independent readers in a code-reading study.
You have never seen this code before and you may not run it.

Read this file only. Do not open, list, grep or search any other file.
Do not execute anything.

For every probe below, predict the EXACT return value as a Python literal
(for example `'1024K'`, `[1, 2]`, `(2.0, 'months')`), or write `raises ExceptionName`.
Never answer "I don't know": always give your best guess with a confidence from 1 to 5.

Reply with ONLY this JSON, no prose, no code fences:

```json
{{"witness": <your id>, "answers": [{{"fn": "<key>", "probe": 0, "prediction": "<literal>", "confidence": 3}}], "summaries": {{"<key>": "<one line: what the function does>"}}}}
```

---

"""

FUNCTION_BLOCK = """
## {qualname}  (`{path}`)

```python
{source}
```

Probes:
{probes}
"""


def build_packet(batch: str, functions: list[dict], probe_entries: dict[str, dict]) -> str:
    parts = [HEADER.format(batch=batch)]
    for fn in functions:
        entry = probe_entries.get(fn["key"], {})
        probes = []
        for i, p in enumerate(entry.get("probes", [])):
            if not p.get("ok"):
                continue
            # inputs only - never the actual output
            call = f"{fn['qualname'].split('.')[-1]}({json.dumps(p.get('args', []))}"
            if p.get("kwargs"):
                call += ", **" + json.dumps(p["kwargs"])
            call += ")"
            probes.append(f"{i}. `{call}`")
        if not probes:
            continue
        parts.append(
            FUNCTION_BLOCK.format(
                qualname=fn["qualname"],
                path=fn["path"],
                source=fn.get("source", ""),
                probes="\n".join(probes),
            )
        )
    return "".join(parts)


def write_packets(
    out_dir: str,
    functions: list[dict],
    probe_entries: dict[str, dict],
    size: int = 6,
) -> list[str]:
    runnable = [f for f in functions if any(
        p.get("ok") for p in probe_entries.get(f["key"], {}).get("probes", [])
    )]
    written: list[str] = []
    for n, start in enumerate(range(0, len(runnable), size), 1):
        batch = f"B{n:02d}"
        path = os.path.join(out_dir, "packets", f"{batch}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_packet(batch, runnable[start:start + size], probe_entries))
        written.append(path)
    return written
