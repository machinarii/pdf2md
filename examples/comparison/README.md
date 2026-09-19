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
The README excerpts preserve exact output and stop at paragraph boundaries;
the complete files retain the whole document. A Markdown renderer may collapse
single newlines visually, but that does not correct the interleaved column order.

This is a designed demonstration of two behaviors, not a random or held-out
benchmark. It does not evaluate tables, equations, OCR or a full range of heading
styles. See the [development comparison](../../benchmarks/comparison-2026-09-19.md)
for the separate real-file measurements and their limitations.
