import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_structure import validate


class StructureChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'services/core').mkdir(parents=True)
        (self.root / 'services/core/main.py').write_text('')
        (self.root / 'packs/_template').mkdir(parents=True)
        self.data = {'modules': [{'path': 'services/core', 'maturity': 'implemented', 'implemented': True, 'responsibility': 'API and workers'}], 'planned_modules': [], 'packs': {'template': 'packs/_template', 'namespaces': ['packs/horizontal', 'packs/vertical'], 'manifest_file': 'manifest.yaml', 'active': []}}

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
        self.data['modules'][0]['implemented'] = False
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
        self.data['packs']['active'] = ['packs/vertical/finance/example']
        self.assertTrue(any('Invalid active pack' in e for e in self.check()))

    def test_placeholder_only_module_is_rejected(self):
        (self.root / 'packages/empty').mkdir(parents=True)
        (self.root / 'packages/empty/README.md').write_text('# soon')
        (self.root / 'packages/empty/.gitkeep').write_text('')
        self.data['modules'].append({'path': 'packages/empty', 'maturity': 'skeleton', 'implemented': False, 'responsibility': 'Soon'})
        self.assertTrue(any('only placeholders' in e for e in self.check()))

    def test_planned_module_must_not_exist(self):
        (self.root / 'apps/portal').mkdir(parents=True)
        self.data['planned_modules'] = [{'path': 'apps/portal', 'maturity': 'planned', 'implemented': False, 'responsibility': 'Portal'}]
        self.assertTrue(any('already exists' in e for e in self.check()))

    def test_nested_vertical_pack_is_accepted(self):
        pack = self.root / 'packs/vertical/finance/policy-review'
        pack.mkdir(parents=True)
        (pack / 'manifest.yaml').write_text('id: policy-review\n')
        self.data['packs']['active'] = ['packs/vertical/finance/policy-review']
        self.assertEqual(self.check(), [])

    def test_vertical_pack_needs_an_industry_folder(self):
        pack = self.root / 'packs/vertical/policy-review'
        pack.mkdir(parents=True)
        (pack / 'manifest.yaml').write_text('id: policy-review\n')
        self.data['packs']['active'] = ['packs/vertical/policy-review']
        self.assertTrue(any('Invalid active pack' in e for e in self.check()))

    def _integrations(self, active):
        self.data['integrations'] = {'active': active, 'namespaces': ['integrations/horizontal', 'integrations/vertical'], 'manifest_file': 'integration.yaml'}

    def test_active_integration_needs_its_definition(self):
        self._integrations(['integrations/horizontal/product/wikipedia'])
        self.assertTrue(any('Invalid active integration' in e for e in self.check()))
        folder = self.root / 'integrations/horizontal/product/wikipedia'
        folder.mkdir(parents=True)
        (folder / 'integration.yaml').write_text('id: wikipedia\n')
        self.assertEqual(self.check(), [])

    def test_integration_needs_a_category_folder(self):
        folder = self.root / 'integrations/vertical/finance-rates'
        folder.mkdir(parents=True)
        (folder / 'integration.yaml').write_text('id: finance-rates\n')
        self._integrations(['integrations/vertical/finance-rates'])
        self.assertTrue(any('Invalid active integration' in e for e in self.check()))

    def test_removed_placeholder_service_is_obsolete(self):
        (self.root / 'services/execution').mkdir(parents=True)
        self.assertTrue(any('Obsolete directory: services/execution' in e for e in self.check()))

    def test_edition_must_name_active_packs(self):
        pack = self.root / 'packs/horizontal/brief'
        pack.mkdir(parents=True)
        (pack / 'manifest.yaml').write_text('id: brief\n')
        self.data['packs']['active'] = ['packs/horizontal/brief']
        (self.root / 'packs/editions').mkdir(parents=True)
        (self.root / 'packs/editions/finance.json').write_text(json.dumps({'edition': 'finance', 'packs': ['brief', 'missing']}))
        errors = self.check()
        self.assertEqual(len(errors), 1)
        self.assertIn("names a pack that is not active: 'missing'", errors[0])

    def test_invalid_inventory_reports_error(self):
        (self.root / 'modules.json').write_text('{')
        self.assertTrue(validate(self.root)[0].startswith('Invalid module inventory'))


if __name__ == '__main__':
    unittest.main()
