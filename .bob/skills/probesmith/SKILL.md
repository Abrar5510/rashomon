---
name: probesmith
description: Design three discriminating probe inputs per function without ever guessing what they return. Use when a Rashomon run needs better inputs than the signature heuristic produced.
---

# Probesmith

You design inputs. You never state outputs.

1. Read `rashomon_out/functions.json` and the target source file the user @-mentions.
   Do not read `rashomon_out/probes.json`, `rashomon_out/results.json`, `tests/` or
   anything under `targets/` — those contain the answers.

2. For each function, write exactly three probes using the atoms-of-confusion recipe:
   - **P1 typical** — the input a normal caller would pass.
   - **P2 boundary** — constants pulled from the function's own branch conditions,
     plus empty, zero, negative or unicode values.
   - **P3 discriminating** — first list two or three plausible *misreadings* of the
     function (for example "it treats the second argument as inclusive", "it returns
     None when the input is empty"), then pick an input on which those readings
     produce different results. Do not write down which reading you believe.

3. Write them to `rashomon_out/probes.proposed.json`, one entry per function:

   ```json
   {"key": "chronex/parsing.py::parse_duration",
    "cases": [{"args": ["1h30m"], "kwargs": {}, "label": "typical", "why": "..."}]}
   ```

   Arguments must be JSON literals the function accepts. Never include an expected
   output anywhere in the file.

4. Tell the user to run `make probes` so the runner executes the inputs and seals
   the actual outputs.
