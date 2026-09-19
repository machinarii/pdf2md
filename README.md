<p align="center">
  <img src="docs/assets/banner.svg" alt="pdf2md — From printed pages to readable Markdown" width="100%">
</p>

<h1 align="center">pdf2md</h1>
<p align="center"><strong>Keep the words. Recover the structure.</strong></p>
<p align="center">Turn books, research papers, and everyday documents into readable, inspectable Markdown.</p>

<p align="center">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-0.1.0-10b981" alt="Version 0.1.0"></a>
  <a href="https://github.com/machinarii/pdf2md/actions/workflows/ci.yml"><img src="https://github.com/machinarii/pdf2md/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.10 or newer"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#see-the-output">See the output</a> ·
  <a href="#cleaner-input-for-graphrag">GraphRAG</a> ·
  <a href="#performance">Performance</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

pdf2md turns PDF, EPUB, and DOCX files into Markdown using typography and page
layout to recover structure. It runs locally with PyMuPDF; no API key is needed.

| Feature | Benefit |
|---|---|
| 📖 **Readable text** | Reflow paragraphs and rejoin words split across printed lines. |
| 🧭 **Adaptive layout** | Infer headings and column reading order for books, papers, and reports. |
| 🔍 **Source traceability** | Inspect classified text, page locations, and optional OCR repair decisions. |
| 🕸️ **GraphRAG preparation** | Give downstream chunking and relationship extraction more coherent source text. |

## Quick start

Requires **Python 3.10+**. Clone the repository and install its dependency:

```bash
git clone https://github.com/machinarii/pdf2md.git
cd pdf2md
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 pdf2md_all.py book.pdf -o book.md
```

On Windows, activate with `.venv\Scripts\activate` instead.

```bash
python3 pdf2md_all.py paper.pdf --no-toc -o paper.md
python3 pdf2md_all.py book.epub -o book.md
python3 pdf2md_all.py document.docx -o document.md
python3 pdf2md_all.py --version  # pdf2md 0.1.0
```

Output includes inferred headings, reflowed text, YAML metadata, and a table of
contents unless disabled. DOC, ODT, and RTF input additionally requires LibreOffice.
Run `python3 pdf2md_all.py --help` for all options.

## See the output

An excerpt from our original book fixture, converted by both tools without
postprocessing. pdf2md rejoins wrapped words and preserves paragraph continuity.

<table>
<tr><th>MarkItDown 0.1.7</th><th>pdf2md 0.1.0</th></tr>
<tr><td valign="top"><code>The archive connects readers with an inter-<br>
national community. Each record includes infor-<br>
mation about the source and its publication.<br>
The team records each decision through careful docu-<br>
mentation helps later readers verify the result.</code></td>
<td valign="top"><code>The archive connects readers with an international community. Each record includes information about the source and its publication. The team records each decision through careful documentation helps later readers verify the result.</code></td></tr>
</table>

[See the full comparison gallery](docs/output-gallery.md) for column order,
chapter headings, repeated headers, and compound hyphens, with source previews
and unedited outputs. These synthetic examples illustrate specific behaviors;
they are not an overall accuracy score.

## OCR and inspection

For scans or damaged text, install Tesseract and the required language data, then:

```bash
python3 pdf2md_all.py scan.pdf -o scan.md --ocr auto --ocr-language eng \
  --artifacts artifacts/scan
```

OCR is optional and off by default. It targets empty image pages and damaged
text lines, records repair decisions, and leaves rejected candidates unchanged.
`--artifacts` also works without OCR to export the document tree and source evidence.
See [usage, OCR limits, and artifact details](docs/usage.md).

## Cleaner input for GraphRAG

Correct reading order keeps unrelated topics apart. Intact words and paragraphs
give entity extraction coherent evidence; headings can guide a structure-aware
chunker. Removing repeated page furniture may reduce unnecessary indexing tokens.

These are expected benefits, not measured GraphRAG improvements. pdf2md prepares
text; your ingestion pipeline must map its structure and provenance into the graph.
See the [GraphRAG integration guide](docs/graphrag.md) for workflow and evaluation.

## Performance

An earlier development comparison used **eight readable PDFs, 635 pages**, and
three trials per converter:

| Metric | pdf2md | MarkItDown 0.1.7 |
|---|---:|---:|
| Sum of per-file median conversion times | 5.41 s | 38.31 s |
| Selected source-grounded checks | 42/42 | 20/42 |

That is about **7.1× faster conversion on this sample**. The sample informed fixes
and predates later changes; it is not a held-out benchmark, a comprehensive
formatting audit, or a GraphRAG speed measurement.
[Methodology and limitations](benchmarks/comparison-2026-09-19.md) ·
[Run your own comparison](benchmarks/README.md)

## Known gaps

- Complex columns, tables, heading styles, and footnotes can still be misclassified.
- Equations are not reconstructed into faithful LaTeX; language heuristics mainly target English and Latin scripts.
- OCR can misread text. Rotated pages and extra image text on otherwise healthy text pages are not automatically OCRed; physical-book dewarping is not implemented.
- Layout learning applies within a document; there is no cross-document training.

Inspect important outputs against their source. See [architecture and limitations](docs/architecture.md).

## Documentation and contributing

- [Usage and CLI reference](docs/usage.md)
- [Full output gallery](docs/output-gallery.md) and [reproduction scripts](examples/comparison/README.md)
- [GraphRAG guide](docs/graphrag.md)
- [Architecture](docs/architecture.md), [benchmarks](benchmarks/README.md), and [changelog](CHANGELOG.md)

Bug reports and source-backed improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
for setup and checks. CI tests Python 3.10–3.13, including optional OCR integration.

Licensed under the [MIT License](LICENSE).
