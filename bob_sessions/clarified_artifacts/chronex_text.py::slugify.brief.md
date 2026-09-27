You are the **Clarifier**. Your only job is to make one function
readable to an independent reader without changing what it does.

Rules:
1. Edit ONLY `rashomon_out/clarified/chronex/text.py`. Touch nothing else.
2. Do not change the function's signature or return value.
3. Do not delete, skip, weaken, or rewrite any test.
4. Run the test suite before you finish; it must stay green.

Current misread rate: **7/15** predictions wrong across 5
independent readers; 2.667 distinct answers on average.
Readers' one-line summaries of what they thought it did:
- (none recorded)

Function under review:

```python
def slugify(text):
    """Turn arbitrary text into a url-safe slug."""
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            if out and out[-1] != "-":
                out.append("-")
    return "".join(out).strip("-")
```

Rename, extract, add a docstring, or restructure so that every reader predicts
the same outputs as the interpreter does.
