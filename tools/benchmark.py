#!/usr/bin/env python3
"""Source-grounded conversion checks; no model judges or network access.

Manifest: {"cases": [{"id": "paper", "input": "paper.pdf", "args": [],
 "checks": [{"type": "contains", "text": "exact words"},
            {"type": "order", "texts": ["first", "second"]},
            {"type": "heading", "text": "Methods", "level": 2}]}]}
Paths are relative to the manifest. Missing inputs and unannotated cases are
reported explicitly, never counted as quality passes.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def evaluate(markdown, checks):
    text = normalize(markdown)
    results = []
    for check in checks:
        kind = check.get("type")
        value = normalize(check.get("text", ""))
        if kind == "contains":
            passed = bool(value) and value in text
        elif kind == "absent":
            passed = bool(value) and value not in text
        elif kind == "count":
            passed = bool(value) and text.count(value) == check["count"]
        elif kind == "order":
            cursor, passed = 0, bool(check.get("texts"))
            for anchor in check.get("texts", []):
                anchor = normalize(anchor)
                folded = anchor.casefold()
                pos = text.casefold().find(folded, cursor) if folded else -1
                if pos < 0:
                    passed = False
                    break
                cursor = pos + len(folded)
        elif kind == "heading":
            passed = any(m.group(2).strip().casefold() == check["text"].casefold() and
                         (check.get("level") is None or len(m.group(1)) == check["level"])
                         for m in re.finditer(r"^(#{1,6})\s+(.+)$", markdown, re.M))
        elif kind == "table_row":
            passed = any([normalize(c) for c in line.strip().strip('|').split('|')] == check['cells']
                         for line in markdown.splitlines() if line.strip().startswith('|'))
        else:
            raise ValueError(f"unknown check type: {kind!r}")
        results.append({**check, "passed": passed})
    return results


def text_metrics(reference, prediction):
    """Multiset precision/recall; deliberately not described as CER or WER."""
    gold, pred = (Counter(re.findall(r"\w+", t.casefold())) for t in (reference, prediction))
    matched = sum((gold & pred).values())
    return {"token_recall": matched / sum(gold.values()) if gold else None,
            "token_precision": matched / sum(pred.values()) if pred else None}


def worker(metrics, arguments, engine="pdf2md"):
    started = time.perf_counter()
    sys.argv = [str(ROOT / 'pdf2md_all.py'), *arguments]
    try:
        if engine == "markitdown":
            from markitdown import MarkItDown
            source, destination = arguments
            result = MarkItDown(enable_plugins=False).convert_local(source)
            Path(destination).write_text(result.text_content, encoding="utf-8")
        else:
            runpy.run_path(str(ROOT / 'pdf2md_all.py'), run_name='__main__')
    finally:
        peak = None
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform != 'darwin':
                peak *= 1024
        except ImportError:
            pass
        Path(metrics).write_text(json.dumps({"elapsed_seconds": time.perf_counter()-started,
                                             "peak_rss_bytes": peak}))


def run_benchmark(manifest, output, timeout=180, engine="pdf2md", artifacts=True):
    data = json.loads(manifest.read_text())
    cases = data['cases']
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[\w-]+', i) for i in ids):
        raise ValueError('case IDs must be unique letters, digits, underscores or hyphens')
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for case in cases:
        src = (manifest.parent / case['input']).resolve()
        dest = output / case['id']
        dest.mkdir(exist_ok=True)
        md_path, perf_path = dest/'output.md', dest/'performance.json'
        args = case.get('args', [])
        if any(a.split('=')[0] in ('-o', '--output', '--artifacts', '--emit-json', '--profile', '--glyph-report') for a in args):
            raise ValueError('benchmark owns output paths; profile-only flags are not supported')
        row = {"id": case['id'], "input": str(src), "checks": []}
        if not src.is_file():
            row.update(status='missing', error='input file not found')
            report.append(row)
            continue
        converter_args = ([str(src), str(md_path)] if engine == "markitdown" else
                          [str(src), *args, '-o', str(md_path)])
        if artifacts and engine == "pdf2md":
            converter_args += ['--artifacts', str(dest/'artifacts')]
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(perf_path),
                   engine, *converter_args]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            (dest/'conversion.log').write_text(result.stdout + result.stderr)
            if perf_path.exists():
                row.update(json.loads(perf_path.read_text()))
            if result.returncode:
                row.update(status='error', error=result.stderr[-2000:])
            else:
                md = md_path.read_text()
                row['checks'] = evaluate(md, case.get('checks', []))
                row['status'] = ('unannotated' if not row['checks'] else
                                 'passed' if all(c['passed'] for c in row['checks']) else 'failed')
                row['replacement_characters'] = md.count('\ufffd')
                if case.get('reference'):
                    row.update(text_metrics((manifest.parent/case['reference']).read_text(), md))
        except subprocess.TimeoutExpired:
            row.update(status='timeout', error=f'exceeded {timeout}s')
        report.append(row)
    summary = {"schema_version": 1, "engine": engine, "manifest": str(manifest.resolve()),
               "statuses": dict(Counter(r['status'] for r in report)), "cases": report}
    (output/'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker(sys.argv[2], sys.argv[4:], sys.argv[3])
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--timeout', type=float, default=180)
    args = ap.parse_args()
    try:
        report = run_benchmark(args.manifest, args.output, args.timeout)
    except (ValueError, KeyError, OSError) as e:
        ap.error(str(e))
    print(json.dumps(report['statuses']))
    return 1 if any(k in report['statuses'] for k in ('failed', 'error', 'missing', 'timeout')) else 0


if __name__ == '__main__':
    sys.exit(main())
