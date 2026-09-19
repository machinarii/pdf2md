"""Grounded structure, selective repair and benchmark regressions."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

import pymupdf
from test_regressions import load_module, run

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark', ROOT/'tools/benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class ResearchPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def line(self, text, kind='body', level=0, page=0, y=100):
        return self.m.Line(page, text, 50, y, 250, y+12, 11, ('Helvetica',),
                           False, False, False, 0, isolated=False,
                           kind=kind, level=level,
                           sources=[{'id': text, 'page': page+1, 'bbox': [50,y,250,y+12], 'text': text}])

    def test_columns_do_not_require_the_left_column_to_have_the_most_lines(self):
        lines = [self.line(f'Left paragraph {i}', y=100+i*15) for i in range(8)]
        for i in range(15):
            line = self.line(f'Right paragraph {i}', y=100+i*15)
            line.x0, line.x1 = 320, 550
            lines.append(line)
        self.assertEqual(self.m.reorder_columns(lines, 600), 1)
        self.assertEqual([l.col for l in lines], [0]*8 + [1]*15)

    def test_minor_sidebar_does_not_disable_two_main_columns(self):
        lines = []
        for x in (200, 475):
            for i in range(32):
                l = self.line(f'Column text {i}', y=100+i*15)
                l.x0, l.x1 = x, x+240
                lines.append(l)
        for i in range(4):
            l = self.line('Sidebar caption', y=200+i*15)
            l.x0, l.x1 = 20, 180
            lines.append(l)
        self.assertEqual(self.m.reorder_columns(lines, 790), 1)
        self.assertTrue(all(l.col in (0,1) for l in lines))

    def test_pdf_font_flags_work_without_recognized_font_name(self):
        page = Mock()
        page.rect = pymupdf.Rect(0,0,600,800)
        page.rotation = 0
        page.rotation_matrix = pymupdf.Matrix(1, 0, 0, 1, 0, 0)
        page.get_text.return_value = {"blocks": [{"type":0,"lines":[{
            "bbox":[50,100,250,112], "spans":[{"text":"Unusual section title",
            "font":"UnknownFace", "flags":16|2, "size":12, "bbox":[50,100,250,112]}]}]}]}
        lines = self.m.extract_lines([page], range(1))
        self.assertTrue(lines[0].is_bold)
        self.assertTrue(lines[0].is_italic)
        self.assertFalse(lines[0].is_mono)
        self.assertEqual(page.get_text.call_args.kwargs['flags'] & pymupdf.TEXT_PRESERVE_IMAGES, 0)

    def test_symbol_bullet_is_repaired_by_font_not_guessed_as_a_letter(self):
        self.assertEqual(self.m.repair_span('\uf0b7', 'SymbolMT'), '•')
        self.assertEqual(self.m.repair_span('\uf0b7', 'UnrelatedFont', preserve_private=True), '\uf0b7')
        self.assertFalse(self.m.verify_repair('\uf0b7 Important item', 'e Important item', 99)[0])
        with pymupdf.open() as doc:
            doc.new_page()
            backend = Mock()
            audit = self.m.selective_ocr(doc, [self.line('\uf0a8')], [0], backend=backend)
            self.assertEqual(audit[0]['status'], 'skipped')
            backend.assert_not_called()

    def test_document_tree_parentage_cross_page_paragraph_and_order(self):
        lines = [self.line('Chapter', 'heading', 1), self.line('Section', 'heading', 2),
                 self.line('A sentence continues'), self.line('on the next page.', page=1),
                 self.line('Another section', 'heading', 2, page=1), self.line('New paragraph.')]
        nodes = self.m.construct_document(lines, self.m.Profile(body_left=50))
        self.assertEqual(list(self.m.document_lines(nodes)), lines)
        self.assertEqual(nodes[2].parent, nodes[1].id)
        self.assertEqual(nodes[3].parent, nodes[2].id)
        self.assertEqual(len(nodes[3].lines), 2)
        self.assertEqual(nodes[4].parent, nodes[1].id)
        self.assertEqual([s['page'] for s in self.m.document_payload(nodes)[3]['sources']], [1,2])

    def test_nested_lists_keep_parent_and_reading_order(self):
        lines = [self.line('Parent', 'list_item', 1), self.line('Child', 'list_item', 2),
                 self.line('continued', 'list_cont'), self.line('Sibling', 'list_item', 1)]
        nodes = self.m.construct_document(lines, self.m.Profile())
        self.assertEqual(nodes[2].parent, nodes[1].id)
        self.assertEqual(list(self.m.document_lines(nodes)), lines)

    def test_repair_gate_rejects_changed_numbers_and_words(self):
        for candidate in ('The cost is 900 euros.', 'The price is 100 euros.',
                          'The cost is 100 euros. Unrelated invented text.' * 3):
            self.assertFalse(self.m.verify_repair('The cost is 100 eu\ufffdos.', candidate, 99)[0])
        self.assertTrue(self.m.verify_repair('The cost is 100 eu\ufffdos.', 'The cost is 100 euros.', 95)[0])
        self.assertFalse(self.m.verify_repair('The cost is 100 euros.', 'The cost is 100 euros.', 95)[0])
        self.assertFalse(self.m.verify_repair('An err\ufffdr.', 'An error.', 79)[0])

    def test_repair_gate_preserves_repeated_tokens_and_order(self):
        self.assertFalse(self.m.verify_repair('very very b\ufffdd', 'very bad', 95)[0])
        self.assertFalse(self.m.verify_repair('first second b\ufffdd', 'second first bad', 95)[0])

    def test_selective_ocr_only_calls_backend_for_damage(self):
        with pymupdf.open() as doc:
            doc.new_page()
            healthy = self.line('Healthy text stays untouched.')
            damaged = self.line('A br\ufffdken word.', y=150)
            backend = Mock(return_value=([{'text': 'A broken word.', 'bbox': [50,150,250,162]}], 95))
            lines = [healthy, damaged]
            audit = self.m.selective_ocr(doc, lines, [0], backend=backend)
            backend.assert_called_once()
            self.assertEqual(healthy.text, 'Healthy text stays untouched.')
            self.assertEqual(damaged.text, 'A broken word.')
            self.assertEqual(damaged.sources[0]['text'], 'A br\ufffdken word.')
            self.assertEqual(audit[0]['status'], 'accepted')

    def test_failed_ocr_preserves_original_and_logs_rejection(self):
        with pymupdf.open() as doc:
            doc.new_page()
            line = self.line('br\ufffdken')
            audit = self.m.selective_ocr(doc, [line], [0], backend=Mock(side_effect=RuntimeError('offline')))
            self.assertEqual(line.text, 'br\ufffdken')
            self.assertEqual(audit[0]['status'], 'rejected')

    def test_blank_page_does_not_invoke_ocr(self):
        with pymupdf.open() as doc:
            doc.new_page()
            backend = Mock()
            self.assertEqual(self.m.selective_ocr(doc, [], [0], backend=backend), [])
            backend.assert_not_called()

    def test_benchmark_checks_fail_for_column_interleaving_and_missing_content(self):
        checks = [{'type':'order','texts':['left one left two','right one right two']},
                  {'type':'contains','text':'missing sentence'},
                  {'type':'heading','level':2,'text':'Methods'}]
        results = benchmark.evaluate('# Methods\nleft one right one left two right two', checks)
        self.assertFalse(any(r['passed'] for r in results))

    def test_table_check_keeps_cell_relationships(self):
        check = [{'type':'table_row','cells':['alpha','12']}]
        self.assertTrue(benchmark.evaluate('| alpha | 12 |', check)[0]['passed'])
        self.assertFalse(benchmark.evaluate('| 12 | alpha |', check)[0]['passed'])

    def test_benchmark_records_unannotated_and_missing_without_false_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with pymupdf.open() as doc:
                p = doc.new_page()
                p.insert_text((50,100), 'A real sentence in this document.')
                doc.save(tmp/'input.pdf')
            manifest = tmp/'manifest.json'
            manifest.write_text(json.dumps({'cases':[
                {'id':'available','input':'input.pdf','checks':[]},
                {'id':'missing','input':'missing.pdf','checks':[]}]}))
            report = benchmark.run_benchmark(manifest, tmp/'results')
            self.assertEqual(report['statuses'], {'unannotated':1,'missing':1})
            self.assertGreater(report['cases'][0]['elapsed_seconds'], 0)
            data = json.loads((tmp/'results/available/artifacts/document.json').read_text())
            self.assertEqual(len(data['source_sha256']), 64)
            self.assertTrue(any(n['sources'] for n in data['nodes']))

    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract not installed')
    def test_real_ocr_recovers_scan_without_changing_text_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with pymupdf.open() as source:
                p = source.new_page(width=600,height=400)
                p.insert_text((50,100), 'Scanned books preserve important knowledge.', fontsize=18)
                p.insert_text((50,140), 'This sentence comes from a page image.', fontsize=18)
                pix = p.get_pixmap(matrix=pymupdf.Matrix(2,2))
                with pymupdf.open() as mixed:
                    p = mixed.new_page(width=600,height=400)
                    p.insert_text((50,100), 'Healthy native text must survive exactly.', fontsize=14)
                    p = mixed.new_page(width=600,height=400)
                    p.insert_image(p.rect, stream=pix.tobytes('png'))
                    mixed.save(tmp/'mixed.pdf')
            result = run(str(tmp/'mixed.pdf'), '-o', str(tmp/'out.md'), '--ocr', 'auto',
                         '--artifacts', str(tmp/'audit'), '--doc-type', 'document')
            self.assertEqual(result.returncode, 0, result.stderr)
            md = (tmp/'out.md').read_text()
            self.assertIn('Healthy native text must survive exactly.', md)
            self.assertIn('Scanned books preserve important knowledge.', md)
            repairs = json.loads((tmp/'audit/repairs.json').read_text())
            self.assertEqual(len(repairs), 1)
            self.assertEqual(repairs[0]['page'], 2)
            self.assertEqual(repairs[0]['status'], 'accepted')

    def test_ocr_requires_audit_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/'input.pdf'
            with pymupdf.open() as doc:
                doc.new_page()
                doc.save(src)
            result = subprocess.run([sys.executable,str(ROOT/'pdf2md_all.py'),str(src),'--ocr','auto'],
                                    capture_output=True,text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--ocr auto requires --artifacts', result.stderr)

    def test_benchmark_repeated_order_anchors_cannot_reuse_one_occurrence(self):
        checks = [{'type':'order','texts':['same','same']}]
        self.assertFalse(benchmark.evaluate('same', checks)[0]['passed'])
        self.assertTrue(benchmark.evaluate('same then SAME', checks)[0]['passed'])



if __name__ == '__main__':
    unittest.main()
