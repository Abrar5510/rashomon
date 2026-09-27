#!/usr/bin/env python3
"""Drive the IBM Bob desktop app: synthetic clicks (CGEvent) + DB status probes.

Used to run and verify the genuine Bob sessions captured in bob_sessions/.
Coordinates are screen points (Bob window bounds come from Accessibility).
"""
import ctypes
import json
import os
import subprocess
import sys
import time

CG = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_CREATE = CG.CGEventCreate
_CREATE.restype = ctypes.c_void_p
_CREATE.argtypes = [ctypes.c_void_p]
_LOC = CG.CGEventGetLocation
_LOC.argtypes = [ctypes.c_void_p]
_LOC.restype = CGPoint
_MOVE = CG.CGEventCreateMouseEvent
_MOVE.restype = ctypes.c_void_p
_MOVE.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_uint32,
]
_POST = CG.CGEventPost
_POST.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

DB = os.path.expanduser("~/.bob/db/bob.db")


def click(x: float, y: float, hold: float = 0.12) -> None:
    _POST(0, _MOVE(None, 5, x, y, 0))
    time.sleep(0.25)
    _POST(0, _MOVE(None, 1, x, y, 0))
    time.sleep(hold)
    _POST(0, _MOVE(None, 2, x, y, 0))
    time.sleep(0.25)


def activate(app: str = "IBM Bob") -> None:
    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], check=True)
    time.sleep(0.8)


def keystemu(actions: list[str]) -> None:
    """Run raw AppleScript action lines inside one System Events tell block."""
    body = "".join(f"  {a}\n" for a in actions)
    script = 'tell application "System Events"\n' + body + "end tell\n"
    subprocess.run(["osascript", "-e", script], check=True)


def db(sql: str):
    out = subprocess.run(["sqlite3", DB, sql], capture_output=True, text=True)
    return out.stdout.strip()


def frontmost() -> str:
    out = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def find_blue_button():
    """Locate the enabled blue Approve button on screen; returns screen points or None."""
    from PIL import Image

    path = "/tmp/_bob_shot.png"
    subprocess.run(["screencapture", "-x", path], check=True)
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    mask = set()
    for y in range(0, min(600, h)):
        for x in range(0, min(1000, w)):
            r, g, b = px[x, y]
            if b - r > 20 and b > 85:
                mask.add((x, y))
    seen = set()
    comps = []
    for p in list(mask):
        if p in seen:
            continue
        st = [p]
        seen.add(p)
        pts = []
        while st:
            cx, cy = st.pop()
            pts.append((cx, cy))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (cx + dx, cy + dy)
                if q in mask and q not in seen:
                    seen.add(q)
                    st.append(q)
        xs = [a for a, _ in pts]
        ys = [b for _, b in pts]
        bw = max(xs) - min(xs) + 1
        bh = max(ys) - min(ys) + 1
        if bw >= 70 and bh >= 16:
            comps.append((min(xs), min(ys), bw, bh))
    if not comps:
        return None, im.size
    x, y, bw, bh = max(comps, key=lambda c: c[2] * c[3])
    return (x + bw / 2, y + bh / 2), im.size


def auto_approve(max_tries: int = 6) -> dict:
    tries = 0
    while tries < max_tries:
        if int(status()["pending"]) == 0:
            return {"approved": tries, "left": 0}
        tries += 1
        if frontmost() != "IBM Bob":
            activate()
            time.sleep(1.2)
        pt, size = find_blue_button()
        if pt is None:
            return {"approved": tries - 1, "left": int(status()["pending"]), "no_button": True}
        click(pt[0], pt[1], hold=0.25)
        time.sleep(1.5)
    return {"approved": tries, "left": int(status()["pending"])}


def status(task_prefix: str = "") -> dict:
    where = f"id like '{task_prefix}%'" if task_prefix else "1=1"
    row = db(
        f"select status, (select count(*) from task_pending_approvals), "
        f"(select count(*) from messages) from tasks where {where} "
        f"order by created_at desc limit 1;"
    )
    status_, pending, msgs = (row.split("|") + ["", "", ""])[:3]
    return {"status": status_, "pending": int(pending or 0), "msgs": int(msgs or 0)}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "click":
        click(float(sys.argv[2]), float(sys.argv[3]))
    elif cmd == "status":
        print(status(sys.argv[2] if len(sys.argv) > 2 else ""))
    elif cmd == "send":
        x, y = float(sys.argv[2]), float(sys.argv[3])
        text = sys.argv[4]
        activate()
        click(x, y)
        time.sleep(0.5)
        keystemu([f'keystroke {json.dumps(text)}', "delay 1", "key code 36"])
        print("sent")
    elif cmd == "approve":
        # blue "Approve" button in the tool-approval card
        click(float(sys.argv[2]), float(sys.argv[3]), hold=0.25)
        print("clicked approve")
    elif cmd == "autoapprove":
        print(auto_approve())
    else:
        raise SystemExit("usage: bob_drive.py click|status|send|approve|autoapprove ...")
