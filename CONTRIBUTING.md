# Contributing

Small, source-backed fixes are welcome. Open an issue describing the source layout,
expected Markdown, actual output, command, and `python3 pdf2md_all.py --version`.
Attach a minimal PDF only if you have permission to share it; remove private text
and metadata first. Generated fixtures are preferred for regression tests.

For code changes:

```bash
pip install -r requirements.txt
pip install ruff
python3 -m unittest discover -s tests -v
python3 tools/sync_structured.py --check
ruff check --select F,E9 pdf2md_all.py structured.py tools tests examples/comparison
```

Install Tesseract and English language data to exercise the optional OCR integration
test. Edit `structured.py` for EPUB/DOCX reader changes, then synchronize with
`python3 tools/sync_structured.py`. PDF pipeline changes go in `pdf2md_all.py`.

Keep fixes grounded in source pages, record limitations, and avoid claiming that
syntax checks establish extraction accuracy. Do not commit private library files
or generated audit directories. The comparison guide in `benchmarks/README.md`
explains how to evaluate text and structure on your own files.

Version numbers follow semantic versioning while the project is pre-1.0. The
canonical version is `__version__` in `pdf2md_all.py`; update the changelog and
README badge when changing it. A version in source does not imply a published
package, Git tag, or GitHub release.
