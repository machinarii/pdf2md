"""Regression tests, one per defect found in the audit.

Each test names the failure it locks down. Most were silent: the converter
exited 0 and produced a plausible-looking file with content missing from it,
which is the worst failure mode a document converter has.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
CONVERTER = ROOT / "pdf2md_all.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf2md_all", CONVERTER)
    m = importlib.util.module_from_spec(spec)
    sys.modules["pdf2md_all"] = m
    spec.loader.exec_module(m)
    return m


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CONVERTER), *args],
                          capture_output=True, text=True, timeout=180)


def epub(path: Path, chapters: list[tuple[str, str]], *, nav: bool = True,
         extra: dict[str, bytes] | None = None) -> None:
    """Minimal but valid EPUB 3 with one XHTML file per chapter."""
    manifest, spine, navlis = [], [], []
    for i, (name, _) in enumerate(chapters):
        manifest.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        navlis.append(f'<li><a href="{name}">Chapter {i + 1}</a></li>')
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">x</dc:identifier><dc:title>Test Book</dc:title>
    <dc:creator>A Person</dc:creator><dc:language>en</dc:language>
  </metadata>
  <manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  {''.join(manifest)}</manifest>
  <spine>{''.join(spine)}</spine>
</package>"""
    navdoc = ('<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" '
              'xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol>'
              + "".join(navlis) + "</ol></nav></body></html>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", opf)
        if nav:
            z.writestr("OEBPS/nav.xhtml", navdoc)
        for name, body in chapters:
            z.writestr(f"OEBPS/{name}",
                       '<?xml version="1.0" encoding="utf-8"?>'
                       '<html xmlns="http://www.w3.org/1999/xhtml" '
                       'xmlns:epub="http://www.idpf.org/2007/ops"><body>' + body + "</body></html>")
        for k, v in (extra or {}).items():
            z.writestr(k, v)


class BuildIntegrity(unittest.TestCase):
    def test_single_file_build_matches_the_module(self):
        """A rename applied without word boundaries once rewrote a regex
        literal inside the merged build, disabling EPUB heading de-duplication
        in the shipped file while structured.py stayed correct."""
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_structured.py"), "--check"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_corrupted_word_boundary_regex(self):
        self.assertNotIn(r'\WML', CONVERTER.read_text())


class StructuredRegressions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def convert(self, src: Path, *args: str) -> str:
        out = self.tmp / (src.stem + ".md")
        r = run(str(src), "-o", str(out), *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return out.read_text(encoding="utf-8")

    def test_div_footnote_does_not_swallow_the_rest_of_the_chapter(self):
        """<div class="footnote"> pushed a note that nothing ever popped, so
        every later paragraph in the file was relabelled a footnote."""
        src = self.tmp / "divnote.epub"
        epub(src, [("c1.xhtml",
                    "<h1>Chapter One</h1>"
                    "<p>FIRST body paragraph of ordinary chapter prose here.</p>"
                    '<div class="footnote" id="fn1"><p>1. The footnote body.</p></div>'
                    "<p>SECOND body paragraph, still ordinary chapter prose here.</p>"
                    "<h2>Section Two</h2>"
                    "<p>THIRD body paragraph under a later heading, still prose.</p>")])
        md = self.convert(src)
        self.assertEqual(md.count("\n[^"), 1, md)
        for marker in ("FIRST", "SECOND", "THIRD"):
            self.assertIn(marker, md, md)
        self.assertIn("Section Two", md)

    def test_inline_toc_section_does_not_truncate_the_file(self):
        """`toc` in epub:type raised a skip counter that only script/style/nav
        ever lowered, so everything after an inline contents block vanished."""
        src = self.tmp / "toc.epub"
        epub(src, [("c1.xhtml",
                    "<h1>Chapter One</h1><p>Paragraph before the inline contents.</p>"
                    '<section epub:type="toc"><ol><li>a</li><li>b</li></ol></section>'
                    "<h2>Section Two</h2><p>TAIL paragraph that must survive.</p>")])
        md = self.convert(src)
        self.assertIn("TAIL paragraph that must survive", md)
        self.assertIn("Section Two", md)

    def test_unclosed_tag_inside_noteref_does_not_drop_the_rest(self):
        src = self.tmp / "unclosed.epub"
        epub(src, [("c1.xhtml",
                    "<h1>Chapter</h1>"
                    '<p>Claim<a epub:type="noteref" href="#fn1"><b>1</a></p>'
                    "<p>SURVIVOR paragraph one of ordinary prose.</p>"
                    "<p>SURVIVOR paragraph two of ordinary prose.</p>")])
        md = self.convert(src)
        self.assertEqual(md.count("SURVIVOR"), 2, md)
        self.assertNotIn("****", md)

    def test_nested_table_keeps_the_outer_cells(self):
        src = self.tmp / "nested.epub"
        epub(src, [("c1.xhtml",
                    "<h1>C</h1><table><tr><td>OUTERA</td>"
                    "<td><table><tr><td>INNER</td></tr></table></td></tr>"
                    "<tr><td>OUTERB</td><td>OUTERC</td></tr></table>")])
        md = self.convert(src)
        for cell in ("OUTERA", "OUTERB", "OUTERC", "INNER"):
            self.assertIn(cell, md, md)

    def test_cross_file_endnote_reference_matches_its_definition(self):
        """Namespacing by the referring file left every endnote collected in a
        separate spine document dangling."""
        src = self.tmp / "split.epub"
        epub(src, [("c1.xhtml",
                    "<h1>Chapter</h1><p>Some claim of sufficient length here."
                    '<a epub:type="noteref" href="notes.xhtml#fn1">1</a> More text.</p>'),
                   ("notes.xhtml",
                    '<section epub:type="endnotes"><ol><li id="fn1">The note body.</li></ol></section>')])
        md = self.convert(src)
        refs = set(__import__("re").findall(r"\[\^([^\]]+)\]", md))
        self.assertEqual(len(refs), 1, f"reference and definition disagree: {refs}\n{md}")

    def test_mislabelled_latin1_text_is_recovered_not_replaced(self):
        src = self.tmp / "latin1.epub"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml",
                       '<?xml version="1.0"?><container version="1.0" '
                       'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="c.opf" media-type="application/oebps-package+xml"/>'
                       "</rootfiles></container>")
            z.writestr("c.opf",
                       '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
                       'version="3.0" unique-identifier="u"><metadata '
                       'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="u">x'
                       "</dc:identifier><dc:title>T</dc:title><dc:language>en</dc:language>"
                       '</metadata><manifest><item id="a" href="a.xhtml" '
                       'media-type="application/xhtml+xml"/></manifest>'
                       '<spine><itemref idref="a"/></spine></package>')
            # declares utf-8, is actually latin-1 -- common in the wild
            z.writestr("a.xhtml", '<?xml version="1.0" encoding="utf-8"?>'
                       '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                       "<h1>Caf\xe9 Chapter</h1><p>Na\xefve r\xe9sum\xe9 text here.</p>"
                       "</body></html>".encode("latin-1"))
        md = self.convert(src)
        self.assertIn("Café", md)
        self.assertNotIn("\ufffd", md)

    def test_malformed_font_size_is_not_fatal(self):
        src = self.tmp / "badcss.epub"
        epub(src, [("c1.xhtml", '<p class="x">Body text of a paragraph here.</p>')],
             extra={"OEBPS/s.css": b".x{font-size:1.2.3pt}"})
        # the stylesheet is only read when the manifest lists it; either way
        # the converter must not crash
        r = run(str(src), "-o", str(self.tmp / "o.md"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class CoreRegressions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.m = load_module()

    def tearDown(self):
        self._tmp.cleanup()

    def test_year_led_heading_does_not_hijack_the_outline_spine(self):
        """"2019 Annual Review" tokenised as section 20, which advanced the
        numbering spine past every real chapter and demoted them to prose."""
        for text in ("2019 Annual Review of Operations", "1984 and Beyond"):
            tok = self.m.OL.tokenize(text)
            self.assertIsNone(tok.num, f"{text} -> {tok.num}")
        self.assertEqual(self.m.OL.tokenize("6.2 Real Section").num, (6, 2))
        self.assertEqual(self.m.OL.tokenize("A.1 Appendix bit").num, ("A", 1))

    def test_yaml_values_with_backslashes_parse(self):
        v = self.m._yq(r"Windows C:\path guide")
        self.assertEqual(v, '"Windows C:\\\\path guide"')

    def test_ordered_list_escape_lands_on_the_delimiter(self):
        """A backslash before a digit is not a Markdown escape; it rendered
        literally and neutralised nothing."""
        self.assertEqual(self.m.escape_md("2023. was a big year"), "2023\\. was a big year")
        self.assertEqual(self.m.escape_md("# not a heading"), "\\# not a heading")
        self.assertEqual(self.m.escape_md("1.5 million people"), "1.5 million people")

    def test_parenthetical_headings_are_accepted(self):
        for t in ("Bandits (Revisited)", "Notes (2019)", "The Method [Draft]"):
            self.assertTrue(self.m.heading_text_ok(t), t)

    def test_page_spec_is_sorted_and_deduplicated(self):
        self.assertEqual(list(self.m.parse_pages("1,1", 5)), [0])
        self.assertEqual(list(self.m.parse_pages("3,1", 5)), [0, 2])

    def test_emit_json_survives_a_document_with_a_table(self):
        """Line.region and Line.table hold back-references, and asdict()
        recursed through them until the stack blew."""
        pdf = self.tmp / "t.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        y = 100
        for row in (("name", "score", "rank"), ("alpha", "12", "1"),
                    ("beta", "9", "2"), ("gamma", "7", "3"), ("delta", "5", "4")):
            for x, cell in zip((72, 220, 360), row):
                page.insert_text((x, y), cell, fontsize=11, fontname="helv")
            y += 22
        doc.save(str(pdf)); doc.close()
        out = self.tmp / "t.json"
        r = run(str(pdf), "-o", str(self.tmp / "t.md"), "--emit-json", str(out))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("RecursionError", r.stdout + r.stderr)
        self.assertTrue(json.loads(out.read_text()))

    def test_untitled_document_gets_a_name_not_a_bare_hash(self):
        pdf = self.tmp / "untitled.pdf"
        doc = pymupdf.open()
        p = doc.new_page(width=595, height=842)
        yy = 100
        for i in range(12):
            p.insert_text((72, yy), f"Ordinary body prose line {i} of this document.",
                          fontsize=11, fontname="helv")
            yy += 16
        doc.save(str(pdf)); doc.close()
        out = self.tmp / "untitled.md"
        r = run(str(pdf), "-o", str(out), "--doc-type", "book")
        self.assertEqual(r.returncode, 0, r.stderr)
        md = out.read_text()
        self.assertNotIn("\n# \n", md, "emitted an empty ATX heading")
        self.assertNotIn('title: ""', md)


if __name__ == "__main__":
    unittest.main()
