#!/usr/bin/env python3
"""Compare local pdf2md and stock MarkItDown on identical PDFs and checks.

Requires optional `markitdown[pdf]`. No cloud backends or plugins are enabled.
Trials alternate engine order. Each file runs in a new Python process. Audit
artifact generation is excluded from timing. Results measure converter imports,
conversion and Markdown writing; common interpreter/harness startup is excluded; peak RSS excludes external OCR children.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics

from benchmark import run_benchmark, ROOT


def compare(manifest, output, repeats=3, timeout=300):
    if repeats < 1:
        raise ValueError('repeats must be positive')
    data = json.loads(manifest.read_text())
    for case in data['cases']:
        if case.get('args', []) not in ([], ['--no-toc']):
            raise ValueError('comparison accepts only --no-toc; use the same complete PDF for both engines')
    versions = {name: importlib.metadata.version(name) for name in ('pymupdf','markitdown','pdfminer-six')}
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for trial in range(repeats):
        engines = ['pdf2md','markitdown'] if trial % 2 == 0 else ['markitdown','pdf2md']
        for engine in engines:
            reports.append(run_benchmark(manifest, output/f'trial-{trial+1}'/engine,
                                         timeout, engine=engine, artifacts=False))
    summaries = []
    for case in data['cases']:
        row = {'id':case['id'],'engines':{}}
        for engine in ('pdf2md','markitdown'):
            runs = [r for report in reports if report['engine'] == engine
                    for r in report['cases'] if r['id'] == case['id']]
            successful = [r for r in runs if r['status'] in ('passed','failed','unannotated')]
            rss = [r['peak_rss_bytes'] for r in successful if r.get('peak_rss_bytes') is not None]
            row['engines'][engine] = {
                'completed':len(successful), 'trials':len(runs),
                'median_seconds':statistics.median(r['elapsed_seconds'] for r in successful) if successful else None,
                'median_peak_rss_bytes':statistics.median(rss) if rss else None,
                'checks_passed':sum(c['passed'] for c in successful[0]['checks']) if successful else 0,
                'checks_total':len(successful[0]['checks']) if successful else len(case.get('checks',[])),
                'statuses':[r['status'] for r in runs]}
        summaries.append(row)
    report = {'versions':versions,'python':platform.python_version(),'platform':platform.platform(),
              'converter_sha256':hashlib.sha256((ROOT/'pdf2md_all.py').read_bytes()).hexdigest(),
              'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'repeats':repeats,'cases':summaries,
              'method':'fresh processes, alternating engines, local files, no cloud, no OCR, no audit artifacts; stock MarkItDown',
              'limitation':'Source-grounded spot checks, not an exhaustive transcription accuracy benchmark.'}
    (output/'comparison.json').write_text(json.dumps(report,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--timeout',type=float,default=300)
    args=ap.parse_args()
    report=compare(args.manifest,args.output,args.repeats,args.timeout)
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
