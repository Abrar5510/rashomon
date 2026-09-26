"""Rashomon: unit tests for readability.

Five independent readers predict what a function returns. We run it for real.
Disagreement and wrong predictions become a number.
"""

__version__ = "0.1.0"

WITNESS_PERSONAS = [
    "careful-stylist",
    "speed-reader",
    "regex-allergic",
    "api-historian",
    "edge-case-hunter",
]
