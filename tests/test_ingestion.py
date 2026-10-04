"""Source accounting, table continuity, and chunk preservation regressions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from test_regressions import load_module


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def table(self, page, caption, value='10'):
        return {'id': f'table-{page}', 'page': page, 'pages': [page+1],
                'bbox': [50, 100, 300, 200], 'cols': 2,
                'grid': [{0: 'Region', 1: 'Revenue (USD m)'}, {0: 'EMEA', 1: value}],
                'context': [caption], 'cells': [], 'sources': [], 'row_pages': [page+1]*2}

    def test_continuation_requires_caption_header_and_geometry(self):
        first = self.table(0, 'Table 1 Revenue')
        second = self.table(1, 'Table 1 (continued)', '20')
        self.m.join_continued_tables([first, second], [])
        self.assertEqual(first['pages'], [1, 2])
        self.assertEqual(len(first['grid']), 3)
        self.assertEqual(first['grid'][-1][1], '20')
        self.assertEqual(second['joined_into'], first['id'])
        for change in ({'context': ['Table 2 (continued)']}, {'context': ['Table 1 Revenue']},
                       {'bbox': [80, 100, 330, 200]}, {'grid': [{0:'Region', 1:'Expenses'}, {0:'EMEA', 1:'20'}]}):
            first = self.table(0, 'Table 1 Revenue')
            second = self.table(1, 'Table 1 (continued)'); second.update(change)
            self.m.join_continued_tables([first, second], [])
            self.assertNotIn('joined_into', second)

    def test_coverage_distinguishes_blank_image_and_lost_source(self):
        original = [{'page': 1, 'native_characters': 0, 'image_regions': [], 'has_vector_content': False, 'sources': []},
                    {'page': 2, 'native_characters': 0, 'image_regions': [[0,0,100,100]], 'has_vector_content': False, 'sources': []},
                    {'page': 3, 'native_characters': 5, 'image_regions': [], 'has_vector_content': False,
                     'sources': [{'id':'x','text':'hello','page':3}]}]
        records = self.m.coverage_report(original, [], [])['pages']
        self.assertTrue(records[0]['blank_candidate'])
        self.assertFalse(records[0]['review_reasons'])
        self.assertIn('image_page_without_recovered_content', records[1]['review_reasons'])
        self.assertIn('source_lines_unaccounted', records[2]['review_reasons'])

    def test_table_chunks_repeat_units_notes_and_preserve_each_row(self):
        table = self.table(0, 'Table 1. Revenue in USD millions')
        table['grid'] += [{0: 'APAC', 1:'20'}, {0:'Americas', 1:'30'}]
        text = '# Results\n\n' + '\n'.join(self.m.render_table(table))
        chunks = self.m.markdown_chunks(text, 100, list, [table])
        rows = [c for c in chunks if c['table_id']]
        self.assertGreater(len(rows), 1)
        for chunk in rows:
            self.assertIn('Revenue (USD m)', chunk['text'])
            self.assertIn('Revenue in USD millions', chunk['text'])
            self.assertEqual(chunk['pages'], [1])
        for name in ('EMEA', 'APAC', 'Americas'):
            self.assertEqual(sum(c['text'].count(name) for c in rows), 1)

    def test_oversize_paragraph_is_kept_and_fenced_code_not_split(self):
        md = '---\ntitle: Test\n---\n\n# Intro\n\n' + 'word '*40 + '\n\n```python\na = 1\n\nb = 2\n```'
        chunks = self.m.markdown_chunks(md, 20, list)
        self.assertFalse(any('title: Test' in c['text'] for c in chunks))
        self.assertTrue(any(c['oversize'] for c in chunks))
        code = [c for c in chunks if '```' in c['text']]
        self.assertEqual(len(code), 1)
        self.assertIn('a = 1\n\nb = 2', code[0]['text'])

    def test_grouped_headers_render_without_losing_rows(self):
        table = self.table(0, 'Table 1')
        table.update(cols=3, header_rows=2,
            grid=[{0:'Region',1:'Revenue',2:'Revenue'}, {0:'Region',1:'2024',2:'2025'}, {0:'EMEA',1:'120',2:'145'}],
            headers={0:'Region',1:'Revenue — 2024',2:'Revenue — 2025'})
        rendered = '\n'.join(self.m.render_table(table))
        self.assertIn('Revenue — 2024', rendered)
        self.assertIn('| EMEA | 120 | 145 |', rendered)
        self.assertEqual(len(rendered.splitlines()), 3)

    def test_model_failure_keeps_native_and_truncation_not_cached(self):
        table = self.table(0, 'Table 1'); table['image'] = 'crop.png'
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'crop.png').write_bytes(b'fake')
            with patch('urllib.request.urlopen', side_effect=OSError('offline')):
                result = self.m.table_model_candidate(table, temp, 'test', 'http://localhost:1')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(table['grid'][1][1], '10')
            self.assertEqual(list(Path(temp).glob('candidate-*')), [])

    def test_native_page_snapshot_survives_line_mutation(self):
        with pymupdf.open() as doc:
            page = doc.new_page(); page.insert_text((50,100), 'Original source text')
            lines = self.m.extract_lines(doc, [0])
            evidence = self.m.capture_page_evidence(doc, [0], lines)
            lines[0].text = 'changed'; lines[0].kind = 'furniture'
            report = self.m.coverage_report(evidence, lines, [])
            self.assertEqual(report['pages'][0]['source_dispositions'][0]['text'], 'Original source text')
            self.assertEqual(report['pages'][0]['source_dispositions'][0]['status'], 'suppressed')
            json.dumps(report)

    def test_html_spans_and_literal_text(self):
        table = self.table(0, 'Table 1')
        table['cells'] = [{'row':0,'column':0,'text':'Revenue <USD>', 'rowspan':1,'colspan':2}]
        html = self.m.table_html(table)
        self.assertIn('colspan="2"', html)
        self.assertIn('Revenue &lt;USD&gt;', html)
        self.assertEqual(html.count('<th '), 1)

    def test_truncated_model_response_is_rejected(self):
        import io
        table = self.table(0, 'Table 1'); table['image'] = 'crop.png'
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'crop.png').write_bytes(b'fake')
            responses = [io.BytesIO(json.dumps({'models':[{'name':'test:latest','digest':'abc'}]}).encode()),
                         io.BytesIO(json.dumps({'done_reason':'length','response':'{}'}).encode())]
            with patch('urllib.request.urlopen', side_effect=responses):
                result = self.m.table_model_candidate(table, temp, 'test', 'http://localhost:1')
            self.assertEqual(result['status'], 'failed')
            self.assertIn('truncated', result['error'])
            self.assertFalse(list(Path(temp).glob('candidate-*')))

    def test_cache_reuses_only_matching_model_revision(self):
        import io
        table = self.table(0, 'Table 1'); table['image'] = 'crop.png'
        content = {'headers':['Region','Revenue (USD m)'], 'rows':[['EMEA','10']], 'notes':[]}
        def tags(digest):
            return io.BytesIO(json.dumps({'models':[{'name':'test','digest':digest}]}).encode())
        def response():
            return io.BytesIO(json.dumps({'done_reason':'stop','response':json.dumps(content)}).encode())
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'crop.png').write_bytes(b'fake')
            with patch('urllib.request.urlopen', side_effect=[tags('abc'), response()]) as request:
                first = self.m.table_model_candidate(table, temp, 'test', 'http://localhost:1')
                self.assertEqual(request.call_count, 2)
            with patch('urllib.request.urlopen', side_effect=[tags('abc')]) as request:
                second = self.m.table_model_candidate(table, temp, 'test', 'http://localhost:1')
                self.assertEqual(request.call_count, 1)
            self.assertEqual(first, second)
            self.assertTrue(first['numeric_tokens_match'])
            with patch('urllib.request.urlopen', side_effect=[tags('def'), response()]) as request:
                self.m.table_model_candidate(table, temp, 'test', 'http://localhost:1')
                self.assertEqual(request.call_count, 2)

    def test_merged_native_header_recovered_from_pdf_geometry(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=400)
            for y in (90, 120, 150, 180):
                page.draw_line((40,y),(340,y))
            for x in (40,140,340):
                page.draw_line((x,90),(x,180))
            page.draw_line((240,120),(240,180))
            for x,y,text in [(50,110,'Region'),(150,110,'Revenue'),(50,140,'Region'),
                             (150,140,'2024'),(250,140,'2025'),(50,170,'EMEA'),
                             (150,170,'120'),(250,170,'145')]:
                page.insert_text((x,y),text,fontsize=10)
            lines = self.m.extract_lines(doc,[0])
            table = dict(page=0,cols=3,grid=[{0:'Region',1:'Revenue',2:''},
                {0:'Region',1:'2024',2:'2025'},{0:'EMEA',1:'120',2:'145'}],first=lines[0])
            for line in lines:
                line.table = table; line.kind = 'table_cell'
            prof = self.m.Profile(tables=[table])
            self.m.prepare_table_evidence(doc, lines, prof)
            self.assertEqual(table['method'], 'native-grid')
            self.assertEqual(table['header_rows'], 2)
            self.assertEqual(table['headers'][2], 'Revenue — 2025')
            self.assertEqual(table['cells'][1]['colspan'], 2)

    def test_cli_textless_document_still_writes_coverage(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp, 'blank.pdf')
            with pymupdf.open() as doc:
                doc.new_page(); doc.save(src)
            output = Path(temp, 'audit')
            run = subprocess.run([sys.executable, str(Path(self.m.__file__)), str(src),
                                  '--artifacts', str(output)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            report = json.loads((output/'coverage.json').read_text())
            self.assertTrue(report['pages'][0]['blank_candidate'])

    def test_cli_mixed_document_accounts_for_blank_page(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp, 'mixed.pdf')
            with pymupdf.open() as doc:
                page = doc.new_page()
                for row in range(8):
                    page.insert_text((50,100+row*20), 'A useful sentence with original source evidence.')
                doc.new_page(); doc.save(src)
            output = Path(temp, 'audit')
            run = subprocess.run([sys.executable, str(Path(self.m.__file__)), str(src),
                                  '--artifacts', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads((output/'coverage.json').read_text())
            self.assertEqual(len(report['pages']), 2)
            self.assertTrue(report['pages'][1]['blank_candidate'])
            self.assertFalse(report['pages'][1]['review_reasons'])

    def test_model_preface_is_excluded_and_only_complete_final_object_accepted(self):
        response = 'Model preface with {bad braces}.\n```json\n{"headers":["A"],"rows":[["1"]]}\n```'
        candidate = self.m.decode_table_json(response)
        self.assertEqual(candidate['rows'], [['1']])
        for invalid in ('{"headers":["A"],"rows":', '{"headers":[],"rows":[]} trailing explanation'):
            with self.assertRaises(ValueError):
                self.m.decode_table_json(invalid)

    def test_model_table_chunk_keeps_warning_and_image_reference(self):
        table = self.table(0, 'Table 1'); table.update(method='model', image_link='audit/tables/table-1.png')
        chunk = self.m.markdown_chunks('\n'.join(self.m.render_table(table)), 1000, list, [table])[0]
        self.assertIn('AI-extracted', chunk['text'])
        self.assertEqual(chunk['image_links'], ['audit/tables/table-1.png'])
        self.assertEqual(chunk['extraction_method'], 'model')
