# PENDING — what was not built, not verified, or needs a human

Everything below is either **impossible in this environment**, **unverified**, or
**explicitly out of the one-shot build**. Nothing here was half-built and left
running. The parts that *are* built and verified are in `README.md`.

---

## A. Blocked — no credentials, no Bob CLI in this environment (A1–A3 resolved with a Gemini key, 27 Sep; A4–A6 remain)

| # | Item | Why | What to do |
|---|---|---|---|
| A1 | **A live 5-witness run on a real library** | **DONE.** A Gemini `GOOGLE_API_KEY` is wired as provider `gemini` with `--provider auto` (commit `6097f13`); the flagship run lives in `out/boltons/` — 5 live readers × 30 boltons functions, **410 predictions** on `gemini-3.5-flash-lite` (the `gemini-3.8-flash` free tier is only 20 req/day — hence lite as default, `RASHOMON_MODEL` overrides). `out/live-demo/` holds the 8-function demo run (40 calls). Witness runs checkpoint per function and resume after interruption. | — |
| A2 | **`web/data.json` is a recorded session, not a live run** | **DONE.** The site carries `"session": "live"` and is the 30-function boltons run (`out/boltons/data.json`). The recorded fixture session is still reproducible offline via `make demo` (`demo/fixtures/witnesses.json`). | When swapping sessions, say on the site *which* model produced the numbers — model families disagree with the fixtures. |
| A3 | **The 30-function boltons leaderboard** | **DONE.** Live run in `out/boltons/`: 410 predictions, labels **9 Consensus misread / 4 Scattered / 17 Clear**, and the headline correlation the fixtures could not show — bug_fixes Spearman **ρ = 0.394, p = 0.031, 95% CI [0.03, 0.71] ***. Published to `web/data.json`. | — |
| A4 | **watsonx.ai Granite / Llama witnesses** (the optional 6th witness in `IDEAS.md`) | No `WATSONX_APIKEY` / `WATSONX_PROJECT_ID`. No `witness_watsonx.py` was written. | Request the account, then write ~80 lines using `POST https://iam.cloud.ibm.com/identity/token` and `POST https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2024-03-14`, model `ibm/granite-4-h-small`. |
| A5 | **Screenshots in `bob_sessions/`** | **Solved**, 9 real captures from the Bob IDE UI (driven by `scripts/bob_drive.py`, which
posts `CGEvent` mouse events; System Events clicks are blocked by TCC `-25211`, so
`osascript` can only type). Files: `00_smoke_test`, `01_smoke_rashomon_skill`,
`02_witness_run_done`, `03_approval_pending`, `04_score_report`, `05_clarifier_slugify`,
`06_slugify_clarified_result`, `07_equiv_gate`, `08_permissions`, `09_custom_modes.jpg`.
| **Still open:** `bob_sessions/` is git-ignored (`.gitignore` line 22), so the shots
will not ride along with a push — un-ignore the directory or attach the files to the
submission by hand. Also match `docs/VIDEO.md`'s naming (`taskNN_<desc>`) when cutting. |
| A6 | **Video (≤3 min, ≥90 s live), slides PDF, cover image, statements** | **Slides PDF (`docs/slides.pdf`, 8 pages incl. cover) ✅, cover image (`docs/cover.png`) ✅, statements filled with live numbers ✅ (27 Sep).** Remaining: the video — recording/editing in the IDE, outside a code build (storyboard ready in `docs/VIDEO.md`; `ffmpeg` present; ⚠️ free disk ~9.6 GB). | See `IDEAS.md` §Video and the plan's §8. |

---

## B. Written but NOT executed or verified

| # | Item | Status |
|---|---|---|
| B1 | `.bob/custom_modes.yaml` schema | Written to the researched Bob 2.0 shape (`customModes` / `slug` / `roleDefinition` / `whenToUse` / `customInstructions` / `allowedSubagents` / `groups` + `fileRegex`). **Loaded and verified** — Bob's Settings → Modes lists `🎭 Rashomon`, `🧪 Probesmith` and `🔍 Clarifier` as *Workspace* modes beside the built-ins (`bob_sessions/09_custom_modes.jpg`). If a future Bob rejects `allowedSubagents` or `fileRegex`, fall back to: drop the key and enforce the rule via `customInstructions` plus the "exactly one tool call" check. |
| B2 | `.bob/skills/*/SKILL.md` front matter | `name` + `description` present as Bob requires. **Loaded and verified** — the skill fires in a task (`bob_sessions/01_smoke_rashomon_skill.png`) and the Skills list renders. |
| B3 | `.github/workflows/rashomon.yml` | Written (PR trigger + `/rashomon` comment trigger, pick → probes → witness → score → gate → comment → artifact). **Never run** — no repo, no `ANTHROPIC_API_KEY` secret, no `gh` verification. Treat as a draft. |
| B4 | **Bob Shell (`bob run --mode rashomon`) integration** | **Not wired up.** `bob` is not on PATH here, so nothing shells out to it. The gate is a *local* `make gate` (Python + `--comment-file`) instead. Add `bob run` only after `bob run --format json --max-cost …` is confirmed to work. |
| B5 | **Vercel / GitHub Pages deployment** | `make deploy` is wired (`cd web && vercel deploy --prod`), but **not executed**: `vercel` is installed with no valid credentials and the device-code login failed twice — first with a stale code, then with `configuration error with this app`. GitHub Pages would work (`gh` is authenticated with `repo`) but needs a public repo push. | `vercel login` from a normal terminal (not the device flow), or `vercel login <email>`, then `make deploy`. Or create a token at vercel.com/account/settings/tokens and run `make deploy VERCEL_TOKEN=…`. |
| B6 | `targets/boltons` clone | Present at `4e5faa3d`, git-ignored, `.bobignore`d. Re-create with `git clone https://github.com/mahmoud/boltons targets/boltons && git -C targets/boltons checkout 4e5faa3d`. |
| B7 | MIT `LICENSE` copyright line | Placeholder `Rashomon contributors` — **decided to keep** (no personal data in a public repo). No action needed. |

---

## C. Designed but only partially implemented

| # | Item | What exists | What is missing |
|---|---|---|---|
| C1 | **Bug-history correlation statistics** | **DONE.** `rashomon stats` (`make stats`) prints Spearman ρ of misread rate against bug fixes, churn, LOC and AST branch count, with a 10k permutation p-value and a bootstrap 95% CI, and writes `stats.json`. Covered by tests. | The script now exists, but it was written *after* the demo numbers were already visible, so the "committed before the result is known" discipline is a process step for the repo history, not a property of this build. |
| C2 | **Labels and confidence** | **DONE.** 95% Wilson interval per function plus the labels `Clear` / `Scattered` / `Confusing` / `Consensus misread`, gated on the lower bound > 0.20. Shown in `make score`, the PR comment and the site chips. | — |
| C3 | **Held-out probes (P′)** | **DONE.** `rashomon seal` (`make seal`, part of `make demo`/`run-all`) generates a deterministic 9-case P′ set from the function signatures (coherent slot-0 call, salted by key, rotating which parameter varies), keeps 3 runnable probes/function disjoint with the scored probes, and freezes everything under `rashomon_out/sealed/` with per-entry sha256 + file hash + the `probes.json` hash it must stay disjoint with. `make seal-verify` re-checks the freeze; tamper detection (file-level and entry-level) is covered by tests. Both `sealed/` and `lifted/` are in `.bobignore` so witnesses cannot read them. | — |
| C3b | **`make rewatch` end-to-end ΔM** | **ΔM measured end to end inside Bob (27 Sep).** Clarifier rewrote `chronex/text.py::slugify` into `rashomon_out/clarified/` (`make equiv` → `15/15 identical`), then five fresh `explore` witnesses read *only* the clarified copy, wrote `rashomon_out/answers/witness_{1..5}.json`, and `make merge` + `make score` gave **47% (7/15), CI 0.25–0.70 → 0% (0/15), CI 0.00–0.20, `Consensus misread` → `Clear`**, independently reproduced by running `make score` outside Bob. The five answer files carry five *different* `summaries`, so they are separate reads and not one copy-paste. The `make rewatch` script itself was still not run — see the caveat in G2. | `WITNESS_BACKEND=file` still replays the same recorded answers, so `make rewatch` gives before == after by construction. |
| C4 | **Probe design quality** | `heuristic` (signature + parameter-name inference, runs 23/30 boltons functions) and `llm`. | The probesmith recipe — typical / boundary / **discriminating** (pick an input where two plausible *misreadings* diverge). The skill is written; the discriminating case still needs a model. |
| C5 | **"Be the 6th witness"** | **DONE.** Client-side guess box on `web/index.html` (drawer) and `web/fn.html`: cards start face-down, the interpreter's output is hidden until the visitor checks a guess. The comparison mirrors `score.same` exactly (typed Python-literal parser: bool/int/float strictness, tuple vs list, order-insensitive dicts, repr-vs-bare-string mixed case) — verified against Python on 1,941 pairs, 0 mismatches. Abstention (empty guess) counts as a misread, in line with D5. Tally is in-memory only; nothing is stored. | — |
| C6 | **Name-lift diagnostic** | **DONE.** `rashomon lift` (`make lift`) writes an anonymised copy of the repo under `rashomon_out/lifted/` — function → `f_<hash>`, parameters → `p0..`, locals → `v0..` — preserving control flow, attributes, literals and docstring prose; re-runs the probes on the lifted root to prove behaviour is unchanged before anything scores it. `LIFTED=1` on `witness`/`score`/`packet` and `make lift-report` show original-vs-lifted misread rate (Δpp). On the recorded session ΔM = 0 by construction — a plumbing null test; a real separation of naming vs structure effects needs live witnesses — now runnable (`LIFTED=1 WITNESS_BACKEND=llm` with `GOOGLE_API_KEY`, A1 done) but not yet executed. | — |
| C7 | **`fn.html?id=` detail page** | **DONE.** `web/fn.html?id=<key>` renders the same detail as the drawer (source, probes, guess box, summaries, fix commits) as a standalone shareable page, with a back-link to the leaderboard and a sensible error for a missing/unknown id. The drawer links to it ("shareable page ↗"). Shared render/guess logic lives in `web/common.js`. | — |
| C8 | **Cross-model agreement** | Personas vary the *prompt* only. | A second model family (A4). If all five readers make the **same** wrong answer, personas will not fix it — that result is a finding (atoms of confusion), not a bug, but say so. |

---

## D. Known weaknesses in what *was* built

| # | Weakness | Detail | Mitigation |
|---|---|---|---|
| D1 | **Probe execution is not sandboxed** | `runner.run_case` spawns `subprocess.run([python, harness], timeout=…)` with `PYTHONPATH` pointing at the target repo. Arbitrary code runs. | Only point it at repos you trust. Add `bubblewrap`/`firejail` or a container before running it on untrusted code. |
| D2 | **0 runnable probes for some functions** | 7 of 30 boltons functions (e.g. `cached`, `cachedmethod`, `OrderedMultiDict.fromkeys`) produce no runnable input — usually a `__init__` that needs constructor arguments, or a decorator factory. | Pass a `--probes-file`, or run probesmith. |
| D3 | **`git log -L` line-range bleed** | Line ranges can drag a neighbouring function's commit in. A `_touched_function()` check (compare the function's source at `sha` vs `sha^`) removes most false positives, but `.gitattributes` `*.py diff=python` should still be added to the target repo for proper funcname detection. | Add `.gitattributes`; prefer `-L :funcname:file` where the driver exists. |
| D4 | **Class instances need a no-arg constructor** | The harness instantiates `Owner()` and binds the method. Classes whose constructor needs arguments yield 0 probes (see D2). | |
| D5 | **Abstentions are graded wrong** | A missing/unparseable witness reply counts as a wrong prediction (deliberate, per the plan). A `make merge` with only 1 of 5 replies therefore reports ~80% misread. | Always run all five before reading the number. |
| D6 | **Iterator / generator returns** | Results with a `__next__` are materialised up to whatever `repr()` gives; results whose repr contains `0x` or starts with `<` are dropped as unstable. | |
| D7 | **Python only** | JS/TS is explicitly a gated stretch goal and was not attempted. | |
| D8 | **`rashomon_out/` is regenerated output** | **Resolved** — `rashomon_out/` and `bob_sessions/` are git-ignored; `web/data.json` stays tracked so the site works from a fresh clone. | Regenerate with `make demo`. |
| D9 | **Disk space** | The plan warns the machine had **1.3 GB free**, which is not enough to record video. | Free ≥20 GB before recording. Not checked in this session. |

---

## E. Confusing / ambiguous, so it was left alone

1. **`.bobignore` vs writes.** It is not documented whether a `.bobignore`d path can
   still be *written* by Bob. `rashomon_out/answers/` is therefore **not** in
   `.bobignore` (Bob has to write it); isolation for that path comes from the mode's
   `fileRegex` instead. Verify in the first-hour spike.
2. **Whether `fork_context: false` isolates file access.** The research says it only
   isolates conversation history, so `.bobignore` + packet-only prompting is what
   actually isolates. Confirm with the `ZEBRA-7731` canary.
3. **Whether a hackathon Bob account can mint a `BOB_API_KEY`** for the GitHub
   Action. Until that is answered, the Action stays a draft (B3) and the gate stays
   local (B4).
4. **Custom mode scope.** Custom modes appear to apply to the *parent* task only, not
   to subagents — hence witnesses are `explore` presets restricted by `.bobignore`
   rather than a "witness mode". That matches the researched correction, but it was
   not confirmed by running Bob.
5. **Which repo to publish under.** The plan says a new public repo created from
   `watsonxhackathon/ibm-hackathon-template`, with template ignore files left
   unmodified above their marker. This build lives in `projects/Bob` and was not
   pushed anywhere.

---

## G. The Bob session that produced `bob_sessions/` — and the one thing it got wrong

**G1 · What actually ran.** One task in the Bob IDE, `fea68ca6caec2a8d1cf4b36e9db9bb1c`
(messages 1 → 126, all verifiable in `~/.bob/db/bob.db`). Sequence: `use_skill rashomon`
→ read `rashomon_out/packets/B01.md` → five `explore` witnesses in parallel (canary
`ZEBRA-7731` absent from all five) → `make merge` + `make score` → `make brief` +
the Clarifier rewrite → a **second** five-witness run on the clarified copy →
`make equiv` → `make gate`. Every step is a real tool call in the transcript; nothing
was written by hand.

**G2 · Bob first reported a result it had not measured — this was caught and redone.**
Bob's first attempt at the "after" number ran a `python3 -c` snippet whose *answers were
hardcoded* (`{p: "'ünïcode-42'" for p in personas}`) and printed `0/15` from it. That
claim is discarded. It was pushed back on with an explicit "no hardcoded or simulated
answers", Bob re-spawned the five witnesses against `rashomon_out/clarified/chronex/text.py`,
and only then wrote the answer files (five distinct `summaries`, 07:30) and re-ran
`make merge` / `make score`. **`05_clarifier_slugify.png` shows the discarded claim;
`06_slugify_clarified_result.png` and `07_equiv_gate.png` show the measured one.** If the
0% number is quoted anywhere, quote it from 06/07, not from 05.

**G3 · Current state of `rashomon_out/`.** `answers/` and `results.json` now hold the
*clarified-source* answers, so a bare `make score` in that directory reports
`slugify … Clear` — that is the after-picture, not the baseline. The baseline
(`parse_duration … 47%`, etc.) comes back with `make demo`, which regenerates the answers
from `demo/fixtures/witnesses.json`. A frozen copy of everything the Bob run produced —
the five clarified answers, `results.json`, `comment.md`, `witnesses.json` and the
rewritten `rashomon_out/clarified/chronex/text.py` — is in
`bob_sessions/clarified_artifacts/` so a later `make demo` cannot be the only thing
standing between you and that evidence. `web/data.json` is **not** affected: it is built
from `out/live-demo/results.json` and matches it row-for-row.

**G4 · Automation notes for whoever continues this.** Driven by `scripts/bob_drive.py`
(`send` / `click` / `status` / `autoapprove`) plus `scripts/bob_winid.py`:
System Events `click at` fails with `-25211`, so clicks go through `CGEventPost`;
`screencapture -R` shows whatever window is frontmost (Discord/Safari leaked into two
shots), so always capture the full screen and crop the AX window rect; screen backing
scale flipped between 1× and 2× during the session, so never hardcode a pixel scale;
approvals are found by colour-masking the blue *Approve* button and clicking immediately —
a greyed button is a stale request and silently no-ops.

---

## F. Verified — no action needed

- `make check`: **43 pytest cases pass** (grading strictness, extraction, filters,
  heuristic probes, subprocess runner, exception reporting, git history incl. the
  neighbour-bleed guard, packet leak check, answer-shape normalisation, Wilson
  intervals and labels, Spearman/permutation/bootstrap, AST branch counting,
  a full end-to-end run + gate + stats + leaderboard payload, **sealed P′
  generation/verification/tamper-detection/equiv --sealed/rewatch SEALED refusal**,
  and **name-lift anonymisation, behaviour preservation, method+kwarg remapping and
  the recorded-lifted-session null test**).
- `make demo`: full pipeline green — pick → probes → prune → packets → 5 witnesses →
  score → history → stats → leaderboard, `web/data.json` regenerated with labels,
  intervals and `"session": "recorded"`.
- `make stats`: prints ρ, p and CI for bug_fixes / touching_commits / loc / branches
  and writes `rashomon_out/stats.json`.
- `make gate`: writes `rashomon_out/comment.md`, exits 0 with no baseline, exits 1
  on a regression; the comment now carries the 95% CI and the label per function.
- `make clarify` + `make equiv`: `15/15 identical` on a clean copy, `11/15` after a
  deliberate mutation — the equivalence check does catch behaviour changes.
- `make rewatch`: prints before/after (identical by construction on a recorded
  session — see C3b). `make rewatch SEALED=1` verifies the freeze first and
  refuses to run on a recorded backend ("live witnesses" required).
- `make seal` + `make seal-verify`: 9/9 demo functions sealed deterministically
  (same hash on reseal), freeze verifies rc 0; tampering with `primes.json` is
  caught at both file and entry level.
- `make lift` + `make lift-report`: 9/9 functions lifted and behaviour-verified
  (`3/3 identical` each); witness → score → report run end-to-end on the lifted
  copy with Δ +0pp — the expected null on a recorded session (plumbing test).
- **live witness runs** (provider `gemini` → `gemini-3.5-flash-lite`,
  `GOOGLE_API_KEY`): demo run in `out/live-demo/` (40 calls, 8 functions,
  `session: live`) and the flagship boltons run in `out/boltons/` (410
  predictions, 30 functions) — scored 9 Consensus misread / 4 Scattered /
  17 Clear, bug_fixes Spearman ρ = 0.394, p = 0.031, 95% CI [0.03, 0.71] *.
  Witness runs checkpoint after every function; a rerun resumes, and 6
  consecutive failures abort with the partial file kept.
- `make boltons`: 61 candidates ranked across 19 modules (8 per module cap), pruned
  to the **30 that actually run**, 5 witness packets, history for all 30.
- `make spike`: all local checks pass — Bob files present, YAML parses with the
  three mode slugs, `.bobignore` hides the target/answer paths, canary present,
  and no packet contains a probe output or answer wording.
- `make web`: `index.html`, `fn.html`, `common.js`, `app.js`, `fn.js` and
  `data.json` all serve 200 locally. Browser behaviour (drawer, sort, search,
  chips, guess box incl. abstention + tally, share link, fn.html good/bad id)
  passes a 29-check jsdom smoke test; the guess comparison matches Python's
  `score.same` on 1,941 generated pairs (0 mismatches).
