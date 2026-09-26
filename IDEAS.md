# IBM Bob 2.0 Hackathon: ideas, round 2

**Deadline: Sun Sep 27, 15:00 UTC (8:00 pm PKT).** Round 1 (CVE fixes, postmortems, handoffs) was rejected as too niche. This round aims for problems every developer has, with a one-line twist that seems obvious once you hear it.

**Recommendation: build Rashomon.** It creates a measurement that didn't exist before, Bob's isolated parallel subagents are what make it work, and it has a single strong image for the video. The last event's judged winners had the same combination: Pedigree used a "code passport" and Atlas showed a repo as a 3D city.

---

## 1. Rashomon: unit tests for readability

> Five AI readers who've never seen your code each predict what a function does. Then we run it. If they disagree or get it wrong, your code is confusing, and now that's a number instead of an opinion.

**Why it lands:** developers have argued about "readable code" for decades using stand-ins like line length and complexity scores. Nobody measured whether readers actually understand the code. A group of independent readers now costs almost nothing. **The 2026 angle:** the most frequent reader of your code is now an AI agent, so every function it misreads is a bug waiting for its next edit.

**The pain:** developers spend about **58% of their time understanding code** ([Xia et al., IEEE TSE 2017](https://dl.acm.org/doi/10.1109/TSE.2017.2734091): 78 professionals, 3,148 hours). Supporting evidence: reasoning-tuned models struggle with the same code humans do ([Le, Nguyen & Nguyen 2026](https://arxiv.org/abs/2606.31725)).

| Step | How | Bob feature |
|---|---|---|
| 1. Pick functions | Functions changed in a PR (`git diff`) or the most frequently changed ones (`git log`) | Plain script, 0 Bobcoins |
| 2. Probe inputs | 3 input cases per function plus a small runner | `general` subagent |
| 3. Witnesses | 5 readers, each sees only the function and predicts outputs plus a one-line summary | 5 parallel `explore` subagents, `fork_context: false`, custom **Witness** mode (read-only, no command execution, so it has to read the code, not run it) |
| 4. Verdict | Run the function for real. Misread rate = wrong predictions; disagreement = number of distinct answers | Plain script |
| 5. Clarify | Rename, extract, add a docstring; tests must stay green | Custom **Clarifier** mode (edits only the target file) + Rollback |
| 6. Gate | PR comment: "this PR made `parse_retry_after` harder to read: 0/5 → 3/5 misreads" | Bob Shell non-interactive in a GitHub Action |
| 7. Validate | Compare misread rate with each function's bug-fix history (`git log -L`) | Plain script |
| Optional | A 6th witness from a different model family | watsonx.ai Granite |

**Files in the repo:** `.bob/custom_modes.yaml` (witness, clarifier), `.bob/skills/rashomon/SKILL.md`, `scripts/{pick_functions,run_probes,score,bugfix_history}.py`, `.github/workflows/rashomon.yml`, `web/` (the deployed leaderboard).

**Demo moment:** a 12-line function on screen: "What does this return for `'1h30m'`?" Five witness cards flip over showing three different answers. Then the real run shows only two were right, and git history shows this function has been fixed 6 times. The Clarifier rewrites it, the witnesses run again, and all 5 agree. End on a leaderboard of the most-misread functions in a well-known library.

**Target repo:** a well-known Python library with many small pure functions and a long bug-fix history (e.g. `python-dateutil`, `boltons`). Avoid very famous functions like lodash's `_.get`, because models have memorized them instead of reading them.

**Numbers to capture:** misread rate before and after Clarifier; functions audited per minute; whether the most-misread functions have more bug fixes. Measure that last one; don't promise it in advance.

**Prior art:** research papers ask an LLM to *rate* readability ([CoReEval / Human-Aligned Code Readability Assessment](https://arxiv.org/html/2510.16579v1)). That is an opinion. "Functional entropy" measures disagreement on whether *AI-generated* code is correct ([arXiv 2605.28500](https://arxiv.org/html/2605.28500)). No shipped tool was found that turns "independent readers disagree, and running the code shows who was right" into a readability check for human-written code.

**Riskiest assumption, test in hour 1:** can you get Bob to run 5 `explore` subagents in parallel on request, with `fork_context: false`, returning structured answers? What does one run cost in Bobcoins? Also check whether witnesses on the same model agree on the same wrong answer. If they do, vary the reader persona in the prompts and add the Granite witness.

**Build plan (~44h):**
- 0–2h: one function, 5 witnesses, measure the cost.
- 2–10h: function picker, probe runner and scoring.
- 10–18h: run on 2 repos; compare against bug history.
- 18–26h: Clarifier mode and the GitHub Action.
- 26–34h: leaderboard page with witness cards; deploy it.
- 34–44h: video, `bob_sessions/` screenshots, write-ups, slides.

**Bobcoins:** roughly 5 witnesses × 30 functions ≈ 150 light subagent calls. Compute the leaderboard once and cache it; in the live demo, run only 1–2 functions.

**Video:** 0:00 "What does this return?" (cards flip) → 0:10 58% of dev time goes to reading code, and your next reader is an AI → 0:30–2:10 live: PR → subagent panel → run → 3/5 misread → Clarifier → 5/5 → PR comment → leaderboard and bug-history chart → 2:40 "Readability was an opinion. Now it's a test."

---

## 2. Receipts: your AI said it's done; make it prove it (called "Toto" in the agent run)

> Your agent says "Done ✅, all tests pass." Receipts checks every claim using an auditor that can read and run code but can't edit a single file.

**Why it lands:** the dangerous AI bug isn't wrong code. It's a missing implementation made to look like a working one: a hardcoded `{success: true}`, a test changed to expect the stub, a skipped test, a swallowed error. Review misses it because it looks intentional and the tests are green.

**The pain:** 84% of developers use or plan to use AI tools, and 46% distrust their accuracy while 33% trust it ([Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/ai)). The top frustration is AI output that is "almost right, but not quite."

**How it works:**
1. Plan/Ask mode splits the agent's summary or PR description into single claims.
2. For each claim, a parallel `general` subagent verifies it in a custom **Auditor** mode. That mode can read and run commands but has **no edit tool**, so it can't change the code to make a claim pass.
3. A skill supplies the checks: run the tests itself; diff the test files for weakened asserts, skips or deleted tests; look for hardcoded returns, `TODO`, mocks of the code under test, and network calls that never happen.
4. Each claim gets a verdict: Proven, Fake or Can't verify, with evidence (file:line and command output).
5. Bob Shell runs it non-interactively as a merge gate, including right after Bob's own Agent mode finishes. That's Bob auditing Bob, a story IBM judges will like.

**Demo:** ask an agent to add checkout to a small app with no API key available and "make the tests pass." It claims it's done. Receipts reports: "Claim 2 FAKE: `charge()` returns hardcoded success (src/pay.ts:14). Claim 3 FAKE: test edited to expect the stub." Then audit a batch of public AI-agent PRs (anonymize usernames) and report what share contain a claim the diff doesn't support.

**Prior art:** reward-hacking benchmarks ([EvilGenie](https://arxiv.org/pdf/2511.21654), [SpecBench](https://arxiv.org/html/2605.21384v1)) are research tools for grading agents, not a developer workflow. [claimcheck](https://github.com/A-Raphie/claimcheck) (another 2026 hackathon project) checks change claims against executed evidence, so name it in the pitch. What's different here: the auditor structurally can't edit, and the checks target test tampering specifically.

**Hour-1 risks:** confirm a custom mode can drop the edit tool but keep command execution. Record the agent faking something ahead of time; don't rely on it happening live.

---

## 3. Déjà Bug: you already fixed this bug, just not in the copy

> You fixed this bug last year. Its copy-pasted twin is still in your code, and your own fix commit proves it.

**Why it lands:** every `fix:` commit is a free, labeled example of a real bug in *your* codebase. Clone detectors find duplicate code but don't know which copy was fixed. Your fix history does.

**How it works:**
1. Mine small `fix:` commits with plain git (0 Bobcoins).
2. An `explore` subagent describes each bug as a pattern, e.g. "missing bounds check before slicing."
3. Parallel `explore` subagents split the repo by folder and search for the pre-fix pattern without the fix. `jscpd` can do a cheap first pass.
4. A `general` subagent adapts the original fix's test to each candidate. If the test fails, the twin is confirmed.
5. It applies the same fix, the test passes, and it opens a PR: "Same bug as abc123 (fixed March 2024); here's the twin."
6. A Bob Shell hook starts a twin hunt on every merged fix.

**Demo:** a real unfixed twin in a well-known repo, shown next to the original fix, with its failing test turning green. Stretch goal: submit that fix as a PR to the real project.

**Prior art:** clone detectors (jscpd, SonarQube), CodeQL variant analysis (security teams writing queries by hand), and FixWizard ([Nguyen et al., ICSE 2010](https://dl.acm.org/doi/10.1145/1806799.1806847), research). Nobody does it automatically from your own history with a failing test as proof.

**Hour-1 risk:** you need a *real* twin to exist. Start scanning 3–4 repos right away, and keep a seeded repo as a fallback.

---

## Honorable mention: Blamestorm (git bisect, run in parallel)
Test 8 commits at once instead of one at a time: parallel subagents cut 9 sequential bisect steps over 400 commits to about 3 rounds. This is the purest showcase of Bob's parallel subagents, but most developers rarely need bisect. The dependency-bump version already exists ([depsect](https://github.com/LilVi02/depsect)).

## Ruled out by the prior-art search (don't pitch these)
- **README QA / fact-checking docs:** 20+ tools ([GitHub topic](https://github.com/topics/documentation-testing)), Swimm, and a [blank-context subagent skill](https://github.com/whykusanagi/zero-context-validation).
- **Never Twice (review comments → rules):** [Qodo Rule Miner](https://www.qodo.ai/blog/codify-what-your-best-reviewers-already-know-with-rule-miner/), Kodus Kody Rules, Greptile.
- **Which dependency bump broke the build:** [depsect](https://github.com/LilVi02/depsect).
- **Catching AI-invented APIs:** an active research area with existing tools.

## Logistics (apply to any pick)
- Use Bob IDE **v2.0.2+**; v2.0.0 stops working Sep 30.
- **Screenshots:** in the IDE, open Tasks → a task → the task header, and screenshot the consumption summary. Save as PNG named like `team_task01_desc.png` in `bob_sessions/`, from **every** team member, as you go.
- **40 Bobcoins each:** measure the cost of one run in hour 1; use plain scripts for anything deterministic; start a fresh task per subtask; @-mention specific files; disconnect MCP servers you aren't using.
- You need a **deployed URL** (a static page on GitHub Pages or Vercel is enough). The video must be ≤3 min with ≥90s of live demo, narrated, and show Bob in use.
