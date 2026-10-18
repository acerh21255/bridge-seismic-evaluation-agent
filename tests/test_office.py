import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_report.report import office
from bridge_report.report.docx_writer import write_docx
from tests.test_docx_writer import sample_doc


class OfficeTests(unittest.TestCase):
    def test_disabled_word_falls_back(self):
        with patch.dict(os.environ, {'BRIDGE_DISABLE_WORD': '1'}):
            self.assertFalse(office.word_available())
            info = office.update_and_export('missing.docx', 'missing.pdf')
        self.assertFalse(info['ok'])
        self.assertIsNone(info['pdf'])
        self.assertIn('Word', info['message'])

    @unittest.skipUnless(os.environ.get('BRIDGE_TEST_WORD') == '1', '设置 BRIDGE_TEST_WORD=1 后运行真实 Word 渲染测试')
    def test_word_refreshes_toc_and_exports_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = write_docx(sample_doc(), Path(tmp) / 'report.docx')
            info = office.update_and_export(docx, Path(tmp) / 'report.pdf')
            self.assertTrue(info['ok'], info['message'])
            self.assertGreaterEqual(info['pages'], 3)
            pages = office.render_pages(info['pdf'], Path(tmp) / 'pages')
            self.assertEqual(len(pages), info['pages'])
            from docx import Document
            toc_text = '\n'.join(p.text for p in Document(str(docx)).paragraphs)
            self.assertNotIn('目录待更新', toc_text)


if __name__ == '__main__':
    unittest.main()
