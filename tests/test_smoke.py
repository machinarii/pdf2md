"""Smoke tests for pdf2md_all.py.

Generates small PDF and EPUB fixtures on the fly (no binary fixtures in the
repo) and checks that the converter exits 0 and emits the expected shape:
YAML front matter, a title, headings, and reflowed body text.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
CONVERTER = ROOT / "pdf2md_all.py"


def run_converter(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CONVERTER), *args],
        capture_output=True, text=True, timeout=120,
    )


def make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    for i in range(1, 4):
        page = doc.new_page(width=595, height=842)
        y = 120
        page.insert_text((72, y), f"{i}. Section {i}", fontsize=16, fontname="hebo")
        y += 40
        for k in range(1, 7):
            page.insert_text(
                (72, y),
                f"This is body paragraph line {k} on page {i}, written to look like prose.",
                fontsize=11, fontname="helv",
            )
            y += 16
        y += 24
        page.insert_text((72, y), f"{i}.1 Subsection", fontsize=12, fontname="hebo")
        y += 30
        for k in range(1, 5):
            page.insert_text(
                (72, y),
                f"More body text for the subsection, line {k}, continuing the discussion.",
                fontsize=11, fontname="helv",
            )
            y += 16
    doc.save(str(path))


def make_epub(path: Path) -> None:
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:isbn:9780000000001</dc:identifier>
    <dc:title>The Quiet Machine</dc:title>
    <dc:creator>A. Novelist</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/><itemref idref="ch2"/></spine>
</package>"""
    nav = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc"><ol>
  <li><a href="ch1.xhtml">Chapter 1: Arrival</a></li>
  <li><a href="ch2.xhtml">Chapter 2: The House</a></li>
</ol></nav></body></html>"""
    ch1 = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>Chapter 1: Arrival</h1>
<p>The train reached the coast at dusk. Nobody met her at the station.</p>
<p>She walked the length of the platform twice before choosing a direction.</p>
</body></html>"""
    ch2 = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>Chapter 2: The House</h1>
<p>The house had three rooms and one working lamp.</p>
<ul><li>Water on Tuesdays</li><li>Post at the shop</li></ul>
</body></html>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/nav.xhtml", nav)
        z.writestr("OEBPS/ch1.xhtml", ch1)
        z.writestr("OEBPS/ch2.xhtml", ch2)


class SmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pdf_converts(self) -> None:
        pdf = self.tmp / "smoke.pdf"
        make_pdf(pdf)
        out = self.tmp / "smoke.md"
        result = run_converter(str(pdf), "-o", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        md = out.read_text(encoding="utf-8")
        self.assertTrue(md.startswith("---\n"), md[:200])
        self.assertIn("generator: pdf2md", md)
        self.assertIn("pages: 3", md)
        self.assertIn("This is body paragraph line 1 on page 1", md)
        # Lines are reflowed into paragraphs, not emitted one per line.
        self.assertIn("line 1 on page 1, written to look like prose. This is body", md)

    def test_pdf_profile_and_artifacts(self) -> None:
        pdf = self.tmp / "smoke.pdf"
        make_pdf(pdf)
        result = run_converter(str(pdf), "--profile")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Content census", result.stdout)

        artifacts = self.tmp / "artifacts"
        result = run_converter(str(pdf), "-o", str(self.tmp / "a.md"), "--artifacts", str(artifacts))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((artifacts / "blocks.jsonl").exists())

    def test_epub_converts(self) -> None:
        epub = self.tmp / "mini.epub"
        make_epub(epub)
        out = self.tmp / "mini.md"
        result = run_converter(str(epub), "-o", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        md = out.read_text(encoding="utf-8")
        self.assertIn("title: The Quiet Machine", md)
        self.assertIn("- A. Novelist", md)
        self.assertIn("9780000000001", md)
        self.assertIn("# Chapter 1: Arrival", md)
        self.assertIn("# Chapter 2: The House", md)
        self.assertIn("- Water on Tuesdays", md)


if __name__ == "__main__":
    unittest.main()
