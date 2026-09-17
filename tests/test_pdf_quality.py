"""Layout and text regressions using generated, inspectable PDFs."""
from pathlib import Path
import tempfile
import unittest

import pymupdf

from test_regressions import load_module, run


class PDFQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def line(self, text, x=50, y=100, width=210, page=0, font='Helvetica', size=11):
        return self.m.Line(page, text, x, y, x + width, y + size,
                           size, (font,), False, False, False, 0,
                           style=(font, size))

    def test_short_paper_columns_are_not_interleaved(self):
        lines = [self.line(f'{side} paragraph line {i}', x=x, y=120+i*16)
                 for i in range(8) for side, x in [('Left', 50), ('Right', 320)]]
        self.assertEqual(self.m.reorder_columns(lines, 600), 1)
        self.assertEqual([l.text.split()[0] for l in lines], ['Left']*8 + ['Right']*8)

    def test_layout_changes_and_spanning_heading(self):
        lines = []
        for page, starts in enumerate([(50, 320), (65, 370)]):
            for ybase in (100, 320):
                lines.extend(self.line(f'Column {x} text {i}', x=x, y=ybase+i*16,
                                       page=page) for i in range(8) for x in starts)
            lines.append(self.line('A heading across the page', x=50, y=270,
                                   width=520, page=page))
        lines.extend(self.line(f'Single column paragraph {i}', width=480,
                               y=100+i*16, page=2) for i in range(12))
        self.assertEqual(self.m.reorder_columns(lines, {0:600, 1:680, 2:600}), 2)
        for page in (0, 1):
            pl = [l for l in lines if l.page == page]
            heading = next(i for i, l in enumerate(pl) if l.text.startswith('A heading'))
            self.assertEqual(heading, 16)
            self.assertTrue(all(l.y0 < 270 for l in pl[:heading]))
            self.assertTrue(all(l.y0 > 270 for l in pl[heading+1:]))
        self.assertTrue(all(l.col == -1 for l in lines if l.page == 2))

    def test_short_table_cells_do_not_become_prose_columns(self):
        lines = [self.line(str(i), x=x, y=100+i*16, width=20)
                 for i in range(8) for x in (50, 250, 450)]
        self.assertEqual(self.m.reorder_columns(lines, 600), 0)

    def test_one_font_ebook_is_not_ocr(self):
        lines = [self.line('Ordinary ebook prose') for _ in range(20)]
        self.assertFalse(self.m.is_ocr_layer(lines))
        for l in lines:
            l.style = ('GlyphLessFont', 11)
        self.assertTrue(self.m.is_ocr_layer(lines))

    def test_repeated_text_on_one_page_is_not_running_furniture(self):
        with pymupdf.open() as doc:
            doc.new_page(width=600, height=800)
            lines = [self.line('Repeated label', x=50+i*100, y=25) for i in range(4)]
            lines += [self.line('Ordinary body text with enough characters', y=120+i*16)
                      for i in range(10)]
            prof = self.m.build_profile(lines, doc, range(1))
            self.assertNotIn('Repeated label', prof.running_heads)

    def test_learns_italic_headings_but_not_italic_paragraphs(self):
        with pymupdf.open() as doc:
            lines = []
            for page in range(3):
                doc.new_page(width=600, height=800)
                lines.append(self.line('Observations', page=page, font='Helvetica-Oblique'))
                lines += [self.line('Ordinary body text with enough characters for prose.',
                                    page=page, y=140+i*16) for i in range(12)]
            prof = self.m.build_profile(lines, doc, range(3))
            self.assertIn(('Helvetica-Oblique', 11), prof.adaptive_styles)
            self.assertTrue(prof.learning_evidence)
            for l in lines:
                if l.style[0] == 'Helvetica-Oblique':
                    l.text = 'This is an italic paragraph of ordinary prose and is not a section heading.'
            prof = self.m.build_profile(lines, doc, range(3))
            self.assertFalse(prof.adaptive_styles)

    def test_reflow_uses_document_spelling_for_compounds(self):
        vocab = self.m.learn_word_forms([self.line('We use self-supervised learning.')])
        self.assertEqual(self.m.reflow(['A self-', 'supervised method.'], vocab),
                         'A self-supervised method.')
        self.assertEqual(self.m.reflow(['An inter-', 'national study.'], vocab),
                         'An international study.')
        self.assertEqual(self.m.reflow(['Une expé-', 'rience.'], vocab), 'Une expérience.')

    def test_heading_density_does_not_cross_pages(self):
        lines = []
        for page in range(3):
            for i in range(3):
                line = self.line(f'Section label {i}', page=page, y=100+i*100)
                line.kind = 'heading'
                lines.append(line)
        self.assertEqual(self.m.demote_dense_headings(lines), 0)
        for line in lines:
            line.page = 0
        self.assertGreater(self.m.demote_dense_headings(lines), 0)

    def test_learned_subheading_is_not_absorbed_into_chapter_title(self):
        chapter = self.line('Chapter 1', font='Helvetica-Bold', size=18)
        sub = self.line('Observations', font='Helvetica-Oblique', y=145)
        chapter.kind = sub.kind = 'heading'
        prof = self.m.Profile(doc_type='book', canonical_title='Test')
        prof.adaptive_styles.add(sub.style)
        prof.heading_styles = {chapter.style: 1, sub.style: 2}
        md = self.m.assemble([chapter, sub], prof, make_toc=False)
        self.assertIn('# Chapter 1\n', md)
        self.assertIn('## Observations\n', md)

    def test_clean_markdown_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp)/'paper.pdf', Path(tmp)/'paper.md'
            with pymupdf.open() as doc:
                p = doc.new_page(width=600, height=800)
                p.insert_text((50, 80), 'A Study of Reading Order', fontsize=20, fontname='hebo')
                p.insert_text((50, 115), 'Abstract', fontsize=12, fontname='hebo')
                p.insert_text((50, 140), 'We examine self-supervised learning and document conversion.', fontsize=11)
                p.insert_text((50, 190), '1 Introduction', fontsize=14, fontname='hebo')
                left = ['The left column begins with self-', 'supervised learning and inter-',
                        'national studies of text extraction.']
                left += [f'Left discussion continues on line {i}.' for i in range(5)]
                right = [f'Right discussion continues on line {i}.' for i in range(8)]
                for x, texts in [(50,left), (320,right)]:
                    for i, text in enumerate(texts):
                        p.insert_text((x, 220+i*16), text, fontsize=11)
                doc.save(src)
            result = run(str(src), '-o', str(out), '--doc-type', 'paper', '--no-toc')
            self.assertEqual(result.returncode, 0, result.stderr)
            md = out.read_text()
            self.assertIn('self-supervised learning and international studies', md)
            self.assertLess(md.index('Left discussion continues on line 4'),
                            md.index('Right discussion continues on line 0'))
            self.assertRegex(md, r'(?m)^#{1,6} .*Introduction')
            self.assertNotIn('\ufffd', md)


if __name__ == '__main__':
    unittest.main()
