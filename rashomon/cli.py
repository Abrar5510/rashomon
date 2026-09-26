from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import WITNESS_PERSONAS, __version__
from .astx import PickFilters, apply_filters, extract_from_files, load_function
from .history import bugfix_history, changed_files, churned_files, is_git_repo
from .llm import BackendUnavailable, LLMBackend
from .probes import heuristic_cases, llm_cases, materialise
from .score import same as score_same  # noqa: F401
from .score import score_all
from .store import func_key, read_json, write_json
from .witnesses import run_witnesses


def _out(args, name: str) -> str:
    return os.path.join(args.out, name)


def _sub_out(args) -> str:
    """Where witness/score/packet read and write: <out>/lifted when --lifted."""
    if getattr(args, "lifted", False):
        return os.path.join(args.out, "lifted")
    return args.out


def _load_functions(args) -> list[dict]:
    return read_json(os.path.join(_sub_out(args), "functions.json"))


def _load_probes(args) -> dict[str, dict]:
    return {e["key"]: e for e in read_json(os.path.join(_sub_out(args), "probes.json"))}


def _filters(args) -> PickFilters:
    exclude = list(args.exclude or [])
    if getattr(args, "exclude_tests", True):
        exclude += ["tests/", "test_"]
    return PickFilters(
        min_lines=args.min_lines,
        max_lines=args.max_lines,
        exclude_privates=not args.allow_privates,
        include=args.include or [],
        exclude=exclude,
    )


def cmd_pick(args) -> int:
    root = os.path.abspath(args.root)
    if args.files:
        rels = args.files
    elif args.diff_base or args.diff:
        rels = changed_files(root, args.diff_base)
    elif args.churn:
        rels = [f for f, _ in churned_files(root, args.churn_files)]
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
            for fn in filenames:
                if fn.endswith(".py"):
                    rels.append(os.path.relpath(os.path.join(dirpath, fn), root))

    fns = extract_from_files(root, rels, _filters(args))

    if args.rank_churn and is_git_repo(root):
        per_module = getattr(args, "per_module", 0) or 0
        # a per-module cap needs a wider candidate pool to still reach --limit
        cap = max(args.history_cap, args.limit * (per_module or 4) * 6)
        pool = fns if per_module > 0 else fns[: args.history_cap]
        pool = pool[:cap]
        ranked = []
        for fn in pool:
            try:
                from .history import function_history

                h = function_history(root, fn.path, fn.qualname, fn.start, fn.end, fn.signature)
            except Exception:
                h = {"touching_commits": 0, "bug_fixes": 0}
            d = fn.to_dict()
            d["touching_commits"] = h["touching_commits"]
            d["bug_fixes"] = h["bug_fixes"]
            d["score"] = h["touching_commits"] + 3 * h["bug_fixes"]
            ranked.append(d)
        ranked.sort(key=lambda d: -d["score"])
        result = ranked[: args.limit]
    else:
        result = [fn.to_dict() for fn in fns[: args.limit]]

    per_module = getattr(args, "per_module", 0) or 0
    if per_module > 0:
        seen: dict[str, int] = {}
        capped = []
        for fn in result:
            n = seen.get(fn["path"], 0)
            if n >= per_module:
                continue
            seen[fn["path"]] = n + 1
            capped.append(fn)
        dropped = len(result) - len(capped)
        result = capped
        if dropped:
            print(f"  capped at {per_module} per module: {dropped} candidate(ies) dropped")

    write_json(_out(args, "functions.json"), result)
    print(f"picked {len(result)} functions -> {_out(args, 'functions.json')}")
    mods = sorted({fn["path"] for fn in result})
    if len(mods) > 1:
        print(f"  across {len(mods)} modules: {', '.join(os.path.basename(m) for m in mods[:8])}"
              + (" ..." if len(mods) > 8 else ""))
    for fn in result[:15]:
        print(f"  {fn['key']}  ({fn['n_lines']} lines)")
    if len(result) > 15:
        print(f"  ... and {len(result) - 15} more")
    return 0


def cmd_probes(args) -> int:
    root = os.path.abspath(args.root)
    fns = _load_functions(args)
    out: list[dict] = []
    t0 = time.time()
    llm = None
    if args.backend == "llm":
        llm = LLMBackend(provider=args.provider, model=args.model)

    if args.backend == "file":
        recorded = read_json(args.probes_file)
        for fn in fns:
            entry = recorded.get(fn["key"])
            if not entry:
                continue
            out.append(
                {
                    "key": fn["key"],
                    "path": fn["path"],
                    "qualname": fn["qualname"],
                    "signature": fn["signature"],
                    "source": fn["source"],
                    "probes": entry,
                    "n_runnable": len([p for p in entry if p.get("ok")]),
                }
            )
    else:
        for fn in fns:
            info = load_function(root, fn["key"])
            if info is None:
                continue
            if args.backend == "llm":
                try:
                    cases = llm_cases(llm, info, count=6)
                except Exception as exc:
                    print(f"  ! probe generation failed for {info.key}: {exc}", file=sys.stderr)
                    cases = heuristic_cases(info)
            else:
                cases = heuristic_cases(info)
            entry = materialise(root, info, cases, timeout=args.timeout, keep=args.keep)
            out.append(entry)
            print(f"  {entry['key']}: {entry['n_runnable']} runnable probe(s)")

    write_json(_out(args, "probes.json"), out)
    print(f"probes for {len(out)} functions in {time.time() - t0:.1f}s -> {_out(args, 'probes.json')}")
    return 0


def cmd_prune(args) -> int:
    """Drop functions the harness could not probe, so a leaderboard only lists runnable code."""
    fns = _load_functions(args)
    probes = _load_probes(args)
    runnable = {k: e.get("n_runnable", 0) for k, e in probes.items()}
    min_probes = getattr(args, "min_probes", 1)
    kept = [f for f in fns if runnable.get(f["key"], 0) >= min_probes]
    dropped = len(fns) - len(kept)
    if args.limit and len(kept) > args.limit:
        dropped += len(kept) - args.limit
        kept = kept[: args.limit]
    keep_keys = {f["key"] for f in kept}
    write_json(_out(args, "functions.json"), kept)
    write_json(_out(args, "probes.json"),
               [probes[k] for k in keep_keys if k in probes])
    print(f"pruned {dropped} unprobed/over-limit function(s) -> {len(kept)} kept")
    return 0


def cmd_seal(args) -> int:
    """Freeze the held-out probe set P' under sha256, or verify the freeze."""
    from .seal import is_sealed, primes_path, seal, verify

    force = getattr(args, "force", False)
    if getattr(args, "verify", False):
        ok, problems = verify(args.out)
        if not ok:
            for p in problems:
                print(f"  ! {p}", file=sys.stderr)
            print(f"seal BROKEN ({len(problems)} problem(s))", file=sys.stderr)
            return 1
        print(f"seal verified: {primes_path(args.out)} (freeze intact)")
        return 0

    if is_sealed(args.out) and not force:
        ok, problems = verify(args.out)
        if ok:
            print(f"already sealed and intact: {primes_path(args.out)} (use --force to reseal)")
            return 0
        for p in problems:
            print(f"  ! {p}", file=sys.stderr)
        print("seal BROKEN — reseal with --force only if you meant to replace the freeze",
              file=sys.stderr)
        return 1

    if not os.path.exists(_out(args, "probes.json")):
        print("error: probes.json missing; run `make probes` before sealing", file=sys.stderr)
        return 2
    fns = _load_functions(args)
    scored = {e["key"]: e for e in read_json(_out(args, "probes.json"))}
    entries = seal(
        os.path.abspath(args.root),
        args.out,
        fns,
        scored=scored,
        count=getattr(args, "count", 9),
        keep=getattr(args, "keep", 3),
        timeout=getattr(args, "timeout", 10.0),
    )
    from .seal import file_hash

    print(f"sealed {len(entries)} held-out probe set(s) -> {primes_path(args.out)}")
    print(f"frozen sha256 {file_hash(primes_path(args.out))}")
    print("verify any time with `make seal-verify`; equiv --sealed trusts P' only if it matches")
    return 0


def _lift_report(args) -> int:
    orig_path = _out(args, "results.json")
    lift_path = os.path.join(_sub_lifted(args), "results.json")
    for p, hint in ((orig_path, "run `make score` first"),
                    (lift_path, "run `make lift`, then witness/score with LIFTED=1")):
        if not os.path.exists(p):
            print(f"error: {p} missing — {hint}", file=sys.stderr)
            return 2
    orig = {r["key"]: r for r in read_json(orig_path)}
    lifted = {r["key"]: r for r in read_json(lift_path)}
    rows = sorted((r for r in orig.values() if r["key"] in lifted),
                  key=lambda r: r.get("rank", 999))
    if not rows:
        print("no lifted results match the original score", file=sys.stderr)
        return 2
    print("name-lift: how much of the misread rate is naming?")
    hdr = f"{'original':>8} {'lifted':>7} {'Δ':>6} {'label':<38}  function"
    print(hdr)
    print("-" * (len(hdr) + 18))
    for r in rows:
        l = lifted[r["key"]]
        delta = (l["misread_rate"] - r["misread_rate"]) * 100
        label = r["label"] if l["label"] == r["label"] else f"{r['label']} -> {l['label']}"
        print(f"{r['misread_rate']:>8.0%} {l['misread_rate']:>7.0%} {delta:>+5.0f}pp "
              f"{label:<38}  {r['key']}")
    print("\nΔ < 0: naming was costing you reads (the anonymised copy read better).")
    print("Δ ≈ 0: what readers struggle with is the structure, not the names.")
    return 0


def _sub_lifted(args) -> str:
    return os.path.join(args.out, "lifted")


def cmd_lift(args) -> int:
    """Anonymise functions into <out>/lifted and prove they behave identically."""
    if getattr(args, "report", False):
        return _lift_report(args)

    from .lift import ALGORITHM as LIFT_ALGO
    from .lift import _remap_kwargs, _signature_of, _splice, _verify_function, anonymise, lifted_dir

    fns = _load_functions(args)
    probes = _load_probes(args)
    if args.key:
        fns = [f for f in fns if f["key"] == args.key]
        if not fns:
            print(f"unknown key {args.key!r}", file=sys.stderr)
            return 2
    root = os.path.abspath(args.root)
    out_root = lifted_dir(args.out)
    order = {f["key"]: i for i, f in enumerate(fns)}
    by_path: dict[str, list[dict]] = {}
    for f in fns:
        by_path.setdefault(f["path"], []).append(f)

    built: list[tuple[dict, dict, dict, str, str]] = []  # (fn, probes, rename, rel, new_name)
    for rel, group in sorted(by_path.items()):
        abs_path = os.path.join(root, rel)
        if not os.path.isfile(abs_path):
            print(f"  ! missing module {rel}, skipped", file=sys.stderr)
            continue
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        infos = []
        for f in group:
            info = load_function(root, f["key"])
            if info is None:
                print(f"  ! could not reload {f['key']}, skipped", file=sys.stderr)
                continue
            infos.append((f, info))
        for f, info in sorted(infos, key=lambda t: t[1].start, reverse=True):
            new_source, rename, new_name = anonymise(info)
            text = _splice(text, info, new_source)
            prefix = f["qualname"].rsplit(".", 1)[0] if "." in f["qualname"] else ""
            new_qual = f"{prefix}.{new_name}" if prefix else new_name
            entry = dict(f)
            entry["name"] = new_name
            entry["qualname"] = new_qual
            entry["source"] = new_source
            entry["signature"] = _signature_of(new_source, new_name)
            pentry = dict(probes.get(f["key"], {}))
            pentry["qualname"] = new_qual
            pentry["signature"] = entry["signature"]
            pentry["source"] = new_source
            pentry["probes"] = [
                dict(p, kwargs=_remap_kwargs(p.get("kwargs", {}), rename))
                for p in pentry.get("probes", [])
            ]
            built.append((entry, pentry, rename, rel, new_name))
        dest = os.path.join(out_root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)

    if not built:
        print("nothing to lift", file=sys.stderr)
        return 2

    manifest = {
        "algorithm": LIFT_ALGO,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "functions": {},
        "verified": {},
    }
    failed = False
    for entry, pentry, rename, rel, new_name in built:
        key = entry["key"]
        manifest["functions"][key] = {"lifted_qualname": entry["qualname"], "map": rename}
        okc, total, fails = _verify_function(
            out_root, rel, entry["qualname"], pentry.get("probes", []), rename, args.timeout
        )
        manifest["verified"][key] = f"{okc}/{total}"
        note = "" if total else "  (no runnable probes)"
        print(f"  {key} -> {entry['qualname']}: {okc}/{total} identical{note}")
        if okc != total:
            failed = True
            for msg in fails[:3]:
                print(f"      ! {msg}", file=sys.stderr)

    built.sort(key=lambda t: order.get(t[0]["key"], 999))
    write_json(os.path.join(out_root, "functions.json"), [b[0] for b in built])
    write_json(os.path.join(out_root, "probes.json"), [b[1] for b in built])
    write_json(os.path.join(out_root, "manifest.json"), manifest)

    if failed:
        print("LIFT VERIFICATION FAILED — the anonymised copy changed behaviour; "
              f"do not score {out_root}", file=sys.stderr)
        return 1
    print(f"lifted {len(built)} function(s) -> {out_root}")
    print("next:  make witness LIFTED=1 ... ; make score LIFTED=1 ... ; make lift-report")
    return 0


def cmd_witness(args) -> int:
    fns = _load_functions(args)
    probes = _load_probes(args)
    llm = None
    if args.backend == "llm":
        llm = LLMBackend(provider=args.provider, model=args.model, temperature=args.temperature)
    try:
        answers = run_witnesses(
            _wrap(fns),
            probes,
            backend=args.backend,
            source_path=args.witness_file,
            llm=llm,
        )
    except (BackendUnavailable, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_json(os.path.join(_sub_out(args), "witnesses.json"), answers)
    n = sum(len(v) for k, v in answers.items() if k != "__summaries__")
    print(f"witness answers for {len([k for k in answers if k != '__summaries__'])} "
          f"functions ({n} probe slots) -> {os.path.join(_sub_out(args), 'witnesses.json')}")
    return 0


def _wrap(fns: list[dict]):
    from .astx import FunctionInfo

    out = []
    for d in fns:
        fi = FunctionInfo(**{k: v for k, v in d.items() if k in FunctionInfo.__dataclass_fields__})
        out.append(fi)
    return out


def _normalise_answers(data: dict) -> dict:
    """Accept either the nested form or the flat `key#probe#persona` form."""
    if not any("#" in k for k in data if not str(k).startswith("__")):
        return data
    out: dict[str, dict] = {"__summaries__": data.get("__summaries__", {})}
    for k, v in data.items():
        if str(k).startswith("__"):
            continue
        fn_key, idx, persona = str(k).rsplit("#", 2)
        out.setdefault(fn_key, {}).setdefault(idx, {})[persona] = v
    return out


def cmd_score(args) -> int:
    fns = _load_functions(args)
    probes = _load_probes(args)
    answers = _normalise_answers(read_json(os.path.join(_sub_out(args), "witnesses.json")))
    results = score_all(fns, probes, answers, WITNESS_PERSONAS)
    write_json(os.path.join(_sub_out(args), "results.json"), results)
    print(f"scored {len(results)} functions -> {os.path.join(_sub_out(args), 'results.json')}\n")
    hdr = f"{'misread':>8} {'95% CI':>13} {'clean':>7} {'label':<18}  function"
    print(hdr)
    print("-" * (len(hdr) + 20))
    for r in results:
        print(
            f"{r['misread_rate']:>8.0%} {r['ci_lo']:>6.2f}..{r['ci_hi']:<6.2f} "
            f"{r['witnesses_correct']:>3}/{r['n_witnesses']:<3} {r['label']:<18}  {r['key']}"
        )
    return 0


def cmd_history(args) -> int:
    fns = _load_functions(args)
    hist = bugfix_history(os.path.abspath(args.root), fns)
    write_json(_out(args, "history.json"), hist)
    print(f"history for {len(hist)} functions -> {_out(args, 'history.json')}")
    return 0


def cmd_stats(args) -> int:
    """Bug-fix history vs misread rate: Spearman rho, permutation p, bootstrap CI."""
    from .stats import bootstrap_ci, branch_count, permutation_p, spearman

    results = read_json(_out(args, "results.json"))
    hist_path = _out(args, "history.json")
    hist = read_json(hist_path) if os.path.exists(hist_path) else {}

    misread = [r.get("misread_rate", 0.0) for r in results]
    series = {
        "bug_fixes": [hist.get(r["key"], {}).get("bug_fixes", 0) for r in results],
        "touching_commits": [hist.get(r["key"], {}).get("touching_commits", 0) for r in results],
        "loc": [r.get("n_lines") or 0 for r in results],
        "branches": [branch_count(r.get("source") or "") for r in results],
    }

    stats: dict[str, dict] = {}
    print(f"correlation with misread rate across {len(results)} functions")
    print(f"{'predictor':>18} {'spearman':>9} {'p':>8}  95% CI")
    print("-" * 52)
    for name, values in series.items():
        rho = round(spearman(misread, values), 3)
        p = permutation_p(misread, values, n=args.permutations, seed=args.seed)
        lo, hi = bootstrap_ci(misread, values, n=args.bootstraps, seed=args.seed)
        stats[name] = {"n": len(results), "spearman": rho, "p": p, "ci": [lo, hi]}
        flag = " *" if p <= 0.05 else ""
        print(f"{name:>18} {rho:>9.3f} {p:>8.4f}  [{lo:>5.2f}, {hi:>5.2f}]{flag}")

    payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "n_functions": len(results), "seed": args.seed,
               "permutations": args.permutations, "bootstraps": args.bootstraps,
               "predictors": stats}
    write_json(_out(args, "stats.json"), payload)
    print(f"\nwritten to {_out(args, 'stats.json')}")
    return 0


def _merged(args) -> list[dict]:
    results = read_json(_out(args, "results.json"))
    hist = read_json(_out(args, "history.json")) if os.path.exists(_out(args, "history.json")) else {}
    for r in results:
        r["history"] = hist.get(r["key"], {})
        r["history"].setdefault("touching_commits", 0)
        r["history"].setdefault("bug_fixes", 0)
    results.sort(key=lambda r: (-r["misread_rate"], -r["history"]["bug_fixes"], -r["disagreement_max"]))
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


def cmd_leaderboard(args) -> int:
    rows = _merged(args)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": f"rashomon {__version__}",
        "session": getattr(args, "session", None),
        "n_functions": len(rows),
        "personas": WITNESS_PERSONAS,
        "functions": rows,
    }
    out_path = args.web_data or _out(args, "data.json")
    write_json(out_path, payload)
    print(f"leaderboard for {len(rows)} functions -> {out_path}")
    return 0


def cmd_gate(args) -> int:
    rows = _merged(args)
    baseline = {}
    if args.baseline and os.path.exists(args.baseline):
        baseline = {r["key"]: r for r in read_json(args.baseline)}

    regressions, lines = [], []
    lines.append("## Rashomon readability gate")
    lines.append("")
    lines.append("| function | misreads (95% CI) | label | clean witnesses | disagreement | bug fixes |")
    lines.append("|---|---:|---|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| `{r['qualname']}` ({r['path']}) | {r['misreads']}/{r['predictions']} "
            f"({r['ci_lo']:.0%}–{r['ci_hi']:.0%}) "
            f"| {r['label']} "
            f"| {r['witnesses_correct']}/{r['n_witnesses']} | {r['disagreement_mean']} "
            f"| {r['history']['bug_fixes']} |"
        )
        base = baseline.get(r["key"])
        if base and r["misread_rate"] > base["misread_rate"]:
            regressions.append(
                f"- `{r['key']}` got harder to read: "
                f"{base['misread_rate']:.0%} -> {r['misread_rate']:.0%} misreads"
            )
    lines.append("")
    if regressions:
        lines.append("**Readability regressions vs baseline:**")
        lines.extend(regressions)
    else:
        lines.append("No readability regressions against the baseline.")
    md = "\n".join(lines) + "\n"

    if args.comment_file:
        write_json(_out(args, "gate_comment.json"), {"body": md})
        with open(args.comment_file, "w", encoding="utf-8") as fh:
            fh.write(md)
    else:
        print(md)

    if args.fail_on_regression and regressions:
        return 1
    return 0


CLARIFIER_BRIEF = """You are the **Clarifier**. Your only job is to make one function
readable to an independent reader without changing what it does.

Rules:
1. Edit ONLY `{path}`. Touch nothing else.
2. Do not change the function's signature or return value.
3. Do not delete, skip, weaken, or rewrite any test.
4. Run the test suite before you finish; it must stay green.

Current misread rate: **{misreads}/{predictions}** predictions wrong across {n_witnesses}
independent readers; {disagreement_mean} distinct answers on average.
Readers' one-line summaries of what they thought it did:
{summaries}

Function under review:

```python
{source}
```

Rename, extract, add a docstring, or restructure so that every reader predicts
the same outputs as the interpreter does.
"""


def cmd_brief(args) -> int:
    rows = {r["key"]: r for r in _merged(args)}
    row = rows.get(args.key)
    if not row:
        print(f"unknown key {args.key!r}; known keys:", file=sys.stderr)
        for k in sorted(rows):
            print(f"  {k}", file=sys.stderr)
        return 2
    summaries = []
    for p in row["probes"]:
        for c in p["cards"]:
            if c.get("summary"):
                summaries.append(f"- {c['witness']}: {c['summary']}")
    seen, uniq = set(), []
    for s in summaries:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    print(
        CLARIFIER_BRIEF.format(
            path=row["path"],
            misreads=row["misreads"],
            predictions=row["predictions"],
            n_witnesses=row["n_witnesses"],
            disagreement_mean=row["disagreement_mean"],
            summaries="\n".join(uniq[:8]) or "- (none recorded)",
            source=row["source"],
        )
    )
    return 0


def cmd_packet(args) -> int:
    from .packet import write_packets

    fns = _load_functions(args)
    probes = _load_probes(args)
    out_dir = _sub_out(args)
    written = write_packets(out_dir, fns, probes, size=args.packet_size)
    for p in written:
        print(f"  {p}")
    print(f"{len(written)} witness packet(s) -> {os.path.join(out_dir, 'packets')}")
    print("Packets contain inputs only. Actual outputs stay in probes.json and are never sent to a witness.")
    return 0


def cmd_merge(args) -> int:
    """Merge witness replies (written by Bob) into witnesses.json."""
    answers_dir = args.answers_dir or os.path.join(args.out, "answers")
    if not os.path.isdir(answers_dir):
        print(f"error: no answers directory at {answers_dir}", file=sys.stderr)
        return 2
    merged: dict[str, str] = {}
    summaries: dict[str, dict] = {}
    used = 0
    for name in sorted(os.listdir(answers_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(answers_dir, name), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "answers" in data:
            idx = data.get("witness")
            persona = (
                WITNESS_PERSONAS[int(idx) - 1]
                if isinstance(idx, int) and 1 <= int(idx) <= len(WITNESS_PERSONAS)
                else os.path.splitext(name)[0]
            )
            for ans in data.get("answers", []):
                merged[f"{ans['fn']}#{int(ans['probe'])}#{persona}"] = str(ans.get("prediction", ""))
            for k, v in (data.get("summaries") or {}).items():
                summaries.setdefault(k, {})[persona] = str(v)
            used += 1
        elif isinstance(data, dict):
            merged.update({k: str(v) for k, v in data.items() if not isinstance(v, (dict, list))})
            summaries.update(data.get("__summaries__", {}))
            used += 1
    if not used:
        print(f"error: no witness replies found in {answers_dir}", file=sys.stderr)
        return 2
    merged["__summaries__"] = summaries
    write_json(_out(args, "witnesses.json"), merged)
    print(f"merged {used} witness repl(y/ies) -> {_out(args, 'witnesses.json')} "
          f"({len([k for k in merged if k != '__summaries__'])} predictions)")
    return 0


def cmd_clarify(args) -> int:
    """Copy the target module (and its package __init__ files) for the Clarifier."""
    rows = {r["key"]: r for r in _merged(args)}
    row = rows.get(args.key)
    if not row:
        print(f"unknown key {args.key!r}", file=sys.stderr)
        return 2
    root = os.path.abspath(args.root)
    rel = row["path"]
    dest_root = os.path.join(args.out, "clarified")
    dest = os.path.join(dest_root, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    parts = rel.split("/")
    for i in range(len(parts) - 1):
        init_src = os.path.join(root, *parts[: i + 1], "__init__.py")
        init_dst = os.path.join(dest_root, *parts[: i + 1], "__init__.py")
        if os.path.isfile(init_src) and not os.path.isfile(init_dst):
            os.makedirs(os.path.dirname(init_dst), exist_ok=True)
            with open(init_src, "r", encoding="utf-8", errors="replace") as fh:
                data = fh.read()
            with open(init_dst, "w", encoding="utf-8") as fh:
                fh.write(data)

    with open(os.path.join(root, rel), "r", encoding="utf-8", errors="replace") as fh:
        data = fh.read()
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(data)

    brief_path = os.path.join(dest_root, args.key.replace("/", "_") + ".brief.md")
    summaries = []
    for p in row["probes"]:
        for c in p["cards"]:
            if c.get("summary"):
                summaries.append(f"- {c['witness']}: {c['summary']}")
    uniq = list(dict.fromkeys(summaries))
    brief = CLARIFIER_BRIEF.format(
        path=dest,
        misreads=row["misreads"],
        predictions=row["predictions"],
        n_witnesses=row["n_witnesses"],
        disagreement_mean=row["disagreement_mean"],
        summaries="\n".join(uniq[:8]) or "- (none recorded)",
        source=row["source"],
    )
    with open(brief_path, "w", encoding="utf-8") as fh:
        fh.write(brief)
    print(f"clarifier working copy -> {dest}")
    print(f"brief -> {brief_path}")
    print(brief)
    return 0


def cmd_equiv(args) -> int:
    """Check that the clarified copy behaves exactly like the original."""
    from .astx import load_function as _load
    from .probes import heuristic_cases
    from .runner import run_case

    rows = {r["key"]: r for r in _merged(args)}
    row = rows.get(args.key)
    if not row:
        print(f"unknown key {args.key!r}", file=sys.stderr)
        return 2

    root = os.path.abspath(args.root)
    fn = _load(root, args.key)
    if fn is None:
        print(f"could not reload {args.key}", file=sys.stderr)
        return 2

    probes = _load_probes(args).get(args.key, {})
    cases = [
        {"args": p["args"], "kwargs": p["kwargs"]}
        for p in probes.get("probes", [])
        if p.get("ok")
    ]
    seen = {(json.dumps(c["args"], sort_keys=True), json.dumps(c["kwargs"], sort_keys=True)) for c in cases}

    from .seal import is_sealed, primes_path
    from .seal import verify as _verify_seal

    use_sealed = getattr(args, "sealed", False)
    extra_pool: list[dict] = []
    if use_sealed:
        if not is_sealed(args.out):
            print(f"--sealed asked for but nothing sealed under {primes_path(args.out)}; "
                  "run `make seal` first", file=sys.stderr)
            return 2
        ok, problems = _verify_seal(args.out)
        if not ok:
            for p in problems:
                print(f"  ! {p}", file=sys.stderr)
            print("refusing to trust P': the freeze does not verify", file=sys.stderr)
            return 2
        prime_entries = {e["key"]: e for e in read_json(primes_path(args.out))}
        entry = prime_entries.get(args.key)
        extra_pool = [
            {"args": p["args"], "kwargs": p["kwargs"]}
            for p in (entry or {}).get("probes", [])
            if p.get("ok")
        ]
        if not extra_pool:
            print("  note: no runnable sealed probes for this key; "
                  "adding signature-derived inputs instead")
    if not extra_pool:
        extra_pool = heuristic_cases(fn, count=args.random_inputs)
    for extra in extra_pool:
        sig = (json.dumps(extra["args"], sort_keys=True), json.dumps(extra["kwargs"], sort_keys=True))
        if sig not in seen:
            seen.add(sig)
            cases.append({"args": extra["args"], "kwargs": extra["kwargs"]})

    clarified_root = os.path.join(args.out, "clarified")
    same_count = 0
    total = 0
    for case in cases:
        a = run_case(root, fn.path, fn.qualname, case, timeout=args.timeout)
        b = run_case(clarified_root, fn.path, fn.qualname, case, timeout=args.timeout)
        total += 1
        if a.get("ok") and b.get("ok"):
            match = score_same(a.get("repr"), b.get("repr"))
        elif not a.get("ok") and not b.get("ok"):
            match = (a.get("error") or "").split(":")[0] == (b.get("error") or "").split(":")[0]
        else:
            match = False
        if match:
            same_count += 1
    print(f"{same_count}/{total} identical")
    return 0 if same_count == total else 1


def cmd_runall(args) -> int:
    import copy

    backend = getattr(args, "backend", "auto")
    if backend == "auto":
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
        backend = "llm" if has_key else "heuristic"
        print(f"backend auto -> {backend}")

    recorded = getattr(args, "recorded_dir", None)
    if recorded:
        args.probes_file = os.path.join(recorded, "probes.json")
        args.witness_file = os.path.join(recorded, "witnesses.json")
        backend = "file"

    probe_args = copy.deepcopy(args)
    witness_args = copy.deepcopy(args)

    if backend == "file":
        missing = [p for p in (args.probes_file, args.witness_file) if not p or not os.path.exists(p)]
        if missing:
            print(
                "error: --backend file needs --recorded-dir (or --probes-file and --witness-file) "
                f"pointing at existing files; missing: {missing}",
                file=sys.stderr,
            )
            return 2
        probe_args.backend = "file"
        witness_args.backend = "file"
    elif backend == "llm":
        probe_args.backend = "llm"
        witness_args.backend = "llm"
    elif backend == "heuristic":
        probe_args.backend = "heuristic"
        witness_args.backend = "file" if getattr(args, "witness_file", None) else "llm"
    else:
        print(f"error: unknown --backend {backend!r}", file=sys.stderr)
        return 2

    steps = [
        (cmd_pick, args),
        (cmd_probes, probe_args),
        (cmd_prune, args),
        (cmd_seal, args),
        (cmd_packet, args),
        (cmd_witness, witness_args),
        (cmd_score, args),
        (cmd_history, args),
        (cmd_stats, args),
        (cmd_leaderboard, args),
    ]
    args.session = "recorded" if backend == "file" else "live"
    for step, step_args in steps:
        rc = step(step_args)
        if rc:
            return rc
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rashomon", description="unit tests for readability")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--out", default="rashomon_out", help="output directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, func, **kw):
        sp = sub.add_parser(name, **kw)
        sp.set_defaults(func=func)
        return sp

    sp = add("pick", cmd_pick, help="select functions from a diff, churn, or the whole tree")
    sp.add_argument("--files", nargs="*")
    sp.add_argument("--diff", action="store_true")
    sp.add_argument("--diff-base")
    sp.add_argument("--churn", action="store_true")
    sp.add_argument("--churn-files", type=int, default=10)
    sp.add_argument("--rank-churn", action="store_true", help="rank by per-function git churn")
    sp.add_argument("--history-cap", type=int, default=40)
    sp.add_argument("--per-module", type=int, default=0, metavar="N",
                    help="cap selected functions at N per module file (0 = no cap)")
    sp.add_argument("--min-lines", type=int, default=1)
    sp.add_argument("--max-lines", type=int, default=60)
    sp.add_argument("--include", nargs="*")
    sp.add_argument("--exclude", nargs="*")
    sp.add_argument("--allow-privates", action="store_true")
    sp.add_argument("--include-tests", dest="exclude_tests", action="store_false",
                    help="also score test functions")
    sp.set_defaults(exclude_tests=True)
    sp.add_argument("--limit", type=int, default=30)

    sp = add("probes", cmd_probes, help="generate and execute probe inputs")
    sp.add_argument("--backend", default="heuristic", choices=["heuristic", "llm", "file"])
    sp.add_argument("--provider", default="anthropic")
    sp.add_argument("--model")
    sp.add_argument("--probes-file", help="recorded probes JSON for --backend file")
    sp.add_argument("--timeout", type=float, default=10.0)
    sp.add_argument("--keep", type=int, default=3)

    sp = add("prune", cmd_prune, help="drop functions with too few runnable probes")
    sp.add_argument("--min-probes", type=int, default=1)
    sp.add_argument("--limit", type=int, default=0, help="0 = keep all survivors")

    sp = add("seal", cmd_seal, help="freeze the held-out probe set P' under sha256")
    sp.add_argument("--verify", action="store_true", help="check the freeze instead of writing it")
    sp.add_argument("--force", action="store_true", help="replace an existing freeze")
    sp.add_argument("--count", type=int, default=9, help="candidate cases per function")
    sp.add_argument("--keep", type=int, default=3, help="runnable probes to keep per function")
    sp.add_argument("--timeout", type=float, default=10.0)

    sp = add("lift", cmd_lift, help="anonymise functions (name-lift) and verify identical behaviour")
    sp.add_argument("--key", help="lift only this key (default: every picked function)")
    sp.add_argument("--timeout", type=float, default=10.0)
    sp.add_argument("--report", action="store_true",
                    help="compare original vs lifted misread rates (needs both results)")

    sp = add("witness", cmd_witness, help="ask 5 independent readers to predict outputs")
    sp.add_argument("--backend", default="llm", choices=["llm", "file"])
    sp.add_argument("--provider", default="anthropic")
    sp.add_argument("--model")
    sp.add_argument("--temperature", type=float, default=0.0)
    sp.add_argument("--witness-file", help="recorded witness answers for --backend file")
    sp.add_argument("--lifted", action="store_true",
                    help="read <out>/lifted/{functions,probes}.json and write <out>/lifted/")

    sp = add("score", cmd_score, help="compare predictions with the real run")
    sp.add_argument("--lifted", action="store_true",
                    help="score the name-lifted set in <out>/lifted/")
    sp = add("history", cmd_history, help="git bug-fix history per function")
    sp = add("stats", cmd_stats, help="spearman rho of misread rate vs bug fixes / LOC / branches")
    sp.add_argument("--permutations", type=int, default=10000)
    sp.add_argument("--bootstraps", type=int, default=2000)
    sp.add_argument("--seed", type=int, default=0)
    sp = add("leaderboard", cmd_leaderboard, help="write the static leaderboard data file")
    sp.add_argument("--web-data")

    sp = add("gate", cmd_gate, help="non-interactive PR gate + comment body")
    sp.add_argument("--baseline", help="previous results.json to diff against")
    sp.add_argument("--comment-file")
    sp.add_argument("--fail-on-regression", action="store_true")

    sp = add("brief", cmd_brief, help="print the Clarifier briefing for one function")
    sp.add_argument("--key", required=True)

    sp = add("packet", cmd_packet, help="write witness packets (inputs only, no answers)")
    sp.add_argument("--packet-size", type=int, default=6)
    sp.add_argument("--lifted", action="store_true",
                    help="packets for the name-lifted set in <out>/lifted/")

    sp = add("merge", cmd_merge, help="merge Bob witness replies into witnesses.json")
    sp.add_argument("--answers-dir", help="default: <out>/answers")

    sp = add("clarify", cmd_clarify, help="copy a module for the Clarifier and print its brief")
    sp.add_argument("--key", required=True)

    sp = add("equiv", cmd_equiv, help="check the clarified copy behaves identically")
    sp.add_argument("--key", required=True)
    sp.add_argument("--random-inputs", type=int, default=60)
    sp.add_argument("--timeout", type=float, default=10.0)
    sp.add_argument("--sealed", action="store_true",
                    help="use the frozen held-out probes P' as the extra inputs")

    ra = add(
        "run-all",
        cmd_runall,
        help="pick -> probes -> witness -> score -> history -> leaderboard",
    )
    ra.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "llm", "file", "heuristic"],
        help="auto: llm when an API key is present, otherwise replay a recorded run",
    )
    ra.add_argument("--recorded-dir", help="directory holding probes.json + witnesses.json")
    ra.add_argument("--probes-file")
    ra.add_argument("--witness-file")
    ra.add_argument("--provider", default="anthropic")
    ra.add_argument("--model")
    ra.add_argument("--temperature", type=float, default=0.0)
    ra.add_argument("--timeout", type=float, default=10.0)
    ra.add_argument("--keep", type=int, default=3)
    ra.add_argument("--packet-size", type=int, default=6)
    ra.add_argument("--min-probes", type=int, default=1)
    ra.add_argument("--permutations", type=int, default=10000)
    ra.add_argument("--bootstraps", type=int, default=2000)
    ra.add_argument("--seed", type=int, default=0)
    ra.add_argument("--files", nargs="*")
    ra.add_argument("--diff", action="store_true")
    ra.add_argument("--diff-base")
    ra.add_argument("--churn", action="store_true")
    ra.add_argument("--churn-files", type=int, default=10)
    ra.add_argument("--rank-churn", action="store_true")
    ra.add_argument("--history-cap", type=int, default=40)
    ra.add_argument("--min-lines", type=int, default=1)
    ra.add_argument("--max-lines", type=int, default=60)
    ra.add_argument("--include", nargs="*")
    ra.add_argument("--exclude", nargs="*")
    ra.add_argument("--allow-privates", action="store_true")
    ra.add_argument("--include-tests", dest="exclude_tests", action="store_false")
    ra.set_defaults(exclude_tests=True)
    ra.add_argument("--limit", type=int, default=30)
    ra.add_argument("--web-data")
    return p


_GLOBAL_FLAGS = ("--root", "--out")


def _hoist_globals(argv: list[str]) -> list[str]:
    """Allow `cmd --root X` as well as `--root X cmd`."""
    head: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in _GLOBAL_FLAGS and i + 1 < len(argv):
            head.extend(argv[i:i + 2])
            i += 2
            continue
        if any(tok.startswith(f + "=") for f in _GLOBAL_FLAGS):
            head.append(tok)
            i += 1
            continue
        rest.append(tok)
        i += 1
    return head + rest


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(_hoist_globals(list(argv)))
    os.makedirs(args.out, exist_ok=True)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
