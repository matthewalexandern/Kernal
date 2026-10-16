#!/usr/bin/python3
"""Read-only CLI help/provenance checks; never query or change packages."""

from pathlib import Path
import os
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CY = ROOT / "config/includes.chroot/usr/local/bin/cy"


def invoke(*arguments, environment=None):
    return subprocess.run([str(CY), *arguments], text=True, capture_output=True,
                          timeout=5, env=environment)


class CyHelp(unittest.TestCase):
    def test_help_uses_cy_for_every_operator_example(self):
        result = invoke("--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.startswith("Usage: cy [options] command\n"))
        self.assertIn("sudo cy update", result.stdout)
        self.assertIn("cy search words", result.stdout)
        self.assertIn("packaged APT", result.stdout)
        self.assertNotIn("Usage: apt", result.stdout)
        for arguments in ((), ("help",), ("-h",), ("install", "--help")):
            with self.subTest(arguments=arguments):
                other = invoke(*arguments)
                self.assertEqual((other.returncode, other.stdout, other.stderr),
                                 (0, result.stdout, ""))

    def test_backend_version_provenance_and_status_are_unchanged(self):
        for arguments in (("--version",), ("-qq", "--version")):
            with self.subTest(arguments=arguments):
                backend = subprocess.run(["/usr/bin/apt", *arguments], text=True,
                                         capture_output=True, timeout=5)
                actual = invoke(*arguments)
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (backend.returncode, backend.stdout, backend.stderr))

    def test_help_does_not_bypass_existing_argument_guards(self):
        result = invoke("--help", "--allow-unauthenticated")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("cy: refusing "))
        environment = dict(os.environ, APT_CONFIG="/should-not-be-read")
        result = invoke("help", environment=environment)
        self.assertEqual(result.returncode, 2)
        self.assertIn("APT_CONFIG", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
