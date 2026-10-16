#!/usr/bin/python3
"""Read-only CLI help/provenance checks; never query or change packages."""

from pathlib import Path
import errno
import json
import os
import pty
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CY = ROOT / "config/includes.chroot/usr/local/bin/cy"
INTERNAL_OPTIONS = ["-o", "APT::Cmd::Show-Update-Stats=false",
                    "-o", "APT::Get::HideAutoRemove=true"]
UPDATE_TIP = "cy: To inspect available upgrades after this command, use: cy list --upgradable"


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
        self.assertIn("cy list --upgradable", result.stdout)
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


class NativeBackendPresentation(unittest.TestCase):
    """Only a private backend fixture receives update/install arguments."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.evidence = self.work / 'evidence.json'
        self.backend = self.work / 'native-backend'
        self.backend.write_text('''#!/usr/bin/python3 -I
import json, os, sys
from pathlib import Path
Path(os.environ['KYTHOS_TEST_EVIDENCE']).write_text(json.dumps({
    'argv': sys.argv[1:], 'pid': os.getpid(), 'tty': os.isatty(1)}))
print('backend stdout')
print('backend stderr', file=sys.stderr)
raise SystemExit(int(os.environ.get('KYTHOS_TEST_EXIT', '0')))
''')
        self.backend.chmod(0o755)
        self.wrapper = self.work / 'cy'
        original = CY.read_text()
        self.assertEqual(original.count('exec /usr/bin/apt '), 1)
        self.wrapper.write_text(original.replace('exec /usr/bin/apt ',
                                                 f'exec {self.backend} '))
        self.wrapper.chmod(0o755)
        self.environment = dict(os.environ, KYTHOS_TEST_EVIDENCE=str(self.evidence))
        self.environment.pop('APT_CONFIG', None)

    def tty_invoke(self, arguments):
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([str(self.wrapper), *arguments], stdin=subprocess.DEVNULL,
                                       stdout=slave, stderr=subprocess.PIPE, env=self.environment)
            os.close(slave)
            slave = None
            _, error = process.communicate(timeout=5)
            output = bytearray()
            while True:
                try:
                    block = os.read(master, 8192)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not block:
                    break
                output.extend(block)
            return process, output.decode().replace('\r\n', '\n'), error.decode()
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_fixed_native_options_preserve_user_argv_status_and_process(self):
        arguments = ['show', 'literal$(never-executed)', 'argument with spaces', '--', 'exact-name']
        self.environment['KYTHOS_TEST_EXIT'] = '37'
        process = subprocess.Popen([str(self.wrapper), *arguments], text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=self.environment)
        output, error = process.communicate(timeout=5)
        evidence = json.loads(self.evidence.read_text())
        self.assertEqual(evidence['argv'], INTERNAL_OPTIONS + arguments)
        self.assertEqual(evidence['pid'], process.pid, 'backend must replace wrapper via exec')
        self.assertFalse(evidence['tty'])
        self.assertEqual((process.returncode, output, error), (37, 'backend stdout\n', 'backend stderr\n'))

    def test_interactive_update_tip_precedes_backend_without_success_claim(self):
        process, output, error = self.tty_invoke(['update'])
        evidence = json.loads(self.evidence.read_text())
        self.assertEqual(evidence['argv'], INTERNAL_OPTIONS + ['update'])
        self.assertTrue(evidence['tty'])
        self.assertEqual(evidence['pid'], process.pid)
        self.assertEqual(output, UPDATE_TIP + '\nbackend stdout\n')
        self.assertEqual(error, 'backend stderr\n')
        self.assertEqual(process.returncode, 0)

    def test_tip_is_silent_for_redirected_quiet_and_machine_output(self):
        process = subprocess.run([str(self.wrapper), 'update'], capture_output=True, text=True,
                                 env=self.environment, timeout=5)
        self.assertEqual(process.stdout, 'backend stdout\n')
        for arguments in (['-q', 'update'], ['-qq', 'update'], ['--quiet', 'update'],
                          ['--quiet=0', 'update'], ['--silent', 'update'], ['--silent=2', 'update'],
                          ['-yq', 'update'], ['update', '-q'], ['--print-uris', 'update'],
                          ['--version', 'update'], ['install', 'update'], ['list', '--upgradable']):
            with self.subTest(arguments=arguments):
                process, output, error = self.tty_invoke(arguments)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(output, 'backend stdout\n')
                self.assertEqual(error, 'backend stderr\n')
                self.assertEqual(json.loads(self.evidence.read_text())['argv'], INTERNAL_OPTIONS + arguments)

    def test_internal_options_do_not_open_user_configuration_bypass(self):
        for arguments in (['update', '-o', 'APT::Cmd::Show-Update-Stats=true'],
                          ['install', '--allow-unauthenticated', 'package'],
                          ['install', './unsigned.deb']):
            with self.subTest(arguments=arguments):
                process = subprocess.run([str(self.wrapper), *arguments], capture_output=True,
                                         env=self.environment, timeout=5)
                self.assertEqual(process.returncode, 2)
                self.assertFalse(self.evidence.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
