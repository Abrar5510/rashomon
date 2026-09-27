import json
import os
import re
import subprocess
import sys

import pytest

from rashomon.astx import FunctionInfo, PickFilters, apply_filters, extract_from_source, load_function
from rashomon.cli import _normalise_answers, main
from rashomon.history import FIX_RE, NOT_FIX_RE, bugfix_history, function_history, is_git_repo
from rashomon.lift import anonymise
from rashomon.packet import build_packet
from rashomon.probes import heuristic_cases, materialise
from rashomon.runner import run_case
from rashomon.score import canon, label, same, score_all, score_function, wilson_interval
from rashomon.stats import branch_count, permutation_p, spearman

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo", "target_repo")


# ---------------------------------------------------------------- grading

def test_same_is_strict_about_types():
    assert not same("True", "1")
    assert not same("(1, 2)", "[1, 2]")
    assert not same("'1'", "1")
    assert same("(1, 2)", "(1, 2)")
    assert same("[1, 2]", "[1, 2]")
    assert same("None", "None")


def test_same_treats_numbers_by_value():
    assert same("1", "1.0")
    assert same("5400", "5400.0")
    assert not same("5400", "5401")


def test_same_falls_back_to_string_comparison():
    assert same("raises ValueError", "raises ValueError")
    assert not same("raises ValueError", "raises KeyError")


def test_canon_normalises_whitespace():
    assert canon("[1,  2]") == "[1, 2]"
    assert canon("  hello  ") == "hello"


def test_abstention_counts_as_wrong():
    entry = {"probes": [{"args": [1], "kwargs": {}, "label": "a", "ok": True, "repr": "2"}]}
    answers = {"k": {"0": {"w1": "2", "w2": ""}}}
    res = score_function("k", entry, answers, personas=["w1", "w2"])
    assert res["misreads"] == 1
    assert res["predictions"] == 2
    assert res["witnesses_correct"] == 1


def test_disagreement_counts_distinct_answers():
    entry = {"probes": [{"args": [], "kwargs": {}, "label": "a", "ok": True, "repr": "1"}]}
    answers = {"k": {"0": {"a": "1", "b": "2", "c": "2", "d": "3", "e": "1"}}}
    res = score_function("k", entry, answers, personas=list("abcde"))
    assert res["disagreement_max"] == 3
    assert res["misreads"] == 3


def test_score_all_sorts_by_misread_rate():
    fns = [
        {"key": "b", "path": "b.py", "qualname": "b", "signature": "", "source": "", "n_lines": 1},
        {"key": "a", "path": "a.py", "qualname": "a", "signature": "", "source": "", "n_lines": 1},
    ]
    probes = {
        "a": {"probes": [{"args": [], "kwargs": {}, "label": "x", "ok": True, "repr": "1"}]},
        "b": {"probes": [{"args": [], "kwargs": {}, "label": "x", "ok": True, "repr": "1"}]},
    }
    answers = {"a": {"0": {"p1": "1"}}, "b": {"0": {"p1": "9"}}}
    out = score_all(fns, probes, answers, personas=["p1"])
    assert out[0]["key"] == "b"
    assert out[0]["rank"] == 1


# ---------------------------------------------------------------- extraction

SOURCE = '''
def top(a, b=1):
    return a + b

class Box:
    def open(self, lid=True):
        return lid

    def nested(self):
        def inner():
            return 1
        return inner()

def _private():
    return 0
'''


def test_extract_quals_and_ranges():
    fns = extract_from_source("pkg/mod.py", SOURCE)
    names = {f.qualname for f in fns}
    assert {"top", "Box.open", "Box.nested", "_private"} <= names
    top = next(f for f in fns if f.qualname == "top")
    assert top.module == "pkg.mod"
    assert top.start < top.end
    assert "def top" in top.source


def test_filters_drop_privates_and_size():
    fns = extract_from_source("m.py", SOURCE)
    kept = apply_filters(fns, PickFilters(min_lines=1, max_lines=60))
    assert "_private" not in {f.qualname for f in kept}
    kept2 = apply_filters(fns, PickFilters(min_lines=1, max_lines=1))
    assert kept2 == []


def test_load_function_roundtrip():
    fn = load_function(DEMO, "chronex/parsing.py::parse_duration")
    assert fn is not None
    assert fn.qualname == "parse_duration"
    assert "units" in fn.source


# ---------------------------------------------------------------- probes + runner

def test_heuristic_cases_are_call_shaped():
    fn = load_function(DEMO, "chronex/seq.py::chunk")
    cases = heuristic_cases(fn, count=4)
    assert len(cases) == 4
    for c in cases:
        # `self` must never appear, chunk has (seq, size)
        assert len(c["args"]) + len(c["kwargs"]) == 2


def test_heuristic_cases_skip_self_on_methods():
    fn = load_function(DEMO, "chronex/seq.py::chunk")
    cases = heuristic_cases(fn, count=3)
    assert all("self" not in c["kwargs"] for c in cases)


def test_runner_executes_a_function():
    res = run_case(DEMO, "chronex/parsing.py", "parse_duration", {"args": ["1h30m"], "kwargs": {}})
    assert res["ok"] is True
    assert res["repr"] == "5400"


def test_runner_reports_exceptions():
    res = run_case(DEMO, "chronex/parsing.py", "parse_duration", {"args": ["5w"], "kwargs": {}})
    assert res["ok"] is False
    assert "KeyError" in res["error"]


def test_materialise_keeps_only_runnable_probes():
    fn = load_function(DEMO, "chronex/num.py::mean")
    entry = materialise(DEMO, fn, heuristic_cases(fn, count=6), keep=3)
    assert entry["n_runnable"] == 3
    assert all(p["ok"] for p in entry["probes"][:3])


# ---------------------------------------------------------------- history

def test_fix_regexes():
    assert FIX_RE.search("fix: parse_duration ignored the d suffix")
    assert FIX_RE.search("bugfix: crash on empty")
    assert not FIX_RE.search("feat: add helper")
    assert NOT_FIX_RE.search("fix: typo in docstring")
    assert not NOT_FIX_RE.search("fix: clamp ignored the lower bound")


def test_history_on_demo_repo():
    assert is_git_repo(DEMO)
    fns = [
        {"key": "chronex/parsing.py::parse_duration", "path": "chronex/parsing.py",
         "qualname": "parse_duration", "start": 7, "end": 18, "signature": "parse_duration(text)"},
    ]
    hist = bugfix_history(DEMO, fns)
    entry = hist["chronex/parsing.py::parse_duration"]
    assert entry["bug_fixes"] >= 1
    assert entry["touching_commits"] >= entry["bug_fixes"]


def test_history_neighbouring_function_is_not_double_counted():
    """git log -L bleeds across neighbours; the source check must not."""
    h = function_history(DEMO, "chronex/num.py", "mean", 1, 6, "mean(values)")
    assert h["bug_fixes"] <= 1


# ---------------------------------------------------------------- packets

def test_packet_never_leaks_the_answers():
    fn = load_function(DEMO, "chronex/parsing.py::parse_duration")
    probe = {"args": ["1h30m"], "kwargs": {}, "label": "typical", "ok": True, "repr": "5400"}
    packet = build_packet("B01", [fn.to_dict()], {fn.key: {"probes": [probe]}})
    assert "1h30m" in packet
    assert "5400" not in packet
    assert "5400" not in packet.replace("1h30m", "")


# ---------------------------------------------------------------- answers

def test_normalise_answers_accepts_both_shapes():
    flat = {"m.py::f#0#w1": "1", "__summaries__": {}}
    nested = _normalise_answers(flat)
    assert nested["m.py::f"]["0"]["w1"] == "1"

    already = {"m.py::f": {"0": {"w1": "1"}}, "__summaries__": {}}
    assert _normalise_answers(already) is already


# ---------------------------------------------------------------- end to end

@pytest.fixture(scope="module")
def demo_run(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("out"))
    rc = main([
        "run-all", "--root", DEMO, "--out", out, "--backend", "file",
        "--recorded-dir", os.path.join(ROOT, "demo", "fixtures"),
        "--max-lines", "200", "--web-data", str(tmp_path_factory.mktemp("web") / "data.json"),
    ])
    assert rc == 0
    return out


def test_end_to_end_scores_every_function(demo_run):
    results = json.load(open(os.path.join(demo_run, "results.json"), encoding="utf-8"))
    assert len(results) == 9
    assert results[0]["key"] == "chronex/parsing.py::parse_duration"
    assert results[0]["misread_rate"] > results[-1]["misread_rate"]
    assert results[-1]["misreads"] == 0


def test_end_to_end_gate_marks_the_headline_function(demo_run):
    proc = subprocess.run(
        [sys.executable, "-m", "rashomon.cli", "gate", "--root", DEMO, "--out", demo_run],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    assert proc.returncode == 0
    assert "parse_duration" in proc.stdout
    assert "Rashomon readability gate" in proc.stdout


def test_end_to_end_leaderboard_payload(demo_run):
    # rebuild into the temp out dir
    rc = main(["history", "--root", DEMO, "--out", demo_run])
    assert rc == 0
    web = os.path.join(demo_run, "data.json")
    assert main(["leaderboard", "--root", DEMO, "--out", demo_run, "--web-data", web]) == 0
    payload = json.load(open(web, encoding="utf-8"))
    assert payload["n_functions"] == 9
    assert payload["personas"] and len(payload["personas"]) == 5
    top = payload["functions"][0]
    assert top["history"]["bug_fixes"] >= 1
    assert top["probes"][0]["cards"] and len(top["probes"][0]["cards"]) == 5
    assert top["ci_lo"] <= top["misread_rate"] <= top["ci_hi"]


def test_end_to_end_stats_file(demo_run):
    rc = main(["history", "--root", DEMO, "--out", demo_run])
    assert rc == 0
    assert main(["stats", "--root", DEMO, "--out", demo_run,
                 "--permutations", "500", "--bootstraps", "200"]) == 0
    payload = json.load(open(os.path.join(demo_run, "stats.json"), encoding="utf-8"))
    assert payload["n_functions"] == 9
    for name in ("bug_fixes", "touching_commits", "loc", "branches"):
        assert name in payload["predictors"]
        assert -1.0 <= payload["predictors"][name]["spearman"] <= 1.0
        assert 0.0 <= payload["predictors"][name]["p"] <= 1.0


# ------------------------------------------- sealed held-out probes (P')

def test_seal_is_frozen_and_verifies(demo_run):
    from rashomon.seal import file_hash, is_sealed, manifest_path, primes_path, verify

    assert is_sealed(demo_run)
    ok, problems = verify(demo_run)
    assert ok, problems
    manifest = json.load(open(manifest_path(demo_run), encoding="utf-8"))
    assert manifest["file_sha256"] == file_hash(primes_path(demo_run))
    assert manifest["n_functions"] == len(manifest["entries"]) >= 9


def test_sealed_probes_are_runnable_and_disjoint(demo_run):
    from rashomon.seal import case_signature, primes_path

    scored = {e["key"]: e for e in json.load(open(os.path.join(demo_run, "probes.json"),
                                                  encoding="utf-8"))}
    primes = json.load(open(primes_path(demo_run), encoding="utf-8"))
    assert len(primes) == 9
    for entry in primes:
        assert entry["n_runnable"] >= 1, entry["key"]
        seen = {
            case_signature(p)
            for p in scored[entry["key"]]["probes"]
            if p.get("ok")
        }
        for p in entry["probes"]:
            assert case_signature(p) not in seen, f"{entry['key']} P' collides with a scored probe"
        assert all(p["label"].startswith("held") for p in entry["probes"])


def test_seal_detects_tampering(demo_run, tmp_path):
    import shutil

    from rashomon.seal import manifest_path, primes_path, verify

    out = str(tmp_path / "out")
    shutil.copytree(demo_run, out)

    # 1. editing a probe is caught by the file hash AND the per-entry hash
    primes = json.load(open(primes_path(out), encoding="utf-8"))
    primes[0]["probes"][0]["label"] = "tampered"
    with open(primes_path(out), "w", encoding="utf-8") as fh:
        json.dump(primes, fh, indent=2, ensure_ascii=False)
    ok, problems = verify(out)
    assert not ok
    assert any("sha256 mismatch" in p for p in problems)

    # 2. even a clever edit that fixes the file hash is caught per entry
    from rashomon.seal import file_hash

    manifest = json.load(open(manifest_path(out), encoding="utf-8"))
    manifest["file_sha256"] = file_hash(primes_path(out))
    with open(manifest_path(out), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    ok, problems = verify(out)
    assert not ok
    assert any("changed after the freeze" in p for p in problems)


def test_seal_refuses_to_reseal_without_force(demo_run):
    from rashomon.seal import primes_path

    before = open(primes_path(demo_run), "rb").read()
    assert main(["seal", "--root", DEMO, "--out", demo_run]) == 0
    after = open(primes_path(demo_run), "rb").read()
    assert before == after


def test_equiv_sealed_uses_the_frozen_held_out_probes(demo_run):
    key = "chronex/parsing.py::parse_duration"
    assert main(["clarify", "--root", DEMO, "--out", demo_run, "--key", key]) == 0
    # the clarified copy is byte-identical here, so P' must come back identical
    assert main(["equiv", "--root", DEMO, "--out", demo_run, "--key", key, "--sealed"]) == 0


def test_equiv_sealed_refuses_a_broken_freeze(demo_run, tmp_path):
    import shutil

    from rashomon.seal import primes_path

    out = str(tmp_path / "out")
    shutil.copytree(demo_run, out)
    key = "chronex/parsing.py::parse_duration"
    assert main(["clarify", "--root", DEMO, "--out", out, "--key", key]) == 0

    primes = json.load(open(primes_path(out), encoding="utf-8"))
    primes[0]["probes"][0]["label"] = "tampered"
    with open(primes_path(out), "w", encoding="utf-8") as fh:
        json.dump(primes, fh, indent=2, ensure_ascii=False)

    rc = main(["equiv", "--root", DEMO, "--out", out, "--key", key, "--sealed"])
    assert rc == 2


def test_rewatch_sealed_refuses_recorded_witnesses(demo_run, tmp_path):
    """P' has no recorded answers: --sealed must demand live witnesses."""
    import shutil

    out = str(tmp_path / "out")
    shutil.copytree(demo_run, out)
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "rewatch.py"),
         "--key", "chronex/parsing.py::parse_duration",
         "--root", DEMO, "--out", out, "--sealed", "--witness-backend", "file"],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    assert proc.returncode == 2
    assert "live witnesses" in proc.stderr


# ---------------------------------------------------------------- name-lift (C6)

def test_anonymise_renames_identifiers_only_and_is_deterministic():
    fn = load_function(DEMO, "chronex/parsing.py::parse_duration")
    src, rename, new_name = anonymise(fn)
    assert new_name != "parse_duration" and new_name.startswith("f_")
    assert not re.search(r"\bparse_duration\b", src)
    assert not re.search(r"\btext\b", src)
    assert "isdigit" in src          # attribute names untouched
    assert 'v3 = {"s": 1' in src     # structure and literals untouched
    assert src.count("\n") == fn.source.count("\n")
    assert rename["text"] == "p0"
    assert anonymise(fn)[0] == src    # deterministic across runs


def test_anonymise_handles_except_as_recursion_and_keywords():
    source = '''def parse(x):
    """parse(x) parses x."""
    try:
        return int(x) if x else parse(x=x + "1")
    except ValueError as err:
        return str(err)
'''
    fn = FunctionInfo(name="parse", qualname="parse", path="m.py", module="m",
                      start=1, end=7, source=source, signature="parse(x)", key="m.py::parse")
    src, rename, new_name = anonymise(fn)
    assert "as err" not in src                      # binding token, not just references
    assert re.search(r"as v\d+\b", src)
    assert "parse(x=" not in src                    # recursive keyword followed the rename
    assert f"{new_name}({rename['x']}=" in src
    assert not re.search(r"\bx\b", src)
    compile(src, "m.py", "exec")
    old, new = {}, {}
    exec(source, old)
    exec(src, new)
    assert new[new_name]("5") == old["parse"]("5")
    assert new[new_name]("") == old["parse"]("")


def test_lift_end_to_end_on_a_method(tmp_path):
    mod = '''class Box:
    def open(self, lid=True):
        count = 0
        if lid:
            count += 1
        return count
'''
    root = tmp_path / "repo"
    root.mkdir()
    (root / "box.py").write_text(mod, encoding="utf-8")
    out = str(tmp_path / "out")
    os.makedirs(out)

    fns = [f.to_dict() for f in extract_from_source("box.py", mod)]
    method = next(f for f in fns if f["qualname"] == "Box.open")
    probes = [{
        "key": method["key"], "path": method["path"], "qualname": method["qualname"],
        "signature": method["signature"], "source": method["source"],
        "probes": [
            {"args": [], "kwargs": {"lid": True}, "label": "typical", "ok": True,
             "repr": "1", "error": None},
            {"args": [], "kwargs": {}, "label": "default", "ok": True, "repr": "1",
             "error": None},
        ],
        "n_runnable": 2,
    }]
    json.dump([method], open(os.path.join(out, "functions.json"), "w", encoding="utf-8"))
    json.dump(probes, open(os.path.join(out, "probes.json"), "w", encoding="utf-8"))

    assert main(["lift", "--root", str(root), "--out", out]) == 0
    lifted = open(os.path.join(out, "lifted", "box.py"), encoding="utf-8").read()
    assert "def open" not in lifted
    assert "self" in lifted                       # self/cls stay
    assert not re.search(r"\bcount\b", lifted)
    assert "class Box" in lifted                  # surrounding module untouched

    manifest = json.load(open(os.path.join(out, "lifted", "manifest.json"), encoding="utf-8"))
    assert manifest["verified"][method["key"]] == "2/2"
    lifted_probes = json.load(open(os.path.join(out, "lifted", "probes.json"), encoding="utf-8"))
    assert lifted_probes[0]["probes"][0]["kwargs"] == {"p0": True}  # kwargs remapped


def test_lifted_recorded_session_scores_identically(demo_run):
    """The recorded answers key on the original fn key, so M' == M offline."""
    assert main(["lift", "--root", DEMO, "--out", demo_run]) == 0
    assert main(["witness", "--root", DEMO, "--out", demo_run, "--backend", "file",
                 "--witness-file", os.path.join(ROOT, "demo", "fixtures", "witnesses.json"),
                 "--lifted"]) == 0
    assert main(["score", "--root", DEMO, "--out", demo_run, "--lifted"]) == 0
    orig = {r["key"]: r for r in json.load(open(os.path.join(demo_run, "results.json"),
                                                encoding="utf-8"))}
    lifted = {r["key"]: r for r in json.load(open(os.path.join(demo_run, "lifted", "results.json"),
                                                  encoding="utf-8"))}
    assert set(orig) == set(lifted) and len(lifted) == 9
    for key in orig:
        assert orig[key]["misread_rate"] == lifted[key]["misread_rate"]
        assert lifted[key]["source"] != orig[key]["source"]
    assert main(["lift", "--root", DEMO, "--out", demo_run, "--report"]) == 0


# ---------------------------------------------------------------- statistics

def test_wilson_interval_matches_the_plan_numbers():
    lo, hi = wilson_interval(0, 15)
    assert lo == 0.0
    assert hi == pytest.approx(0.20, abs=0.01)
    lo7, hi7 = wilson_interval(7, 15)
    assert lo7 == pytest.approx(0.25, abs=0.01)
    assert lo7 < hi7 <= 1.0


def test_labels_follow_the_interval_not_the_raw_rate():
    assert label(0, 15) == "Clear"
    assert label(1, 15) == "Scattered"
    assert label(7, 15, consensus_wrong=4) == "Consensus misread"
    assert label(7, 15, consensus_wrong=2) == "Confusing"
    assert label(5, 5, consensus_wrong=5) == "Consensus misread"


def test_spearman_ranks_and_ties():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    assert spearman([1, 2, 3], [7, 7, 7]) == 0.0
    tied = spearman([1, 1, 2, 3], [1, 2, 3, 4])
    assert -1.0 <= tied <= 1.0


def test_permutation_p_is_deterministic_and_significant_for_a_clear_signal():
    x = list(range(1, 11))
    y = [v * 3 for v in x]
    first = permutation_p(x, y, n=500, seed=0)
    assert first == permutation_p(x, y, n=500, seed=0)
    assert first < 0.05
    assert permutation_p(x, list(reversed(x)), n=500, seed=0) < 0.05
    assert permutation_p([1, 2], [1, 2], n=100, seed=0) == 1.0


def test_branch_count_counts_decision_points():
    assert branch_count("") == 0
    assert branch_count("def f():\n    pass") == 0
    assert branch_count("if a:\n    pass") == 1
    assert branch_count("x = 1 if a else 2") == 1
    assert branch_count("def f():\n    for i in y:\n        pass") == 1
    assert branch_count("a and b") == 1
    assert branch_count("try:\n    pass\nexcept E:\n    pass\nexcept F:\n    pass") == 2
    assert branch_count("[i for i in x if i]") == 1
    assert branch_count("match x:\n    case 1:\n        pass\n    case 2:\n        pass") == 2


def test_score_reports_interval_consensus_and_label():
    entry = {"probes": [{"args": [], "kwargs": {}, "label": "a", "ok": True, "repr": "1"}]}
    answers = {"k": {"0": {p: "9" for p in list("abcde")}}}
    res = score_function("k", entry, answers, personas=list("abcde"))
    assert res["consensus_wrong"] == 5
    assert res["label"] == "Consensus misread"
    assert res["verdict"] == "confusing"
    assert res["probes"][0]["wrong"] == 5


# ------------------------------------------------- live witness checkpoints

def _wf(key, name):
    return FunctionInfo(name=name, qualname=name, path="m.py", module="m",
                        start=1, end=2, source=f"def {name}(x):\n    return x\n",
                        signature=f"{name}(x)", key=key)


class _FakeLLM:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        if self.fail:
            raise RuntimeError("quota exhausted")
        return '{"summary": "s", "predictions": ["1", "2"]}'


def test_witness_checkpoint_resumes_without_rerunning_done_functions(tmp_path):
    from rashomon.witnesses import run_witnesses

    ck = tmp_path / "witnesses.json"
    personas = ["w1", "w2", "w3", "w4", "w5"]
    done = {"0": dict.fromkeys(personas, "1"), "1": dict.fromkeys(personas, "1")}
    ck.write_text(json.dumps({"m.py::a": done, "__summaries__": {"m.py::a": {}}}), encoding="utf-8")

    probes = {k: {"probes": [{"args": [0], "ok": True}, {"args": [1], "ok": True}]}
              for k in ("m.py::a", "m.py::b")}
    llm = _FakeLLM()
    out = run_witnesses([_wf("m.py::a", "a"), _wf("m.py::b", "b")], probes,
                        backend="llm", llm=llm, personas=personas, checkpoint=str(ck))
    assert llm.calls == 5                       # only b was answered live
    assert out["m.py::a"]["0"]["w1"] == "1"     # a resumed from the checkpoint
    assert out["m.py::b"]["0"]["w1"] == "1"


def test_witness_checkpoint_aborts_after_consecutive_failures(tmp_path):
    from rashomon.witnesses import run_witnesses

    ck = tmp_path / "witnesses.json"
    personas = ["w1", "w2", "w3", "w4", "w5"]
    probes = {k: {"probes": [{"args": [0], "ok": True}]} for k in ("m.py::a", "m.py::b")}
    llm = _FakeLLM(fail=True)
    with pytest.raises(ValueError, match="consecutive"):
        run_witnesses([_wf("m.py::a", "a"), _wf("m.py::b", "b")], probes,
                      backend="llm", llm=llm, personas=personas, checkpoint=str(ck))
    assert ck.exists()                          # partial progress survived
    saved = json.loads(ck.read_text(encoding="utf-8"))
    assert "m.py::a" in saved                   # a was written before the abort
