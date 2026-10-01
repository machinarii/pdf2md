# pdf2md agent skill

Convert documents to Markdown with the [pdf2md CLI](https://github.com/machinarii/pdf2md).
The same skill works with Claude Code, Codex, OpenClaw, and Hermes. It includes
instructions for installing a tested converter revision, ordinary extraction,
selective OCR, figure handling, and checking output against the source.

Requires Python 3.10+, Git for initial installation, and PyMuPDF. Tesseract,
LibreOffice, and Ollama are optional and depend on the requested conversion.
The converter is installed separately; this plugin does not run installation
hooks, require credentials, or start background services.

See [installation and publishing](https://github.com/machinarii/pdf2md/blob/main/docs/agent-skills.md).
