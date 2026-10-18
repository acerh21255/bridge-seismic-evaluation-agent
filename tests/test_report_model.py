import unittest

from bridge_report.report.model import (Cell, Equation, Figure, FigureRow, Heading, Para, ReportDoc, Run, Table,
                                        finalize, iter_runs)


def para_ref(key):
    return Para([Run('见'), Run(ref=key), Run('。')])


def table(key, caption='验算表'):
    return Table(key=key, caption=caption, header=[[Cell([Run('项目')])]], rows=[[Cell([Run('1')])]])


class NumberingTests(unittest.TestCase):
    def labels(self, blocks):
        doc = finalize(ReportDoc(meta={}, blocks=blocks))
        return doc, [b.label for b in doc.blocks if isinstance(b, (Heading, Figure, Table, Equation)) and b.label]

    def test_heading_numbers(self):
        _, labels = self.labels([Heading(1, '工程概况'), Heading(2, '桥梁概况'), Heading(3, '主梁'), Heading(2, '研究内容'),
                                 Heading(4, '（1）纵向输入', numbered=False), Heading(1, '参考规范')])
        self.assertEqual(labels, ['1.', '1.1', '1.1.1', '1.2', '2.'])

    def test_captions_follow_level2_and_reset(self):
        blocks = [Heading(1, 'A'), Heading(2, 'B'), Figure('f1', '图一'), Figure('f2', '图二'), table('t1'),
                  Heading(3, 'C'), table('t2'), Heading(2, 'D'), Figure('f3', '图三'), table('t3')]
        doc, _ = self.labels(blocks)
        self.assertEqual(doc.labels, {'f1': '图1.1-1', 'f2': '图1.1-2', 't1': '表1.1-1', 't2': '表1.1-2',
                                      'f3': '图1.2-1', 't3': '表1.2-1'})

    def test_captions_directly_under_level1(self):
        blocks = [Heading(1, 'A'), Heading(1, 'B'), Figure('f1', '方案图'), Heading(2, 'B1'), table('t1')]
        doc, _ = self.labels(blocks)
        self.assertEqual(doc.labels['f1'], '图2-1')
        self.assertEqual(doc.labels['t1'], '表2.1-1')

    def test_equations_numbered_by_chapter(self):
        blocks = [Heading(1, 'A'), Heading(2, 'A1'), Equation(None, key='e1', numbered=True), Equation(None, key='e2', numbered=True),
                  Equation(None), Heading(1, 'B'), Equation(None, key='e3', numbered=True)]
        doc, _ = self.labels(blocks)
        self.assertEqual((doc.labels['e1'], doc.labels['e2'], doc.labels['e3']), ('（1-1）', '（1-2）', '（2-1）'))

    def test_figure_row_members_numbered_in_order(self):
        blocks = [Heading(1, 'A'), Heading(2, 'B'), FigureRow([Figure('a', '桩'), Figure('b', '墩')])]
        doc, _ = self.labels(blocks)
        self.assertEqual((doc.labels['a'], doc.labels['b']), ('图1.1-1', '图1.1-2'))

    def test_forward_reference_resolved(self):
        blocks = [Heading(1, 'A'), Heading(2, 'B'), para_ref('t1'), table('t1')]
        doc, _ = self.labels(blocks)
        self.assertEqual(''.join(r.text for r in doc.blocks[2].runs), '见表1.1-1。')

    def test_reference_inside_table_cell_and_note(self):
        t = table('t1')
        t.rows[0][0] = Cell([Run(ref='f1')])
        t.notes.append(para_ref('f1'))
        doc, _ = self.labels([Heading(1, 'A'), Heading(2, 'B'), Figure('f1', '图'), t])
        texts = [r.text for r in iter_runs(doc) if r.ref == 'f1']
        self.assertEqual(texts, ['图1.1-1', '图1.1-1'])

    def test_heading_key_reference(self):
        blocks = [Heading(1, 'A'), Heading(2, 'B', key='sec'), para_ref('sec')]
        doc, _ = self.labels(blocks)
        self.assertEqual(doc.labels['sec'], '1.1')

    def test_unknown_reference_raises(self):
        with self.assertRaises(KeyError):
            finalize(ReportDoc(meta={}, blocks=[Heading(1, 'A'), para_ref('missing')]))

    def test_duplicate_key_raises(self):
        with self.assertRaises(ValueError):
            finalize(ReportDoc(meta={}, blocks=[Heading(1, 'A'), Heading(2, 'B'), table('t'), table('t')]))


if __name__ == '__main__':
    unittest.main()
