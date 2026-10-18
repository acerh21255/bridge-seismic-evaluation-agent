import copy
import json
import tempfile
import unittest
from pathlib import Path

from bridge_report.contract.package import Package, load_file
from bridge_report.engine.gates import evaluate
from bridge_report.paths import EXAMPLES_DIR, GOLDEN_DIR, SCENARIOS_DIR
from bridge_report.report.chapters import build_report
from bridge_report.report.model import Figure, FigureRow, Heading, Para, Table, iter_runs


def load(name):
    path = GOLDEN_DIR / 'handoff.json' if name == 'golden' else SCENARIOS_DIR / f'{name}.json'
    return load_file(path, root_limit=EXAMPLES_DIR)


def build(package):
    tmp = tempfile.mkdtemp()
    result = evaluate(package.data, package.base_dir)
    return build_report(package, result, tmp), result


def h1_titles(doc):
    return [b.title for b in doc.blocks if isinstance(b, Heading) and b.level == 1]


def table(doc, fragment):
    return next(b for b in doc.blocks if isinstance(b, Table) and b.caption and fragment in b.caption)


def cell_texts(tbl):
    return [[''.join(r.text for r in c.runs) for c in row] for row in tbl.rows]


class GoldenChapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.result = build(load('golden'))

    def test_chapter_sequence(self):
        self.assertEqual(h1_titles(self.doc), ['工程概况', '参考规范', '设计标准及参数', '抗震设防标准、性能目标与地震动输入',
                                               '结构动力模型及动力特性', '抗震验算', '延性抗震设计验算', '韧性提升方案', '结论'])

    def test_table_numbers_follow_reference(self):
        labels = {b.caption: b.label for b in self.doc.blocks if isinstance(b, Table) and b.caption}
        self.assertEqual(labels['E1地震作用下桥墩各关键截面抗震验算结果(纵桥向)'], '6.3-1')
        self.assertEqual(labels['E2地震作用下承台冲切承载力验算（横桥向）'], '6.3-19')
        self.assertEqual(labels['三级抗震措施验算表格'], '6.4-3')

    def test_all_references_resolved(self):
        self.assertTrue(all(run.text for run in iter_runs(self.doc) if run.ref))

    def test_plastic_wording(self):
        rows = cell_texts(table(self.doc, 'E2地震作用下桥墩各关键截面抗震验算结果(纵桥向)'))
        self.assertEqual(rows[0][-1], '进入塑性')
        self.assertNotIn('不通过', json.dumps(rows, ensure_ascii=False))

    def test_provisional_limit_note(self):
        tbl = table(self.doc, 'E1地震作用下支座位移抗震验算结果(纵桥向)')
        self.assertEqual(cell_texts(tbl)[0][3], '0.0375')
        self.assertTrue(any('暂按' in ''.join(r.text for r in n.runs) for n in tbl.notes))

    def test_hinge_phi_note_and_ratio(self):
        tbl = table(self.doc, 'E2地震作用下桥墩塑性铰区抗剪验算结果(纵桥向)')
        self.assertEqual(cell_texts(tbl)[0][5], '0.423')
        self.assertTrue(any('φ=0.9' in ''.join(r.text for r in n.runs) for n in tbl.notes))

    def test_all_figures_resolved(self):
        figures = [b for b in self.doc.blocks if isinstance(b, Figure)] + [f for b in self.doc.blocks if isinstance(b, FigureRow) for f in b.figures]
        missing = [f.caption for f in figures for image, _ in f.images() if not image or not Path(image).is_file()]
        self.assertEqual(missing, [])
        self.assertEqual(len(figures), 25)

    def test_conclusion_mentions_key_findings(self):
        start = next(i for i, b in enumerate(self.doc.blocks) if isinstance(b, Heading) and b.title == '结论')
        text = '\n'.join(''.join(r.text for r in b.runs) for b in self.doc.blocks[start:] if isinstance(b, Para))
        for phrase in ('纵桥向E2地震作用下1#墩底截面弯矩大于等效屈服弯矩，进入塑性状态', '能需比为0.423＜1', '经韧性提升后',
                       '限位装置设置不满足要求', '承台斜压杆承载力、拉杆承载力、冲切承载力验算均满足规范要求', '综上所述'):
            self.assertIn(phrase, text)

    def test_cover_note(self):
        self.assertIn('非工程签发', self.doc.meta['cover_note'])
        self.assertEqual(self.doc.meta['cover_lines'][0], 'G8511昆磨高速（抗震韧性提升工程）')


class VariantChapterTests(unittest.TestCase):
    def test_e1_failure_drops_ductility_and_renumbers(self):
        doc, result = build(load('e1_fail'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(h1_titles(doc)[-1], '结论')
        self.assertNotIn('延性抗震设计验算', h1_titles(doc))
        self.assertEqual(next(b.label for b in doc.blocks if isinstance(b, Heading) and b.title == '结论'), '7.')
        texts = [''.join(r.text for r in b.runs) for b in doc.blocks if isinstance(b, Para)]
        self.assertTrue(any('E2地震作用下的抗震验算未开展' in t for t in texts))
        self.assertIn('演示变体', doc.meta['cover_note'])

    def test_elastic_has_no_ductility_chapter(self):
        doc, result = build(load('elastic'))
        self.assertEqual(result['status'], 'PASS')
        self.assertNotIn('延性抗震设计验算', h1_titles(doc))
        self.assertNotIn('韧性提升方案', h1_titles(doc))

    def test_missing_value_marked_pending(self):
        doc, _ = build(load('missing'))
        rows = cell_texts(table(doc, 'E2地震作用下桩基截面抗震验算结果(横桥向)'))
        self.assertIn('待补正', [r[-1] for r in rows])

    def test_overstrength_note(self):
        doc, _ = build(load('overstrength'))
        tbl = table(doc, 'E2地震作用下桩基截面抗震验算结果(纵桥向)')
        self.assertTrue(any('超强弯矩' in ''.join(r.text for r in n.runs) for n in tbl.notes))

    def test_package_level_block_produces_notice(self):
        broken = copy.deepcopy(load('golden').data)
        broken['analysis']['converged'] = False
        package = Package(broken)
        doc, result = build(package)
        self.assertFalse(result['evaluated'])
        self.assertEqual(h1_titles(doc), ['交接资料审查意见', '后续处理'])
        self.assertIn('补正通知', doc.meta['cover_note'])


if __name__ == '__main__':
    unittest.main()
