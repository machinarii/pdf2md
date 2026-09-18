#!/usr/bin/env python3
"""Rename converted Markdown after the title pdf2md found inside it.

The converter names its output after its input, because that is the only name
it is given: a library of `p517.pdf`, `p1025.pdf` produces `p517.md`,
`p1025.md`, even though the YAML front matter of each says what the document
actually is. This renames them from that front matter.

    python3 tools/name_by_title.py out/              # show what it would do
    python3 tools/name_by_title.py out/ --apply      # do it
    python3 tools/name_by_title.py out/ --apply --with-author

Only the title recorded by the converter is used; nothing is re-read from the
PDF, and a file whose front matter has no usable title is left alone.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
MAX = 90


def field(front: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", front, re.M)
    if not m:
        return ""
    return m.group(1).strip().strip('"').strip("'").strip()


def first_author(front: str) -> str:
    m = re.search(r"^authors:\n\s+-\s*(.+)$", front, re.M)
    return m.group(1).strip().strip('"') if m else ""


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-{2,}", "-", text).strip("-")[:MAX].rstrip("-")


def new_name(md: Path, with_author: bool) -> str | None:
    m = FRONT.match(md.read_text(errors="replace"))
    if not m:
        return None
    front = m.group(1)
    title = field(front, "title")
    # the converter falls back to the file name when it finds no real title
    if not title or title.lower() in {md.name.lower(), md.stem.lower(),
                                      md.stem.lower() + ".pdf"}:
        return None
    parts = [slug(title)]
    if with_author:
        who = first_author(front)
        if who:
            parts.insert(0, slug(who.split(",")[0]))
    stem = "--".join(p for p in parts if p)
    return stem + md.suffix if stem else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", type=Path)
    ap.add_argument("--apply", action="store_true", help="rename; otherwise just report")
    ap.add_argument("--with-author", action="store_true", help="prefix the first author")
    args = ap.parse_args()

    if not args.directory.is_dir():
        sys.exit(f"not a directory: {args.directory}")

    taken = {p.name for p in args.directory.glob("*.md")}
    renamed = skipped = 0
    for md in sorted(args.directory.glob("*.md")):
        want = new_name(md, args.with_author)
        if not want or want == md.name:
            skipped += 1
            continue
        target, n = want, 2
        while target in taken:                   # two papers can share a title
            target = f"{Path(want).stem}-{n}{md.suffix}"
            n += 1
        print(f"{md.name}  ->  {target}")
        if args.apply:
            md.rename(md.with_name(target))
            taken.discard(md.name)
            taken.add(target)
        renamed += 1
    print(f"\n{renamed} to rename, {skipped} left alone"
          f"{'' if args.apply else '  (nothing changed; pass --apply)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
