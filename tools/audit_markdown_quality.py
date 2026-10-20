#!/usr/bin/env python3
"""Corpus-wide cleanliness audit for Markdown emitted by pdf2md."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote


CHECKS = {
    "replacement_chars": (5, "Unicode replacement characters remain"),
    "private_use_chars": (5, "Private-use glyphs remain"),
    "unclosed_fence": (4, "Code fence is not balanced"),
    "broken_image_link": (4, "A local image link is missing"),
    "heading_jump": (2, "Heading hierarchy skips a level"),
    "duplicate_heading": (2, "A heading repeats unusually often"),
    "standalone_page_number": (2, "Standalone page-number furniture remains"),
    "broken_text_layer": (5, "Long word-like strings suggest lost spaces in the PDF text layer"),
    "possible_broken_hyphen": (2, "A word appears split across Markdown lines"),
    "excess_blank_lines": (1, "Two or more consecutive blank lines outside code fences"),
    "trailing_whitespace": (1, "Trailing whitespace remains"),
    "short_prose_fragment": (1, "Many short non-structural lines may be unreflowed"),
    "malformed_table": (2, "A pipe-table row has inconsistent cell counts"),
    "corrupt_title_spacing": (4, "Title contains likely letter-by-letter extraction"),
    "implausible_title_length": (4, "Title appears to have swallowed body text"),
    "corrupt_subtitle_spacing": (3, "Subtitle contains likely letter-by-letter extraction"),
    "implausible_subtitle_length": (3, "Subtitle appears to have swallowed unrelated text"),
}


def inspect(path: Path) -> tuple[Counter, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    issues = Counter()
    examples = defaultdict(list)

    def add(kind: str, line: int = 0, sample: str = "") -> None:
        issues[kind] += 1
        if len(examples[kind]) < 3:
            examples[kind].append({"line": line, "text": sample[:180]})

    for field, corrupt_kind, length_kind, limit in (
            ("title", "corrupt_title_spacing", "implausible_title_length", 240),
            ("subtitle", "corrupt_subtitle_spacing", "implausible_subtitle_length", 300)):
        match = re.search(rf"^{field}:\s*(.+)$", text, re.M)
        if not match:
            continue
        value = match.group(1).strip().strip("\"'")
        singles = re.findall(r"(?<!\w)[A-Za-z0-9](?!\w)", value)
        if len(singles) >= 4:
            add(corrupt_kind, text[:match.start()].count("\n") + 1, value)
        if len(value) > limit or len(value.split()) > 40:
            add(length_kind, text[:match.start()].count("\n") + 1, value)

    in_fence = False
    blank_run = 0
    blank_start = 0
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            if not in_fence and blank_run >= 2:
                add("excess_blank_lines", blank_start, f"{blank_run} consecutive blank lines")
            blank_run = 0
            in_fence = not in_fence
            continue
        if not in_fence:
            if not line.strip():
                if not blank_run:
                    blank_start = i
                blank_run += 1
            else:
                if blank_run >= 2:
                    add("excess_blank_lines", blank_start, f"{blank_run} consecutive blank lines")
                blank_run = 0
        if "\ufffd" in line:
            add("replacement_chars", i, line)
        if any(0xE000 <= ord(c) <= 0xF8FF for c in line):
            add("private_use_chars", i, line)
        if not in_fence and re.fullmatch(r"\s*\d{1,4}\s*", line):
            add("standalone_page_number", i, line)
        if not in_fence and line.rstrip() != line and not line.endswith("  "):
            add("trailing_whitespace", i, line)
        if (not in_fence and re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]-$", line)
                and i < len(lines) and re.match(r"^[a-zà-öø-ÿ]", lines[i])):
            add("possible_broken_hyphen", i, line + " / " + lines[i])
    if blank_run >= 2:
        add("excess_blank_lines", blank_start, f"{blank_run} consecutive blank lines")
    if sum(1 for line in lines if line.lstrip().startswith("```")) % 2:
        add("unclosed_fence")

    content = lines
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            content = lines[end + 1:]
    plain = []
    in_fence = False
    for line in content:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            plain.append(line)
    prose_text = "\n".join(plain)
    ascii_words = re.findall(r"[A-Za-z]{3,}", prose_text)
    ascii_letters = sum(c.isascii() and c.isalpha() for c in prose_text)
    if len(prose_text) >= 2000 and ascii_letters >= 0.4 * len(prose_text) and len(ascii_words) >= 200:
        letter_count = sum(map(len, ascii_words)) or 1
        runon_share = sum(len(word) for word in ascii_words if len(word) > 24) / letter_count
        vowelless_share = (sum(not re.search(r"[aeiouyAEIOUY]", word) for word in ascii_words)
                           / len(ascii_words))
        if runon_share > 0.06 or (len(ascii_words) >= 300 and vowelless_share > 0.15):
            add("broken_text_layer", 0,
                f"{runon_share:.3f} of ASCII word characters are in words longer than 24 letters")

    headings = []
    heading_counts = Counter()
    previous = 0
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level, title = len(match.group(1)), match.group(2).strip().casefold()
        headings.append((i, level, title))
        heading_counts[title] += 1
        if previous and level > previous + 1:
            add("heading_jump", i, line)
        previous = level
    for title, count in heading_counts.items():
        if count >= 4 and title not in {"references", "notes"}:
            add("duplicate_heading", 0, f"{title} ({count} times)")

    short = 0
    prose = 0
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        structural = (not line.strip() or in_fence or re.match(r"^(#|>|[-*+] |\d+[.)] |\|)", line))
        if structural:
            continue
        if re.search(r"[A-Za-z]", line):
            prose += 1
            short += len(line.strip()) < 45 and not re.search(r"[.!?:;]$", line.strip())
    if prose >= 20 and short / prose > 0.22:
        add("short_prose_fragment", 0, f"{short}/{prose} prose lines are short fragments")

    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in re.finditer(r"!\[[^]]*\]\(([^)]+)\)", line):
            target = unquote(match.group(1))
            if "://" not in target and not (path.parent / target).resolve().exists():
                add("broken_image_link", i, target)

    table_rows = []
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if in_fence and table_rows:
                table_rows = []
            continue
        if in_fence:
            continue
        if line.startswith("|") and line.endswith("|"):
            table_rows.append((i, line.count("|") - 1, line))
        elif table_rows:
            expected = Counter(n for _, n, _ in table_rows).most_common(1)[0][0]
            for row_i, cells, row in table_rows:
                if cells != expected:
                    add("malformed_table", row_i, row)
            table_rows = []

    score = sum(CHECKS[k][0] * min(n, 10) for k, n in issues.items())
    return issues, {"score": score, "bytes": len(text.encode()), "lines": len(lines),
                    "headings": len(headings), "examples": examples}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    files = sorted(p for p in args.root.rglob("*.md") if ".figures" not in p.parts)
    totals = Counter()
    affected = Counter()
    records = []
    for path in files:
        issues, meta = inspect(path)
        totals.update(issues)
        affected.update(issues.keys())
        records.append({"path": path.relative_to(args.root).as_posix(), "issues": issues,
                        **meta, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    records.sort(key=lambda r: (-r["score"], r["path"].casefold()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(json.dumps({"files": len(files), "issue_totals": totals,
        "affected_files": affected, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")

    report = ["# pdf2md corpus cleanliness audit", "", f"Files inspected: **{len(files):,}**", "",
              "## Findings", "", "| Check | Affected files | Occurrences | Priority |", "|---|---:|---:|---:|"]
    for kind, count in totals.most_common():
        report.append(f"| {kind} | {affected[kind]:,} | {count:,} | {CHECKS[kind][0]} |")
    report += ["", "## Highest-scoring files for review", ""]
    for record in records[:50]:
        kinds = ", ".join(f"{k}={v}" for k, v in record["issues"].most_common()) or "none"
        report.append(f"- `{record['path']}` — score {record['score']}: {kinds}")
    report += ["", "## Recommended pdf2md improvement order", "",
               "1. Fix corruption and data-loss signals: replacement/private-use glyphs and broken figure links.",
               "2. Tighten output validity: balanced fences, consistent tables, and heading-level continuity.",
               "3. Improve furniture removal and paragraph reflow using the worst-file samples in `audit.json`.",
               "4. Turn confirmed patterns into minimal regression fixtures before changing heuristics.", "",
               "This report flags candidates. It does not treat every flag as a converter defect; source PDFs and authored Markdown vary."]
    (args.output / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"audited {len(files)} files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
