"""Error-path tests.

Every one of these inputs used to reach the user as an uncaught traceback, or
as a confident but wrong diagnosis. A converter that says "this is an
image-only scan, run OCR" when the real fault is a mistyped page range sends
people to spend an hour on the wrong problem, so the message matters as much
as the exit code.
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


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CONVERTER), *args],
        capture_output=True, text=True, timeout=120,
    )


class ErrorPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.pdf = self.tmp / "doc.pdf"
        doc = pymupdf.open()
        for i in range(3):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 120), f"Body text on page {i + 1}.",
                             fontsize=11, fontname="helv")
        doc.save(str(self.pdf))
        doc.close()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def assertClean(self, result: subprocess.CompletedProcess, *needles: str) -> None:
        """Non-zero exit, a readable message, and no Python traceback."""
        self.assertNotEqual(result.returncode, 0)
        blob = result.stdout + result.stderr
        self.assertNotIn("Traceback (most recent call last)", blob, blob)
        for needle in needles:
            self.assertIn(needle, blob, blob)

    def test_non_pdf_with_pdf_extension(self) -> None:
        bad = self.tmp / "fake.pdf"
        bad.write_text("this is not a pdf\n")
        self.assertClean(run(str(bad), "-o", str(self.tmp / "o.md")), "not a PDF")

    def test_directory_as_input(self) -> None:
        d = self.tmp / "adir.pdf"
        d.mkdir()
        self.assertClean(run(str(d), "-o", str(self.tmp / "o.md")), "is a directory")

    def test_encrypted_pdf(self) -> None:
        enc = self.tmp / "enc.pdf"
        doc = pymupdf.open(str(self.pdf))
        doc.save(str(enc), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                 owner_pw="o", user_pw="u")
        doc.close()
        self.assertClean(run(str(enc), "-o", str(self.tmp / "o.md")), "password-protected")

    def test_missing_input(self) -> None:
        self.assertClean(run(str(self.tmp / "nope.pdf")), "not found")

    def test_malformed_page_spec(self) -> None:
        self.assertClean(
            run(str(self.pdf), "--pages", "abc", "-o", str(self.tmp / "o.md")),
            "--pages", "expected numbers")

    def test_backwards_page_range(self) -> None:
        self.assertClean(
            run(str(self.pdf), "--pages", "3-1", "-o", str(self.tmp / "o.md")),
            "runs backwards")

    def test_page_range_out_of_bounds_is_not_called_a_scan(self) -> None:
        """The old code reported an image-only scan and told the user to run OCR."""
        result = run(str(self.pdf), "--pages", "500-600", "-o", str(self.tmp / "o.md"))
        self.assertClean(result, "selects no page", "3-page")
        self.assertNotIn("image-only", result.stdout + result.stderr)

    def test_figure_vlm_requires_figure_dir(self) -> None:
        self.assertClean(
            run(str(self.pdf), "--figure-vlm", "qwen2.5vl:7b", "-o", str(self.tmp / "o.md")),
            "--figure-vlm needs --figure-dir")

    def test_refuses_to_overwrite_input(self) -> None:
        self.assertClean(run(str(self.pdf), "-o", str(self.pdf)), "refusing to overwrite")

    def test_output_parent_directory_is_created(self) -> None:
        out = self.tmp / "deep" / "nested" / "out.md"
        result = run(str(self.pdf), "-o", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.exists())

    def test_non_zip_epub(self) -> None:
        bad = self.tmp / "fake.epub"
        bad.write_text("not a zip\n")
        self.assertClean(run(str(bad), "-o", str(self.tmp / "o.md")), "not a valid EPUB")

    def test_non_zip_docx(self) -> None:
        bad = self.tmp / "fake.docx"
        bad.write_text("not a zip\n")
        self.assertClean(run(str(bad), "-o", str(self.tmp / "o.md")), "not a valid DOCX")

    def test_epub_missing_container(self) -> None:
        bad = self.tmp / "hollow.epub"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
        self.assertClean(run(str(bad), "-o", str(self.tmp / "o.md")), "hollow.epub")

    def test_image_only_pdf_is_still_reported_as_a_scan(self) -> None:
        """The real image-only case must keep its OCR advice."""
        blank = self.tmp / "blank.pdf"
        doc = pymupdf.open()
        doc.new_page(width=595, height=842)
        doc.save(str(blank))
        doc.close()
        self.assertClean(run(str(blank), "-o", str(self.tmp / "o.md")),
                         "image-only", "OCR")


if __name__ == "__main__":
    unittest.main()
