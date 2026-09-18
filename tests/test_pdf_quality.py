"""Layout and text regressions using generated, inspectable PDFs."""
from pathlib import Path
import re
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

    def test_rotated_pages_are_read_in_reading_order(self):
        """A landscape scan-free PDF stores upright text plus /Rotate 90.

        get_text() then reports dir and bbox in unrotated space while
        page.rect is the rotated one, so an unaware reader throws every line
        away as sideways and reports an image-only scan.
        """
        want = ['Rotated Heading'] + [f'Body line {i} of the rotated page.'
                                      for i in range(6)]
        for rotation in (90, 270):
            with pymupdf.open() as doc:
                page = doc.new_page(width=612, height=792)
                page.set_rotation(rotation)
                # place each line where the *reader* sees it, then write it in
                # the page's own unrotated frame, the way a real landscape PDF
                # from Quartz or InDesign stores it
                back = page.derotation_matrix
                for i, text in enumerate(want):
                    page.insert_text(pymupdf.Point(60, 70 + i * 20) * back,
                                     text, fontsize=11, rotate=rotation)
                lines = self.m.extract_lines(doc, range(1))
            self.assertEqual([l.text.strip() for l in lines], want,
                             f'/Rotate {rotation}')
            # geometry must be expressed in the frame page.rect describes
            self.assertTrue(all(l.x1 <= 792 and l.y1 <= 612 for l in lines),
                            f'/Rotate {rotation}: boxes left in unrotated space')

    def test_sideways_text_on_an_upright_page_is_still_set_aside(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=612, height=792)
            for i in range(6):
                page.insert_text((60, 120 + i * 18), f'Body line {i} of prose.', fontsize=11)
            page.insert_text((30, 400), 'arXiv:2401.00001v1', fontsize=9, rotate=90)
            lines = self.m.extract_lines(doc, range(1))
        self.assertNotIn('arXiv:2401.00001v1', [l.text.strip() for l in lines])
        self.assertIn('arXiv:2401.00001v1', ''.join(self.m.ROTATED_TEXT))

    def slide(self, page, title, bullets, *, size=24, body=14):
        """One slide: a display-sized title over body-sized bullets."""
        out = [self.line(title, y=60, size=size, page=page)]
        out += [self.line(b, x=70, y=140 + i * 22, size=body, page=page)
                for i, b in enumerate(bullets)]
        return out

    def deck(self, slides):
        lines = [l for s in slides for l in s]
        prof = self.m.Profile(doc_type='deck', body_size=14)
        self.m.label_deck(lines, prof)
        return [l for l in lines if l.kind != 'consumed']

    def test_animation_build_collapses_to_one_slide(self):
        """One PDF page per click is one slide, not four."""
        reveal = ['Engineers', 'End Users', 'Regulators', 'Auditors']
        kept = self.deck([self.slide(0, 'Cover', ['a', 'b', 'c']),
                          self.slide(1, 'Executives', reveal[:1]),
                          self.slide(2, 'Executives', reveal[:2]),
                          self.slide(3, 'Executives', reveal[:3]),
                          self.slide(4, 'Executives', reveal)])
        heads = [l.text for l in kept if l.kind == 'heading']
        self.assertEqual(heads.count('Executives'), 1)
        self.assertEqual(sorted(l.text for l in kept
                                if l.kind == 'list_item' and l.page), sorted(reveal))

    def test_a_build_that_removes_an_overlay_keeps_the_fuller_slide(self):
        kept = self.deck([self.slide(0, 'Cover', ['a', 'b', 'c']),
                          self.slide(1, 'Method', ['Step one', 'Callout', 'Step two']),
                          self.slide(2, 'Method', ['Step one', 'Step two'])])
        self.assertEqual([l.text for l in kept if l.kind == 'heading'].count('Method'), 1)
        self.assertIn('Callout', [l.text for l in kept if l.kind == 'list_item'])

    def test_two_real_slides_sharing_a_title_are_both_kept(self):
        kept = self.deck([self.slide(0, 'Cover', ['a', 'b', 'c']),
                          self.slide(1, 'Results', ['Accuracy rose', 'on every split']),
                          self.slide(2, 'Results', ['Latency fell', 'on every split'])])
        self.assertEqual([l.text for l in kept if l.kind == 'heading'].count('Results'), 2)

    def test_a_wrapped_slide_title_is_one_heading(self):
        lines = self.slide(0, 'Cover', ['a', 'b', 'c'])
        lines += [self.line('Specific: The', y=70, size=18, page=1),
                  self.line('Prioritization', y=92, size=18, page=1),
                  self.line('Exercise', y=114, size=18, page=1),
                  self.line('How to run it', y=157, size=18, page=1),
                  self.line('Score each item', y=179, size=18, page=1)]
        self.m.label_deck(lines, self.m.Profile(doc_type='deck', body_size=18))
        heads = [l.text for l in lines if l.kind == 'heading' and l.page == 1]
        self.assertEqual(heads, ['Specific: The Prioritization Exercise'])
        self.assertIn('How to run it', [l.text for l in lines if l.kind == 'list_item'])

    def test_private_use_glyphs_do_not_reach_the_markdown(self):
        # Wingdings and Symbol land in the PUA with no Unicode meaning
        self.assertEqual(self.m.repair_span(' Decreased fixation', 'Wingdings'),
                         '• Decreased fixation')
        self.assertEqual(self.m.repair_span('England  2022 MIT', 'Times'),
                         'England  2022 MIT')

    def test_a_section_number_stays_with_its_own_title(self):
        """LaTeX puts '4.1' and its title on one baseline, a hair apart in y."""
        num = self.line('4.1', x=306.6, y=259.71, width=20)
        title = self.line('Repeated Sampling and Output Variabil-', x=333.5, y=259.70)
        lines = [self.line(f'Body line {i}', x=306.6, y=100 + i * 14) for i in range(6)]
        lines += [num, title]
        lines += [self.line(f'More body {i}', x=306.6, y=300 + i * 14) for i in range(6)]
        lines += [self.line(f'Left column {i}', x=50, y=100 + i * 14) for i in range(14)]
        self.assertEqual(self.m.reorder_columns(lines, 600), 1, 'fixture must be two-column')
        order = [l.text for l in lines]
        self.assertLess(order.index('4.1'), order.index(title.text),
                        'the number must precede the title it numbers')

    def test_a_numbered_heading_absorbs_its_own_wrapped_tail(self):
        num = self.line('4.1', y=259.7, width=20)
        title = self.line('Repeated Sampling and Output Variabil-', x=80, y=259.7)
        tail = self.line('ity', x=80, y=273.7)
        num.kind = title.kind = 'heading'
        num.level = title.level = 2
        tail.kind = 'body'
        self.m._PROF = self.m.Profile(doc_type='paper')
        self.m._WORD_FORMS = set()
        out = self.m.merge_split_headings([num, title, tail])
        self.assertEqual([l.text for l in out], ['4.1 Repeated Sampling and Output Variability'])

    def test_acm_front_matter_does_not_become_affiliations(self):
        """A CHI title block holds keywords and ACM codes, not just addresses."""
        self.assertTrue(self.m.is_affiliation('RWTH Aachen'))
        self.assertTrue(self.m.is_affiliation('University of California, Berkeley'))
        self.assertTrue(self.m.is_affiliation('Berkeley, CA 94720'))
        for label in ('Author Keywords', 'Keywords', 'General Terms',
                      'Design, Human Factors, Theory',
                      'ACM Classification Keywords',
                      'H.5.2 Information interfaces and presentation: User',
                      '(Dated: September 16, 2026)',
                      'Copyright is held by the author/owner(s).'):
            self.assertFalse(self.m.is_affiliation(label), label)
        self.assertFalse(self.m.is_affiliation(
            'This video features a scaled prototype of RWal that was built.'))

    def test_the_title_page_is_chosen_over_the_half_title_and_backlist(self):
        """Front matter offers several display-set pages; only one is it."""
        join = lambda v: " ".join(l.text.strip() for l in v)

        def page(n, *spec):
            return [self.line(t, page=n, size=s) for t, s in spec]

        # the half-title is set *bigger* than the title page it faces
        half = page(1, ('Commensality', 52))
        title = page(3, ('Commensality', 21), ('From Everyday Food to Feast', 20))
        ornament = page(0, ('‹', 93))          # a printer's mark, alone
        backlist = page(7, *[(f'Other Books {i}', 10) for i in range(9)])

        pages = {1: half, 3: title}
        self.assertEqual(self.m.pick_title_page(pages, 11.0, join),
                         'Commensality From Everyday Food to Feast')
        # a longer page set in body type is a backlist, not a title page
        pages = {1: half, 3: title, 7: backlist}
        self.assertEqual(self.m.pick_title_page(pages, 11.0, join),
                         'Commensality From Everyday Food to Feast')
        # an ornament is display-set but carries no title block
        pages = {0: ornament, 3: title}
        self.assertEqual(self.m.pick_title_page(pages, 11.0, join),
                         'Commensality From Everyday Food to Feast')
        self.assertEqual(self.m.pick_title_page({}, 11.0, join), '')

    def test_a_dedication_set_in_display_type_is_still_a_dedication(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.insert_text((60, 300), 'For Damian Kelly', fontsize=17)
            page.insert_text((60, 330), 'and for the thousands of students.', fontsize=17)
            for n in range(3):                      # body, so a regime exists
                body = doc.new_page(width=600, height=800)
                body.insert_text((60, 60), f'Chapter {n + 1}', fontsize=18, fontname='hebo')
                for i in range(30):
                    body.insert_text((60, 100 + i * 22),
                                     f'Ordinary body prose number {i} on page {n}.', fontsize=11)
            lines = self.m.extract_lines(doc, range(4))
            prof = self.m.build_profile(lines, doc, range(4))
            prof.doc_type = 'book'
            # front matter is whatever precedes the first Chapter heading
            for l in lines:
                if l.text.strip().startswith('Chapter'):
                    l.kind, l.level = 'heading', 1
            self.m.assign_regimes(lines, prof)
        ded = [l for l in lines if l.text.startswith('For Damian')]
        self.assertEqual(ded[0].kind, 'dedication',
                         'display type is how dedications are set, not evidence against')

    def test_every_genre_records_what_it_was_identified_as(self):
        """Books were the one genre whose front matter omitted `type`."""
        for kind in ('book', 'paper', 'deck', 'document'):
            prof = self.m.Profile(doc_type=kind, canonical_title='A Title',
                                  source_name='in.pdf', page_count=10)
            line = self.line('Body text for the document.')
            line.kind = 'body'
            md = self.m.assemble([line], prof, make_toc=False)
            self.assertRegex(md, rf'(?m)^type: {kind}$', kind)

    def test_a_soft_hyphen_at_a_line_end_rejoins_the_word(self):
        """A discretionary hyphen means the word was broken here."""
        self.assertEqual(self.m.reflow(['How­', 'ever, we find'], set()),
                         'However, we find')
        self.assertEqual(self.m.reflow(['illus­', 'trates the point'], set()),
                         'illustrates the point')
        self.assertTrue(self.m.looks_continued('and audi­', 'ence'))
        # the glyph has width, so the span joiner can leave a space after it
        self.assertEqual(self.m.repair_line('How­ ever'), 'However')

    def test_layout_whitespace_does_not_reach_the_markdown(self):
        self.assertEqual(self.m.repair_line('3.2.\t Critical Design'),
                         '3.2. Critical Design')
        self.assertEqual(self.m.repair_line('a    b'), 'a b')
        self.assertEqual(self.m.repair_line('    indented code'), '    indented code')

    def test_latexit_annotations_are_not_content(self):
        """Inkscape keeps a figure label's LaTeX source in an invisible tag."""
        self.assertEqual(
            self.m.repair_line('ILe0ceitYDymWP4A/T5A+UkjqQ=</latexit>w2 = 0.6'),
            'w2 = 0.6')
        self.assertEqual(
            self.m.repair_line('F/7x2htFVMBYqzZArNl8UZJgQqa/k57QnKEcWUKZFvZWwgZU4Y2oaINw='), '')
        self.assertEqual(self.m.repair_line('ordinary prose here'), 'ordinary prose here')

    def test_revtex_roman_sections_become_headings(self):
        """REVTeX centres 'I. INTRODUCTION' in the body face at body size."""
        prof = self.m.Profile(doc_type='paper', body_size=10, body_left=50)
        lines = []
        for n, name in enumerate(['I. INTRODUCTION', 'II. THEORY', 'III. RESULTS'], 1):
            head = self.line(name, x=240, y=100 + n * 200)     # centred, not at margin
            head.isolated = True
            lines.append(head)
            lines += [self.line(f'Section {n} prose line {i}.', y=120 + n * 200 + i * 12)
                      for i in range(6)]
        self.assertEqual(self.m.promote_roman_sections(lines, prof), 3)
        self.assertEqual([l.text for l in lines if l.kind == 'heading'],
                         ['I. INTRODUCTION', 'II. THEORY', 'III. RESULTS'])
        self.assertTrue(all(l.level == 1 for l in lines if l.kind == 'heading'))

    def test_a_stray_roman_initial_does_not_start_a_spine(self):
        prof = self.m.Profile(doc_type='paper', body_size=10, body_left=50)
        lines = [self.line('V. Smith, Some paper title', x=50, y=100),
                 self.line('I. Jones, Another paper', x=50, y=120)]
        lines += [self.line(f'Reference {i} text.', y=140 + i * 12) for i in range(8)]
        self.assertEqual(self.m.promote_roman_sections(lines, prof), 0)

    def test_ieee_inline_abstract_is_recognised(self):
        # IEEE writes 'Abstract—' with no space at all after the dash
        self.assertTrue(self.m.ABSTRACT_INLINE_RE.match('Abstract—Extending the model'))
        self.assertTrue(self.m.ABSTRACT_INLINE_RE.match('Abstract. This paper shows'))
        self.assertTrue(self.m.ABSTRACT_INLINE_RE.match('Abstract: We show'))
        self.assertIsNone(self.m.ABSTRACT_INLINE_RE.match('Abstraction is a tool'))

    def test_a_page_about_copyright_is_not_a_copyright_page(self):
        """The rule counts keywords; a real colophon is also short."""
        prose = ('Copyright law and the right to copy are contested. '
                 'All rights reserved is a phrase first published widely, and '
                 'the printing of such notices became routine. ') * 30
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            for i, chunk in enumerate(re.findall(r'.{1,90}(?:\s|$)', prose)[:40]):
                page.insert_text((50, 60 + i * 16), chunk.strip(), fontsize=10)
            lines = self.m.extract_lines(doc, range(1))
            prof = self.m.build_profile(lines, doc, range(1))
            prof.doc_type = 'book'
            self.m.assign_regimes(lines, prof)
        self.assertNotIn('copyright_drop', {l.kind for l in lines})

    def test_undecodable_text_layers_are_reported(self):
        def layer(make):
            return [self.line(make(i), y=100 + i * 14) for i in range(120)]

        healthy = layer(lambda i: f'The quality of this ordinary prose line {i} is fine.')
        self.assertIsNone(self.m.broken_text_layer(healthy))

        # a subset font with no ToUnicode: 'Farming management' -> ')DUPLQJ ...'
        cipher = layer(lambda i: 'PQRS TVWX BCDF GHJK LMNP QRST VWXY ZBCD FGHJ KLMN')
        share, why = self.m.broken_text_layer(cipher)
        self.assertGreater(share, 0.15)
        self.assertIn('nonsense', why)

        # same, but the encoding drops the space as well
        welded = layer(lambda i: ' '.join(
            ['Farmingmanagementbasedonobservingandrespondingtovariations'] * 3))
        share, why = self.m.broken_text_layer(welded)
        self.assertIn('run together', why)

        # a cipher into the punctuation range leaves barely any letters
        symbols = layer(lambda i: '/ $ / 0 [t/ $ :/E/ $ // X #/ $ / 9 % , / $ ///')
        share, why = self.m.broken_text_layer(symbols)
        self.assertIn('not letters', why)

    def test_broken_text_layer_warns_but_still_converts(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / 'cipher.pdf', Path(tmp) / 'cipher.md'
            with pymupdf.open() as doc:
                page = doc.new_page(width=612, height=792)
                for i in range(48):
                    page.insert_text((50, 60 + i * 15),
                                     'PQRS TVWX BCDF GHJK LMNP QRST VWXY ZBCD FGHJ KLMN',
                                     fontsize=11)
                doc.save(src)
            result = run(str(src), '-o', str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('warning', result.stderr)
            self.assertIn('nonsense', result.stderr)
            self.assertTrue(out.exists())


if __name__ == '__main__':
    unittest.main()
