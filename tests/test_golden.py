import json
import tempfile
import unittest
from pathlib import Path

from bridge_report.contract.package import load_file
from bridge_report.contract.schema import schema_issues
from bridge_report.engine.gates import evaluate
from bridge_report.paths import EXAMPLES_DIR, SCENARIOS_DIR
from bridge_report.report.chapters import build_report
from bridge_report.report.docx_writer import write_docx
from tests.test_chapters import load
from tools.compare_golden import compare


class ScenarioTests(unittest.TestCase):
    def test_index_matches_judgement(self):
        index = json.loads((SCENARIOS_DIR / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual([e['id'] for e in index], ['golden-76K', 'golden-53K', 'retrofit_pass', 'elastic', 'e1_fail', 'missing', 'overstrength'])
        for entry in index:
            with self.subTest(entry['id']):
                package = load_file(EXAMPLES_DIR / entry['file'], root_limit=EXAMPLES_DIR)
                self.assertEqual(schema_issues(package.data), [])
                self.assertEqual(evaluate(package.data, package.base_dir)['status'], entry['expected_status'])
                self.assertEqual(len(package.assets()), len([a for a in package.assets() if package.asset_path(a)]))

    def test_variants_are_marked(self):
        for name in ('retrofit_pass', 'elastic', 'e1_fail', 'missing', 'overstrength'):
            data = load(name).data
            self.assertEqual(data['data_kind'], 'synthetic_variant')
            self.assertIn('variant-note', data['sources'])
            self.assertTrue(data['variant']['changes'])


class GoldenComparisonTests(unittest.TestCase):
    def test_generated_report_matches_reference(self):
        package = load('golden')
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(package.data, package.base_dir)
            docx = write_docx(build_report(package, result, Path(tmp) / 'work'), Path(tmp) / 'report.docx')
            report = compare(docx)
        self.assertEqual(report['unmatched'], [])
        self.assertEqual(report['number_diffs'], [])
        self.assertEqual(report['heading_diff'], [])
        self.assertEqual(len(report['matched']), 34)
        self.assertEqual(len(report['expected_diffs']), 1)


if __name__ == '__main__':
    unittest.main()
