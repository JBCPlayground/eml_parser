# Refactoring Learnings — EML Parser

**Date:** 2026-02-06
**Scope:** Shared utilities extraction, dead code removal, logging, template separation

---

## Code duplication signals missing abstractions

The email header HTML was built in three places (pdf_converter, rtf_converter, and the plain-text fallback in extractor), each slightly different. The filename dedup loop was copied three times too. Once we pulled these into `utils.py`, each call site shrank to one line and the inconsistencies disappeared.

## Dead code accumulates quietly

`replace_problematic()` in pdf_converter was defined but never called — the character loop right below it did the same work. `html_to_text()` and `clean_text()` in extractor had no external callers. Nobody noticed because the code still worked. Grepping for actual usage before deleting was the only reliable way to confirm.

## Duplication causes bugs, not just mess

The plain-text double-header wasn't just cosmetic duplication — `get_html_for_pdf()` injected Subject/From/Date, then both converters injected their own header on top. Plain-text emails got the header twice. Centralizing the header to one place (the converters) fixed a real bug, not just style.

## Hardcoded environment assumptions break silently

`get_wsl_distro()` defaulted to `'Ubuntu-24.04'` when `WSL_DISTRO_NAME` wasn't set. On any other distro or non-WSL system, it would generate broken file URLs without any error. The fix was to check `_is_wsl()` first and fall back to standard `file:///` URLs.

## `print()` is invisible in library code

All the warnings in `parser.py` and status messages in the converters went to stdout, mixed with CLI output, with no way to filter or silence them. Switching to `logging` with a `--verbose` flag made diagnostics opt-in and routed them to stderr.

## Environment friction is worth documenting

`python` vs `python3`, `--break-system-packages`, `punkt_tab` in addition to `punkt` — these are the kind of things that cost 5 minutes each time someone sets up the project. We caught the `punkt_tab` gap during testing and added it to CLAUDE.md.
