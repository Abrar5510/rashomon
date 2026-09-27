"""Tiny committed targets for the readability-gate demo (see README "PR gate")."""


def parse_duration(text: str) -> int:
    """Parse a duration like '1h30m' into whole seconds."""
    minutes = 0
    factor = {"h": 3600, "m": 60, "s": 1}
    seen = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if "0" <= ch <= "9":
            seen += ch
        elif ch in factor and seen:
            minutes = minutes + int(seen) * factor[ch]
            seen = ""
        i += 1
    return minutes + int(seen) if seen else minutes


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value into the closed interval [low, high]; both bounds are inclusive."""
    if value < low:
        return low
    if value > high:
        return high
    return value
