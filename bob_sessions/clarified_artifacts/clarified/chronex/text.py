"""String helpers."""


def slugify(text):
    """Turn arbitrary text into a lowercase URL-safe slug.

    Each character in *text* is lowercased, then classified:
    - alphanumeric (including Unicode letters/digits such as ü, ï, é) → kept as-is
    - anything else (spaces, punctuation, …) → replaced by a single "-" separator

    Leading and trailing "-" separators are stripped from the result.

    Examples::

        slugify("Hello, World!")  -> "hello-world"
        slugify("  a  --  b  ")  -> "a-b"
        slugify("Ünïcode 42")    -> "ünïcode-42"   # ü and ï are alphanumeric in Python
    """
    slug_chars = []
    for ch in text.lower():
        if ch.isalnum():
            # Unicode alphanumerics (ü, ï, é, …) pass this check too
            slug_chars.append(ch)
        elif slug_chars and slug_chars[-1] != "-":
            # Collapse any run of non-alphanumeric characters into one "-"
            slug_chars.append("-")
    return "".join(slug_chars).strip("-")


def is_palindrome(text):
    """True when the text reads the same forwards and backwards."""
    clean = [ch for ch in text.lower() if ch.isalnum()]
    return clean == clean[::-1]
