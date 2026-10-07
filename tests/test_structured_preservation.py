"""Source-backed structured tables, equations, resource limits and API checks."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pymupdf
from test_regressions import load_module, ROOT


class PreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()
        spec = importlib.util.spec_from_file_location('pdf2md_api', ROOT/'pdf2md_api.py')
        cls.api = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.api
        spec.loader.exec_module(cls.api)

    def docx(self, body):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><w:body>'+body+'</w:body></w:document>')
        return stream.getvalue()

    def test_html_spans_and_row_headers(self):
        html = '<table><tr><th rowspan="2">Region</th><th colspan="2">Revenue</th></tr><tr><th>2024</th><th>2025</th></tr><tr><th>EMEA</th><td>120</td><td>145</td></tr></table>'
        _, blocks = self.m.html_to_blocks(html, {})
        b = next(b for b in blocks if b.kind == 'table')
        self.assertEqual(b.header_rows, 2)
        self.assertEqual(self.m.structured_table_rows(b), [['Region','Revenue — 2024','Revenue — 2025'],['EMEA','120','145']])
        slots = self.m.canonical_table(b.cells)
        self.assertEqual(next(c for c in slots if c['row']==1 and c['column']==0)['covered_by'], [0,0])

    def test_docx_vertical_merge_preserves_alignment(self):
        body = '<w:tbl><w:tr><w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>EMEA</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>120</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p/></w:tc><w:tc><w:p><w:r><w:t>145</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp,'source.docx'); path.write_bytes(self.docx(body))
            meta, blocks = self.m.read_docx(path)
            try:
                b = blocks[0]
                self.assertEqual(b.rows, [['EMEA','120'],['EMEA','145']])
                self.assertEqual(b.cells[0]['rowspan'], 2)
                self.assertEqual(self.m.structured_table_rows(b)[0], ['', ''])
            finally:
                meta['zip'].close()

    def test_equation_fraction_scripts_and_unsupported(self):
        element = self.m.bounded_xml('<math><mfrac><msup><mi>x</mi><mn>2</mn></msup><msqrt><mi>y</mi></msqrt></mfrac></math>')
        self.assertEqual(self.m.math_record(element)['latex'], r'\frac{{x}^{2}}{\sqrt{y}}')
        unsupported = self.m.math_record(self.m.bounded_xml('<math><mystery>x</mystery></math>'))
        self.assertEqual(unsupported['status'],'unsupported')
        self.assertIn('<mystery>', unsupported['source_xml'])

    def test_docx_equation_end_to_end_and_mislabeled_bytes_api(self):
        body = '<w:p><w:r><w:t>Value: </w:t></w:r><m:oMath><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath></w:p>'
        result = self.api.convert_bytes(self.docx(body),filename='example.pdf')
        self.assertEqual(result.format,'docx')
        self.assertIn(r'$\frac{a}{b}$',result.markdown)

    def test_archive_depth_entities_and_span_limits(self):
        with patch.object(self.m, 'MAX_XML_DEPTH', 3):
            with self.assertRaises(self.m.ResourceLimitError):
                self.m.bounded_xml('<a><b><c><d/></c></b></a>')
        for encoding in ('utf-8','utf-16'):
            with self.assertRaises(self.m.ResourceLimitError):
                self.m.bounded_xml('<!DOCTYPE x [<!ENTITY a "boom">]><x>&a;</x>'.encode(encoding))
        with patch.object(self.m,'MAX_TABLE_SLOTS',10):
            with self.assertRaises(self.m.ResourceLimitError):
                self.m.canonical_table([dict(row=0,column=0,rowspan=100,colspan=100,text='x')])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp,'test.zip')
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('data','x'*100)
            with patch.object(self.m,'MAX_ENTRY_BYTES',50):
                with self.assertRaises(self.m.ResourceLimitError):
                    self.m.BoundedZip(path)

    def test_strict_coverage_preserves_existing_output_on_mixed_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src=root/'source.pdf'; out=root/'output.md'; audit=root/'audit'
            with pymupdf.open() as doc:
                p=doc.new_page(); p.insert_text((50,100),'A readable original paragraph.')
                p=doc.new_page()
                pix=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,10,10),False); pix.clear_with(128)
                p.insert_image(p.rect,stream=pix.tobytes('png')); doc.save(src)
            out.write_text('original output')
            run=subprocess.run([sys.executable,str(ROOT/'pdf2md_all.py'),str(src),'-o',str(out),'--strict-coverage','--artifacts',str(audit)],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('strict coverage',run.stderr)
            self.assertEqual(out.read_text(),'original output')
            report=json.loads((audit/'coverage.json').read_text())
            self.assertIn('image_page_without_recovered_content',report['pages'][1]['review_reasons'])

    def test_api_limits_and_timeout(self):
        with self.assertRaises(self.api.ConversionError):
            self.api.convert_bytes(b'12345',max_bytes=4)
        with patch.object(self.api.subprocess,'run',side_effect=subprocess.TimeoutExpired('pdf2md',1)):
            with self.assertRaises(self.api.ConversionError):
                self.api.convert_bytes(b'%PDF-1.7',timeout=1)

    def test_html_row_header_is_not_a_column_header(self):
        _, blocks = self.m.html_to_blocks('<table><tr><th scope="row">EMEA</th><td>120</td></tr><tr><th scope="row">APAC</th><td>145</td></tr></table>', {})
        self.assertEqual(blocks[0].header_rows,0)
        self.assertEqual(self.m.structured_table_rows(blocks[0])[1],['EMEA','120'])

    def test_table_overlap_is_rejected_before_expansion(self):
        with self.assertRaises(ValueError):
            self.m.canonical_table([dict(row=0,column=0,rowspan=1,colspan=2,text='a'),
                                    dict(row=0,column=1,rowspan=1,colspan=1,text='b')])

    def test_epub_math_audit_preserves_unsupported_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp,'test.epub')
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('META-INF/container.xml','<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>')
                archive.writestr('content.opf','<package xmlns="http://www.idpf.org/2007/opf"><metadata/><manifest><item id="p" href="page.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="p"/></spine></package>')
                archive.writestr('page.xhtml','<html><body><p>Formula <math><mfrac><mi>a</mi><mi>b</mi></mfrac></math></p><p>Unknown <math><mystery>x</mystery></math></p><p><math><m:mi>z</m:mi></math></p></body></html>')
            meta,blocks=self.m.read_epub(path)
            try:
                self.assertEqual([r['status'] for r in meta['math']],['converted','unsupported','unsupported'])
                self.assertIn(r'$\frac{a}{b}$',' '.join(b.text for b in blocks))
                self.assertIn('[unconverted equation: x]',' '.join(b.text for b in blocks))
            finally:
                meta['zip'].close()
