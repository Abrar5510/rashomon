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
| 0:00–0:12 | Cold open, five cards face down | `parse_duration('1h30m') → ?` Cards flip: `'1h30m'` · `5400` · `5400` · `3600` · `90`. Then the real run prints `5400`. | “What does this return? Five readers, three answers, only one right, and we know which, because we ran the code. Predict the output, then run the function.” |
| 0:12–0:30 | Three title cards | `58% of dev time is reading code` · `121 readability metrics, none of them track people` · `ask an LLM if code is readable: ρ ≈ 0` | “Fifty-eight percent of development time is spent reading code. A hundred and twenty-one metrics have been proposed, and none of them track what humans think. Ask a model instead, and it correlates with people at roughly zero. So we stopped asking.” |
| 0:30–0:45 | Bob Tasks → mode `rashomon` | Modes list showing `rashomon` / `probesmith` / `clarifier`; skill fires | “This is Bob. The rashomon mode picks up one witness packet: the function, its probe inputs, and nothing else. No answers, no history, no hint of what the right output looks like.” |
| 0:45–1:05 | **Parallel panel, 5 explore subagents** | Five `explore` cards running at once, one tool call each; label `fork_context: false` | “Five readers fork their own context, so they cannot influence each other. No groupthink. Each gets exactly one tool call: read the function, predict what it returns, then stop. They never see the real output, each other, or the answer key.” |
| 1:05–1:20 | `make score` | Verdict card: `parse_duration — 7/15 misread, 47%` | “Then we execute it. This function fooled seven of fifteen readings: one reader said thirty-six hundred when the answer was fifty-four hundred. That disagreement is the measurement.” |
| 1:20–1:35 | `make history` | Three real boundary-bug commits under `git log · demo/target_repo` (`e12e3c6`, `dddce92`, `4101cc2`), then the footer `9 / 9 functions carry a boundary-bug fix` and `parse_duration · 1 bug fix · 2 touching commits` | “Nine of nine functions here carry a boundary-bug fix, and they still mislead readers. Fixing the bug never fixed the confusion. The confusion was never in the behaviour. It was in the code.” *(shipped line — see `PENDING.md` §VIDEO-DEVIATION)* |
| 1:35–2:00 | Mode `clarifier` + `make equiv` | Rewrite lands in `rashomon_out/clarified/`, then `15/15 identical` (label the count from the run) | “So the clarifier takes a swing. It reads the confusing function and writes a plainer version into a copy, never the real file. Then we prove the behaviour did not move: fifteen probes, fifteen identical results, before anyone is allowed to judge the new wording. If a rewrite changes a single return value, that is a bug fix, not a rewrite.” |
| 2:00–2:15 | `make rewatch` + PR comment | Before/after misread rate; the gate comment appearing | “Then fresh readers, with no memory of the first pass, score the clarified copy. Before: seven of fifteen misled. After: nobody. And the gate posts that change to the pull request.” |
| 2:15–2:45 | Leaderboard + scatter | Live site, misread rate vs bug-fix count | “Thirty functions from a real library, ranked by how often independent readers disagree, and every row carries its own bug-fix history. The correlation with past fixes is not zero: point three nine, with a p-value of point naught three. The top row misleads every reader and has three historical bug fixes. Readability is now a number you can regress on.” |
| 2:45–3:00 | Title card | `RASHOMON — unit tests for readability` | “CRUXEval uses code to grade models. Rashomon uses models to grade code. Five readers disagreeing means it is unclear. Readability was an opinion. Now it is a test.” |

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
**180.000 s**, H.264 + AAC, **14.9 MB** (spec: ≤ 3:00, < 300 MB), narration as a
mixed audio track. 694 kbps average — plenty for a dark UI composition.

Built as a HyperFrames composition, not a concat: `video/my-video/index.html`
(ten scenes on one paused GSAP timeline, `hyperframes check` → 0 errors),
storyboard in `video/my-video/STORYBOARD.md`, footage + narration in
`video/my-video/assets/`.

**Footage.** One 260 s real-time recording of the Bob IDE,
`assets/take4.mov`, cut into three 1× windows on track 1 —
`#vid-a` 30–80 s (media 7 s), `#vid-b` 80–122 s (media 95 s),
`#vid-c` 122–165 s (media 211 s) — **135 s of Bob running live** (spec: ≥ 90 s).
Real-time, never sped up → the "label any speed-up 2×" rule never applies.
Captured with `scripts/record_window.swift` (compiled to `scripts/record_window`,
git-ignored), prompt sent at 7.6 s of the take, no approval stalls (permissions
pre-allowed everything).

**Narration.** Ten clips generated offline with local Kokoro-82M (voice
`am_michael`) by `video/my-video/make_narration.py`, which holds the shipped
script in `LINES`, checks each clip against its scene budget and writes
`assets/narr/*.wav` + `*.txt` + `durations.json`. **151.2 s of speech in 180 s
(84%)** — the first cut spoke for only 82 s and left 98 s of silence; the copy
was rewritten (not sped up) and the longest gap is now 5.9 s. Clips land at
0.8 / 12.6 / 30.6 / 45.4 / 65.6 / 80.6 / 95.6 / 120.6 / 135.6 / 166.0 s
(verified against the rendered track with `silencedetect`).

```bash
cd video/my-video
npx hyperframes check          # 0 errors (warnings only)
npx hyperframes render --workers 1 --video-frame-format png --crf 22 \
  --skill general-video -o renders/rashomon.mp4
ffprobe -v error -show_entries format=duration,size -of csv renders/rashomon.mp4
ffmpeg -i renders/rashomon.mp4 -af silencedetect=noise=-35dB:d=1.0 -f null -
```

`--workers 1` is required on this machine: the default multi-worker path buffers
every frame to disk (~5.6 GB for 5,400 frames). Disk was also tight during this
build — the renderer refuses under ~1 GB free, and `npm cache clean --force`
reclaimed enough to run.

QA frames of the delivered cut are in `video/my-video/snapshots/v2/`.
