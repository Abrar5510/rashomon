"""Duration and HTTP header parsing."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_duration(text):
    """Parse a compact duration such as '1h30m' into whole seconds."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    total = 0
    pending = ""
    for ch in text:
        if ch.isdigit():
            pending += ch
        else:
            total += int(pending) * units[ch]
            pending = ""
    return total


def parse_retry_after(headers):
    """Seconds a client should wait, read from a Retry-After header."""
    raw = str(headers.get("Retry-After", "0")).strip()
    if raw.isdigit():
        return int(raw)
    when = parsedate_to_datetime(raw)
    delta = when - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))
