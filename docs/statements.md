# Submission texts

Word counts are checked with `wc -w`. All numbers below come from the live
runs of 27 Sep 2026 (`out/live-demo/`, `out/boltons/`); no placeholders remain.

---

## Title

`Rashomon` (8 characters, letters only)

## Short description (≤ 255 characters)

```
Five isolated AI readers predict what your function returns, then we run it.
Disagreement and wrong guesses turn readability into a test, with a PR gate, a
Clarifier that rewrites confusing code, and a leaderboard for real libraries.
```

```
wc -c <<< "..."   # keep it under 255
```

---

## Long description (≤ 500 words)

Software teams spend most of their time reading code — about 58% of it (Xia et
al., TSE 2018) — and almost all of our tooling measures the wrong side of that.
We count tokens, lines and cyclomatic complexity: over 120 readability metrics
have been proposed and Scalabrino et al. showed they fail to track human
judgement. The newest idea, asking an LLM "is this readable?", is worse: CoReEval
found the model's ratings correlate with humans at roughly ρ ≈ 0. Opinions, all the way down.

**The insight: don't ask, check.** Predict what the function returns, then run it.
A wrong prediction is not a style complaint — the code genuinely misled a reader.
Five readers who disagree with each other are five readings of the same source,
and the executing program decides who was right.

**Pipeline.** Rashomon picks functions from a diff or by git churn, generates probe
inputs from each signature, and executes them in a subprocess with a timeout to
record ground truth. Five independent readers — `careful-stylist`, `speed-reader`,
`regex-allergic`, `api-historian`, `edge-case-hunter` — see only the source and
the inputs, never the outputs, and each returns a prediction per probe. Every prediction is graded against execution-derived rules, with abstentions
counted as wrong. Separately, `git log` plus a source-diff filter counts how often each
function has actually been fixed. The result is a misread rate, a disagreement
count and a bug-fix history for every function.

**Users.** Developers and reviewers, especially teams whose code is edited by AI
agents: an agent's rewrite that is easier for five readers to predict is a rewrite
that is easier for the next human *and* the next model to maintain.

**How it is used.** In Bob, mode `rashomon` runs the skill that fans out the five
readers as isolated subagents. `make gate` turns a run into a non-blocking PR
comment that fails only when a function gets more confusing. Mode `clarifier`
rewrites one confusing function, and `equiv` proves the copy behaves identically
before the new reading is measured. The static leaderboard ranks functions by
misread rate and overlays bug-fix counts.

**Novelty.** CRUXEval uses code to grade models; Rashomon inverts it: independent
readers, ground truth, disagreement metric — a lab study turned into a CI check
that runs on every pull request.

**Measured results (bundled demo, recorded session).** 9 functions, 5 readers,
135 graded predictions, 21 wrong (16%). `parse_duration` was misread by 7 of 15
readers (47%) while `mean` was read by all 5 — the ranking separates the confusing
code from the clear code with no human label anywhere.

**Live run on `boltons` (30 functions).** Five independent `gemini-3.5-flash-lite`
readers, 410 graded predictions: 9 functions are *Consensus misread* (every
reader wrong), 4 *Scattered* (readers disagree), 17 *Clear* (all readers clean).
Side-effecting APIs like `iteritems` are misread 100% of the time. Misread rate correlates with real bug-fix history
— Spearman ρ = 0.394, p = 0.031, 95% CI [0.03, 0.71] — so the score tracks
maintenance pain, not style opinions.

---

## Bob Usage Statement (≤ 500 words)

**Three custom modes** in `.bob/custom_modes.yaml`, each with tool limits.
`rashomon` reads exactly one witness packet per invocation; `probesmith` may run
the probe harness but never sees witness answers; `clarifier` edits one module and
must prove equivalence afterwards.

**Three skills.** `.bob/skills/rashomon/SKILL.md` (fan out five readers, collect
JSON), `.bob/skills/probesmith/SKILL.md` (invent inputs that separate two
plausible misreadings), `.bob/skills/clarify/SKILL.md` (rewrite for a new reader,
behaviour frozen).

**Parallel isolated witnesses.** Five `explore` subagents run concurrently with
`fork_context: false`, one tool call each: read the packet, return JSON. They never
share context, so agreement between them is real agreement, not groupthink.

**`.bobignore` is the isolation boundary.** `targets/`, `out/`, `rashomon_out/`,
`demo/target_repo/tests/` and the answer files are hidden from every witness. A
sealed canary, `ZEBRA-7731` in `.bob/sealed/canary.json`, proves it: the spike asks
each witness what is in that file and the answer must be "not present".

**Rollback in the Clarifier loop.** The Clarifier writes to a copy under
`rashomon_out/clarified/`, never to the target. `equiv` re-runs the sealed probes
plus signature-derived extra inputs and prints `N/N identical`; a mutation as small
as flipping `<` to `<=` is caught, so a failed check means the edit is discarded.

**Gate (current state).** `make gate` runs the pipeline locally and writes the
PR comment body to `rashomon_out/comment.md` (it fails only when a function gets
more confusing, and the comment carries the 95% CI). The designed `bob run
--mode rashomon --max-cost …` wrapper is written but unconfirmed — `bob` is not
on PATH in this environment — so the gate has not been wired through Bob Shell.

**Agent-mode build tasks.** Every stage of this project was delegated to Bob
subagents — extraction, probe design, scoring, history, web UI, tests — against the
briefs in `IDEAS.md`.

**Coin discipline.** Subagents that only read take the cheapest settings;
`fork_context: false` prevents five witnesses from paying for each other's context;
packets are ≤ 6 functions so each task stays inside one task's budget.

**watsonx.** Not used in this build.

**`bob_sessions/`.** Ten captures from the Bob task that produced the live
clarified result: `00_smoke_test`, `01_smoke_rashomon_skill` (the skill firing),
`02_witness_run_done`, `03_approval_pending`, `04_score_report`,
`05_clarifier_slugify` (a discarded hardcoded claim — caught on the spot, never
quoted), `06_slugify_clarified_result` + `07_equiv_gate` (the measured 47% → 0%
with `15/15 identical`), `08_permissions`, `09_custom_modes` (the three modes in
Settings). The frozen run artifacts — five answers, `results.json`,
`witnesses.json`, `comment.md`, the rewritten copy — sit beside them in
`bob_sessions/clarified_artifacts/`.
