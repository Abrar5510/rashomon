# Video script — ≤ 3:00, narrated, ≥ 90 s of Bob running live

**Spec:** MP4, 1920×1080, ≤ 3:00 and < 300 MB, narration burned in or as a track.
Speed-ups during waits are allowed but must be **labelled on screen ("2×"**) and
the running Bob panel must stay visible.

**Cold-open data is real** (recorded session, `demo/fixtures/witnesses.json`):
`parse_duration('1h30m')` → actual `5400`;
predictions `1h30m` (api-historian), `5400` (careful-stylist), `5400`
(edge-case-hunter), `3600` (regex-allergic), `90` (speed-reader).

---

## Shot list

| Time | Shot | On screen | Narration |
|---|---|---|---|
| 0:00–0:12 | Cold open, five cards face down | `parse_duration('1h30m') → ?` Cards flip: `'1h30m'` · `5400` · `5400` · `3600` · `90`. Then the real run prints `5400`. | "What does this return? Five readers. Three different answers. Only one of them is right — and we can prove it, because we ran the code." |
| 0:12–0:30 | Three title cards | `58% of dev time is reading code` · `121 readability metrics, none of them track people` · `ask an LLM if code is readable: ρ ≈ 0` | "Fifty-eight percent of development time goes to understanding code. One hundred and twenty-one proposed metrics don't track what humans think. And asking a model 'is this readable?' correlates with people at basically zero. So we stopped asking." |
| 0:30–0:45 | Bob Tasks → mode `rashomon` | Modes list showing `rashomon` / `probesmith` / `clarifier`; skill fires | "This is Bob. Mode rashomon picks up one witness packet." |
| 0:45–1:05 | **Parallel panel, 5 explore subagents** | Five `explore` cards running at once, one tool call each; label `fork_context: false` | "Five isolated readers fork their own context — no groupthink — each gets one tool call: read the function, predict the output. They never see the answers." |
| 1:05–1:20 | `make score` | Verdict card: `parse_duration — 7/15 misread, 47%` | "Then we run it. This one misleads seven of fifteen readings." |
| 1:20–1:35 | `make history` | Three real boundary-bug commits under `git log · demo/target_repo` (`e12e3c6`, `dddce92`, `4101cc2`), then the footer `9 / 9 functions carry a boundary-bug fix` and `parse_duration · 1 bug fix · 2 touching commits` | "Every function in this repo carries a boundary-bug fix. Fixing the bug never fixed the confusion." *(shipped line — see `PENDING.md` §VIDEO-DEVIATION; the draft said "three commits on that function", which `rashomon_out/history.json` does not support)* |
| 1:35–2:00 | Mode `clarifier` + `make equiv` | Rewrite lands in `rashomon_out/clarified/`, then `15/15 identical` (label the count from the run) | "The clarifier rewrites it — into a copy, not the real file — and equivalence proves the behaviour didn't move before we judge the new wording." |
| 2:00–2:15 | `make rewatch` + PR comment | Before/after misread rate; the gate comment appearing | "Fresh readers, and the gate posts what changed to the pull request." |
| 2:15–2:45 | Leaderboard + scatter | Live site, misread rate vs bug-fix count | "Functions ranked by how often real readers disagree, with their fix history on top. Readability is now a number you can regress." |
| 2:45–3:00 | Title card | `RASHOMON — unit tests for readability` | "CRUXEval uses code to grade models. Rashomon uses models to grade code. Readability was an opinion. Now it's a test." |

---

## Capture checklist (screenshots → `bob_sessions/`)

Every Bob task, immediately after it, as
`bob_sessions/rashomon_taskNN_<desc>_summary.png`, from the IDE's task header →
consumption summary:

1. `task01_mode_setup` — Modes screen with the three custom modes
2. `task02_rashomon_packet` — rashomon mode reading `B01.md`, one tool call
3. `task03_parallel_witnesses` — the five `explore` subagents side by side
4. `task04_canary_isolation` — witness asked about `.bob/sealed/canary.json` → "not present"
5. `task05_score` — score output
6. `task06_history` — git history output
7. `task07_clarifier` — clarifier rewrite
8. `task08_equiv` — `N/N identical`
9. `task09_gate` — PR comment / `rashomon_out/comment.md`
10. `task10_leaderboard` — deployed site

## Assembly

**Delivered:** `video/my-video/renders/rashomon.mp4` — 1920×1080, 30 fps,
**180.000 s**, H.264 + AAC, **9.7 MB** (spec: ≤ 3:00, < 300 MB), narration as a
mixed audio track.

Built as a HyperFrames composition, not a concat: `video/my-video/index.html`
(ten scenes on one paused GSAP timeline), storyboard in
`video/my-video/STORYBOARD.md`, footage + narration in `video/my-video/assets/`.

```bash
cd video/my-video
npx hyperframes check          # 0 errors
# 450 kbps average — plenty for a dark UI composition; far under the 300 MB cap
npx hyperframes render --workers 1 --video-frame-format png --crf 22 \
  --skill general-video -o renders/rashomon.mp4
ffprobe -v error -show_entries format=duration,size -of csv renders/rashomon.mp4
```

`--workers 1` is required on this machine: the default multi-worker path buffers
every frame to disk (~5.6 GB for 5,400 frames) and fails here, while a single
worker streams straight into the encoder.

Narration is recorded separately (`hyperframes tts`, local Kokoro-82M) and mixed
in as ten `<audio>` clips — one per shot, never sped up.
