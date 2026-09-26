# Data sources

| What | Project | Licence | Source |
|---|---|---|---|
| Target library | `boltons` | BSD-3-Clause | https://github.com/mahmoud/boltons @ `4e5faa3d` |
| Demo target library | `chronex` (generated) | MIT (this repo) | `demo/build_target_repo.py` |

`targets/boltons` is a clone used for extraction, probes and git history only.
No boltons source file is redistributed as a standalone artefact; short snippets
appear on the leaderboard pages as quotations of the code under test.

The demo library `chronex` and the recorded witness session in `demo/fixtures/`
were written for this repository. No personal data is stored anywhere in the repo.

Machine-readable keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `WATSONX_*`,
`BOB_API_KEY`) are read from the environment only and are never written to disk.
