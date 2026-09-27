"""Tiny committed targets for the readability-gate demo (see README "PR gate")."""


def parse_duration(text: str) -> int:
    """Parse a duration like '1h30m' into whole seconds."""
    minutes = 0
    units = {"h": 3600, "m": 60, "s": 1}
    pending = ""
    for ch in text:
        if ch.isdigit():
            pending += ch
        elif ch in units and pending:
            minutes = minutes + int(pending) * units[ch]
            pending = ""
    return minutes


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value into the closed interval [low, high]; both bounds are inclusive."""
    if value < low:
        return low
    if value > high:
        return high
    return value
