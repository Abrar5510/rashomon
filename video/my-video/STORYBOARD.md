# STORYBOARD — RASHOMON submission video

Workflow: `general-video` · flow `automation` · storyboard `no` · 1920×1080 · 180 s · en · angle `demo`

**Palette** (declared once): bg `#0e1014`, surface `#161a21`, line `#262c37`, fg `#e8eaf0`,
muted `#99a2b4`, accent `#ffb454`, semantic-bad `#f06f5f`, semantic-good `#79d7a7`.
Warm amber accent on cool-neutral dark (tech / code / IDE content → dark per house-style).
**Type:** `ui-sans-serif, sans-serif` for display (700–900), `ui-monospace, monospace` for code and
data — two roles, no named webfonts (no `@font-face` needed).

**Runtime:** one paused GSAP timeline on `window.__timelines["main"]`; root `data-duration="180"`.
Motion vocabulary: `waterfall-entry` (title/list arrivals), `spring-pop-entrance` (cards, no
overshoot), `counting-dynamic-scale` (stat counters + paired bar fills), `sine-wave-loop`
(bounded ambient on backdrop, finite repeats only). No `repeat:-1`, no CSS `@keyframes` idle,
no `width/height/top/left` tweens.

**Live Bob footage:** `assets/take1.mov` (30–65 s, source offset 5 s) and `assets/take3.mov`
(65–165 s, source offset 0 s) play full-bleed under scenes s3–s9 → **135 s of Bob running live**
(rule: ≥90 s). Real-time, never sped up → no "2×" label required. Narration is a separate
`<audio>` track (10 clips, 82.3 s total), generated offline with `hyperframes tts`.

**Evidence rule:** every number, commit, path and verdict on screen comes from this repo
(`README.md`, `docs/VIDEO.md`, `docs/statements.md`, `web/data.json`, `rashomon_out/`,
`bob_sessions/clarified_artifacts/`). Nothing is invented. One deviation from the draft shot list
is documented in `PENDING.md` §VIDEO-DEVIATION.

---

## Frames

### F1 · 00:00–00:12 · Cold open — the puzzle
- `src`: designed (no footage) · `beat`: what does this return?
- On screen: `parse_duration('1h30m') → ?`; five face-down witness cards flip up
  (`api-historian '1h30m'`, `careful-stylist 5400`, `edge-case-hunter 5400`,
  `regex-allergic 3600`, `speed-reader 90`); then `we ran it → 5400`, `2 of 5 readers right`.
- Motion: `waterfall-entry` (kicker + code line), `spring-pop-entrance` (5 cards, stagger 0.09 s),
  verdict ticks pop at 7.0 s. Rules: `rules/waterfall-entry.md`, `rules/spring-pop-entrance.md`.
- Narration `n1` @0.8 s — "What does this return? Five readers. Three different answers…"

### F2 · 00:12–00:30 · Three title cards — why this matters
- `src`: designed · `beat`: the problem, stated as three numbers
- On screen: `58%` of dev time is reading code (Xia et al., IEEE TSE 2018) ·
  `121` proposed readability metrics (Scalabrino et al. — they don't track people) ·
  `ρ ≈ 0` ask an LLM "is this readable?" (CoReEval).
- Motion: rows arrive on `waterfall-entry` at 12.4 / 17.6 / 23.2 s;
  counters `58` and `121` use `counting-dynamic-scale` (shared `power3.out`, 1.6 s).
- Narration `n2` @12.6 s.

### F3 · 00:30–00:45 · Bob → mode `rashomon`
- `src`: `assets/take1.mov` @ media 5 s (live) · `beat`: the tool picks up the packet
- On screen: right-hand mode panel `rashomon` (active) / `probesmith` / `clarifier`,
  bottom-left chip `mode: rashomon`.
- Motion: `spring-pop-entrance` on the panel, `waterfall-entry` on mode rows.
- Narration `n3` @30.6 s.

### F4 · 00:45–01:05 · Five isolated readers
- `src`: `assets/take1.mov` @ media 20 s (live) · `beat`: parallel, forked, blind
- On screen: label `fork_context: false · one tool call each` + five witness cards along the
  bottom carrying each reader's prediction.
- Motion: label `waterfall-entry`, cards `spring-pop-entrance` stagger 0.09 s (≤0.5 s window).
- Narration `n4` @45.4 s — "Five isolated readers fork their own context…"

### F5 · 01:05–01:20 · `make score`
- `src`: `assets/take3.mov` @ media 0 s (live) · `beat`: the run decides who was right
- On screen: verdict panel `chronex/parsing.py::parse_duration`, counter `47%` MISREAD,
  paired fill bar at 47 %, `7 / 15 readings`, badge `Consensus misread`.
- Motion: `counting-dynamic-scale` + `stat-bars-and-fills`-style `scaleX` fill, same ease/duration
  so number and bar land as one beat.
- Narration `n5` @65.6 s.

### F6 · 01:20–01:35 · `make history`
- `src`: `assets/take3.mov` @ media 15 s (live) · `beat`: the bug was fixed, the confusion wasn't
- On screen: real commits `e12e3c6` / `dddce92` / `4101cc2` + footer
  `9 / 9 functions carry a boundary-bug fix` · `parse_duration · 1 bug fix · 2 touching commits`.
- Motion: `waterfall-entry` on commit rows (weight-varied y offsets), footer fades on VO.
- Narration `n6` @80.6 s (re-recorded — see PENDING §VIDEO-DEVIATION).

### F7 · 01:35–02:00 · Clarifier + `make equiv`
- `src`: `assets/take3.mov` @ media 30 s (live) · `beat`: rewrite into a copy, prove behaviour held
- On screen: card A `mode: clarifier` → `rashomon_out/clarified/` · *a copy, never the real file*;
  card B `make equiv` → counter `15 / 15 identical`.
- Motion: card A pop @95.4 s, card B pop @104 s with counter.
- Narration `n7a` @95.6 s.

### F8 · 02:00–02:15 · `make rewatch` + PR comment
- `src`: `assets/take3.mov` @ media 55 s (live) · `beat`: before/after, then it lands in the PR
- On screen: `slugify 13 % → 0 %`, `clean witnesses 3/5 → 5/5`; then the real gate comment
  row from `bob_sessions/clarified_artifacts/comment.md`.
- Motion: two `spring-pop-entrance` cards; arrow + numbers settle on VO.
- Narration `n7b` @120.6 s.

### F9 · 02:15–02:45 · Leaderboard + correlation
- `src`: `assets/take3.mov` @ media 70 s (live, scrimmed) · `beat`: readability as a number
- On screen: top-6 leaderboard from `web/data.json` (rank · function · misread bar · bug fixes),
  headline `ρ = 0.394 · p = 0.031 · 95 % CI [0.03, 0.71]`, footer
  `30 functions · 410 predictions · 9 Consensus misread / 4 Scattered / 17 Clear`.
- Motion: rows `waterfall-entry`, bars `scaleX` fills on one shared beat, ρ line settles after.
- Narration `n8` @135.6 s.

### F10 · 02:45–03:00 · Title card
- `src`: designed (footage has ended) · `beat`: the one-line takeaway
- On screen: `RASHOMON` / `unit tests for readability` / footer metrics.
- Motion: `waterfall-entry` word cascade (final word split into fragments), footer fade.
- Narration `n9` @166.0 s — "Readability was an opinion. Now it's a test."

---

## Track layout

| track | contents |
|---|---|
| 0 | `#backdrop` (0–180): base colour, drifting grid, two decorative rings (text-free, so the WCAG contrast audit stays clean), grain, amber glow |
| 1 | `#vid-a` (30–65, media 5 s), `#vid-b` (65–165, media 0 s) |
| 2 | scenes `#s1`…`#s10`, back-to-back, half-open windows, no overlap |
| 10–19 | narration clips `#a1`…`#a10` (one per track → no overlap warnings) |
