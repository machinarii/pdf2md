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
  <a href="#measured-comparison-and-limits">Measurements</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

| | Feature | What you get |
|---|---|---|
| 📖 | **Readable text** | Reflow printed lines into paragraphs and rejoin wrapped words. |
| 🧭 | **Adaptive structure** | Infer headings and reading order from typography and page geometry, including unfamiliar layouts. |
| 🗂️ | **More than PDF** | Read EPUB and DOCX directly; DOC, ODT, and RTF through LibreOffice. |
| 🔍 | **Inspectable conversion** | Trace classified text to source pages and bounding boxes through optional audit artifacts. |
| 🖥️ | **Local by default** | Convert text layers with PyMuPDF; no cloud account or API key required. |
| 🧪 | **Optional selective OCR** | Use local Tesseract for empty image pages and damaged text, with logged repair decisions. |

The default install needs only PyMuPDF. pdf2md learns layout patterns within each
file; it does not train or remember a model across your library. Complex layouts,
formulas, and damaged text still need review. See [known gaps](#known-gaps).

```bash
pip install -r requirements.txt
python3 pdf2md_all.py book.pdf -o book.md
python3 pdf2md_all.py --version  # pdf2md 0.1.0
```

## See the output

Same original two-column PDF, two unedited converter outputs. This small synthetic
example demonstrates paragraph reflow and reading order, not general accuracy.
Both tools use their local defaults; pdf2md only adds `--no-toc`.

<details>
<summary>View the source page</summary>

![Original two-column demo page](examples/comparison/source.png)

</details>

<table>
<tr><th>MarkItDown 0.1.7</th><th>pdf2md 0.1.0</th></tr>
<tr><td valign="top"><code>1 Introduction<br>
<br>
2 Preservation<br>
<br>
A useful archive preserves the structure<br>
of a document as well as its words. Short<br>
lines on a printed page should become<br>
one readable paragraph in Markdown.<br>
<br>
Clear text is easier to search and review.<br>
Keep the source file so each conversion<br>
can be checked against the printed page.<br>
Record the tool version with the output.<br>
<br>
Research papers often place two columns<br>
on the same page. Reading order matters:<br>
finish the left column before continuing<br>
with the text at the top of the right.</code></td>
<td valign="top"><code>1 Introduction<br>
<br>
A useful archive preserves the structure of a document as well as its words. Short lines on a printed page should become one readable paragraph in Markdown.<br>
<br>
Research papers often place two columns on the same page. Reading order matters: finish the left column before continuing with the text at the top of the right.</code></td></tr>
</table>

Here, MarkItDown places the right-column heading before the left-column text,
and alternates paragraphs between columns. pdf2md keeps the left column together
and joins its printed lines into paragraphs. **Both miss the two section heading
tags in this demo**; pdf2md does recover the document title as an H1. These are
literal excerpts; the full outputs below retain all content from the example.

[Full pdf2md output](examples/comparison/pdf2md.md) ·
[Full MarkItDown output](examples/comparison/markitdown.md) ·
[Source generator and reproduction](examples/comparison/README.md)

### More cleanup examples

Three more contrasts from the same original three-page book fixture. These are
selected demonstrations, not a representative failure rate. Both converters use
the same settings as above; excerpts are copied from the complete outputs.

<details open>
<summary><strong>Broken words: inter- / national, infor- / mation, docu- / mentation</strong></summary>

<table>
<tr><th>MarkItDown 0.1.7</th><th>pdf2md 0.1.0</th></tr>
<tr><td valign="top"><code>The archive connects readers with an inter-<br>
national community. Each record includes infor-<br>
mation about the source and its publication.<br>
The team records each decision through careful docu-<br>
mentation helps later readers verify the result.</code></td>
<td valign="top"><code>The archive connects readers with an international community. Each record includes information about the source and its publication. The team records each decision through careful documentation helps later readers verify the result.</code></td></tr>
</table>

pdf2md rejoins the split words and reconstructs the paragraph.

</details>

<details>
<summary><strong>Keep real hyphens: self-supervised stays self-supervised</strong></summary>

<table>
<tr><th>MarkItDown 0.1.7</th><th>pdf2md 0.1.0</th></tr>
<tr><td valign="top"><code>A self-supervised method can identify patterns.<br>
Readers can inspect the training data. This self-<br>
supervised example also shows why every printed<br>
hyphen should not be removed in the same way.</code></td>
<td valign="top"><code>A self-supervised method can identify patterns. Readers can inspect the training data. This self-supervised example also shows why every printed hyphen should not be removed in the same way.</code></td></tr>
</table>

pdf2md uses the spelling elsewhere in the document to preserve the compound's
hyphen while removing its line break.

</details>

<details>
<summary><strong>Page boundaries: remove running headers and page numbers; restore heading tags</strong></summary>

<table>
<tr><th>MarkItDown 0.1.7</th><th>pdf2md 0.1.0</th></tr>
<tr><td valign="top"><code>Page furniture belongs outside the body text.<br>
A repeated running header provides navigation on<br>
paper, but becomes distracting inside an archive.<br>
Page numbers should not interrupt a paragraph.<br>
<br>
1<br>
<br>
␌FIELD NOTES ON DOCUMENT ARCHIVES<br>
<br>
Chapter 2: Checking</code></td>
<td valign="top"><code>Page furniture belongs outside the body text. A repeated running header provides navigation on paper, but becomes distracting inside an archive. Page numbers should not interrupt a paragraph.<br>
<br>
# Chapter 2: Checking</code></td></tr>
</table>

MarkItDown retains the page number and repeated running header between chapters.
pdf2md removes them and emits `# Chapter 2: Checking`. The visible `␌` represents
MarkItDown's form-feed character; that is the only display substitution here.

</details>

[Book source preview](examples/comparison/book/source.png) ·
[Complete pdf2md output](examples/comparison/book/pdf2md.md) ·
[Complete MarkItDown output](examples/comparison/book/markitdown.md) ·
[Reproduce these examples](examples/comparison/README.md#book-cleanup-gallery)

The full pdf2md output also shows a limitation: without a cover, its document title
falls back to the filename (`source`), despite the PDF metadata. The chapter
headings are recovered. No title override or output editing was used.

For a broader view, the earlier eight-file development comparison measured about
7.1× faster conversion and 42/42 selected checks versus 20/42. These are
sample-specific results from before the later library-sweep integration, not a
complete Markdown formatting score. [Read the methodology and limits](benchmarks/comparison-2026-09-19.md).

---

## Cleaner PDF Markdown

Conversion automatically adapts to each PDF's text and layout:

- Page-local column detection keeps research-paper paragraphs in reading order,
  including short papers, spanning headings and changes in page width or layout.
- Repeated short, isolated text in a distinct font style can establish headings,
  including body-sized italic headings in unfamiliar document formats.
- Ordinary single-font ebooks retain their authored typography instead of being
  treated as synthetic OCR layers.
- Running headers require repetition on distinct pages, reducing accidental
  removal of repeated content on a single page.
- Paragraph reflow joins line-wrapped words, including accented words, and uses
  compounds found elsewhere in the document to preserve spellings such as
  `self-supervised`.

```bash
python3 pdf2md_all.py ebook.pdf -o ebook.md
python3 pdf2md_all.py paper.pdf -o paper.md --doc-type paper --no-toc
python3 pdf2md_all.py unfamiliar.pdf -o unfamiliar.md --artifacts artifacts
```

Learning is local to the current conversion; it does not train a model or retain
information between files. `--profile` reports learned heading styles, and
`--artifacts` includes the supporting evidence and detected columns per page.
These heuristics cannot reconstruct missing OCR text or guarantee exact formula
transcription from a PDF text layer.

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
[benchmarks/README.md](benchmarks/README.md). MarkItDown comparison uses its stock
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


## Measured comparison and limits

A September 19, 2026 development comparison, before integration of the separate
library-sweep changes, used eight readable PDFs (635 pages)
from a seeded sample of a local library, with three trials per converter. Both
converters rejected one additional empty file.

| Metric | pdf2md | MarkItDown 0.1.7 |
|---|---:|---:|
| Selected source-grounded checks | 42/42 | 20/42 |
| Sum of per-file median conversion times | 5.41 s | 38.31 s |
| Median across per-file median peak RSS | 69.1 MiB | 124.7 MiB |

pdf2md was about 7.1× faster on this sample. These results are development
measurements, not an independent benchmark: the sample helped identify and fix
converter defects. The checks cover selected text, reading order, heading tags
and some heading levels, and replacement characters. **They do not establish
that every Markdown file is clean or correctly formatted throughout.** Paragraph
spacing, nested lists, tables, code fences, footnotes, duplicate headers, and
rendered readability were not systematically audited across all outputs.

See [comparison methodology and results](benchmarks/comparison-2026-09-19.md)
for the sampling, environment, timing boundaries, and remaining evaluation work.
Private source files and generated outputs are not distributed in this repository.

## Quick start

```
pip install -r requirements.txt        # pymupdf; Python 3.10+
python3 pdf2md_all.py book.pdf         # -> book.md
python3 pdf2md_all.py book.epub -o out.md
python3 pdf2md_all.py book.pdf --profile   # show what the classifier decided
```

DOC / ODT / RTF input additionally needs LibreOffice (`soffice`) on `PATH` or passed with `--soffice`.

---

## Contents

- [See the output](#see-the-output)
- [Cleaner PDF Markdown](#cleaner-pdf-markdown)
- [Structure, selective OCR, and quality evaluation](#structure-selective-ocr-and-quality-evaluation)
- [Measured comparison and limits](#measured-comparison-and-limits)
- [Quick start](#quick-start)
- [Why this exists](#why-this-exists)
- [Architecture](#architecture)
- [Document type identification](#document-type-identification)
- [The outline tree](#the-outline-tree)
- [Content types handled](#content-types-handled)
- [Genre-specific paths](#genre-specific-paths)
- [EPUB, DOCX and DOC input](#epub-docx-and-doc-input)
- [Output format](#output-format)
- [CLI reference](#cli-reference)
- [Findings](#findings)
- [Audit and fixes](#audit-and-fixes)
- [Design principles](#design-principles)
- [Robustness sweep](#robustness-sweep)
- [Real-library sweep](#real-library-sweep)
- [Whole-library run](#whole-library-run)
- [EPUB sweep](#epub-sweep)
- [arXiv sweep](#arxiv-sweep)
- [Testing](#testing)
- [Known gaps](#known-gaps)
- [Files](#files)
- [License](#license)

---

## Why this exists

The predecessor (`txt-cleaner.py`, and its TypeScript port `book-cleaner-cli-ollama`) operated on **already-extracted plain text**. That is the wrong input. Once a PDF has been flattened to a string, the font size, weight, and x/y position that identified an H2 are gone forever, and every subsequent decision is a regex guessing at what the layout used to be. That design could not:

- distinguish a heading from a bold figure caption, or a page number from a table cell
- detect running heads shorter than 25 characters (a `len(text) < 25` guard skipped every `Chapter 1: Introduction`)
- produce any heading hierarchy at all — the output was cleaned prose named `.md`
- tell a table cell from a one-word paragraph, or a two-column paper's left column from its right
- avoid Markdown injection (a body line starting with `#` became an H1)

pdf2md reads the PDF directly with PyMuPDF, so every line carries `(font, size, bold, italic, mono, bbox, direction, math-ratio)`. Structure is decided by evidence, evaluated **globally across the whole document**, within the **genre** the document was identified as, and against a **tree** the headings must fit.

---

## Architecture

```
Stage 0  IDENTIFY   book / paper / deck / document, from four independent
                    signal families, with recorded evidence  (doctype.py)

Stage 1  EXTRACT    span-level lines with full typographic metadata;
                    font-class-aware glyph repair; rotated text kept aside;
                    page-local column reading order; optional audited selective OCR

Stage 2  PROFILE    global passes over the whole document:
                      body style    = modal (font, size) by character count
                      margin bands  = fixed fractions; repetition discriminates
                      running heads = digit-normalised text repeated in a band
                      heading styles= bold/large styles filtered by family share,
                                      frequency, caption shape, text shape
                      OCR layer?    = one synthetic font -> relative size tiers

Stage 3  CLASSIFY   furniture | heading | caption | code | body | footnote
                    then, by genre: tables -> figure regions -> panel labels ->
                    [book: density demotion, index regime] ->
                    caption wraps -> regimes (front matter, references, glossary,
                    notes, index) -> acronym learning -> de-shouting ->
                    [book: front-matter labelling, copyright tightening] ->
                    footnote anchors

Stage 4  ASSEMBLE   merge split / wrapped headings -> OUTLINE TREE (levels,
                    run-ins, cross-refs, TOC membership from numbering
                    consistency) -> reflow paragraphs across pages and columns
                    -> section/paragraph/list document tree -> render each kind
                    -> head (YAML, title block, grouped TOC)
```

The project originated as a modular development build. **This repository ships the single-file build**, `pdf2md_all.py`, which contains the PDF pipeline and inlined structured-format reader. Section banners mark where each module begins; the design notes in each module docstring are kept. `python3 pdf2md_all.py in.pdf` is the whole tool. `structured.py` is also kept here as a standalone module for importing the EPUB / DOCX readers on their own.

The modular development build is kept outside this repository. Its shape, which is also the map of the section banners inside the single file:

| Module | Lines | Role |
|---|---|---|
| `pdf2md.py` | 2,156 | extraction, profiling, classification, tables, figures, assembly, CLI |
| `regimes.py` | 490 | content-type engine: regime state machine, lists, footnotes, references, glossary, de-shouting, front matter, copyright |
| `outline.py` | 201 | heading tree: tokenise → validate numbering → level, kind, TOC membership |
| `doctype.py` | 203 | document-type classifier with evidence |
| `papers.py` | 284 | paper signals, page-local column detection, title block, heading promotion |
| `decks.py` | 87 | slide rendering |
| `documents.py` | 66 | PRD / spec / memo title block and metadata fields |
| `structured.py` | 801 | EPUB / DOCX readers, CSS style ranking, LibreOffice conversion |
| `build_single.py` | 85 | merges the modules into `pdf2md_all.py` |
| `test_books.py` | ~245 | regression suite (eleven tests, ~100 invariants, 16–21 documents) |

Requires `pymupdf`, Python 3.10+.

---

## Document type identification

Every later stage assumes a genre: front-matter labelling assumes a book, column reordering assumes a paper, per-slide rendering assumes a deck. A wrong genre cascades into confident nonsense — a PRD's author table becomes "Publication details", a deck's slide titles become an index. So the type is decided **once, first**, by scoring four independent signal families, and the evidence is recorded. `--profile` prints it; `stats.json` keeps it; `--doc-type` overrides it.

| Family | Signals | Points to |
|---|---|---|
| **Geometry** | exact screen dimensions (960×540, 720×540, 1024×768, 720×405, 1920×1080); landscape ratio 16:9 / 4:3 / 16:10; page count (≤3 → document; ≤25 → document, paper, deck; >60 → book) | deck, book, document |
| **Metadata** | producer / creator: PowerPoint, Keynote, Skia, Impress, beamer → deck; Word, Writer, Docs → document; InDesign, Quark → book; TeX → paper or book | any |
| **Density** | words per page (<100 deck; <250 document; more → paper, book); bullet share >25%; a *display-sized* title at the same position on ≥60% of pages | deck, document |
| **Markers** | `Abstract` on page 1, arXiv id, keywords / related work, two-column pages → paper; ISBN / © / edition, `Chapter N` headings, dot-leader contents, cover page → book; `Agenda`, `Thank you`, `Confidential`, `N / M` → deck; `Product Requirements`, `Revision History`, `Status: Draft`, `Version`, `Author:`, `Reviewers:`, `To: / From:` → document | any |

No family can decide alone. The generated deck and PRD carry the same generic `LibreOffice` producer and are still classified at 89% and 100% from geometry, density and markers; a book with a cover, chapters and an ISBN scores those three independently.

| Fixture | Result | Winner / runner-up |
|---|---|---|
| Sutton & Barto | book | 15 / 4 |
| Design Leadership | book | 11 / 2 |
| Cognitive Structure | book | 13 / 1 |
| Ammar 2018 | paper | 10 / 2 |
| Futoma 2017 | paper | 12 / 2 |
| Wang 2008 | paper | 7 / 1 |
| Growth-review deck | deck | 17 / 2 |
| Spam-detection PRD | document | 10 / 0 |

The suite asserts every type and requires the winner to beat the runner-up by at least 3.

---

## The outline tree

Headings are not classified one at a time. They are tokenised into `(label, number, title)` and walked as a tree whose numbering must be internally consistent — and that consistency is the evidence:

- **Spine.** A number must extend the open path and advance: after `6.2` comes `6.3` (sibling), `6.2.1` (child), or `7` (new chapter). A number that runs backwards — `5.7` appearing after `5.10 Summary` — is a cross-reference label, not a heading, and is returned to body text. Chapter counters (integers) and appendix counters (letters) are separate sequences.
- **Labelled series.** Any word followed by a counter that advances in parallel with the spine and restarts per chapter — `Example 6.1, 6.2, 6.3`; `Figure 6.1, 6.2`; `Characterization 5.1, 5.2`. The word is never looked up; the counter's behaviour identifies it. Members are run-in lead-ins (`**Example 6.2 Random Walk**`), never sections, never in the contents. A "series" of one is just an unnumbered heading.
- **Unnumbered headings** take the depth of the open spine node plus one, and are in the contents only when the document does not number that depth. In the RL book, `Bibliographical and Historical Remarks` sits among `6.1 … 6.9` and is body structure, not skeleton; in the OCR'd trade books nothing is numbered below chapter, so their unnumbered sections *are* the skeleton. If an unnumbered heading's typographic style ranks below every numbered section's, it is a run-in, not a heading.
- **Rendered level** comes from tree depth, not from counting dots.

Per document the tree reports what it found: RL `section 183, labelled 11, unnumbered 31, runin 12, depths [1,2,3]`; Design Leadership `section 8, unnumbered 44, depths [1]`; the ACL paper `section 12, depths [1,2]`. The RL contents went from 231 entries across six depths to 177 across three.

Tokenising is where regex still lives, and where its bugs live: `A simple bandit algorithm` once tokenised as appendix `A`, a string entered the chapter counter, and 161 sections went off-sequence. A bare capital letter is a number only under an explicit `Appendix` or with a dotted child (`A.1`).

---

## Content types handled

A book is a sequence of *regimes* — front matter, body, back matter — each with its own block vocabulary. The same physical shape (a short isolated line) is a heading in the body, an entry in an index, a term in a glossary, an author on a title page. Regime is decided by level-1 headings and page signatures; block type is decided within the regime.

| Type | Detected by | Rendered as |
|---|---|---|
| **Title / cover page** | ≤14 short lines, ≥2 display-sized, no prose (shape, not size: LaTeX titles are 1.4× body, trade covers 5×) | canonical `# Title` + subtitle + `**authors**` + imprint line, once |
| **Praise page** | "Praise for…" opener | `> quote` / `> — attribution` |
| **Copyright page** | ≥3 of ©, ISBN, LCCN, "rights reserved", "published by" | `## Publication details` — keeps ©, ISBN, DOI, edition/printing history, publisher; drops addresses, CIP dumps, legal text |
| **Dedication** | <220 chars, ≤5 lines, "To…" / "In memory of…" | `> *text*` |
| **Jacket copy / author bios** | front pages before Contents; `NAME is Professor…` shape | `## About this book` / `## About the authors` |
| **Contents page** | dot-leader density (ratio ≥0.25 or ≥6 leader lines) or a `Contents` heading regime for leaderless layouts | consumed; replaced by the generated TOC; entries harvested as heading-level truth |
| **List of Figures / Tables** | `Figures` / `Tables` heading regime | `## List of Figures` with `- ` entries |
| **Preface, Foreword, Notation, Abstract** | keyword headings | `#` sections, grouped under **Front matter** |
| **Part / Chapter** | style ranking + `Chapter N` pattern; wrapped titles merged on the page and across a page break | `#` |
| **Section / subsection** | style ranking validated by text shape and isolation; a title beside an accepted section number gets a lenient gate (`TD(λ)`); level from the outline tree | `##` / `###` |
| **Run-in heading** | labelled series in the tree; or unnumbered with a style below the section floor | `**bold**` lead-in, never in the TOC |
| **Body** | default | paragraphs reflowed across pages and columns, de-hyphenated |
| **Lists** | bullet glyph; or `-` / `*` **with a sibling within two lines** (OCR renders quote em-dashes as `-`) | `- item`, wrapped lines rejoined; indentation = nesting on slides |
| **Epigraph / quote** | short block + `— Author` at chapter start | `> quote` / `> — author` |
| **Footnote** | 0.70–0.93× body size, lower page, leading marker; continuations joined | `[^n]: text` at section end; in-text `word.1` → `word[^1]` when n exists on that page and the digit is not part of a decimal |
| **Caption** | `Figure N.N` + a capitalised word (prose "Figure 2.3 illustrates…" excluded); wraps folded to three lines | `> **caption**` |
| **Figure text** | <0.72× body, off-margin, ≥3 lines in a region | image crop (`--figure-dir`) + deduplicated label list; optional VLM transcription |
| **Panel labels** | `a) … b) … c) …` on one baseline, interleaved with panel titles | one italic line joined with `·` |
| **Table** | ≥3 rows at regular pitch, short cells on ≥3 shared columns (clustered on **both** edges, chosen greedily by coverage); cells ≥0.55× body; fill ≥0.7; <25% math cells; wordy or word-headed; per column on two-column pages | Markdown pipe table |
| **Code** | monospace font | fenced block |
| **References** | `Surname, I.` / `(Year)` / `[12]` / `12.` at the column margin; hanging-indent continuations joined | `- entry` |
| **Glossary** | short term + definition (implemented, no fixture) | `- **Term**: definition` |
| **Notes / endnotes** | numbered entries after `Notes` (implemented, no fixture) | `1. text` |
| **Index** | regime after `Index`; adaptive — hanging-indent mode or isolation mode, chosen per index; ends at the next chapter, About the Author, Colophon | `- entry`, `**A**` dividers |
| **Running heads / folios** | margin band + repetition, no minimum length | dropped |
| **Rotated text** | line direction vector | out of prose; the arXiv id harvested from it |

`--profile` prints a census of these kinds for any document.

---

## Genre-specific paths

**Book** runs everything above.

**Columns** (papers, and anything else typeset in columns) are a property of the document's *template*, not of a page. They are found once: a histogram of the left edges of narrow lines over the whole document has one peak per column — 72 and 307 for an ACL paper; 45, 222 and 399 for the Federal Register. A peak inside the previous column's extent (a table's numeric column) is not a column. Boundaries sit in the **gutters** — between a column's right edge and the next start — never at the midpoint of the starts, which the left column's own text would cross. Columns must be *filled* (text runs at least halfway to the gutter), which is what keeps a key/value table from posing as two columns. Per page, a peak populated by enough of that page's lines is active. Two and three columns are handled.

**Paper** — nearly every book assumption inverts:

| Book assumption | Paper reality | What changed |
|---|---|---|
| One column; sort by y | Two or three columns; y-sort interleaves them | Column-major order from the document-level column template (above); full-width or gutter-straddling lines split the page into bands; within a band each column is read top to bottom, left to right. Each line carries `col`, `col_left`. |
| A title page exists | The title block is the top of page 1 | Title = largest contiguous lines; then emails, affiliations (University / Institute / city-state-zip), authors with superscripts and glued digits stripped, Unicode-aware. `Abstract` becomes a level-1 heading; inline `Abstract. text…` is split. |
| Bold is `BX` / `Bold` | Times/Nimbus bold is `-Medi`, `-Demi`, `-B` | Bold regex extended. |
| Headings are rare | 20 heading lines on 8 pages | Frequency cap gets a floor of 40. |
| `2.1 Title` on one line | `1. Introduction`; or `2.1` and `Node Types` as separate spans in a style captions also use | Numbered regex allows the period; a bare number at the column margin with a short bold title on its baseline is promoted regardless of style. |
| Indent = `x0 > page margin` | The right column is always "indented" | Every indent, list, and reference test uses `col_left`; a column change behaves like a page change for continuation. |
| Nothing is rotated | The arXiv id runs sideways | Non-horizontal lines are kept aside, not dropped; the id goes to YAML. |
| Tables are page-wide | The other column's prose shares every baseline | Table detection per `(page, column)`. |
| Columns are left-aligned | Label columns are right-aligned | Cluster on both edges; greedy selection by coverage. |
| A table is mostly words | A results table is mostly numbers | Accept when the header row is words. |

**Deck** — each page is a slide. Page 1 with one or two display lines → document title and subtitle. A page with ≤3 lines, all display-sized against the *median slide-title size* → section divider (`#`). Otherwise the largest line → slide title (`##`); glyph bullets and short lines → list items, with indentation as nesting; long lines → paragraphs; `---` between slides (Marp / reveal-compatible); `Thank you` / `Questions?` slides dropped. No regimes, no outline tree. Speaker notes are not present in exported PDFs.

**Document** (PRD, spec, memo) — page-1 title block: largest lines → title; `Key: value` lines and two-cell table rows (Author, Status, Version, Date, Reviewers, Owner…) → YAML fields; the first remaining short line → subtitle. Sections go through the outline tree. No book regimes.

---

## EPUB, DOCX and DOC input

These formats carry real structure — heading levels, list nesting, tables, footnotes, metadata — so nothing is inferred from geometry. `structured.py` turns the native markup into typed blocks, the **same outline tree** validates numbering and TOC membership, and the renderer emits the same YAML / title block / grouped contents / body layout as the PDF path. Only the standard library is used (`zipfile`, `xml.etree`, `html.parser`).

| Format | Read from | Notes |
|---|---|---|
| **EPUB 3** | `container.xml` → OPF metadata, manifest, spine → each XHTML in spine order; `nav.xhtml` for contents truth | `dc:title / creator / publisher / date / identifier(ISBN) / language`; `<h1>–<h6>`, lists with nesting, tables, `<blockquote>`, `<pre>`, `<figure>/<img>`, footnote `<aside epub:type="footnote">` and `role="doc-noteref"` references; back-links suppressed; **note ids namespaced per chapter** (pandoc restarts at `fn1` in every file) |
| **EPUB 2** | same, with `toc.ncx` for contents | LibreOffice and Calibre exports often have **no heading tags at all** — every block is `<p class="paraN">` and hierarchy lives in the stylesheet. The reader parses the CSS (`font-size`, `font-weight`), ranks paragraph styles by size — the PDF style-ranking idea in CSS clothing — and promotes a tier larger, or bold-and-short, paragraphs to headings. Body size defaults to 12pt when most paragraphs carry no size (their class sets only margins). A spine file with no heading takes its title from the contents, unless that title is a generic `Section N`. |
| **DOCX** | `word/document.xml`, `styles.xml` (outline levels and `Heading N` names through `basedOn` chains), `footnotes.xml` / `endnotes.xml`, `document.xml.rels` for images, `docProps/core.xml` | Title / Subtitle / Quote / Caption / List / Code styles; numbering → list nesting; short all-bold unstyled paragraphs → run-in headings; a Word-generated contents control is dropped and regenerated; a first table of `Key | Value` pairs (Author, Status, Version, Reviewers…) becomes YAML fields; generator defaults (`creator: python-docx`, the 2013 template date, `Unknown Title`) are rejected |
| **DOC / ODT / RTF** | `soffice --headless --convert-to docx`, then as DOCX | `--soffice PATH` if LibreOffice is not on `PATH`; times out at 180 s with a clear message |

Type classification for structured input is by content rather than geometry: an `Abstract` heading near the top → paper; two `Chapter N` headings, an ISBN, ≥8,000 words, or a contents of ≥8 entries → book; otherwise document. `--doc-type` overrides.

Fixtures: the PRD as `.docx` and `.doc`, a whitepaper exported by LibreOffice as EPUB 2 (CSS-only headings), and a three-chapter mini-book built with pandoc as EPUB 3 (nav, footnotes, table, list, quote, ISBN). The suite asserts, among other things, that the LibreOffice EPUB recovers `1.1 Constraints` from a 13pt bold span, that the mini-book's two chapter-local `fn1` notes become `[^2-fn1]` and `[^3-fn1]`, and that pandoc's title page is not echoed into the body.

**Prefer the EPUB or DOCX when you have one.** A PDF of the same book needs every inference in this document; the EPUB needs none of them.

---

## Output format

```markdown
---
title: The Cognitive Structure of Emotions
edition: Second Edition
authors:
  - Andrew Ortony
  - Gerald Clore
  - Allan Collins
publisher: Cambridge University Press
year: 2022
isbn:
  - 9781108844246
  - 9781108928755
  - 9781108934053
pages: 575
source: The_Cognitive_Structure_of_Emotions.pdf
generator: pdf2md
---

# The Cognitive Structure of Emotions
**Andrew Ortony, Gerald Clore and Allan Collins**
*Second Edition · Cambridge University Press, 2022*

## Contents

- **Front matter**
  - [Preface to the Second Edition](#preface-to-the-second-edition)
- [Chapter 1: Introduction](#chapter-1-introduction)
  - [The Study of Emotion](#the-study-of-emotion)
- …
- **Back matter**
  - [References](#references)
  - [Subject Index](#subject-index)

---
```

Papers add `type: paper`, `affiliations`, `arxiv`, `venue`; decks add `type: deck`, `subtitle`, `slides`; documents add `type: document` and whatever fields the title block carried (`status`, `version`, `reviewers`…).

Metadata provenance: **book authors come from the `©` line** (copyright holders are reliable; cover text kept yielding subtitle fragments), with initials handled; paper authors come from the title block; document authors from the `Author` field. ISBNs are found labelled or bare, including inside CIP records. The newest `©` year wins. Publisher is stripped of street addresses. The title block is a fixed layout — title, subtitle, **authors**, imprint — regardless of the order the cover printed them in. TOC indentation is by rank among levels used; duplicate headings get GitHub-style `#summary-1` anchors.

---

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

## Findings

What each document taught, in the order it was learned. Each is a rule in the code.

### Sutton & Barto (LaTeX, authored text layer)

1. **Section headings are bold at body size** (CMBX10 @ 10pt). No size threshold finds them; detection is by `(font, size)` style with boldness read from the font name.
2. **Section numbers and titles are separate spans on one baseline** (`2.1` / `A k-armed Bandit Problem`); reading order between them is not guaranteed. Sort by `(page, y-band, x)` before merging.
3. **Figure captions are bold too**, and text baked into vector figures (Helvetica, Times, Symbol) is large and bold. Heading candidates are restricted to font families carrying ≥2% of the document's characters; a style whose lines mostly start with `Figure N:` is a caption style.
4. **Spans are joined with no space character.** TeX writes each font run as its own span; `"".join()` welds words (`First-visitMCprediction`). The space is reinstated from the geometric gap between span boxes.
5. **Computer Modern has no ToUnicode map for many slots.** `↵` is `ff` in a text font but **α** in a math font; `⇡` is π; `✓` is θ. The glyph map is keyed by font class. CMEX10 decodes to arbitrary ASCII including `#`, which then renders as an H1: CMEX spans are dropped and **all body text is Markdown-escaped**.
6. **Bold math labels share the heading style exactly** (`xt`, `w3`, `w>x`). A text-shape gate rejects them: real headings are words, ≥90% prose characters, no operators; a one-word heading is Capitalised or ALL CAPS.
7. **The printed Contents page is ground truth when the PDF has no bookmarks** (none of the eight had any). Dot-leader pages are detected, parsed, and consumed; the old cleaner deleted them.
8. **Tables extract as one-word paragraphs.** Detection is geometric; geometry alone also matches multi-line equations and pseudocode, which content gates reject; diagram labels also align in columns but at ~0.3× body, where real tables are ≥0.6×.
9. **A contents page is a skeleton, not an index of bold lines.** Fifty run-in labels and fifteen `Bibliographical and Historical Remarks` were reaching the TOC — the problem the outline tree was built for.
10. **Density demotion was counting the wrong things.** Bold cross-reference numbers in one chapter's remarks pushed the next chapter's opener over the limit and demoted its title. Bare numbers and labelled series no longer count; the line under `Chapter N` is protected.

### Design Leadership (OCRmyPDF, glyphless layer)

11. **An OCR layer has one synthetic font.** Family, boldness, style identity are gone. Size survives as a noisy analog: body text smears across 12.7–14.8pt, producing 30 bogus heading levels if treated as discrete styles.
12. **Two boundaries, two methods.** Body-vs-heading is *anchored* at 1.15× the body median (jitter fills that valley); heading-vs-chapter-title is found by *detecting the gap*. Counts per line, not per character.
13. **Isolation is independent evidence.** Size jitter promotes random body lines; a real heading has whitespace above it.
14. **Wrapped headings fail the isolation test.** Continuation — same style, same page, directly below an accepted heading — is evidence too.
15. **Zero furniture can be correct.** These page images are pre-cropped; fixed-margin assumptions would have eaten body text.
16. **Headings are sparse.** Index entries with 40pt gaps passed isolation and OCR sized 88 of them above threshold. Density demotion caught 61; the index regime caught the rest.
17. **A hyphen bullet needs a sibling.** OCR renders the em dash of `— I think…` as `- I think`. Real lists have neighbours.
18. **This ebook has no printed Contents page** (the EPUB→PDF conversion dropped it); its 44 sections are what the size tiers find.

### Cognitive Structure of Emotions (OCRmyPDF, glyphless layer)

19. **Headings wrap across page breaks.** A heading ending on a dangling function word, followed by a same-style heading at the top of the next page, is one heading.
20. **Diagram text is a word salad.** No text method rebuilds a tree the OCR walked row by row. Recognise the region, keep it out of prose, crop the pixels, keep the labels searchable.
21. **A leaderless Contents page reflows into sentences.** A `contents` regime consumes it.
22. **De-shouting must protect acronyms, learned from the book** — any all-caps token recurring three times inside mixed-case sentences (OCC, EMA, APS here; TD, MDP, GPI in RL); small words excluded; `RNNS` → `RNNs`.
23. **Two index typographies.** Hanging indent vs. extra space above each entry; the script samples the index's x-distribution and picks the rule (77/799 → 483/393 entries/continuations).
24. **Name regexes match sentence boundaries** (`Virginia. He is…`) and, once fixed, initials (`S. Sutton`). Name tokens may not carry a trailing period unless they are an initial.
25. **Prose cross-references look like captions.** A caption requires a capitalised word after the number.

### Research papers (three, different pipelines)

26. **Bold has many spellings** — `-Medi`, `-BoldMT`, `-Demi`, `,B`. The ACL paper had zero headings until the regex learned them.
27. **The abstract is indented, so it lies to a column detector** anchored on the mode of left edges. Ask whether a populous group sits at the margin instead.
28. **A centred figure's labels look like a left column** on a single-column page. Anchor the left column to the document-wide margin.
29. **The rotated arXiv identifier is furniture and metadata at once.** Keep rotated text aside and pass it through the profile — `papers.py` importing `pdf2md` while `pdf2md.py` runs as `__main__` created a second, empty module.
30. **Right-aligned label columns** split into three left-edge clusters. Cluster both edges; choose greedily by coverage.
31. **A results table is mostly numbers.** The gate that rejected equation blocks also rejected `Precision / Recall / F1`; the header row being words is the discriminator.
32. **Footnote anchoring vs. decimals**: `89.3` with footnote 3 on the page became `89.[^3]`.
33. **Papers set captions and subsections in the same bold face**, so the subsection style became a caption style and `2.1 Node Types` vanished. The geometry — bare number at the margin, short bold title on its baseline — identifies it without the style.

### Structure and genre

34. **Regex lists don't scale; the tree does.** A run-in word list, a density hack, and a lenient exception were three patches for one missing idea: the outline is a tree whose numbering must be consistent.
35. **A title beside its accepted number needs a lenient gate.** `Optimality of TD(0)` scored 0.895 against a 0.90 cut; `TD(λ)` failed on the λ.
36. **Genre must be decided first.** `is_paper` had been deciding paper-vs-book *inside* classification, after book-only passes had already run.
37. **"Largest line in the same place on every page" is a deck signal only when that line is display-sized.** On a book's body pages the largest line is the first body line, always at the top.
38. **Decks have no reliable body size.** Sparse slides let the title style dominate character count; section dividers are judged against the median slide-title size.
39. **The producer string is a bonus, not a basis.** LibreOffice stamps decks and documents identically.

### Robustness sweep (17 unseen documents)

40. **`Skia/PDF` renders Google Docs and Google Slides alike.** A one-word Docs page scored `deck +4` on its producer. Only `slides` in the string is a deck signal.
41. **Checkbox glyphs are bullets too.** A Japanese deck's `□` bullets scored eight "form markers" and nearly flipped it to document. Glyphs count once; form vocabulary counts.
42. **Sparse words on one page is not deck evidence.** A landscape vendor table tied deck 4 – document 4 and lost on insertion order. The words-per-page signal needs three pages; ties break document > paper > book > deck.
43. **A template can have two title placements.** Section slides and content slides put the title at different heights; the top two placements together covering 70% of pages is the template.
44. **Column templates need geometric evidence.** Per-page chain-merging of left edges collapsed two columns into one on any page with a wide table (cells fill the gap in ≤25pt steps). The original document-level histogram helped with this case. Current detection uses page-local evidence to accommodate changes in layout and page width.
45. **Boundaries belong in the gutter.** The midpoint between column *starts* is inside the left column's text, so every left-column line "crossed" it and became spanning. Gutters lie between a column's right edge and the next start.
46. **A cluster inside a column's extent is not a column.** A results table's numeric column formed a third "column" until starts were required to lie beyond the previous column's right edge.
47. **A key/value table is not two columns.** Columns must be *filled* — text running at least halfway to the gutter. A PRD's `Author / Jin` table has two short columns and fails that.
48. **A document's title block must stop at the first table.** With no heading below the title, "everything above the first heading" was the whole page, and a vendor table became metadata fields.
49. **My own grep lied twice.** `awk '/^  - /'` prints affiliations as well as authors; a check that matches on a crash's stale output is not a check. Read the artifact, not the terminal.

### EPUB, DOCX and DOC (four generated fixtures)

50. **LibreOffice's EPUB export has no heading tags.** Every block is `<p class="paraN">`; the hierarchy is entirely in the stylesheet. Parsing the CSS and ranking paragraph styles by size is the PDF style-ranking idea again, and it recovers sections and subsections the nav never mentions.
51. **Body paragraphs may carry no CSS size at all** — their class sets only margins — so the modal size of *sized* paragraphs is the size of the decorated ones, not the body. When most paragraphs are unsized, the body is the browser default.
52. **pandoc numbers footnotes per chapter file.** Both chapters had `fn1`; note ids are namespaced by spine position. Its back-link anchors (`class="footnote-back"`) contain the word "footnote" and were read as references until back-links were handled first and their text suppressed.
53. **A generator's defaults are not metadata.** python-docx writes `creator: python-docx` and a 2013 template date; LibreOffice writes `dc:title: Unknown Title`. These are rejected, and a `Key | Value` table in the document (`Author | Jin`) fills the gap.
54. **A generated title page echoes the metadata into the body.** Headings and paragraphs equal to the title, an author, the publisher or the year are consumed.
55. **The largest first line is the title** regardless of genre — the same rule the PDF path uses for papers — which is what let the CSS-only EPUB name itself.

### Process

56. **A silent failure is worse than a loud one.** For two rounds, edits appeared to do nothing: a rewrite had swallowed `render_table`, the converter crashed on assembly, and `2>&1 >/dev/null` hid it while stale outputs were grepped. The suite exists because of this.
57. **Every change runs every fixture.** A fix for the OCR books broke the LaTeX book's chapter titles; a fix for one book's authors dropped another's; a tokenizer bug in the tree went unnoticed on five documents and collapsed the sixth. The heterogeneous corpus is the regression suite.
58. **Metadata from the book beats metadata from the cover.** Copyright holders are authors; cover text is subtitle fragments, brand marks and cities.

---

## Audit and fixes

An adversarial review of both readers, driven by generated hostile fixtures, found nineteen defects. All are fixed, and each has a test in `tests/test_regressions.py`. They are recorded here because the failure mode they share is the dangerous one: **the converter exited 0 and wrote a plausible file with content missing from it.**

### Silent content loss

1. **A rename corrupted a regex in the shipped build.** The single-file build renames `W` to `WML`; applied without word boundaries, it rewrote `re.sub(r"\W", ...)` into `re.sub(r"\WML", ...)`, disabling EPUB heading de-duplication in `pdf2md_all.py` while `structured.py` stayed correct. Nothing compared the two copies. `tools/sync_structured.py` now renames NAME tokens only, and CI fails if the copies diverge.
2. **`<div class="footnote">` swallowed the rest of the chapter.** The note was pushed and never popped, so every later paragraph in the file was relabelled a footnote and merged under one colliding id.
3. **An inline `<section epub:type="toc">` truncated the file.** It raised a skip counter that only `script`/`style`/`nav` ever lowered.
4. **An unclosed tag inside a noteref anchor dropped everything after it.** Suppression was popped only when the sentinel sat on top of the stack.
5. **A detected table was deleted or flattened.** Cells were claimed by the table pass, then re-typed as list items or stolen by the front-matter labeller; the table was emitted only at one remembered cell, so re-typing that cell erased the whole grid.
6. **A chapter title beginning with a year demoted every later chapter.** `2019 Annual Review` tokenised as section 20, which advanced the outline spine past every real chapter.
7. **One ellipsis run deleted a page.** Four dots on a sparse page cleared the dot-leader ratio and the page was dropped as a printed contents page.
8. **A nested table wiped the enclosing one.** The inner `<table>` reset the shared row buffer.
9. **Figures collided on basename.** `img/a/fig.png` and `img/b/fig.png` both became `fig.png`; the second overwrote the first and both links pointed at it.

### Wrong output

10. **Footnotes all rendered as `[^*]` and merged.** Notes detected during classification carried no number, so consecutive notes were joined and every definition shared one label. Labels are now page-qualified and unique.
11. **Cross-file endnotes dangled.** References were namespaced by the file they appeared in rather than the file the note lives in, so a reference and its definition never matched.
12. **A backslash in any metadata value produced unparseable YAML.** `_yq` escaped the quote but not the backslash.
13. **Number-led lines got an invalid escape.** The backslash landed before the digits, where Markdown does not honour it, leaving a literal `\` in the prose.
14. **Headings with a parenthetical were demoted to prose.** `(` and `)` were missing from the prose-character set behind a 90% gate.
15. **A DOCX footnote cited twice was defined twice.**
16. **A mislabelled encoding was decoded as UTF-8 regardless.** Latin-1 text became replacement characters; a legal UTF-16 document became NUL bytes and raw markup in the output.
17. **An untitled document emitted `title: ""` and a bare `#`.**
18. **`--pages 1,1` converted the page twice.**

### Crashes and diagnostics

19. **Fifteen inputs produced a raw traceback** instead of a diagnosis: a non-PDF, a directory, an encrypted PDF, a malformed `--pages` spec, a non-zip EPUB or DOCX, an EPUB missing a rootfile / navMap / navLabel / manifest href, a DOCX with no `w:body`, a malformed CSS `font-size`, a failing LibreOffice, and an output path whose directory did not exist. `--emit-json` crashed with `RecursionError` on any document containing a table, because the JSON walk followed back-references between lines. A page range outside the document reported "this is an image-only scan, run OCR" — a confident diagnosis of the wrong problem.

Also fixed: `--figure-vlm` was accepted without `--figure-dir` and silently did nothing; a failing vision model was swallowed without a word, against the project's own "a silent failure is worse than a loud one" principle; the PDF handle, the EPUB zip handle and LibreOffice's temp directory were never released.

## Design principles

**Decide the genre first, with evidence.** Everything downstream assumes one. Score independent families, record why, allow override.

**Structure is a tree, and the tree is evidence.** Numbering consistency, sibling uniformity, and parent–child extension decide levels and TOC membership. Before reaching for a word list, ask what the surrounding hierarchy already implies.

**Evidence, then shape, then position, then density.** A line is a heading if its *style* is a heading style, its *text* looks like words, it has *air* above it, and it is not one of many. Each test was added because the previous ones let a specific failure through. Keep them all.

**Global before local.** Per-page heuristics cannot tell a running head from a real heading; "appears at y=39 on 400 pages" is unambiguous. Body style, running heads and heading styles use document-wide evidence; column geometry also adapts to each page.

**Regimes.** A book is not one distribution of lines. The same shape means different things in front matter, body, and back matter.

**Never emit Markdown from unescaped text.** Extraction artefacts at line starts silently become structure.

**Keep text corrections verifiable.** Structure inference does not justify rewriting words. Optional selective OCR uses the source image and conservative acceptance gates, records its decisions, and leaves rejected candidates unchanged.

**Deterministic first, model last.** The default pipeline uses local extraction and heuristics. Optional Tesseract OCR and `--figure-vlm` are explicit additions; their backend versions and settings can affect results.

---

## Robustness sweep

Seventeen documents the converter had never seen, from pdfminer, pdfplumber, camelot, pypdf and olmOCR test corpora plus four generated with LibreOffice:

| Document | Pages | Type | Margin | Notes |
|---|---|---|---|---|
| NLP 2004 slides (Japanese, Quartz) | 31 | deck | 9/3 | two title placements; Wingdings `o` bullets |
| Shinyama & Sekine 2006 (NAACL) | 8 | paper | 9/5 | 12 sections, 4 tables, affiliations separated from authors |
| DMCA summary (US Copyright Office) | 18 | document | 5/2 | legal text; long headings wrap unmerged |
| Federal Register 85/152 (three columns) | 15 | document | 6/4 | reading order correct across three columns |
| IRS Form 1040-NR | 5 | document | 6/4 | form vocabulary (OMB, signature, checkboxes) |
| Google Docs one-word page | 1 | document | 4/1 | `Skia/PDF` is Docs *and* Slides |
| camelot budget / superscript tables | 1 | document | 2/1 | |
| Japanese government page (kampo) | 1 | document | 2/1 | script out of scope; no crash |
| NICS background-check report | 1 | document | 2/1 | large numeric table not detected |
| olmOCR dolma page, pypdf crazyones | 1 | document | | |
| Memo (To / From / Subject) | 1 | document | 10/0 | fields into YAML |
| Whitepaper (numbered sections, table) | 4 | document | 5/2 | `1.1` nested, results table |
| Landscape vendor-comparison table | 1 | document | 4/2 | landscape ≠ deck; table intact |
| 4:3 hardware-review deck | 5 | deck | 19/2 | |
| Image-only scan (pdfminer 175) | 2 | — | — | refused with an OCR-first message |

Six classifier and layout fixes came out of the sweep: `Skia/PDF` removed from deck producers (it renders Google Docs too); form vocabulary added as a document signal, counting checkbox *glyphs* once (they are also bullets); sparse words on a one-page document no longer scores as a deck; a deterministic tie-break (document > paper > book > deck); two title placements (section and content slides) counted as a template; and the document-level column template with gutter boundaries, which is what made three columns work and stopped a PRD's key/value table from reading as two columns.

---

## Real-library sweep

The generated fixtures above are inspectable but agreeable. A second sweep ran the converter over a personal library of **1,566 real PDFs** — 99 subject folders, 21 KB to 727 MB, authored ebooks, ACM and CHI papers, conference decks, scanned art books and government reports — measuring, per file, the share of PyMuPDF's own words that survived into the Markdown.

The measurement set was 376 documents (35,661 pages, 8.3 minutes to convert): a size-stratified sample of 212 covering every subject folder, plus every document in the library whose pages are all rotated. Median word recall **0.972**; 364 of 376 convert, and all 12 refusals are verified image-only scans.

It found seven defects that no generated fixture had:

- **Every page of a `/Rotate 90` or `/Rotate 270` PDF was thrown away.** 178 documents — 11.4% of the library — were affected. `get_text()` reports each line's `dir` and `bbox` in *unrotated* page space while `page.rect` is the rotated one, so on a landscape PDF the body text reads as `dir (0,-1)` and the sideways-text filter discarded it. The converter then reported "no text layer — this is an image-only scan" on documents with a perfect text layer, or, where a handful of genuinely vertical lines survived, emitted those and called it a 30-page deck: one 30-page compendium came out as 424 characters of its 33,000. Both `dir` and `bbox` now pass through `page.rotation_matrix`, which is the identity on an upright page. 174 of the 178 now convert at 0.970 median recall; the other four are real scans.
- **An undecodable text layer produced megabytes of confident gibberish.** A PDF whose fonts are subset with no usable ToUnicode map extracts as a substitution cipher — `Farming management` comes back as `)DUPLQJ PDQDJHPHQW` — and nothing downstream can tell, because the line count, font metrics and layout are exactly as healthy as a good document's. Six library documents converted this way, one of them 301 KB. This is the same failure the image-only guard exists to prevent, so it now warns in the same voice. See [Known gaps](#known-gaps) for the thresholds and what still slips through.
- **ACM front matter landed in the YAML as affiliations.** The title-block labeller took every unrecognised line as an affiliation, so author keywords, ACM classification codes, General Terms, copyright notices and — where a sidebar layout defeats the column split — whole sentences of the abstract were published as the authors' institutions. 48 of 364 outputs were affected, now 21.
- **An animation build came out as four slides.** A slide whose bullets appear one click at a time exports one PDF page per click, and each page was read as a slide of its own: the heading repeated four times, the first bullet three. This was the single largest source of duplicated headings in the library. Consecutive pages sharing a title now collapse to the one that already contains the rest — in either direction, because a build can take an overlay away as well as add one, and tested both as a set of lines and as a prefix of the slide's text, because revealing a bullet re-wraps the lines above it. Documents with a quarter or more of their headings duplicated: 12 → 6.
- **A wrapped slide title was cut at the first line.** `Specific: The Prioritization Exercise` arrived as a heading `Specific: The` followed by two one-word bullets. On a deck whose body is set at the title's own size, size cannot decide this; the continuation is recognised by geometry instead — the title's left edge, the title's line pitch, and a visibly bigger gap before the body.
- **Symbol-font glyphs printed as tofu.** Wingdings and Symbol have no Unicode meaning, so they are encoded into the Private Use Area. One book carried 7,266 of them into its Markdown, including inside headings and the anchors generated from them. A leading one is the line's bullet and becomes a real one; the rest are dropped. Across the library, 8,580 → 90.
- **A page *about* copyright was dropped as a copyright page.** The rule counts keywords and had no length guard, so two 11,800-character pages of an article on copyright law vanished — the silent-content-loss failure this converter exists to avoid. A colophon is also short, and the rule now says so.

---

## Whole-library run

The sweeps above sample. This is the whole of `~/knowledge-base/books-pdf`, in
randomised order, with nothing held back: **1,593 files, 18.8 GB, 138,464
pages**, five minutes of wall-clock across eight shards, 227 MB of Markdown.

**1,562 of 1,593 convert (98.1%).** All 29 refusals were checked against
PyMuPDF's own extraction and every one is a genuine image-only scan — **zero
false refusals**. (The two remaining non-conversions are `.rtf` files, which
need LibreOffice.) Unique-word recall against PyMuPDF has a median of
**0.9868**; 10 documents fall below 0.80, and those are the ones whose own
font encodings are broken, which the converter now warns about. Private-use
and control characters across all 227 MB of output: **364**.

It also turned up two defects the sampled sweeps had hidden.

**Books did not record their own genre.** Papers, decks and documents all
write a `type` field; books did not, so 347 outputs said nothing about what
they had been identified as.

**The title page was chosen by length, so dedications won.** A book's front
matter offers several short display-set pages, and the longest of them was
taken as the title -- which published `To Karen, Paul, Anna, and Jack --
Michael T. Goodrich To Isabel...` and an "other books by this author" list as
the titles of their books, over real title pages set at 25pt and 78pt a few
leaves earlier. Two things were wrong. Dedications were reaching the title
test at all, because the rule that recognises them required small type, and a
dedication is set in display type as often as not. And the choice between the
genuine title pages was being made on length rather than on typography.

Size now decides *whether* a page is a title page -- it must be display-set
against the document's own body size, which is what separates it from a 12pt
dedication or a 10pt backlist. Among the pages that pass, the title page
proper is the one carrying the most of the title block: the half-title is one
line, the title page is several. Picking the largest type instead is just as
wrong in the other direction -- the half-title is set *bigger* than the title
page it faces (51pt against 21pt in one book, and one book opens on a
printer's ornament at 93pt), which picks a single word and loses every
subtitle with it.

Across the 1,562 converted documents this changed 31 titles: 21 are plain
repairs (`Figure 4 2 6 8 8 9 R A Relationship Diagram` to `Games People Play`,
a dedication to `Data Structures and Algorithms in Java`), four are lateral
moves between two equally poor readings of a badly built PDF, and none turned
a good title into a bad one. Word recall over the whole corpus is unchanged.

---

## EPUB sweep

Every EPUB in the same library — 23 books, 0.4 GB, nine seconds. An EPUB is the
easiest input to grade, because it carries its own structure: the OPF names the
title and authors, and the XHTML says exactly where the headings are.

All 23 convert. Word recall against the books' own XHTML has a **median of
1.0000** and a worst case of 0.9951; the title matches the OPF metadata on
**23 of 23**; no HTML entity and no control character reaches the Markdown. The
only raw tags in any output are the HTML *code examples* that three of the books
print in `<pre>` blocks, which is correct. The two `.rtf` files alongside them
are refused with `converting .rtf needs LibreOffice (soffice) on PATH` — the
documented dependency, reported rather than crashed on.

No defect was found in the EPUB path.

---

## arXiv sweep

Fifty papers pulled at random from arXiv across eleven subject categories — cs.CL, cs.CV, cs.LG, cs.SE, cs.HC, math.PR, math.AG, physics.optics, cond-mat.soft, q-bio.NC, stat.ME, econ.EM, eess.SP and astro-ph.GA — 1,012 pages, 39 seconds. Every paper's title and author list was checked against arXiv's own metadata rather than by eye.

All 50 convert and all 50 are classified `paper`. The title matches arXiv's exactly on 47 of 50; the arXiv identifier is recovered from the sideways stamp on 48 of 50; word recall against PyMuPDF's own extraction has a median of 0.971.

Four more defects came out of it, all of them in papers whose typography carries no heading style at all:

- **REVTeX and IEEE section headings were invisible.** `I. INTRODUCTION` is centred and set in the body face at the body size — there is no style to rank and no margin to measure against, so five of the six papers written that way lost *every* section heading in the document. What is left is the numbering, and it is strong evidence: a run of short isolated lines numbered I, II, III in order is a section spine and nothing else. Three members are required, counting from the first, so a stray `V. Smith` in a bibliography cannot start one; letter subsections between two members are then placed under them.
- **The abstract came out as a stack of H1s.** IEEE sets the abstract in a bold face of its own, the style ranking learned that face as a heading style, and every wrapped line of the abstract became a heading. Papers now get the same heading-density check that books already had: ten heading candidates in ten consecutive lines is a paragraph.
- **`Abstract—` was not an abstract.** The inline-abstract pattern required whitespace after the delimiter, which the IEEE em-dash convention does not have, so the abstract went unlabelled.
- **A soft hyphen left every hyphenated word broken.** A discretionary hyphen means "the typesetter broke the word here", and it has width, so the span joiner adds a space after it: one 12-page paper carried 183 of `How\u00ad ever`, `illus\u00ad trates`, `audi\u00ad ence`. Reflow now treats it as the hyphenation mark it is.
- **A tab survived into a heading and its anchor.** `3.2.\t Critical Design`. A tab, or a run of spaces, inside an extracted line is the PDF's own layout spacing; leading whitespace is still left alone, because a code block's indent is real.
- **A figure's LaTeX source was printed as a code block.** A figure exported from Inkscape keeps the source of its labels in an invisible base64 `<latexit>` annotation: none of it is drawn on the page, all of it is in the text layer, and it arrived as a fenced block of gibberish with the real label welded onto the end.
- **A section number was separated from its own title.** LaTeX emits `4.1` and its title as two blocks on one baseline, a hair apart in *y*. The extractor bands the baseline to keep them together and says so in a comment; the column reordering then re-sorted on raw `y0` and undid it, so `Repeated Sampling and Output Variabil-` came out ahead of its own `4.1`, the merge that rejoins them never fired, and the tail `ity` was left as a paragraph. Headings truncated mid-word across the 50 papers: 16 → 6.

---

## Testing

```
pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

Five test modules generate their fixtures at runtime so no binaries live in the repository:

| File | Covers |
|---|---|
| `tests/test_smoke.py` | a PDF and an EPUB convert: YAML front matter, paragraph reflow, artifacts, EPUB metadata / headings / lists |
| `tests/test_errors.py` | every bad-input path exits with a readable message and no traceback: non-PDF, directory, encrypted, malformed `--pages`, non-zip EPUB/DOCX, overwriting the input |
| `tests/test_regressions.py` | one test per defect fixed in the audit below, plus a build-integrity check that `pdf2md_all.py` still matches `structured.py` |
| `tests/test_pdf_quality.py` | layout and text quality on generated PDFs: column reading order, learned heading styles, running heads, reflow — and the defects the real-library and arXiv sweeps found: rotated pages read in order, undecodable text layers reported, ACM front matter kept out of the YAML, animation builds collapsed, wrapped slide and numbered headings rejoined, private-use glyphs dropped, REVTeX section spines found |
| `tests/test_research_pipeline.py` | document trees, provenance, OCR acceptance/rollback, font flags, symbols, and benchmark reporting |

The current suite has 83 tests, including the library-sweep regressions and research-pipeline tests. CI runs on Python 3.10–3.13 and installs
Tesseract with English data for the scan integration test. Locally, that test
requires the same optional OCR dependency. Also run:

```bash
python3 tools/sync_structured.py --check
python3 -m py_compile pdf2md_all.py structured.py tools/benchmark.py tools/compare_converters.py
ruff check --select F,E9 pdf2md_all.py structured.py tools tests
```

These regression tests are separate from the source-grounded sample comparison;
neither constitutes a comprehensive Markdown formatting audit.

The full regression suite (`test_books.py`) and its fixtures live with the modular development build and are not in this repository. It runs the eight core fixtures, the four generated sweep documents, and any of the five third-party sweep documents that are present, with `--artifacts`, and asserts ~80 golden invariants:

- converter exits 0 on every fixture (the silent-failure guard)
- document type for all eight, with the winner ≥3 points clear of the runner-up
- YAML front matter, authors present, title precedes TOC, every chapter in the TOC
- exact chapter counts (17 / 8 / 10) and merged titles, including the cross-page wrap
- glyph repair (`different`, `| high | search | high | α | rsearch |`), no injection, no shouting, no dot leaders
- TOC depth ≤3; `Bibliographical…` and run-ins out; `**Example 6.2 Random Walk**` merged and bold in the body
- indexes free of fake headings, rendered as lists; `chasing that dragon` is prose
- front matter labelled; leaderless contents consumed; figure regions; ebook ISBN; diagrams are not tables
- papers: type, exact title, author lists (20th author, Unicode names), Abstract/References, `#`/`##`/`###` from numbering, arXiv id, contiguous two-column reading order, the exact right-aligned table row, subsections from the baseline, no anchors in decimals
- deck: title, dividers at `#`, slide titles at `##`, nested bullets, `---` separators, end slide dropped, no book regimes
- PRD: type, `status` / `version` / `reviewers`, nested `5.x`, revision-history table, no book regimes
- sweep: memo fields, whitepaper `1.1` and table, landscape table row, 4:3 deck slide; Federal Register three-column reading order; NAACL authors and `3.1`; types for all, with the winner ≥3 clear of the runner-up on documents of three or more pages

The suite found real bugs on its first run and on the first tree implementation. Run it after every change.

---

## Known gaps

- **Subsection depth on OCR layers.** Bold-at-body-size subsections are invisible in a glyphless layer; Design Leadership's "About the Author" and colophon therefore land inside the index list.
- **Sparse grids** (tic-tac-toe boards) render as code blocks; they are figures and a drawing-rule check would trigger a crop.
- **Large numeric tables** without a wordy header (the NICS state-by-state report) are not detected.
- **Long legal headings** that wrap (the DMCA summary's `Title I, the “WIPO Copyright…`) are emitted as separate headings.
- **Non-Latin scripts** convert without crashing but the de-shouting, name, and heading-shape rules are Latin-only.
- **Math is passed through, not reconstructed.** Equations survive as approximate Unicode; the ACL paper's math font maps `=` to `D`.
- **Multi-row table headers** render as two header rows.
- **Glossary and endnotes** are implemented against the taxonomy but no fixture exercises them.
- **Language.** Regime keywords, copyright vocabulary, and small-word lists are English-only.
- **Landscape books** (photo books, catalogs, manuals) are not distinguished from decks; the design (image coverage, template repetition, prose test) was worked out but not implemented.
- **Deck fixtures are synthetic.** A real PowerPoint export with charts, SmartArt and two-column layouts will stress the per-slide path further; speaker notes are not in exported PDFs.
- **Image-only PDFs** need optional `--ocr auto --artifacts DIR` and Tesseract. OCR is off by default; rotated pages and additional image text on otherwise healthy text pages are not automatically recovered. Physical-book dewarping is not implemented.
- **Column reading order is wrong on a minority of two-column pages.** The template is misread and the columns interleave line by line, which welds sentences together, invents words where a hyphen is then joined across the break, and runs reference-list entries into the body. Two targeted repairs were written and measured over the 376-document library sweep -- anchoring the template on whichever column start matches the page's left margin, and ignoring gutter-crossing lines when measuring a column's right edge. They fixed a handful of pages and made more documents worse (mean word precision unchanged, recall 0.973 to 0.969, better on 42 documents and worse on 65), so they were reverted. The current branch also integrates a different modal-column adjustment validated on the smaller development sample; its effect on that larger sweep has not been remeasured.
- **Output is named after the input file**, because that is the only name the converter is given -- a library of `p517.pdf` yields `p517.md`, even though its front matter says `title: "Accessible Voting: One Machine, One Vote for Everyone"`. `tools/name_by_title.py` renames a directory of output from that front matter.
- **Undecodable text layers are warned about, not repaired.** Three signals, each calibrated against the 1,566-book library so the threshold sits in open space between the worst honest document and the best broken one: under 30% letters (honest worst 54%), over 15% of words vowel-less (honest worst 8%), over 6% of letters inside 24-character run-ons where the encoding dropped the space (honest worst 1.7%). That catches six of the library's seven broken documents and fires on none of the other 1,473. A cipher into the *accented-letter* range still reads as letters and words and slips through, and no attempt is made to solve the substitution — OCR is the answer, and the warning says so. The conversion still runs, because the caller may want the layout anyway.
- **Structured input coverage** is what four generated fixtures exercise: no real-world EPUB with images, nested lists in footnotes, or a multi-level nav has been run yet; DOCX tracked changes, comments and text boxes are ignored.
- **Nested tables** are flattened, not nested: the inner table is emitted as its own table and the cell that held it is left empty. Markdown has no nested-table syntax; the cell text survives, the containment does not.
- **Footnote labels are page-qualified** (`[^p12-3]`) because printed numbering restarts on every page. They are stable and unique, but they are not the numbers the book printed.
- **A document whose declared encoding is wrong** is decoded by trying UTF-8, then cp1252, then latin-1. That recovers the common mislabelled-Western-European case and will still mis-decode a mislabelled document in another script.

---

## Files

```
pdf2md_all.py               # single-file build (everything); `python3 pdf2md_all.py in.pdf` is the whole tool
structured.py               # EPUB / DOCX / DOC reader module (also merged into pdf2md_all.py)
tools/sync_structured.py    # copies structured.py into the merged build; --check fails if they diverge
tools/name_by_title.py      # renames converted Markdown after the title in its front matter
tests/test_smoke.py         # conversion smoke tests
tests/test_errors.py        # bad-input diagnostics
tests/test_pdf_quality.py   # adaptive PDF layout and text quality
tests/test_research_pipeline.py # structure, provenance, OCR and benchmark tests
tools/benchmark.py         # manifest-driven quality and performance checks
tools/compare_converters.py # repeated local MarkItDown comparisons
benchmarks/                # manifest documentation and comparison results
tests/test_regressions.py   # one test per fixed defect + build-integrity check
examples/minibook-epub3.md  # sample output from the pandoc EPUB 3 mini-book fixture
requirements.txt            # pymupdf
```

`structured.py` is inlined into `pdf2md_all.py` with three globals renamed. Edit `structured.py`, then run `python3 tools/sync_structured.py`; it renames NAME tokens only, so a rename can never reach inside a string or a regex. `--check` is wired into CI.

The modular development build (`pdf2md.py`, `regimes.py`, `outline.py`, `doctype.py`, `papers.py`, `decks.py`, `documents.py`, `build_single.py`), the regression suite `test_books.py`, and the PDF / EPUB / DOCX fixtures with their `.md` outputs are kept outside this repository.

---

## License

MIT — see [`LICENSE`](LICENSE).
