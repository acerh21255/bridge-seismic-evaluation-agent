import hashlib
import json
import unittest
import zipfile

from docx import Document
from lxml import etree

from bridge_report.paths import FORMAT_SPEC, LIBRARY_DIR, TEMPLATE_DOCX

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def q(tag):
    return '{%s}%s' % (W, tag)


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zip = zipfile.ZipFile(TEMPLATE_DOCX)
        cls.body = etree.fromstring(cls.zip.read('word/document.xml')).find(q('body'))
        cls.spec = json.loads(FORMAT_SPEC.read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.zip.close()

    def part_text(self, name):
        root = etree.fromstring(self.zip.read(name))
        return ''.join(t.text or '' for t in root.iter(q('t')))

    def test_opens_with_python_docx(self):
        self.assertEqual(len(Document(str(TEMPLATE_DOCX)).sections), 3)

    def test_visible_master_has_examples_and_three_sections(self):
        self.assertEqual(len(list(self.body.iter(q('sectPr')))), 3)
        text = ''.join(t.text or '' for t in self.body.iter(q('t')))
        for expected in ('桥梁抗震验算报告母版', '目录与使用说明', '工程概况', '抗震验算', '结论与建议'):
            self.assertIn(expected, text)
        self.assertTrue(self.body.findall(q('tbl')))

    def test_header_and_footer_placeholders(self):
        texts = {n: self.part_text(n) for n in self.zip.namelist() if n.startswith('word/header') or n.startswith('word/footer')}
        self.assertTrue(any('{{HEADER}}' in t for t in texts.values()))
        self.assertTrue(any('{{ORG}}' in t for t in texts.values()))
        joined = ''.join(texts.values())
        for stale in ('宁夏省道305', '附件10', '右汊方案'):
            self.assertNotIn(stale, joined)
        footers = [etree.fromstring(self.zip.read(n)) for n in self.zip.namelist() if n.startswith('word/footer')]
        instr = ''.join(t.text or '' for f in footers for t in f.iter(q('instrText')))
        self.assertIn('PAGE', instr)

    def test_no_even_page_references(self):
        for sect in self.body.iter(q('sectPr')):
            kinds = [e.get(q('type')) for e in sect if etree.QName(e).localname in ('headerReference', 'footerReference')]
            self.assertNotIn('even', kinds)

    def test_no_orphan_media(self):
        self.assertFalse([n for n in self.zip.namelist() if n.startswith('word/media/') or n.startswith('word/charts/') or n.startswith('word/embeddings/')])

    def test_required_styles(self):
        styles = etree.fromstring(self.zip.read('word/styles.xml'))
        names = {s.find(q('name')).get(q('val')) for s in styles.findall(q('style')) if s.find(q('name')) is not None}
        for name in ('heading 1', 'heading 2', 'heading 3', 'heading 4', '图表', '正文表格图名', 'toc 1', 'toc 2', 'toc 3', '封面1',
                     '报告-正文', '报告-无缩进', '报告-表头', '报告-表文', '报告-资料表文', '报告-表注', '报告-公式', '报告-图',
                     '报告-图题', '报告-表题', '报告-封面注记', '报告-目录标题'):
            self.assertIn(name, names)

    def test_heading1_centered_and_breaks_page(self):
        styles = etree.fromstring(self.zip.read('word/styles.xml'))
        h1 = next(s for s in styles.findall(q('style')) if s.find(q('name')).get(q('val')) == 'heading 1')
        ppr = h1.find(q('pPr'))
        self.assertEqual(ppr.find(q('jc')).get(q('val')), 'center')
        self.assertIsNotNone(ppr.find(q('pageBreakBefore')))

    def test_format_spec_sections(self):
        for key in ('source', 'sections', 'styles', 'table', 'caption', 'numbering'):
            self.assertIn(key, self.spec)
        self.assertEqual([s['pgMar']['top'] for s in self.spec['sections']], [1440, 1418, 1418])

    def test_library_manifest_hashes(self):
        manifest = json.loads((LIBRARY_DIR / 'manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(manifest['figures'] and manifest['fragments'])
        for item in manifest['figures'] + manifest['fragments']:
            path = LIBRARY_DIR / item['file']
            self.assertTrue(path.is_file(), item['file'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])


if __name__ == '__main__':
    unittest.main()
