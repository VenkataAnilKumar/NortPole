import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rename_nortpole import rename_paths, replace_names, rewrite_file


class RenameNortPoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_replaces_both_requested_variants(self):
        self.assertEqual(replace_names("EVOLVXSI / EvolvXSI / evolvxsi"), "NORTPOLE / NortPole / nortpole")

    def test_dry_run_does_not_write(self):
        path = self.root / "README.md"
        path.write_text("EvolvXSI", encoding="utf-8")
        self.assertTrue(rewrite_file(path, apply=False))
        self.assertEqual(path.read_text(encoding="utf-8"), "EvolvXSI")

    def test_apply_rewrites_utf8_text_and_skips_binary(self):
        text = self.root / "config.json"
        binary = self.root / "image.bin"
        text.write_text('{"name": "evolvxsi"}', encoding="utf-8")
        binary.write_bytes(b"EvolvXSI\x00")
        self.assertTrue(rewrite_file(text, apply=True))
        self.assertFalse(rewrite_file(binary, apply=True))
        self.assertEqual(text.read_text(encoding="utf-8"), '{"name": "nortpole"}')
        self.assertEqual(binary.read_bytes(), b"EvolvXSI\x00")

    def test_renames_paths_when_requested(self):
        old = self.root / "evolvxsi-data"
        old.mkdir()
        self.assertEqual(rename_paths(self.root, apply=True), 1)
        self.assertTrue((self.root / "nortpole-data").is_dir())


if __name__ == "__main__":
    unittest.main()
