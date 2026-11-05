import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_structure import SERVICES, validate


class StructureChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in SERVICES:
            for area in ('domain', 'application', 'interfaces', 'adapters'):
                (self.root / 'services' / name / 'src' / area).mkdir(parents=True)
        (self.root / 'packs/_template').mkdir(parents=True)
        self.data = {'modules': [{'path': 'services/control-plane', 'maturity': 'skeleton', 'implemented': False, 'responsibility': 'Control plane'}], 'planned_modules': [], 'packs': {'template': 'packs/_template', 'namespaces': ['packs/horizontal', 'packs/vertical'], 'manifest_file': 'manifest.yaml', 'active': []}}

    def check(self):
        (self.root / 'modules.json').write_text(json.dumps(self.data))
        return validate(self.root)

    def test_valid_baseline(self):
        self.assertEqual(self.check(), [])

    def test_duplicate_across_existing_and_planned(self):
        self.data['planned_modules'] = [dict(self.data['modules'][0], maturity='planned')]
        self.assertTrue(any('Duplicate module' in e for e in self.check()))

    def test_escaping_module_path(self):
        self.data['modules'][0]['path'] = '../outside'
        self.assertTrue(any('Invalid module path' in e for e in self.check()))

    def test_false_implementation_claim(self):
        self.data['modules'][0]['implemented'] = True
        self.assertTrue(any('Inconsistent maturity' in e for e in self.check()))

    def test_generated_dependencies_excluded(self):
        d = self.root / 'node_modules/example'
        d.mkdir(parents=True)
        (d / 'README.md').write_text('[bad](missing.md)')
        self.assertEqual(self.check(), [])

    def test_duplicate_heading_and_encoded_link(self):
        (self.root / 'A B.md').write_text('# Heading\n\n# Heading\n')
        (self.root / 'README.md').write_text('[ok](A%20B.md#heading-1)')
        self.assertEqual(self.check(), [])

    def test_missing_link_and_old_pack_path(self):
        (self.root / 'README.md').write_text('packs/<selected-domain>\n[bad](missing.md)')
        errors = self.check()
        self.assertTrue(any('Obsolete module reference' in e for e in errors))
        self.assertTrue(any('missing missing.md' in e for e in errors))

    def test_active_pack_requires_manifest(self):
        self.data['packs']['active'] = ['packs/vertical/example']
        self.assertTrue(any('Invalid active pack' in e for e in self.check()))

    def test_invalid_inventory_reports_error(self):
        (self.root / 'modules.json').write_text('{')
        self.assertTrue(validate(self.root)[0].startswith('Invalid module inventory'))


if __name__ == '__main__':
    unittest.main()
