import unittest

from bridge_report.advisor import diagnose, draft_memo, grounding
from bridge_report.contract.package import load_file
from bridge_report.engine.gates import evaluate
from bridge_report.paths import EXAMPLES_DIR
from tests.test_chapters import load


def diag_of(package):
    result = evaluate(package.data, package.base_dir)
    return diagnose(result), result


class AdvisorTests(unittest.TestCase):
    def test_pile_yield_is_controlling_and_warns_against_pier_strengthening(self):
        diag, result = diag_of(load_file(EXAMPLES_DIR / 'golden' / '53K271+730' / 'handoff.json', root_limit=EXAMPLES_DIR))
        first = diag['modes'][0]
        self.assertEqual(first['key'], 'pile_yield')
        self.assertEqual(first['items'][0]['exceed_pct'], 11.2)
        self.assertIn('isolation', first['measures'])
        self.assertIn('不宜单独增强桥墩抗弯', first['note'])
        self.assertIn('data_overstrength', [m['key'] for m in diag['modes']])
        self.assertTrue(any('未开展' in s['action'] for s in diag['next_steps']))
        self.assertEqual(diag['status'], result['status'])

    def test_retrofit_effect_and_pile_recheck(self):
        diag, _ = diag_of(load('golden'))
        rows = {r['label']: r for r in diag['retrofit_effect']}
        shear = rows['1#墩底 纵桥向 塑性铰区抗剪']
        self.assertTrue(shear['improved'])
        self.assertEqual(rows['1#墩底 纵桥向 E2抗弯']['demand_change_pct'], 26.9)
        self.assertIn('复核加固后桩基能力保护', [s['action'] for s in diag['next_steps']])
        self.assertEqual(diag['modes'][0]['key'], 'restrainer')

    def test_elastic_bridge_has_no_retrofit_measures(self):
        diag, result = diag_of(load('elastic'))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(diag['measures'], {})
        self.assertIn('未识别到需要加固的薄弱环节', draft_memo(diag))

    def test_missing_data_becomes_supply_request(self):
        diag, _ = diag_of(load('missing'))
        data = [m for m in diag['modes'] if m['severity'] == 'data']
        self.assertEqual(data[0]['key'], 'data_missing')
        self.assertTrue(any(s['owner'] == '第三步' and '补交' in s['action'] for s in diag['next_steps']))

    def test_draft_memo_is_fully_grounded(self):
        for name in ('golden', 'e1_fail', 'overstrength', 'retrofit_pass'):
            package = load(name)
            diag, result = diag_of(package)
            memo = draft_memo(diag, 'K278+308 ')
            self.assertEqual(grounding(memo, diag, result, package.data.get('codes')), [], name)
            self.assertIn('engineering_release=false', memo)

    def test_grounding_tolerates_rounding_only(self):
        source = {'demand': 7503.0, 'ratio': 0.787}
        self.assertEqual(grounding('需求 7503 kN·m，比值 0.79', source), [])
        self.assertEqual(grounding('需求 7600 kN·m', source), ['7600'])


if __name__ == '__main__':
    unittest.main()
