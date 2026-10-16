#!/usr/bin/python3
"""Verify optional space-saving retention preserves audited output bytes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retain_output', ROOT / 'scripts/retain-build-output.py')
output = importlib.util.module_from_spec(spec)
spec.loader.exec_module(output)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.source = self.root / 'candidate.iso'
        self.source.write_bytes(b'Nonbootable artifact-retention fixture\0\xff')
        self.destination = self.root / 'artifacts'
        self.destination.mkdir()

    def test_default_copy_is_independent(self):
        output.retain(self.source, self.destination)
        retained = self.destination / self.source.name
        self.assertEqual(retained.read_bytes(), self.source.read_bytes())
        self.assertNotEqual(retained.stat().st_ino, self.source.stat().st_ino)

    def test_explicit_hardlink_survives_build_input_removal(self):
        original = self.source.read_bytes()
        output.retain(self.source, self.destination, 'hardlink')
        retained = self.destination / self.source.name
        self.assertEqual(retained.stat().st_ino, self.source.stat().st_ino)
        self.assertEqual(retained.stat().st_nlink, 2)
        self.source.unlink()
        self.assertEqual(retained.read_bytes(), original)

    def test_rejects_existing_artifact_and_symlink_inputs(self):
        retained = self.destination / self.source.name
        retained.write_bytes(b'Existing user artifact')
        for mode in ('copy', 'hardlink'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                output.retain(self.source, self.destination, mode)
        self.assertEqual(retained.read_bytes(), b'Existing user artifact')
        retained.unlink()
        link = self.root / 'alias.iso'
        link.symlink_to(self.source.name)
        with self.assertRaises(ValueError):
            output.retain(link, self.destination)


if __name__ == '__main__':
    unittest.main()
