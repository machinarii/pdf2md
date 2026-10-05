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
python3 pdf2md_all.py in.pdf --max-file-size 500MiB   # refuse larger input before parsing
python3 pdf2md_all.py in.pdf --skip-mostly-images     # skip photobooks (60% default)
python3 pdf2md_all.py in.pdf --no-visual-ai           # never call a vision model
python3 pdf2md_all.py in.pdf --artifacts DIR          # tree, coverage, tables, provenance, repairs, blocks
python3 pdf2md_all.py scan.pdf --ocr auto --ocr-language eng --artifacts DIR
python3 pdf2md_all.py in.pdf --emit-json blocks.json  # typed blocks for RAG chunking
python3 pdf2md_all.py in.pdf --figure-dir figs        # crop figures to PNG and link them
python3 pdf2md_all.py in.pdf --figure-dir figs --figure-vlm qwen3.8:27b
python3 pdf2md_all.py in.pdf --artifacts DIR --table-vlm MODEL  # save table alternatives
python3 pdf2md_all.py in.pdf --artifacts DIR --table-vlm MODEL --table-render model
python3 pdf2md_all.py in.pdf --chunks chunks.json --chunk-tokens 800  # optional tiktoken
python3 pdf2md_all.py in.pdf --body-only              # chapters only
python3 pdf2md_all.py in.pdf --title T --author A --author B
python3 pdf2md_all.py in.pdf --no-toc
python3 pdf2md_all.py in.pdf --math-delims            # wrap math-heavy lines in $$
```

`--max-file-size` applies to every supported input format. Omit it for no size
limit. A bare integer is bytes; `KB`, `MB`, `GB`, and `TB` use decimal units,
while `KiB`, `MiB`, `GiB`, and `TiB` use binary units. A file exactly at the
configured limit is accepted.

`--skip-mostly-images [RATIO]` exits with status 3 and creates no Markdown when
the document meets the configured image-dominance threshold (default `0.6`).
For PDFs, a page is image-dominant when raster images cover at least half its
area; EPUB and DOCX use the share of meaningful content blocks that are images.
This check uses document geometry and metadata only—it does not call AI or try
to interpret the images. `--no-visual-ai` (also `--no-figure-vlm`) overrides a
supplied `--figure-vlm` and `--table-vlm` options, which is useful in shared batch
configurations. Combining it with `--table-render model` is an argument error.

Table-model and chunk-export options currently support PDF input only. See
[table preservation and page coverage](#table-preservation-and-page-coverage)
for dependencies, model limits, cache behavior, and output formats.

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
from line repair. PDF page rotations are handled in displayed page coordinates.
Separate image regions on mixed pages are OCRed, but regions overlapping native
text are skipped. Tiny images are ignored. This is not arbitrary orientation
detection, camera deskewing, or curved-page dewarping. New OCR text must also pass
a per-line confidence check and fit within the requested region.

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
- `coverage.json`: source-line dispositions and review reasons for every selected
  PDF page; blank candidates are distinct from pages with unrecovered content.
- `tables.json` and `tables/`: detected table evidence, PNG crops, native HTML, and
  optional model candidates. Keep the crops with Markdown to preserve its links.
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



## Visual context for RAG

`--figure-dir DIR` preserves detected diagram regions and separate raster images.
Full-page raster scans are excluded from raster-figure discovery because they
need OCR. Existing label-based diagram detection still handles some vector
figures. Captioned vector drawings use clipped path bounds, and nearby panels
sharing a caption are grouped into one crop. Captionless drawings, captions above
figures, and complex layouts are not fully covered.

Add `--figure-vlm MODEL` to use a vision-capable model served by Ollama at
`http://localhost:11434` by default. Select any installed vision-capable tag; there
is no fixed model allowlist or automatic model choice. Install the model and start
Ollama separately. Use `--ollama-host URL` to select another server. Figure
images and captions are sent to that endpoint only when the option is requested.
The converter asks for faithful transcription where possible; otherwise it asks
for visible chart/image context, readable labels, trends, and ambiguities. It
explicitly discourages invented values, causation, or unreadable equations.
These prompt constraints do not guarantee model accuracy.
Descriptions request prominent patterns and their visible evidence: per-metric
leaders and trade-offs, chart changes, and diagram branches or feedback loops.
Simple flowcharts are described as numbered steps in arrow order. Complex,
heavily branching flows use connected prose explaining stages, splits, merges,
and feedback. Parallel paths and alternatives must not be presented as a single
sequence; process meaning takes priority over box colors and icons.
For any diagram too complex to represent faithfully in a table, list, or other
structured format, the description uses connected sentences covering the main
components, relationships, and supported patterns. This prose fallback applies
to all diagram types; it must preserve ambiguity rather than force a false structure.
For boards and grids, they also request meaningful per-cell quantities, including
pip or marker counts, rather than tile colors alone. Marker counts are not treated
as game values without source evidence. Exact counting and inferred relationships
still require verification; radar polygon area is not an overall performance score.
Optional thinking is disabled and the output budget allows 1,600 tokens.
Responses reported as truncated are discarded in favor of the image and labels.
Some model backends still include planning text or unsupported details; a completed
response is not an accuracy check. See the [real-model evaluation](../benchmarks/visual-context.md).

```bash
python3 pdf2md_all.py paper.pdf -o paper.md --figure-dir figures \
  --figure-vlm qwen3.8:27b --artifacts artifacts/paper
```

Generated descriptions are visibly labeled in Markdown. `figures/visuals.json`
records the model, page, displayed-page region coordinates, image filename/hash,
caption, generated text, and whether the model returned a result. The same records
are included in `document.json` when artifacts are enabled. Region boxes identify
the figure; saved crops include a small surrounding margin. Each crop remains
linked even when model inference fails, with extracted labels where available.

For RAG, keep generated visual context distinct from source transcription and
carry the image/page provenance into retrieved chunks. Review exact numbers and
relationships against the image. Rendering/integration is regression-tested with
mocked vision responses; real-model description quality has not been benchmarked.


### Choosing a visual model and server

```bash
# Local model; install it on the server first with ollama pull MODEL.
python3 pdf2md_all.py paper.pdf --figure-dir figures --figure-vlm qwen3.8:27b

# Another installed local vision model, on a remote Ollama server.
python3 pdf2md_all.py paper.pdf --figure-dir figures \
  --figure-vlm qwen3-vl:30b --ollama-host http://SERVER:11434

# Cloud model through Ollama: images and captions leave your machine.
python3 pdf2md_all.py paper.pdf --figure-dir figures --figure-vlm glm-5.3-flash:cloud

# Preserve images without model requests.
python3 pdf2md_all.py paper.pdf --figure-dir figures
```

`--ollama-host` defaults to `http://localhost:11434` and only affects requested
visual descriptions. Use the exact model tag installed on that server (`ollama
list` on the server). Model downloads are not automatic. A `:cloud` model may
forward crops and captions to its provider even when Ollama itself runs locally.

Our four-figure diagnostic favored GLM-5.3-Flash for overall explanations and
Qwen3.8:27b for local descriptions and complete tables. GLM-OCR was fastest for
transcription. Qwen3-VL 8B/30B were faster than Qwen3.8 in these runs but omitted
more values and made serious chart-interpretation errors. All require review;
see [methods, results and confidence limits](../benchmarks/visual-context.md).

The current audit fields indicate generation state, not measured accuracy.
There is no automatic confidence threshold or model-selection benchmark built
into the CLI. Contradiction, coverage and cross-view checks are proposed in the
evaluation document; they are not yet implemented.


### Report layouts and book running headers

The PDF pipeline uses per-page dimensions for header/footer detection, including
books with a small cover and larger interior pages. A section/chapter label paired
with a page number on the same header baseline provides additional evidence for
removing a running header. Small margin terms are suppressed only when the same
phrase appears in nearby body text; unique sidebar content is retained.

For ruled reports, isolated figure/table numbers above a horizontal rule and a
source line below provide region boundaries. Tables within these bounds use PDF
cell geometry; charts remain figures rather than becoming false tables. Prose
columns around these regions are ordered separately. Use `--figure-dir figures`
to save and link chart crops. Extracted figure labels appear in a collapsible list,
explicitly labeled as transcription rather than chart interpretation.

This additional detector is conservative: it requires the caption/rule/source
pattern and currently skips rotated pages. It does not solve arbitrary report
layouts or every sidebar. Verify important tables and chart relationships against
the source.

## Table preservation and page coverage

For PDFs, `--artifacts DIR` now also writes:

- `coverage.json`: every selected page, original native source lines, classification
  dispositions, image regions, OCR decisions, and concrete review reasons.
- `tables.json`: detected table cells, headers, context, source IDs, pages, available
  cell bounds and spans, and continuation evidence.
- `tables/table-N.png` and `.html`: a source crop and native table representation.
  Markdown links to the source crop; retain this directory when moving the output.

Blank candidates are distinguished from image/vector pages without recovered text.
Coverage is source-line accounting, **not a calibrated accuracy score or a complete
mapping of emitted Markdown**. It cannot detect every misread word or omitted visual.
A textless conversion still exits with an error, but writes coverage first when
artifacts are requested. Suppressed roles remain inspectable rather than being
assumed correct.

Detected tables are matched against native cell geometry. Known merged cells are
expanded in Markdown; a supported two-row grouped header becomes explicit column
labels. HTML retains known spans. Unknown spans remain unknown in JSON. Adjacent
pages join only with matching numbered continuation captions, matching headers,
and aligned bounds. Uncertain cases remain separate. General detection of every
complex table, arbitrary header depth, and continuations without repeated headers
is not implemented.

### Optional table vision

```bash
python3 pdf2md_all.py report.pdf -o report.md --artifacts artifacts/report \
  --table-vlm qwen3-vl:30b --ollama-host http://localhost:11434
```

This saves model alternatives in `tables.json` while keeping native Markdown.
To explicitly render model candidates, add `--table-render model`. These tables
are labeled AI-extracted; native cells and grids remain in the audit. Unreadable
model cells become `[unreadable]`. Failed or malformed responses retain native
output. Model tables are not automatically joined across pages.

`--table-max-calls 8` limits attempts per document (default eight, no retries,
180-second generation timeout per attempt). `--no-visual-ai` disables table and
figure calls. The table option operates on already detected tables; it does not
add image-only table detection. Cloud model tags may send crops to a provider.

Checks reject invalid row shapes and truncated responses. Numeric-token agreement
and native/model shape agreement are recorded, but neither establishes correctness
or header/value association. Successful alternatives are cached by crop, prompt,
settings, endpoint, model tag, and the digest reported by Ollama; unresolved
revisions disable reuse. A provider can change a cloud model without changing a
local tag digest, so cloud reproducibility is not guaranteed. To force a new run,
use a fresh artifacts directory.

### Optional Markdown chunks

Well-formed Markdown is already useful RAG input. Use this export only if your
consumer needs help keeping tables intact:

```bash
pip install tiktoken
python3 pdf2md_all.py report.pdf -o report.md --artifacts artifacts/report \
  --chunks report.chunks.json --chunk-tokens 800 --chunk-tokenizer cl100k_base
```

The JSON records the tokenizer and actual token counts. It keeps ordinary blocks
intact and splits oversized tables by rows, repeating headers, nearby captured
captions/notes, and section context. Oversized individual rows, paragraphs, or code
blocks are preserved and flagged, not truncated. Front-matter metadata is excluded.
Image links remain relative to the Markdown output location.

Table chunks carry table-level pages and source IDs, not exact per-row attribution.
Prose chunks have document-level attribution; their page/source-ID lists are empty.
This exporter does not build an index or establish retrieval gains. It currently
supports PDF conversions only; EPUB/DOCX users can ingest their Markdown directly.
