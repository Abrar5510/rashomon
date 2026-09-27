---
workflow: general-video
flow: automation
storyboard: no
message: "Readability is a number with a confidence interval — Rashomon runs five independent readers on your function and fails the build when they disagree"
destination: hackathon-submission
aspect: 1920x1080
language: en
audience: hackathon judges and developer-tool engineers
length: 180s
angle: demo
---

## Intent

A ≤3:00 narrated submission video for Rashomon — "unit tests for readability" —
built for the hackathon judges. Cold-open on a real disagreement (five readers
predict `parse_duration('1h30m')` and return three different answers), state the
problem, then show **Bob actually running the thing live**: the `rashomon` mode
spawning five isolated `explore` witnesses, `make score`, `make history`, the
`clarifier` rewrite, `make equiv`, and the leaderboard. Confident and concrete —
proof over persuasion. Every number on screen was measured; nothing staged.

## Assets

- `assets/take1.mov` — 150 s, 15 fps, 960×526 window capture of Bob running the
  real five-witness task (19 new messages). Source for the ≥90 s live-beat.
  Un-trimmed master; sub-ranges are cut in the composition.
- `assets/modes.png` — Bob Settings → Modes with 🎭 Rashomon / 🧪 Probesmith /
  🔍 Clarifier (beat 0:30–0:45).
- `assets/witnesses.png` — five `explore` witness cards, one tool call each.
- `assets/score.png` — `make score` table (misread rate, Wilson CI, label).
- `assets/clarifier.png`, `assets/clarified.png` — clarifier rewrite landing in
  `rashomon_out/clarified/` and the measured before/after.
- `assets/equiv.png` — `15/15 identical` + `rashomon_out/comment.md`.
- `assets/comment.md` — the gate's PR comment text.
- Shot list, narration copy and cold-open numbers: `docs/VIDEO.md` in the repo
  root (outside this project) — it is the script of record.

## Customizations

- Narration as a separate audio track (offline TTS), mixed under the visuals;
  the same lines burned in as on-screen text so the video survives without sound.
- Speed-ups during waits are allowed but must be labelled on screen ("2×")
  with the running Bob panel still visible.
- At least 90 s of the finished video must be Bob running live.

## Notes

- Hard spec: MP4, 1920×1080, ≤3:00, <300 MB. Submit by Sun 27 Sep 15:00 UTC.
- Never fabricate Bob evidence: every screenshot, clip and number comes from a
  real run and must match the repo's own outputs.
- Cold-open data (real, from `demo/fixtures/witnesses.json`):
  `parse_duration('1h30m')` → actual `5400`; predictions `1h30m`, `5400`,
  `5400`, `3600`, `90`.
- Headline live result (30 boltons functions, 5 readers, 410 predictions):
  9 Consensus misread · 4 Scattered · 17 Clear; Spearman ρ = 0.394,
  p = 0.031, 95% CI [0.03, 0.71].
- No stock-photo aesthetics; dark, typographic, IDE-native.
