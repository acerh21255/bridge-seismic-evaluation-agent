import copy
import tempfile
import unittest
from pathlib import Path

from bridge_report.report.html_writer import write_html
from bridge_report.report.model import Para, Run, Table
from bridge_report.report.qa import check
from tests.test_chapters import build, load


class QaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.result = build(load('golden'))

    def fresh(self):
        return copy.deepcopy(self.doc)

    def test_golden_has_no_errors(self):
        report = check(self.doc, self.result)
        self.assertEqual(report['errors'], [])
        self.assertTrue(any('暂定限值' in w for w in report['warnings']))
        self.assertTrue(any('桩基' in h for h in report['hints']))
        self.assertEqual(report['counts']['tables'], 35)

    def test_numbering_gap_detected(self):
        doc = self.fresh()
        tables = [b for b in doc.blocks if isinstance(b, Table) and b.caption]
        tables[3].label = tables[3].label.rsplit('-', 1)[0] + '-9'
        self.assertTrue(any('编号不连续' in e for e in check(doc, self.result)['errors']))

    def test_empty_cell_detected(self):
        doc = self.fresh()
        tbl = next(b for b in doc.blocks if isinstance(b, Table) and b.kind == 'check')
        tbl.rows[0][2].runs = [Run('')]
        self.assertTrue(any('空单元格' in e for e in check(doc, self.result)['errors']))

    def test_forbidden_wording_detected(self):
        doc = self.fresh()
        doc.blocks.append(Para([Run('1#墩底抗弯不通过')]))
        self.assertTrue(any('抗弯不通过' in e for e in check(doc, self.result)['errors']))

    def test_wrong_verdict_detected(self):
        result = copy.deepcopy(self.result)
        item = next(i for i in result['items'] if i['kind'] == 'e2_moment' and i['component_kind'] == 'pier')
        item['verdict'] = '强度破坏'
        self.assertTrue(any('措辞错误' in e for e in check(self.doc, result)['errors']))

    def test_html_escapes_and_contains_captions(self):
        doc = self.fresh()
        doc.blocks.append(Para([Run('<script>alert(1)</script>')]))
        with tempfile.TemporaryDirectory() as tmp:
            path = write_html(doc, Path(tmp) / 'report.html')
            html = path.read_text(encoding='utf-8')
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('表6.3-1 E1地震作用下桥墩各关键截面抗震验算结果(纵桥向)', html)
        self.assertIn('9. 结论', html)


if __name__ == '__main__':
    unittest.main()
