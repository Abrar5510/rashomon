"""Tiny committed targets for the readability-gate demo (see README "PR gate")."""


def parse_duration(text: str) -> int:
    """Parse a duration like '1h30m' into whole seconds."""
    seconds_per_unit = {"h": 3600, "m": 60, "s": 1}
    total_seconds = 0
    number = ""
    for char in text:
        if char.isdigit():
            number += char
            continue
        if char in seconds_per_unit and number:
            total_seconds += int(number) * seconds_per_unit[char]
            number = ""
    if number:
        total_seconds += int(number)
    return total_seconds


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value into the closed interval [low, high]; both bounds are inclusive."""
    if value < low:
        return low
    if value > high:
        return high
    return value
