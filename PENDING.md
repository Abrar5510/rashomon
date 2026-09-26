# PENDING — what was not built, not verified, or needs a human

Everything below is either **impossible in this environment**, **unverified**, or
**explicitly out of the one-shot build**. Nothing here was half-built and left
running. The parts that *are* built and verified are in `README.md`.

---

## A. Blocked — no credentials, no Bob CLI in this environment

| # | Item | Why | What to do |
|---|---|---|---|
| A1 | **A live 5-witness run on a real library** | No `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `WATSONX_*` is set anywhere in the shell config or `~/.bob/settings/settings.json`, and `bob` is **not on PATH**. So no model could be called. | `export ANTHROPIC_API_KEY=…` then `make witness ROOT=targets/boltons OUT=out/boltons WITNESS_BACKEND=llm`, **or** run the 🎭 rashomon skill in Bob on `out/boltons/packets/B*.md` and then `make merge score ROOT=targets/boltons OUT=out/boltons`. |
| A2 | **`web/data.json` is a recorded session, not a live run** | Same reason as A1. The shipped leaderboard is built from `demo/fixtures/witnesses.json` — a session whose predictions were authored offline against the demo repo, with the disagreements written down explicitly in `CONFUSIONS` in `demo/fixtures/make_fixtures.py`. It is labelled as a recorded session in this file and should be labelled on the site too. | Re-run `make leaderboard` after a live witness run and delete the "recorded" label. |
| A3 | **The 30-function boltons leaderboard** | `make boltons` produces functions + probes + packets + history, but scoring needs witnesses (A1). | Run A1, then `make score history leaderboard ROOT=targets/boltons OUT=out/boltons`. |
| A4 | **watsonx.ai Granite / Llama witnesses** (the optional 6th witness in `IDEAS.md`) | No `WATSONX_APIKEY` / `WATSONX_PROJECT_ID`. No `witness_watsonx.py` was written. | Request the account, then write ~80 lines using `POST https://iam.cloud.ibm.com/identity/token` and `POST https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2024-03-14`, model `ibm/granite-4-h-small`. |
| A5 | **Screenshots in `bob_sessions/`** | Requires the Bob IDE UI. Cannot be captured from a shell. | One PNG per Bob task, `team_taskNN_<desc>.png`, from the IDE's Tasks → task → consumption summary. |
| A6 | **Video (≤3 min, ≥90 s live), slides PDF, cover image, statements** | Recording/editing work in the IDE, outside a code build. | See `IDEAS.md` §Video and the plan's §8. |

---

## B. Written but NOT executed or verified

| # | Item | Status |
|---|---|---|
| B1 | `.bob/custom_modes.yaml` schema | Written to the researched Bob 2.0 shape (`customModes` / `slug` / `roleDefinition` / `whenToUse` / `customInstructions` / `allowedSubagents` / `groups` + `fileRegex`). **Never loaded by Bob.** If Bob rejects `allowedSubagents` or `fileRegex`, fall back to: drop the key and enforce the rule via `customInstructions` plus the "exactly one tool call" check. |
| B2 | `.bob/skills/*/SKILL.md` front matter | `name` + `description` present as Bob requires. **Never loaded by Bob.** |
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
| C3b | **`make rewatch` end-to-end ΔM** | Mechanics work: pick the clarified copy → reuse the sealed probes → witnesses → score → prints before/after. | With `WITNESS_BACKEND=file` the *same* recorded answers are replayed, so before == after **by construction**. A real ΔM needs `WITNESS_BACKEND=llm` (A1) or fresh Bob witnesses on the clarified source. |
| C4 | **Probe design quality** | `heuristic` (signature + parameter-name inference, runs 23/30 boltons functions) and `llm`. | The probesmith recipe — typical / boundary / **discriminating** (pick an input where two plausible *misreadings* diverge). The skill is written; the discriminating case still needs a model. |
| C5 | **"Be the 6th witness"** | **DONE.** Client-side guess box on `web/index.html` (drawer) and `web/fn.html`: cards start face-down, the interpreter's output is hidden until the visitor checks a guess. The comparison mirrors `score.same` exactly (typed Python-literal parser: bool/int/float strictness, tuple vs list, order-insensitive dicts, repr-vs-bare-string mixed case) — verified against Python on 1,941 pairs, 0 mismatches. Abstention (empty guess) counts as a misread, in line with D5. Tally is in-memory only; nothing is stored. | — |
| C6 | **Name-lift diagnostic** | **DONE.** `rashomon lift` (`make lift`) writes an anonymised copy of the repo under `rashomon_out/lifted/` — function → `f_<hash>`, parameters → `p0..`, locals → `v0..` — preserving control flow, attributes, literals and docstring prose; re-runs the probes on the lifted root to prove behaviour is unchanged before anything scores it. `LIFTED=1` on `witness`/`score`/`packet` and `make lift-report` show original-vs-lifted misread rate (Δpp). On the recorded session ΔM = 0 by construction — a plumbing null test; a real separation of naming vs structure effects needs live witnesses (A1). | — |
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

## F. Verified — no action needed

- `make check`: **41 pytest cases pass** (grading strictness, extraction, filters,
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
