#!/usr/bin/env python3
"""Corpus-wide cleanliness audit for Markdown emitted by pdf2md."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


CHECKS = {
    "replacement_chars": (5, "Unicode replacement characters remain"),
    "private_use_chars": (5, "Private-use glyphs remain"),
    "unclosed_fence": (4, "Code fence is not balanced"),
    "broken_image_link": (4, "A local image link is missing"),
    "heading_jump": (2, "Heading hierarchy skips a level"),
    "duplicate_heading": (2, "A heading repeats unusually often"),
    "standalone_page_number": (2, "Standalone page-number furniture remains"),
    "possible_broken_hyphen": (2, "A word appears split across Markdown lines"),
    "excess_blank_lines": (1, "Four or more consecutive blank lines"),
    "trailing_whitespace": (1, "Trailing whitespace remains"),
    "short_prose_fragment": (1, "Many short non-structural lines may be unreflowed"),
    "malformed_table": (2, "A pipe-table row has inconsistent cell counts"),
    "visual_context_unavailable": (1, "A saved figure lacks AI-generated context"),
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

    for i, line in enumerate(lines, 1):
        if "\ufffd" in line:
            add("replacement_chars", i, line)
        if any(0xE000 <= ord(c) <= 0xF8FF for c in line):
            add("private_use_chars", i, line)
        if re.fullmatch(r"\s*\d{1,4}\s*", line):
            add("standalone_page_number", i, line)
        if line.rstrip() != line:
            add("trailing_whitespace", i, line)
        if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]-$", line) and i < len(lines) and re.match(r"^[a-zà-öø-ÿ]", lines[i]):
            add("possible_broken_hyphen", i, line + " / " + lines[i])
    if re.search(r"\n[ \t]*\n(?:[ \t]*\n){2,}", text):
        add("excess_blank_lines")
    if sum(1 for line in lines if line.lstrip().startswith("```")) % 2:
        add("unclosed_fence")

    headings = []
    heading_counts = Counter()
    previous = 0
    for i, line in enumerate(lines, 1):
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

    for i, line in enumerate(lines, 1):
        for match in re.finditer(r"!\[[^]]*\]\(([^)]+)\)", line):
            target = match.group(1).replace("%20", " ")
            if "://" not in target and not (path.parent / target).resolve().exists():
                add("broken_image_link", i, target)
    if "*diagram, page " in text and "AI-generated visual context" not in text:
        add("visual_context_unavailable")

    table_rows = []
    for i, line in enumerate(lines, 1):
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
               "4. Review missing visual descriptions separately from text cleanliness; retain the source crop for verification.",
               "5. Turn confirmed patterns into minimal regression fixtures before changing heuristics.", "",
               "This report flags candidates. It does not treat every flag as a converter defect; source PDFs and authored Markdown vary."]
    (args.output / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"audited {len(files)} files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
