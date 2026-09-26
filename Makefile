# Rashomon - unit tests for readability
#
#   make demo      end-to-end run on demo/target_repo with the recorded witness session
#   make boltons   extract + probes + history + packets on the real target library
#   make check     test suite
#
# Override the target repo, output dir or backends:
#   make run ROOT=path/to/repo OUT=rashomon_out BACKEND=llm

ROOT      ?= demo/target_repo
OUT       ?= rashomon_out
BACKEND   ?= auto
RECORDED  ?=
MAXLINES  ?= 200
LIMIT     ?= 30
WEBDATA   ?= web/data.json
PYTHON    ?= python3

R := PYTHONPATH=. $(PYTHON) -m rashomon.cli

# witness backend + recorded file, shared by witness / score / rewatch
WITNESS_ARGS := --backend $(or $(WITNESS_BACKEND),llm) \
	$(if $(WITNESS_FILE),--witness-file $(WITNESS_FILE))

.PHONY: all demo run extract probes packet witness merge score history stats \
        leaderboard gate brief clarify equiv rewatch check web deploy boltons spike \
        seal seal-verify lift lift-report clean help

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

all: check demo ## run the tests, then the demo

demo: ## end-to-end run on the bundled demo repo (offline, recorded witnesses)
	$(PYTHON) demo/build_target_repo.py
	$(PYTHON) demo/fixtures/make_fixtures.py
	$(MAKE) run ROOT=demo/target_repo BACKEND=file RECORDED=demo/fixtures

run: ## pick -> probes -> prune -> witnesses -> score -> history -> stats -> leaderboard
	$(R) run-all --root $(ROOT) --out $(OUT) --backend $(BACKEND) \
		$(if $(RECORDED),--recorded-dir $(RECORDED)) --max-lines $(MAXLINES) --limit $(LIMIT) \
		--web-data $(WEBDATA)

extract: ## step 1 - pick functions (diff / churn / whole tree)
	$(R) pick --root $(ROOT) --out $(OUT) --max-lines $(MAXLINES) --limit $(LIMIT)

probes: ## steps 2+4 - generate probe inputs and run them for real
	$(R) probes --root $(ROOT) --out $(OUT) --backend $(or $(PROBE_BACKEND),heuristic)

packet: ## write witness packets (inputs only, no answers)
	$(R) packet --root $(ROOT) --out $(OUT) $(if $(LIFTED),--lifted)

seal: ## freeze the held-out probe set P' under sha256 (before witnesses run)
	$(R) seal --root $(ROOT) --out $(OUT) $(if $(FORCE),--force)

seal-verify: ## check the P' freeze is intact (fails if anything was edited)
	$(R) seal --root $(ROOT) --out $(OUT) --verify

lift: ## anonymise every picked function; verify identical behaviour
	$(R) lift --root $(ROOT) --out $(OUT)

lift-report: ## misread rate: original vs name-lifted (the naming effect)
	$(R) lift --root $(ROOT) --out $(OUT) --report

witness: ## step 3 - five independent readers (LIFTED=1 reads <out>/lifted)
	$(R) witness --root $(ROOT) --out $(OUT) $(WITNESS_ARGS) $(if $(LIFTED),--lifted)

merge: ## fold Bob's witness replies (<out>/answers/*.json) into witnesses.json
	$(R) merge --root $(ROOT) --out $(OUT)

score: ## steps 3+4 - ask the readers, then score them against the real run (LIFTED=1 for the lift)
	$(R) score --root $(ROOT) --out $(OUT) $(if $(WITNESS_FILE),--witness-file $(WITNESS_FILE)) $(if $(LIFTED),--lifted)

history: ## step 7 - git bug-fix history per function
	$(R) history --root $(ROOT) --out $(OUT)

stats: ## spearman rho of misread rate vs bug fixes / LOC / branches
	$(R) stats --root $(ROOT) --out $(OUT)

leaderboard: ## write web/data.json
	$(R) leaderboard --root $(ROOT) --out $(OUT) --web-data $(WEBDATA)

brief: ## print the Clarifier briefing for one function (ID=<key>)
	$(R) brief --root $(ROOT) --out $(OUT) --key $(ID)

clarify: ## copy the module for the Clarifier and print the brief (ID=<key>)
	$(R) clarify --root $(ROOT) --out $(OUT) --key $(ID)

equiv: ## check the clarified copy behaves identically (ID=<key>, prints N/N identical)
	$(R) equiv --root $(ROOT) --out $(OUT) --key $(ID)

rewatch: ## fresh witnesses on the clarified copy, before/after misread rate (ID=<key>)
	$(PYTHON) scripts/rewatch.py --key $(ID) --root $(ROOT) --out $(OUT) \
		--backend $(or $(PROBE_BACKEND),heuristic) \
		$(if $(SEALED),--sealed) \
		$(if $(WITNESS_FILE),--witness-file $(WITNESS_FILE)) \
		$(if $(WITNESS_BACKEND),--witness-backend $(WITNESS_BACKEND))

gate: ## non-interactive readability gate + PR comment body
	$(R) gate --root $(ROOT) --out $(OUT) $(if $(BASELINE),--baseline $(BASELINE)) \
		--comment-file $(OUT)/comment.md --fail-on-regression

boltons: ## extract + probes + prune to runnable functions + packets + history
	$(R) pick --root targets/boltons --out out/boltons --rank-churn --limit 80 --per-module 8 \
		--min-lines 3 --max-lines 45 --exclude misc tests docs
	$(R) probes --root targets/boltons --out out/boltons --backend heuristic
	$(R) prune --root targets/boltons --out out/boltons --limit 30
	$(R) packet --root targets/boltons --out out/boltons
	$(R) history --root targets/boltons --out out/boltons
	@echo ""
	@echo "Next: run the 🎭 rashomon skill in Bob on out/boltons/packets/B*.md,"
	@echo "then:  make merge score ROOT=targets/boltons OUT=out/boltons"

check: ## test suite
	$(PYTHON) -m pytest -q tests

web: ## serve the leaderboard locally
	cd web && $(PYTHON) -m http.server 8000

deploy: ## publish web/ to Vercel production (needs `vercel login`, or VERCEL_TOKEN=…)
	@test -n "$(VERCEL_TOKEN)" || vercel whoami >/dev/null 2>&1 || \
		{ echo "not logged in: run 'vercel login' or pass VERCEL_TOKEN=<token>"; exit 1; }
	cd web && vercel deploy --prod --yes $(if $(VERCEL_TOKEN),--token $(VERCEL_TOKEN))

spike: ## the first-hour Bob checklist (prints what to run inside the IDE)
	@$(PYTHON) scripts/spike.py

clean:
	rm -rf rashomon_out out __pycache__ rashomon/__pycache__ .pytest_cache
