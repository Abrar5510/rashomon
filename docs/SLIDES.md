# Slides (7) — 2–3 sentences each → export as `docs/slides.pdf`

**Cover:** five cards fanned out showing `'1h30m'`, `3600`, `90`, `5400`, `5400`,
titled **RASHOMON: unit tests for readability**. 16:9.

1. **Problem.** 58% of development time is spent reading code, yet every metric we
   have measures the file, not the reader. 121 readability metrics have been
   proposed and shown not to track human judgement.

2. **Insight.** Don't ask whether code is readable — ask what it returns, then run
   it. A wrong prediction is ground truth that the source misled a reader, and five
   readers who disagree give you a distribution instead of an opinion.

3. **How it works.** Bob fans five isolated `explore` subagents out over one witness
   packet with `fork_context: false` and one tool call each; `.bobignore` hides
   every answer and the target repo from them, proven by a sealed canary. The
   harness executes probe inputs, grades the predictions, and `git log` supplies
   the fix history.

4. **Results.** Live run on 30 `boltons` functions, 5 readers, 410 predictions:
   9 consensus-misread, 4 scattered, 17 clear — and misread rate tracks real
   bug-fix history (Spearman ρ = 0.394, p = 0.031). On the demo, `parse_duration`
   misleads 7 of 15 readings while `mean` is read correctly by all five, with no
   human label anywhere in the system.

5. **PR gate.** `make gate` writes a pull-request comment with a misread rate per
   function and fails only when a change makes code *more* confusing. Readability
   becomes a check a team can regress on, not a review argument.

6. **Market and competition.** CoReEval rates code with an LLM (ρ ≈ 0 against
   humans), CRUXEval grades models with code, linters count tokens. Rashomon is the
   one that turns independent readings plus execution into a test.

7. **Future.** JS/TS targets, a cross-model-family witness panel, an editor squiggle
   for confusing code, and a watsonx witness for a sixth independent reader.
