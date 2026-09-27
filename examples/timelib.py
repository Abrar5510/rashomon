"""Tiny committed targets for the readability-gate demo (see README "PR gate")."""


def parse_duration(text: str) -> int:
    """Parse a duration like '1h30m' into whole seconds."""
    weights = {"h": 3600, "m": 60, "s": 1}
    seconds = 0
    digits = ""
    for ch in text:
        if ch.isdigit():
            digits += ch
        elif ch in weights and digits:
            seconds += int(digits) * weights[ch]
            digits = ""
    if digits:
        seconds += int(digits)
    return seconds


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value into the inclusive range [low, high]."""
    if value < low:
        return low
    if value > high:
        return high
    return value
