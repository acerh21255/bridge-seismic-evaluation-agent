import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from bridge_report.contract.evidence import content_hash, file_hash, verify_sources
from bridge_report.contract.package import Package, PackageError, load_file, load_zip, parse_json
from bridge_report.contract.schema import schema_issues
from bridge_report.paths import CONTRACTS_DIR
from tests.fixtures import base_package


def make_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_template_matches_schema(self):
        template = json.loads((CONTRACTS_DIR / 'handoff.template.json').read_text(encoding='utf-8'))
        self.assertEqual(schema_issues(template), [])

    def test_fixture_matches_schema_and_null_capacity_allowed(self):
        package = base_package()
        package['checks'][0]['capacity'] = None
        self.assertEqual(schema_issues(package), [])

    def test_inline_hash_is_canonical(self):
        self.assertEqual(content_hash({'b': 1, 'a': '中'}), content_hash({'a': '中', 'b': 1}))

    def test_file_evidence(self):
        (self.dir / 'calc.txt').write_text('M-phi', encoding='utf-8')
        package = {'sources': {'calc': {'kind': 'file', 'title': 'x', 'path': 'calc.txt', 'sha256': file_hash(self.dir / 'calc.txt')}}}
        self.assertEqual(verify_sources(package, self.dir), [])
        package['sources']['calc']['sha256'] = '0' * 64
        self.assertTrue(verify_sources(package, self.dir))
        self.assertTrue(verify_sources(package, None))

    def test_zip_round_trip_and_assets(self):
        package = base_package()
        package['assets'] = [{'id': 'fig', 'path': 'assets/fig.png'}, {'id': 'escape', 'path': '../../outside.png'}]
        raw = make_zip({'handoff.json': json.dumps(package, ensure_ascii=False), 'assets/fig.png': b'png'})
        loaded = load_zip(raw, self.dir / 'pkg')
        self.assertEqual(loaded.data['bridge_id'], 'TEST-01')
        self.assertEqual(loaded.asset_path('fig').read_bytes(), b'png')
        self.assertIsNone(loaded.asset_path('escape'))
        self.assertIsNone(loaded.asset_path('unknown'))

    def test_zip_rejects_traversal(self):
        with self.assertRaises(PackageError):
            load_zip(make_zip({'handoff.json': '{}', '../evil.txt': 'x'}), self.dir / 'pkg')

    def test_zip_requires_handoff(self):
        with self.assertRaises(PackageError):
            load_zip(make_zip({'data/handoff.json': '{}'}), self.dir / 'pkg')

    def test_not_a_zip(self):
        with self.assertRaises(PackageError):
            load_zip(b'not a zip', self.dir / 'pkg')

    def test_json_rejects_nan(self):
        with self.assertRaises(PackageError):
            parse_json('{"a": NaN}')

    def test_load_file_limits_assets_to_root(self):
        (self.dir / 'examples' / 'golden').mkdir(parents=True)
        (self.dir / 'examples' / 'golden' / 'a.png').write_bytes(b'x')
        (self.dir / 'examples' / 'v').mkdir()
        (self.dir / 'examples' / 'v' / 'p.json').write_text(json.dumps({'assets': [{'id': 'a', 'path': '../golden/a.png'}]}),
                                                           encoding='utf-8')
        inside = load_file(self.dir / 'examples' / 'v' / 'p.json', root_limit=self.dir / 'examples')
        self.assertIsNotNone(inside.asset_path('a'))
        narrow = load_file(self.dir / 'examples' / 'v' / 'p.json')
        self.assertIsNone(narrow.asset_path('a'))

    def test_dict_package_has_no_files(self):
        self.assertIsNone(Package({'assets': [{'id': 'a', 'path': 'a.png'}]}).asset_path('a'))


if __name__ == '__main__':
    unittest.main()
