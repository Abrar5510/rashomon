# Rashomon

> **Unit tests for readability.**
> Five AI readers who've never seen your code each predict what a function returns.
> Then we run it. If they disagree or get it wrong, your code is confusing — and now
> that's a number instead of an opinion.

Readability has been argued about for decades using stand-ins: line length,
cyclomatic complexity, "it looks fine to me". Nobody measured whether an independent
reader actually understands the function. Independent readers used to cost a lab
study. They now cost five subagent calls, and you can check them against reality
because **the interpreter is the ground truth**.

Tagline: *CRUXEval uses code to grade models. Rashomon uses models to grade code.*

---

## Quick start

```bash
make check      # 41 tests
make demo       # end-to-end on the bundled demo repo, offline
make web        # serve the leaderboard at http://localhost:8000
make spike      # what can be verified without the Bob IDE, and what to do inside it
```

`make demo` runs the whole pipeline — pick → probes → 5 witnesses → score →
git history → leaderboard — on `demo/target_repo` using a **recorded** witness
session, so it needs no API key and no network.

Real run on a real library:

```bash
make boltons    # extract + probes + prune + packets + history on targets/boltons @ 4e5faa3d
```

then score it with witnesses, either from Bob (below) or from a model API:

```bash
make witness ROOT=targets/boltons OUT=out/boltons WITNESS_BACKEND=llm   # needs ANTHROPIC_API_KEY
make score   ROOT=targets/boltons OUT=out/boltons
make history ROOT=targets/boltons OUT=out/boltons
make leaderboard ROOT=targets/boltons OUT=out/boltons
```

## The pipeline

| Step | What | Bob feature | Command |
|---|---|---|---|
| 1 | Pick functions changed in a PR, or the most frequently changed ones | plain script | `make extract` |
| 2 | Probe inputs: typical, boundary, discriminating | `probesmith` mode | `make probes` |
| 3 | 5 readers see **only** a packet (source + inputs, never the answers) | 5 parallel `explore` subagents, `fork_context: false` | `make packet` + 🎭 rashomon skill |
| 4 | Run the function for real; score every prediction | plain script | `make score` |
| 5 | Rewrite the confusing one; tests must stay green | `clarifier` mode + Rollback | `make clarify` → `make equiv` → `make rewatch SEALED=1` |
| 5b | Did the rewrite *actually* help? Score on frozen held-out probes (P′) and on an anonymised copy | plain script | `make seal` → `make rewatch SEALED=1`; `make lift` → `make lift-report` |
| 6 | PR comment: *"this PR made `parse_retry_after` harder to read: 4/15 → 9/15 misreads"* | Bob Shell / GitHub Action | `make gate` |
| 7 | Does misread rate track bug-fix history? | plain script | `make history` + `make stats` |

**Metrics** (5 witnesses × 3 probes = 15 predictions per function):

- **misread rate** `M` = wrong predictions / total. An abstention counts as wrong.
- **95% Wilson interval** on `M`. A function is only flagged when the *lower*
  bound clears 0.20 — with 15 predictions that means ≥ 7 wrong, so a single bad
  reader can never convict a function.
- **label** — `Clear` (nothing wrong), `Scattered` (some wrong, but the interval
  is still inconclusive), `Confusing` (lower bound > 0.20), `Consensus misread`
  (same, and ≥ 3 readers missed it on one probe).
- **disagreement** = number of distinct answers per probe, averaged.
- **clean witnesses** = readers who got *every* probe right, out of 5.
- **bug fixes** = commits whose subject matches `fix|bug|patch|resolve|…` **and**
  whose diff actually changed that function (neighbouring functions don't count).
- **`make stats`** — Spearman ρ of misread rate against bug fixes, churn, LOC and
  AST branch count, with a 10k permutation p-value and a bootstrap 95% CI. The
  script is committed before the numbers are read, and LOC/branches are reported
  alongside so a length effect cannot masquerade as a readability effect.
- **sealed held-out probes (P′)** — `make seal` freezes a deterministic probe set
  (sha256 per entry + file hash + the scored-probes hash it must stay disjoint
  with) *before* any witness runs, so the Clarifier cannot overfit to the scored
  probes; `make seal-verify` re-checks, and `make rewatch SEALED=1` refuses to
  proceed without an intact freeze and live witnesses. `sealed/` and `lifted/`
  are `.bobignore`d — witnesses never see them.
- **name-lift** — `make lift` rewrites the repo with every function renamed
  `f_<hash>` (params `p0..`, locals `v0..`), re-runs the probes to prove
  behaviour is identical, then `LIFTED=1 make witness/score` and
  `make lift-report` show original-vs-anonymised misread rate: naming effects
  separated from structure effects.

## Isolation: why a witness can't cheat

1. `.bobignore` hides `targets/`, `out/`, `demo/target_repo/tests/`,
   `rashomon_out/probes.json`, `rashomon_out/results.json` and `.bob/sealed/`.
2. A witness only ever receives `rashomon_out/packets/B0n.md`, which contains the
   function source and the probe **inputs** — never an output.
3. `.bob/sealed/canary.json` holds the token `ZEBRA-7731`. If it ever shows up in a
   reply, that witness read outside its packet and the reply is discarded.
4. The rashomon mode's edit permission is limited to `.*answers/.*\.json$`.

## Bob integration

- `.bob/custom_modes.yaml` — three modes: **🎭 rashomon** (orchestrates the five
  readers, `allowedSubagents: [explore]`), **🧪 probesmith** (designs inputs, never
  predicts), **🔍 clarifier** (edits only the clarified copy, may run `make equiv`).
- `.bob/skills/rashomon/SKILL.md` — spawn 5 explore subagents in one turn, file the
  replies verbatim under `rashomon_out/answers/`.
- `.bob/skills/probesmith/SKILL.md` — the typical / boundary / discriminating recipe.
- `.bob/skills/clarify/SKILL.md` — rewrite → `make equiv` → Rollback, ≤2 attempts.

After the witnesses answer in Bob:

```bash
make merge score ROOT=targets/boltons OUT=out/boltons
```

`merge` folds `out/boltons/answers/witness-*.json` into `witnesses.json`, in either
the skill's shape (`{"witness": k, "answers": [...]}`) or the flat
`key#probe#persona` shape.

## Layout

```
rashomon/            the library: astx, probes, runner, witnesses, score, stats,
                     history, packet, seal, lift, cli
scripts/             thin CLIs: pick_functions, run_probes, score, bugfix_history,
                     build_leaderboard, rewatch, run_all, spike
.bob/                custom modes, skills, the sealed canary
tests/               41 pytest cases (grading, extraction, probes, history, packets,
                     Wilson labels, correlation stats, sealed P′, name-lift, e2e)
web/                 static leaderboard: index.html, fn.html, style.css,
                     common.js, app.js, fn.js, data.json
demo/                build_target_repo.py + fixtures (the recorded offline session)
docs/                statements.md (submission texts), VIDEO.md, SLIDES.md
targets/boltons      cloned target library @ 4e5faa3d (git-ignored)
.github/workflows/   rashomon.yml — PR gate that comments on the pull request
Makefile             demo, run, extract, probes, packet, witness, merge, score,
                     history, stats, leaderboard, brief, clarify, equiv, rewatch,
                     seal, lift, gate, boltons, spike, check, web, deploy, clean
```

## Results (bundled offline demo)

`python3 -m rashomon.cli score --root demo/target_repo --out rashomon_out`

```
 misread        95% CI   clean label               function
-------------------------------------------------------------------------------
     47%   0.25..0.70     1/5   Consensus misread   chronex/parsing.py::parse_duration
     27%   0.11..0.52     1/5   Scattered           chronex/parsing.py::parse_retry_after
     13%   0.04..0.38     3/5   Scattered           chronex/seq.py::chunk
     13%   0.04..0.38     3/5   Scattered           chronex/seq.py::flatten
     13%   0.04..0.38     3/5   Scattered           chronex/seq.py::merge_intervals
     13%   0.04..0.38     3/5   Scattered           chronex/text.py::slugify
      7%   0.01..0.30     4/5   Scattered           chronex/num.py::clamp
      7%   0.01..0.30     4/5   Scattered           chronex/text.py::is_palindrome
      0%   0.00..0.20     5/5   Clear               chronex/num.py::mean
```

```
$ make stats
         predictor  spearman        p  95% CI
----------------------------------------------------
         bug_fixes     0.000   1.0000  [ 0.00,  0.00]
  touching_commits     0.000   1.0000  [ 0.00,  0.00]
               loc     0.723   0.0301  [ 0.04,  0.93] *
           branches     0.464   0.2161  [-0.54,  0.87]
```

The hero: `parse_duration("1h30m")` — five readers, three different wrong answers,
one reader clean, and the function carries bug-fix commits in its history.

## Safety

Probe execution spawns a fresh Python subprocess with a timeout. **It is not a
sandbox.** Only point Rashomon at repositories you already trust to run code from.

## Prior art

- CoReEval / Human-Aligned Code Readability Assessment ([arXiv 2510.16579](https://arxiv.org/html/2510.16579v1))
  asks an LLM to *rate* readability — an opinion, not a test.
- Functional entropy ([arXiv 2605.28500](https://arxiv.org/html/2605.28500)) measures
  disagreement on whether *AI-generated* code is correct.
- Atoms of confusion (Gopstein et al., FSE'17) and Scalabrino et al. (TSE'21) measured
  confusion with paid humans in labs. No shipped tool turns *independent readers
  disagree, and running the code shows who was right* into a check for human-written code.

## Publishing

`web/` is buildless static HTML/CSS/JS: the leaderboard plus a shareable
`web/fn.html?id=<key>` detail page per function, and a "be the 6th witness"
guess box on every probe — you predict the output before the cards flip; the
check runs entirely in the browser and stores nothing. Serve it anywhere:

```bash
make web                                # local
make deploy                             # Vercel production (needs `vercel login`)
# or push web/ to GitHub Pages, or npx serve web
```

## See also

- `docs/statements.md` — submission texts (short/long description, Bob usage statement)
- `docs/VIDEO.md` — video storyboard, narration, capture checklist
- `docs/SLIDES.md` — the 7 slides
- `PENDING.md` — everything **not** built or not verifiable in this environment, and
  what has to happen next
