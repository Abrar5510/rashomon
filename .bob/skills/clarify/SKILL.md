---
name: clarify
description: Rewrite one confusing Python function so independent readers predict its outputs correctly, without changing its behaviour. Use after a Rashomon score shows misreads.
---

# Clarifier

1. Run `make clarify ID=<key>` first. It copies the module to
   `rashomon_out/clarified/` and writes the brief. Read the brief — it contains the
   function, the misread rate, and what each reader thought it did.

2. Edit **only** the file under `rashomon_out/clarified/`. Allowed changes:
   - rename locals and parameters that mislead;
   - extract a well-named helper inside the same file;
   - reorder branches so the common path is first;
   - add or rewrite the docstring and comments.
   Forbidden: changing the signature, the return value, the exception types, or
   any test.

3. After every edit run `make equiv ID=<key>`. It prints `N/N identical`.
   - Not `N/N` → use **Rollback**, then retry. At most **2** attempts per function.
   - Two failures → stop and report; the user will pick another function.

4. Never read, guess or search for the held-out inputs. The brief deliberately
   does not contain them.

5. When `equiv` is `N/N`, tell the user to run `make rewatch ID=<key>` so fresh
   witnesses read the clarified version, and report the change in misread rate.
