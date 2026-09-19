#!/usr/bin/env python3
"""Copy structured.py into the merged section of pdf2md_all.py.

The single-file build inlines structured.py, renaming three module-level
globals so they do not collide with the core's own names. The original build
script did that with a plain textual substitution and no word boundaries,
which rewrote `re.sub(r"\\W", ...)` into `re.sub(r"\\WML", ...)` -- silently
disabling EPUB heading de-duplication in the shipped build while the module
kept working. Nobody could see it, because nothing compared the two copies.

This tool renames NAME tokens only, using the `tokenize` module, so a rename
can never reach inside a string or a regex again.

    python3 tools/sync_structured.py           # rewrite the merged section
    python3 tools/sync_structured.py --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "structured.py"
MERGED = ROOT / "pdf2md_all.py"

# module-level name -> name it takes inside the single-file build
RENAMES = {
    "BLOCK_TAGS": "HTML_BLOCK_TAGS",
    "NS": "EPUB_NS",
    "W": "WML",
}

MODULE_BANNER = "# structured.py  —"
NEXT_BANNER = "# pdf2md.py  —"
BODY_START = "@dataclass"


def rename_identifiers(src: str, mapping: dict[str, str]) -> str:
    """Rename NAME tokens only; strings, comments and numbers are untouched."""
    # untokenize changes continuation whitespace on Python 3.10/3.11.
    # Apply token-position edits to the original source to keep it byte-stable.
    offsets = [0]
    for line in src.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.NAME and tok.string in mapping:
            start = offsets[tok.start[0] - 1] + tok.start[1]
            end = offsets[tok.end[0] - 1] + tok.end[1]
            edits.append((start, end, mapping[tok.string]))
    for start, end, replacement in reversed(edits):
        src = src[:start] + replacement + src[end:]
    return src


def module_body() -> str:
    src = MODULE.read_text(encoding="utf-8")
    body = src[src.index(BODY_START):]
    return rename_identifiers(body, RENAMES).rstrip() + "\n"


def merged_bounds(lines: list[str]) -> tuple[int, int]:
    banner = next(i for i, l in enumerate(lines) if l.startswith(MODULE_BANNER))
    nxt = next(i for i, l in enumerate(lines) if i > banner and l.startswith(NEXT_BANNER))
    start = next(i for i, l in enumerate(lines) if i > banner and l.startswith(BODY_START))
    end = nxt - 1                      # the "# ===" rule opening the next banner
    while end > start and not lines[end - 1].strip():
        end -= 1
    return start, end


def main() -> int:
    check = "--check" in sys.argv
    lines = MERGED.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = merged_bounds(lines)
    current = "".join(lines[start:end])
    wanted = module_body()
    if current.rstrip() == wanted.rstrip():
        print("pdf2md_all.py is in sync with structured.py")
        return 0
    if check:
        print("OUT OF SYNC: pdf2md_all.py's structured section differs from "
              "structured.py. Run `python3 tools/sync_structured.py`.", file=sys.stderr)
        return 1
    MERGED.write_text("".join(lines[:start]) + wanted + "\n" + "".join(lines[end:]),
                      encoding="utf-8")
    print(f"synced structured.py -> pdf2md_all.py lines {start + 1}-{end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
