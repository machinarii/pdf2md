# Changelog

## Unreleased

- Recover captioned vector figure bounds from clipped drawing paths, combining adjacent panels and replacing fragmentary label crops.
- Keep captions below the crop out of the image padding.
- Increase visual-description output headroom, disable optional thinking, and retain image fallback when Ollama reports a truncated response.
- Evaluate corrected crops with GLM-5.3-Flash cloud; descriptions still require review.

## 0.2.0 — 2026-09-19

- OCR rotated PDF pages and separate image regions on mixed pages, with per-line confidence and overlap checks.
- Recognize two consecutive numbered headings in short documents with strong typographic evidence.
- Accept Unicode heading words and preserve Chinese/Japanese line-joining conventions.
- Retain long numeric tables with a complete text header.
- Discover raster figures and add optional, explicitly labeled vision-model descriptions for RAG.
- Record model and image provenance in `visuals.json`; fix figure links relative to Markdown output.
- Add regression fixtures for the above; equation reconstruction, dewarping, and cross-document training remain unimplemented.

## 0.1.0 — 2026-09-19

First explicit version of the existing converter; this is not its first commit.

- Adaptive PDF layout and text cleanup for books, papers, and other documents.
- EPUB and DOCX readers; DOC, ODT, and RTF through LibreOffice.
- Document trees, source provenance, and optional audited Tesseract OCR.
- Source-annotated quality checks and repeatable local MarkItDown comparisons.
- `--version`, Markdown `generator_version`, and artifact `converter_version`.
- Reproducible output showcase and refreshed project documentation.

Known limits include complex tables, mathematical transcription, unusual layouts,
and OCR accuracy. See the README for details and the scope of validation.
