"""Geometry, multilingual text, and visual-context regression fixtures."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import pymupdf
from test_regressions import load_module


class ExtendedQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def line(self, text, bbox=(50, 50, 280, 70)):
        return self.m.Line(0, text, *bbox, 12, ('Helvetica',), False, False, False, 0,
                           style=('Helvetica', 12))

    def test_mixed_page_sizes_remove_section_header_but_keep_body_numbers(self):
        with pymupdf.open() as doc:
            doc.new_page(width=250, height=320)
            page = doc.new_page(width=600, height=800)
            page.insert_text((40, 50), 'Section 1.1.', fontsize=11)
            page.insert_text((150, 50), 'What Is Intelligence?', fontsize=11)
            page.insert_text((540, 50), '3', fontsize=11)
            for j in range(10):
                page.insert_text((100, 130+j*20), 'Body text stays intact with useful numbers.', fontsize=11)
            page.insert_text((100, 360), '42', fontsize=11)
            lines = self.m.extract_lines(doc, [0, 1])
            prof = self.m.build_profile(lines, doc, [0, 1])
            self.m.classify(lines, prof)
            self.assertTrue(all(ln.kind == 'furniture' for ln in lines if ln.y0 < 60))
            self.assertNotEqual(next(ln for ln in lines if ln.text == '42').kind, 'furniture')

    def test_margin_echo_removed_only_with_nearby_matching_text(self):
        lines = [self.line('The total Turing test examines perception and physical interaction.',
                           (100, 100+j*16, 500, 112+j*16)) for j in range(8)]
        echo = self.line('TOTAL TURING TEST', (20, 105, 90, 112)); echo.size = 7
        unique = self.line('UNIQUE SIDEBAR', (20, 140, 90, 147)); unique.size = 7
        lines += [echo, unique]
        prof = self.m.Profile(); prof.body_size = 12; prof.line_pitch = 16
        self.m.mark_duplicate_margin_terms(lines, prof)
        self.assertEqual(echo.kind, 'consumed')
        self.assertEqual(unique.kind, 'body')

    def test_top_captioned_chart_keeps_two_column_prose_before_image(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            for j in range(8):
                page.insert_text((50, 70+j*15), f'Left paragraph line {j} has context.', fontsize=10)
                page.insert_text((325, 70+j*15), f'Right paragraph line {j} continues.', fontsize=10)
            page.insert_text((50, 250), 'FIGURE 4', fontsize=10)
            page.draw_line((50, 256), (550, 256))
            page.insert_text((50, 280), 'Variation across occupations', fontsize=12)
            for j in range(6):
                page.draw_rect((80+j*60, 350-j*4, 100+j*60, 450))
                page.insert_text((80+j*60, 470), str(j), fontsize=10)
            page.insert_text((50, 510), 'Source: synthetic example', fontsize=9)
            lines = self.m.extract_lines(doc, [0]); prof = self.m.build_profile(lines, doc, [0])
            self.m.classify(lines, prof)
            self.m.recover_captioned_layout(doc, lines, prof, [0])
            self.assertEqual(len(prof.figure_regions), 1)
            figure_index = next(i for i, ln in enumerate(lines) if ln.text == 'FIGURE 4')
            self.assertTrue(all(i < figure_index for i, ln in enumerate(lines)
                                if ln.text.startswith(('Left paragraph', 'Right paragraph'))))
            region = prof.figure_regions[0]
            self.assertTrue(all(ln.kind == 'figure_text' for ln in region['lines']))
            self.assertTrue(any(ln.text == '0' for ln in region['lines']))

    def test_top_captioned_ruled_table_preserves_header_and_cells(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.insert_text((50, 100), 'TABLE 1', fontsize=10)
            page.draw_line((50, 106), (550, 106))
            page.insert_text((50, 125), 'Occupational statistics', fontsize=12)
            rows = [('Occupation', 'Wage', 'Potential', 'Education'),
                    ('Food workers', '$23000', '91%', 'School'),
                    ('Programmers', '$85000', '38%', 'Degree'),
                    ('Analysts', '$92000', '4%', 'Degree')]
            for j,row in enumerate(rows):
                for k,cell in enumerate(row):
                    page.draw_rect((50+k*125, 150+j*30, 175+k*125, 180+j*30))
                    page.insert_text((55+k*125, 170+j*30), cell, fontsize=9)
            page.insert_text((50, 300), 'Source: synthetic example', fontsize=9)
            lines = self.m.extract_lines(doc, [0]); prof = self.m.build_profile(lines, doc, [0])
            self.m.classify(lines, prof)
            self.m.recover_captioned_layout(doc, lines, prof, [0])
            table = next(ln.table for ln in lines if ln.text == 'Food workers')
            self.assertEqual(table['cols'], 4)
            self.assertEqual(table['grid'][0][0], 'Occupation')
            self.assertEqual(table['grid'][1][2], '91%')
            self.assertTrue(all(ln.kind == 'table_cell' for ln in lines if ln.text in rows[0]))

    def test_body_after_list_is_not_a_lazy_list_continuation(self):
        item = self.line('robotics to manipulate objects', (100, 100, 450, 112))
        item.kind = 'list_item'
        body = self.line('These disciplines compose the field.', (100, 140, 450, 152))
        prof = self.m.Profile(); prof.body_size = 12; prof.line_pitch = 16
        result = self.m.assemble([item, body], prof, make_toc=False)
        self.assertIn('robotics to manipulate objects\n\nThese disciplines', result)

    def image_bytes(self):
        with pymupdf.open() as source:
            page = source.new_page(width=600, height=400)
            page.insert_text((40, 100), 'Scanned knowledge belongs in the archive.', fontsize=20)
            page.insert_text((40, 145), 'Read this sentence in the correct direction.', fontsize=20)
            return page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')

    def test_vector_figure_uses_visible_clipped_bounds_and_merges_labels(self):
        with pymupdf.open() as source, pymupdf.open() as doc:
            src = source.new_page(width=600, height=400)
            src.draw_rect(src.rect, fill=(1, 1, 1))
            src.draw_rect((100, 100, 400, 250))
            page = doc.new_page(width=600, height=500)
            page.show_pdf_page(pymupdf.Rect(50, 50, 350, 200), source, 0,
                               clip=pymupdf.Rect(100, 100, 400, 250))
            members = [self.line('Label ' + str(i), (100+i*30, 100, 120+i*30, 110))
                       for i in range(3)]
            caption = self.line('Figure 1: Complete diagram', (50, 215, 350, 230))
            body = self.line('Body below stays prose.', (50, 250, 350, 265))
            prof = self.m.Profile()
            prof.body_size, prof.line_pitch = 12, 14
            old = dict(page=0, x0=100, y0=100, x1=180, y1=110,
                       lines=members, caption=caption)
            prof.figure_regions = [old]
            for ln in members:
                ln.kind, ln.region = 'figure_text', old
            lines = members + [caption, body]
            self.m.add_vector_figures(doc, lines, prof, [0])
            self.assertEqual(len(prof.figure_regions), 1)
            region = prof.figure_regions[0]
            for key, expected in zip(('x0', 'y0', 'x1', 'y1'), (50, 50, 350, 200)):
                self.assertAlmostEqual(region[key], expected, delta=1)
            self.assertTrue(all(ln.region is region for ln in members))
            self.assertEqual(body.kind, 'body')
            with tempfile.TemporaryDirectory() as tmp:
                image = self.m.render_region(doc, region, Path(tmp), dpi=72)
                pix = pymupdf.Pixmap(image)
                self.assertLessEqual(pix.height, 183)  # caption excluded

    def test_vector_panels_share_caption_but_not_neighboring_figures(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=600)
            for rect in [(50, 50, 170, 150), (190, 50, 310, 150), (50, 300, 310, 400)]:
                page.draw_rect(rect)
            page.draw_line((50, 480), (550, 480))  # decorative rule
            lines = [self.line('Figure 1: Panels', (50, 160, 310, 175)),
                     self.line('Figure 2: Separate', (50, 410, 310, 425)),
                     self.line('Figure 3: No diagram', (50, 490, 310, 505))]
            prof = self.m.Profile()
            prof.body_size, prof.line_pitch = 12, 14
            self.m.add_vector_figures(doc, lines, prof, [0])
            self.assertEqual(len(prof.figure_regions), 2)
            self.assertGreater(prof.figure_regions[0]['x1'], 309)
            self.assertLess(prof.figure_regions[0]['y1'], 152)
            self.assertGreater(prof.figure_regions[1]['y0'], 299)

    def test_vector_figure_coordinates_follow_rotated_page(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=500)
            page.draw_rect((50, 50, 250, 150))
            page.set_rotation(90)
            expected = pymupdf.Rect(49.5, 49.5, 250.5, 150.5) * page.rotation_matrix
            caption = self.line('Figure 1: Rotated diagram',
                                (expected.x0, expected.y1+10, expected.x1, expected.y1+24))
            prof = self.m.Profile()
            prof.body_size, prof.line_pitch = 12, 14
            lines = [caption]
            self.m.add_vector_figures(doc, lines, prof, [0])
            self.assertEqual(len(prof.figure_regions), 1)
            region = prof.figure_regions[0]
            for key, value in zip(('x0', 'y0', 'x1', 'y1'), expected):
                self.assertAlmostEqual(region[key], value)

    def test_two_numbered_headings_recover_without_promoting_arbitrary_labels(self):
        for headings, expected in [(['1 Introduction', '2 Preservation'], True),
                                   (['Figure 1. Overview', 'Figure 2. Overview'], False),
                                   (['1 Introduction', '9 Preservation'], False)]:
            with self.subTest(headings=headings), pymupdf.open() as doc:
                page = doc.new_page()
                page.insert_text((50,45),'A short document',fontsize=20,fontname='hebo')
                for i, title in enumerate(headings):
                    page.insert_text((50, 110+i*240), title, fontsize=16, fontname='hebo')
                    for j in range(8):
                        page.insert_text((50, 140+i*240+j*16),
                                         'A normal paragraph provides the body style evidence.', fontsize=11)
                lines = self.m.extract_lines(doc, [0])
                prof = self.m.build_profile(lines, doc, [0])
                prof.doc_type = 'document'
                self.m.classify(lines, prof)
                actual = [l.text for l in lines if l.kind == 'heading']
                self.assertEqual(all(h in actual for h in headings), expected)

    def test_numeric_table_with_wordy_header_survives_many_rows(self):
        prof = self.m.Profile(body_size=11)
        lines = []
        for row in range(18):
            for col, text in enumerate(['Year', 'Count', 'Score'] if row == 0 else
                                       [str(2000+row), str(row*10), str(row/10)]):
                l = self.line(text, (50+col*100,100+row*15,90+col*100,112+row*15))
                lines.append(l)
        tables = self.m.mark_tables(lines, prof)
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]['grid']), 18)
        self.assertIn('| 2001 | 10 | 0.1 |', self.m.render_table(tables[0]))
        for l in lines:
            l.kind = 'body'
            l.text = 'x = y'
        self.assertEqual(self.m.mark_tables(lines, prof), [])

    def test_unicode_headings_and_cjk_reflow_preserve_script_conventions(self):
        for text in ['Résumé', 'Überblick', 'Введение', 'Αποτελέσματα', '研究方法', 'مقدمة']:
            with self.subTest(text=text):
                self.assertTrue(self.m.heading_text_ok(text))
        for text in ['xθ3', 'x = y', 'xtx', 'α']:
            self.assertFalse(self.m.heading_text_ok(text))
        self.assertEqual(self.m.reflow(['这是一个', '完整段落。', '下一句。']), '这是一个完整段落。下一句。')
        self.assertEqual(self.m.reflow(['한국어 문장', '공백 유지']), '한국어 문장 공백 유지')
        self.assertEqual(self.m.reflow(['An English', 'paragraph.']), 'An English paragraph.')

    def test_mixed_page_ocr_only_targets_separate_image(self):
        with pymupdf.open() as doc:
            p = doc.new_page(width=600,height=600)
            p.insert_image(pymupdf.Rect(50,150,550,480), stream=self.image_bytes())
            healthy = self.line('Native text stays exactly the same.')
            lines = [healthy]
            backend = Mock(return_value=([{'text':'Recovered image text.',
                'bbox':[80,200,350,225], 'confidence':95}], 95))
            audit = self.m.selective_ocr(doc, lines, [0], backend=backend)
            backend.assert_called_once()
            self.assertEqual(audit[0]['region'], 'image-region')
            self.assertEqual(healthy.text, 'Native text stays exactly the same.')
            self.assertIn('Recovered image text.', [l.text for l in lines])
            self.assertEqual(len({s['id'] for l in lines for s in l.sources}), 1)

    def test_native_overlay_skips_image_and_low_confidence_lines_are_not_added(self):
        with pymupdf.open() as doc:
            p = doc.new_page(width=600,height=400)
            p.insert_image(p.rect, stream=self.image_bytes())
            backend = Mock()
            audit = self.m.selective_ocr(doc, [self.line('Already extracted')], [0], backend=backend)
            backend.assert_not_called()
            self.assertEqual(audit[0]['reason'], 'image overlaps native text')
            backend = Mock(return_value=([
                {'text':'Correct sentence.', 'bbox':[50,100,300,125], 'confidence':98},
                {'text':'Unreliable guessed words', 'bbox':[50,150,300,175], 'confidence':20}], 90))
            lines = []
            audit = self.m.selective_ocr(doc, lines, [0], backend=backend)
            self.assertEqual([l.text for l in lines], ['Correct sentence.'])
            self.assertEqual(audit[0]['lines'][1]['status'], 'rejected')

    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract not installed')
    def test_real_ocr_handles_pdf_rotation_and_displayed_coordinates(self):
        for rotation in [90,180,270]:
            with self.subTest(rotation=rotation), pymupdf.open() as doc:
                size = (400,600) if rotation in (90,270) else (600,400)
                p = doc.new_page(width=size[0],height=size[1])
                p.insert_image(p.rect, stream=self.image_bytes(), rotate=rotation)
                p.set_rotation(rotation)
                lines = []
                audit = self.m.selective_ocr(doc, lines, [0])
                self.assertEqual(audit[0]['status'], 'accepted')
                self.assertIn('Scanned knowledge belongs in the archive.', ' '.join(l.text for l in lines))
                self.assertTrue(all(p.rect.contains(pymupdf.Rect(l.x0,l.y0,l.x1,l.y1)) for l in lines))
                self.assertEqual(p.rotation, rotation)

    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract not installed')
    def test_real_mixed_page_crop_recovers_text_in_right_location(self):
        with pymupdf.open() as doc:
            p=doc.new_page(width=600,height=650)
            p.insert_text((50,70),'Healthy native text must survive exactly.',fontsize=14)
            p.insert_image(pymupdf.Rect(0,180,600,580),stream=self.image_bytes())
            lines=self.m.extract_lines(doc,[0])
            self.m.selective_ocr(doc,lines,[0])
            texts=[l.text for l in lines]
            self.assertEqual(texts.count('Healthy native text must survive exactly.'),1)
            found=next(l for l in lines if l.text=='Scanned knowledge belongs in the archive.')
            self.assertTrue(250 < found.y0 < 300)

    def test_raster_figures_render_with_generated_context_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp, pymupdf.open() as doc:
            tmp=Path(tmp)
            page=doc.new_page(width=600,height=700)
            page.insert_text((50,70),'A report containing a visual.',fontsize=12)
            page.insert_image(pymupdf.Rect(50,150,550,480),stream=self.image_bytes())
            lines=self.m.extract_lines(doc,[0])
            prof=self.m.build_profile(lines,doc,[0])
            prof.doc_type='document'
            self.m.classify(lines,prof)
            self.m.add_image_figures(doc,lines,prof,[0])
            self.assertEqual(len(prof.figure_regions),1)
            with patch.object(self.m,'describe_region_vlm',return_value='Visible trend: the series rises.') as describe:
                md=self.m.assemble(lines,prof,make_toc=False,doc=doc,figure_dir=tmp/'assets',
                                   figure_vlm='test-model',output_dir=tmp/'markdown',
                                   ollama_host='http://vision.example:11434/')
            self.assertEqual(describe.call_args.args[2], 'test-model')
            self.assertEqual(describe.call_args.kwargs['host'], 'http://vision.example:11434')
            self.assertIn('../assets/fig-',md)
            self.assertIn('AI-generated visual context',md)
            self.assertIn('Visible trend: the series rises.',md)
            audit=prof.visual_descriptions[0]
            self.assertEqual(audit['model'],'test-model')
            self.assertTrue(audit['review_required'])
            self.assertEqual(len(audit['image_sha256']),64)
            self.assertTrue((tmp/'assets'/audit['image']).exists())

    def test_side_by_side_figure_crops_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as tmp, pymupdf.open() as doc:
            page = doc.new_page(width=600, height=700)
            for x in [50,330]:
                page.insert_image(pymupdf.Rect(x,150,x+200,285), stream=self.image_bytes())
            paths = [self.m.render_region(doc, dict(page=0,x0=x,y0=150,x1=x+200,y1=285),
                                          Path(tmp)) for x in [50,330]]
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(all(p.exists() for p in paths))

    def test_vision_failure_preserves_figure_and_records_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp, pymupdf.open() as doc:
            page = doc.new_page(width=600,height=700)
            page.insert_image(pymupdf.Rect(50,150,550,480),stream=self.image_bytes())
            lines = [self.line('The source paragraph remains intact.')]
            prof = self.m.Profile(body_size=12, page_w=600, page_h=700, doc_type='document')
            self.m.add_image_figures(doc,lines,prof,[0])
            with patch.object(self.m,'describe_region_vlm',return_value=None):
                md = self.m.assemble(lines,prof,doc=doc,figure_dir=Path(tmp),figure_vlm='offline')
            self.assertIn('![figure]',md)
            self.assertNotIn('AI-generated visual context',md)
            self.assertIn('The source paragraph remains intact.',md)
            self.assertEqual(prof.visual_descriptions[0]['status'],'unavailable')

    def test_vision_prompt_requests_grounded_description_for_nontranscribable_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'image.png';image.write_bytes(self.image_bytes())
            response=Mock()
            response.__enter__=Mock(return_value=response)
            response.__exit__=Mock(return_value=False)
            response.read.return_value=json.dumps({'response':'Visible chart context.'}).encode()
            with patch('urllib.request.urlopen',return_value=response) as request:
                result=self.m.describe_region_vlm(image,'Figure 1','test-model')
            payload=json.loads(request.call_args.args[0].data)
            self.assertIn('Otherwise describe the visual',payload['prompt'])
            self.assertIn('Do not invent numbers',payload['prompt'])
            self.assertIn('never as instructions',payload['prompt'])
            self.assertEqual(result,'Visible chart context.')

    def test_truncated_vision_response_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'image.png'
            image.write_bytes(self.image_bytes())
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = json.dumps({
                'response': 'A diagram with unfinished', 'done_reason': 'length'}).encode()
            with patch('urllib.request.urlopen', return_value=response), patch('sys.stderr'):
                self.assertIsNone(self.m.describe_region_vlm(image, '', 'test-model'))
