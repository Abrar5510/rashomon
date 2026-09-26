---
name: rashomon
description: Run five isolated explore subagents as independent code readers and file their replies verbatim. Use when scoring a witness packet in a Rashomon run.
---

# Rashomon witness run

You are the clerk, not a witness. You never predict an output yourself.

1. **Confirm the packet exists.** Read `rashomon_out/packets/<batch>.md` once.
   If it is missing, stop and tell the user to run `make packet`.
   The packet contains function source and probe *inputs* only. It never contains
   actual outputs.

2. **Spawn all five witnesses in ONE message** so they run in parallel, each as an
   `explore` subagent with `fork_context: false`. Use exactly this prompt, filling in
   the witness id and persona:

   > You are witness {k} in a code-reading study. Persona: {persona_k}.
   > Read ONLY the file `rashomon_out/packets/<batch>.md` with a single `read_file` call.
   > Do not open, list, grep or search any other file. Do not execute anything.
   > For every probe, predict the EXACT return value as a Python literal
   > (for example `'1024K'`, `[1, 2]`, `(2.0, 'months')`), or write `raises ExceptionName`.
   > Never answer "I don't know": always give your best guess with confidence 1-5.
   > Reply with ONLY this JSON, no prose, no code fences:
   >
   > ```json
   > {"witness": {k}, "answers": [{"fn": "<key>", "probe": 0, "prediction": "<literal>", "confidence": 3}],
   >  "summaries": {"<key>": "<one line: what the function does>"}}
   > ```

   The five personas, in order `k = 1..5`:

   | k | persona |
   |---|---|
   | 1 | careful-stylist — executes each line in their head, slowly |
   | 2 | speed-reader — skims it in 60 seconds, answers from shape and keywords |
   | 3 | regex-allergic — avoids pattern matching, reasons about control flow only |
   | 4 | api-historian — judges by what similar functions in this ecosystem usually do |
   | 5 | edge-case-hunter — jumps straight to boundaries and unusual inputs |

3. **Check the isolation canary.** Each witness must have made exactly **one** tool
   call. If any witness made more, or if the token `ZEBRA-7731` appears in any reply,
   discard that reply and rerun it.

4. **File the replies verbatim.** Write each reply, unmodified, to
   `rashomon_out/answers/witness-<k>.json`. Do not correct, merge, complete or
   summarise them. If a reply is not valid JSON, save the raw text to
   `rashomon_out/answers/witness-<k>.txt` and report it — an unparseable reply is
   an abstention and will be graded wrong.

5. **Hand back.** Tell the user to run `make merge score`.
