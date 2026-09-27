#!/usr/bin/env python3
"""Regenerate the narration track (local Kokoro-82M, voice am_michael).

Each clip must fit inside its scene with a 0.6 s lead-in and 0.4 s tail:
if a clip overflows, trim the copy in LINES below — never speed the audio up.

    HYPERFRAMES_PYTHON=<venv>/bin/python python3 make_narration.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "assets" / "narr"

# clip -> (scene start, scene end) — a clip must end before scene end - TAIL
SCENES = {
    "n1": (0, 12), "n2": (12, 30), "n3": (30, 45), "n4": (45, 65),
    "n5": (65, 80), "n6": (80, 95), "n7a": (95, 120), "n7b": (120, 135),
    "n8": (135, 165), "n9": (165, 180),
}
LEAD, TAIL = 0.6, 0.4

LINES = {
    "n1": "What does this return? Five readers, three answers, only one right, and we know "
          "which, because we ran the code. Predict the output, then run the function.",
    "n2": "Fifty-eight percent of development time is spent reading code. "
          "A hundred and twenty-one metrics have been proposed, and none of them "
          "track what humans think. Ask a model instead, and it correlates with people at roughly zero. "
          "So we stopped asking.",
    "n3": "This is Bob. The rashomon mode picks up one witness packet: the function, its probe inputs, "
          "and nothing else. No answers, no history, no hint of what the right output looks like.",
    "n4": "Five readers fork their own context, so they cannot influence each other. No groupthink. "
          "Each gets exactly one tool call: read the function, predict what it returns, then stop. "
          "They never see the real output, each other, or the answer key.",
    "n5": "Then we execute it. This function fooled seven of fifteen readings: one reader said "
          "thirty-six hundred when the answer was fifty-four hundred. That disagreement is the "
          "measurement.",
    "n6": "Nine of nine functions here carry a boundary-bug fix, and they still misle"
          "ad readers. Fixing the bug never fixed the confusion. The confusion was never in the behaviour. "
          "It was in the code.",
    "n7a": "So the clarifier takes a swing. It reads the confusing function and writes a plainer version "
           "into a copy, never the real file. Then we prove the behaviour did not move: fifteen probes, "
           "fifteen identical results, before anyone is allowed to judge the new wording. "
           "If a rewrite changes a single return value, that is a bug fix, not a rewrite.",
    "n7b": "Then fresh readers, with no memory of the first pass, score the "
           "clarified copy. Before: seven of fifteen misled. After: nobody. And the gate posts that "
           "change to the pull request.",
    "n8": "Thirty functions from a real library, ranked by how often independent readers disagree, and "
          "every row carries its own bug-fix history. The correlation with past fixes is not zero: "
          "point three nine, with a p-value of point naught three. The top row misleads every reader "
          "and has three historical bug fixes. Readability is now a number you can regress on.",
    "n9": "CRUXEval uses code to grade models. Rashomon uses models to grade code. "
          "Five readers disagreeing means it is unclear. "
          "Readability was an opinion. Now it is a test.",
}


def synth(key: str, text: str) -> float:
    OUT.mkdir(parents=True, exist_ok=True)
    txt = OUT / f"{key}.txt"
    wav = OUT / f"{key}.wav"
    txt.write_text(text)
    code = f"""
from kokoro_onnx import Kokoro
import soundfile as sf
k = Kokoro(
    "/Users/abrar/.cache/hyperframes/tts/models/kokoro-v1.0.onnx",
    "/Users/abrar/.cache/hyperframes/tts/voices/voices-v1.0.bin",
)
s, sr = k.create(open(r"{txt}").read(), voice="am_michael", lang="en-us")
sf.write(r"{wav}", s, sr)
print(len(s)/sr)
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr[-2000:])
        raise SystemExit(f"TTS failed for {key}")
    return float(out.stdout.strip().splitlines()[-1])


def main():
    durs = {}
    bad = []
    for key, text in LINES.items():
        d = synth(key, text)
        durs[key] = round(d, 2)
        lo, hi = SCENES[key]
        budget = (hi - lo) - LEAD - TAIL - 1.0
        flag = "OK " if d <= budget else "OVER"
        if d > budget:
            bad.append(key)
        print(f"{flag} {key:4s} {d:6.2f}s / {budget:5.1f}s budget  ({lo}-{hi}s scene)")
    (OUT / "durations.json").write_text(json.dumps(durs, indent=1) + "\n")
    total = sum(durs.values())
    print(f"\nspeech {total:.1f}s of 180s ({total/180*100:.0f}%)")
    if bad:
        print(f"OVERFLOW — trim the copy in LINES for: {', '.join(bad)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
