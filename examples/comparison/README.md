# Reproducible output showcase

The source is an original, synthetic one-page document with two columns and six
short paragraphs. Its text and generator are covered by the repository's MIT
license. No private library text or third-party book excerpts are included.

- [Source preview](source.png)
- [Source generator](generate.py)
- [Unedited pdf2md output](pdf2md.md)
- [Unedited MarkItDown output](markitdown.md)

Recorded with pdf2md 0.1.0, PyMuPDF 1.28.2, MarkItDown 0.1.7 and pdfminer-six
20260107 on Python 3.14.7. No OCR, plugins, cloud backends or postprocessing.
The source preview was visually checked against the text and column layout.

From the repository root:

```bash
pip install -r requirements.txt
pip install 'markitdown[pdf]==0.1.7'
python3 examples/comparison/generate.py
python3 pdf2md_all.py artifacts/readme-demo/source.pdf --no-toc -o artifacts/readme-demo/pdf2md.md
python3 - <<'PY'
from pathlib import Path
from markitdown import MarkItDown
result = MarkItDown(enable_plugins=False).convert_local('artifacts/readme-demo/source.pdf')
Path('artifacts/readme-demo/markitdown.md').write_text(result.text_content, encoding='utf-8')
PY
```

The generator also writes `artifacts/readme-demo/source.png`. Output can change
with dependency versions; the versions above identify this recorded example.

## What it demonstrates

pdf2md joins printed lines into complete paragraphs and reads the left column
before the right. MarkItDown retains printed line breaks and interleaves the
columns' paragraphs on this source. pdf2md also produces a title heading and
YAML metadata.

Both converters miss the section heading tags in this particular example.
The README comparison preserves the complete body from both outputs, including
both section labels and all six paragraphs. Only the title blocks and metadata
are omitted from the table; the complete files retain them. A Markdown renderer may collapse
single newlines visually, but that does not correct the interleaved column order.

This is a designed demonstration of two behaviors, not a random or held-out
benchmark. It does not evaluate tables, equations, OCR or a full range of heading
styles. See the [development comparison](../../benchmarks/comparison-2026-09-19.md)
for the separate real-file measurements and their limitations.

## Book cleanup gallery

`generate_book.py` creates a three-page original book excerpt with chapter
headings, line-wrapped words, repeated running headers, and page numbers. The
body text is deliberately repeated across the three chapters to isolate these
behaviors. It is a synthetic demonstration, not a natural-document benchmark.

- [Generator](generate_book.py) and [first source page](book/source.png)
- [Complete pdf2md output](book/pdf2md.md)
- [Complete MarkItDown output](book/markitdown.md)

Use the same dependencies as above, then run:

```bash
python3 examples/comparison/generate_book.py
python3 pdf2md_all.py artifacts/readme-demo/book/source.pdf --no-toc -o artifacts/readme-demo/book/pdf2md.md
python3 - <<'PY'
from pathlib import Path
from markitdown import MarkItDown
result = MarkItDown(enable_plugins=False).convert_local('artifacts/readme-demo/book/source.pdf')
Path('artifacts/readme-demo/book/markitdown.md').write_text(result.text_content, encoding='utf-8')
PY
```

The gallery shows paragraph/word reflow, preservation of an observed compound,
and removal of running furniture around a recovered chapter heading. README
excerpts preserve output; the form-feed character is displayed as `␌` for
visibility. Full files retain the original character. The generated page was
visually inspected. pdf2md still falls back to the filename for this coverless
book's title instead of using the PDF's title metadata; no override was applied.
These examples do not establish that pdf2md is better for every document.
