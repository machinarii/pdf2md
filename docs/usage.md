[← README](../README.md)

# Usage guide

## CLI reference

```
python3 pdf2md_all.py --version                       # installed converter version
python3 pdf2md_all.py in.pdf                          # -> in.md, type auto-detected
python3 pdf2md_all.py book.epub                       # EPUB 2 or 3
python3 pdf2md_all.py spec.docx                       # Word
python3 pdf2md_all.py old.doc --soffice /opt/libreoffice/program/soffice   # DOC / ODT / RTF via LibreOffice
python3 pdf2md_all.py in.pdf -o out.md
python3 pdf2md_all.py in.pdf --profile                # type + evidence, detection report, census
python3 pdf2md_all.py in.pdf --doc-type deck          # override the classifier
python3 pdf2md_all.py in.pdf --glyph-report           # unmapped non-ASCII with context
python3 pdf2md_all.py in.pdf --pages 44-120           # subset (1-based, inclusive)
python3 pdf2md_all.py in.pdf --artifacts DIR          # tree, provenance, repairs, profile, blocks, pages
python3 pdf2md_all.py scan.pdf --ocr auto --ocr-language eng --artifacts DIR
python3 pdf2md_all.py in.pdf --emit-json blocks.json  # typed blocks for RAG chunking
python3 pdf2md_all.py in.pdf --figure-dir figs        # crop figures to PNG and link them
python3 pdf2md_all.py in.pdf --figure-dir figs --figure-vlm qwen2.5vl:7b
python3 pdf2md_all.py in.pdf --body-only              # chapters only
python3 pdf2md_all.py in.pdf --title T --author A --author B
python3 pdf2md_all.py in.pdf --no-toc
python3 pdf2md_all.py in.pdf --math-delims            # wrap math-heavy lines in $$
```

The filename convention `<author>#<title>[#index].pdf` is recognised for metadata. `--artifacts` writes what every stage decided — `blocks.jsonl` has every line with kind, regime, level, geometry and text — which is how to debug: read the decision log, don't add prints.

---

## Structure, selective OCR, and quality evaluation

The PDF renderer now consumes an explicit document tree: sections have parents,
body lines form paragraph blocks (including continuations across pages), and
nested list items have parent relationships. Source records retain page numbers,
bounding boxes and original extracted text through heading and caption merges.
The tree uses the existing classifiers; it is not a trained layout model and can
still inherit their mistakes.

```bash
# Lightweight text-layer conversion, with inspectable structure and provenance
python3 pdf2md_all.py book.pdf -o book.md --artifacts artifacts/book

# Local OCR only for empty image pages and visibly damaged text lines
python3 pdf2md_all.py scan.pdf -o scan.md --ocr auto --ocr-language eng \
  --artifacts artifacts/scan

# Source-grounded quality and performance checks
python3 tools/benchmark.py manifest.json --output artifacts/benchmark

# Optional comparison dependency; not required for normal conversion
pip install 'markitdown[pdf]'
python3 tools/compare_converters.py manifest.json \
  --output artifacts/comparison --repeats 3
```

`--ocr auto` requires the Tesseract executable and installed language data. It
runs locally, with a per-region timeout and a raster pixel budget. Healthy text
is not sent through OCR. Lines containing replacement/private-use characters are
recognized from cropped images; empty image pages are recognized as whole pages.
Known Symbol-font bullets are decoded directly; isolated unknown symbols are
skipped rather than guessed as letters. Code and math-heavy lines are excluded
from line repair. Rotated pages are
explicitly recorded as skipped. Mixed pages with healthy text plus an image
containing additional text are not automatically OCRed by this first router.

Repairs must pass a confidence threshold and checks for intact token order,
counts, numerical values and plausible length. Rejected candidates leave the
original text unchanged. Newly recognized scans have no trustworthy original
text for comparison, so accepted results still need visual review. These gates
are conservative heuristics, not guarantees of faithful transcription. There
is no generative spell-check, translation, or modernization of historical text.
Choose language packs explicitly, for example `--ocr-language eng+deu`.
With OCR disabled, the existing cleanup maps leading private-use glyphs to bullets
and removes other private-use glyphs. OCR mode preserves unknown private-use text
for repair or review instead. Source records retain the original extracted text.

OCR requires `--artifacts` so that the audit cannot be silently lost. Alongside
the existing profile and block exports, artifacts now include:

- `document.json`: section/paragraph/list tree, original text locations, source
  and converter SHA-256 hashes, output hash, command arguments, extraction-text
  transformations and elapsed time. It does not map every Markdown byte or log
  every renderer formatting operation.
- `repairs.json`: original and candidate text, crop location, backend, language,
  confidence, and accepted/rejected/skipped decision. Written even if OCR does
  not recover enough text for conversion.
- `blocks.jsonl`: classified lines with original source records, including
  furniture that does not appear in Markdown.

Original PDFs are never changed. The source path and hash permit verification;
these artifacts are not a self-contained archival package or RO-Crate export.

The benchmark manifest and supported assertions are documented in
[benchmarks/README.md](../benchmarks/README.md). MarkItDown comparison uses its stock
local PDF converter, disables plugins, and uses no cloud services. Both engines
process identical complete PDFs in fresh processes, alternating engine order.
Audit writing and OCR are excluded from that comparison. Timing includes
converter imports, conversion and output writing; common interpreter/harness
startup is excluded. Peak RSS includes the worker process, not OCR subprocesses.

These implementations borrow practical ideas from
[Detect-Order-Construct](https://arxiv.org/abs/2401.11874),
[MinerU2.5](https://arxiv.org/abs/2509.22186),
[ParseFixer](https://arxiv.org/abs/2606.11977),
[OmniDocBench](https://arxiv.org/abs/2412.07626),
[olmOCR 2](https://arxiv.org/abs/2510.19817), and
[No Free Lunches](https://arxiv.org/abs/2502.01205).
They do not reproduce those models, train on DocLayNet, perform learned page
dewarping, or implement the official benchmark scoring protocols. The default
installation remains PyMuPDF-only. Local learning still means adapting to the
current document; cross-document model training is not performed.


