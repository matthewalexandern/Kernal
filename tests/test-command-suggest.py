#!/usr/bin/python3
"""Exercise command proposals using private files, without running proposals."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest'
CATALOGUE = ROOT / 'config/includes.chroot/usr/share/kythos/command-intents.json'
loader = importlib.machinery.SourceFileLoader('command_suggest', str(ENGINE))
spec = importlib.util.spec_from_loader(loader.name, loader)
engine = importlib.util.module_from_spec(spec)
loader.exec_module(engine)


class Suggestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = engine.load_catalogue(CATALOGUE)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        self.commands = self.path / 'bin'
        self.commands.mkdir()
        self.marker = self.path / 'executed'
        self.cli = self.path / 'suggest'
        self.cli.write_text(ENGINE.read_text().replace(
            "CATALOGUE = Path('/usr/share/kythos/command-intents.json')",
            f'CATALOGUE = Path({str(CATALOGUE)!r})'))
        self.cli.chmod(0o755)

    def executable(self, name):
        location = self.commands / name
        location.write_text('#!/bin/sh\ntouch ' + shlex.quote(str(self.marker)) + '\n')
        location.chmod(0o755)
        return location

    def suggest(self, phrase, root=False):
        result = engine.suggest(phrase, self.catalogue, root=root, path=str(self.commands))
        self.assertFalse(self.marker.exists(), 'suggestions must never execute PATH files')
        return result

    def assertCommand(self, phrase, arguments, root=False):
        result = self.suggest(phrase, root=root)
        self.assertEqual(result['kind'], 'suggestion', phrase)
        self.assertEqual(shlex.split(result['command']), arguments, phrase)
        self.assertEqual(set(result), {'command', 'kind', 'message', 'intent'})

    def cli_result(self, phrase, mode='--json', environment=None):
        return subprocess.run([str(self.cli), mode], input=phrase, capture_output=True,
                              timeout=5, env=environment)

    def test_user_phrases_preserve_exact_account_and_root_privilege(self):
        for phrase in ("change matthew's password", 'change password matthew',
                       'change the password for matthew', 'chnage password matthew'):
            self.assertCommand(phrase, ['sudo', 'passwd', 'matthew'])
            self.assertCommand(phrase, ['passwd', 'matthew'], root=True)
        self.assertCommand("change MattHeW’s password", ['sudo', 'passwd', 'MattHeW'])
        self.assertCommand('create user matthew', ['sudo', 'adduser', 'matthew'])
        for phrase in ('make matthew an admin', 'add matthew to administrators'):
            self.assertCommand(phrase, ['sudo', 'usermod', '-aG', 'sudo', 'matthew'])
        self.assertCommand('make matthwe an admin', ['sudo', 'usermod', '-aG', 'sudo', 'matthwe'])

    def test_missing_users_and_root_group_ambiguity_never_guess(self):
        for phrase in ('change password', 'reset password', 'create user'):
            result = self.suggest(phrase)
            self.assertEqual(result['kind'], 'incomplete')
            self.assertIsNone(result['command'])
        for phrase in ('add matthew to root users', 'make matthew root',
                       'add matthew to the root group'):
            result = self.suggest(phrase)
            self.assertEqual(result['kind'], 'ambiguous')
            self.assertIsNone(result['command'])
            self.assertIn('UID 0', result['message'])
        for phrase in ('change password --root', 'make -matthew an admin',
                       'make matthew/admin an admin'):
            self.assertIsNone(self.suggest(phrase))

    def test_ssh_alias_and_destinations_are_literal(self):
        self.executable('ssh')
        self.assertCommand('ssh copy di', ['ssh-copy-id'])
        self.assertCommand('sshcopyid 192.0.2.10', ['ssh-copy-id', '192.0.2.10'])
        self.assertCommand('ssh_copy_id User@sevrer-01', ['ssh-copy-id', 'User@sevrer-01'])
        self.assertCommand('ssh copy id User@sevrer-01', ['ssh-copy-id', 'User@sevrer-01'])
        self.assertCommand('copy ssh key to user@[2001:db8::1]', ['ssh-copy-id', 'user@[2001:db8::1]'])
        self.assertIsNone(self.suggest('ssh user@sevrer-01'))
        self.assertIsNone(self.suggest('ssh copy id -oProxyCommand=anything'))

    def test_package_semantics_and_guarded_backend(self):
        self.assertCommand('refresh package lists', ['sudo', 'cy', 'update'])
        self.assertCommand('check for updates', ['sudo', 'cy', 'update'])
        self.assertCommand('upgrade packages', ['sudo', 'cy', 'upgrade'])
        self.assertEqual(self.suggest('update packages')['kind'], 'ambiguous')
        self.assertCommand('install packages nvdia-driver libfoo:amd64',
                           ['sudo', 'cy', 'install', 'nvdia-driver', 'libfoo:amd64'])
        self.assertCommand('search packages for "network manager"',
                           ['cy', 'search', 'network manager'])
        for phrase in ('install package ./unsigned.deb', 'install package --allow-unauthenticated',
                       'install package /tmp/package.deb'):
            self.assertIsNone(self.suggest(phrase))

    def test_only_declared_cy_action_is_corrected(self):
        self.executable('cy')
        self.assertCommand('cy udpate', ['sudo', 'cy', 'update'])
        self.assertCommand('cy udpate', ['cy', 'update'], root=True)
        self.assertCommand('cy isntall nvdia-driver', ['sudo', 'cy', 'install', 'nvdia-driver'])
        self.assertCommand('cy searhc "network manager"', ['cy', 'search', 'network manager'])
        self.assertCommand('sudo cy udpate', ['sudo', 'cy', 'update'])
        self.assertCommand('sudo cy udpate', ['cy', 'update'], root=True)
        self.assertIsNone(self.suggest('cy install nvdia-driver'))
        self.assertIsNone(self.suggest('cy update'))
        self.assertIsNone(self.suggest('cy unknown nvdia-driver'))

    def test_diagnostics_use_existing_project_commands_without_privilege_guess(self):
        self.assertCommand('check hardware', ['kythos-hardware-status'])
        self.assertCommand('check nvidia', ['kythos-nvidia-readiness'])
        self.assertCommand('check security', ['sudo', 'kythos-security-status'])
        self.assertCommand('show network interfaces', ['ip', '-brief', 'address'])
        self.assertCommand('show routes', ['ip', 'route'])

    def test_executable_typo_is_unique_minimum_four_and_never_executes(self):
        command = self.executable('systemctl')
        result = self.suggest("systmctl status 'name with spaces' /etc/typoo.conf ''")
        self.assertEqual(shlex.split(result['command']),
                         ['systemctl', 'status', 'name with spaces', '/etc/typoo.conf', ''])
        self.executable('systmctl')
        self.assertIsNone(self.suggest('systmctl status'))
        self.assertIsNone(self.suggest('systemctl statuz'))
        self.executable('rm')
        self.assertIsNone(self.suggest('rn document'))
        self.executable('boot')
        self.executable('boat')
        result = self.suggest('boet /a/target')
        self.assertEqual(result['kind'], 'ambiguous')
        self.assertIsNone(result['command'])
        (self.commands / 'system-link').symlink_to(command)
        names, complete = engine.discover_commands(str(self.commands))
        self.assertTrue(complete)
        self.assertIn('system-link', names)

    def test_existing_executable_blocks_fuzzy_natural_phrase_reinterpretation(self):
        self.executable('chage')
        self.assertIsNone(self.suggest('chage password matthew'))
        self.executable('change')
        self.assertCommand('change password matthew', ['sudo', 'passwd', 'matthew'])

    def test_shell_expansion_and_invisible_direction_controls_are_not_reinterpreted(self):
        self.executable('systemctl')
        for phrase in ('systmctl status *.service', 'systmctl status unit?.service',
                       'systmctl status ~/unit', 'cy searhc nginx*',
                       'search packages for abc\u202edef', 'sshcopyid host\u2066name'):
            with self.assertRaises(ValueError, msg=phrase):
                self.suggest(phrase)
        self.assertIsNone(self.suggest('systmctl status unit[12].service'))
        self.assertCommand('sshcopyid user@[2001:db8::1]',
                           ['ssh-copy-id', 'user@[2001:db8::1]'])

    def test_path_entries_are_only_inspected_and_incomplete_scan_declines_typos(self):
        self.executable('systemctl')
        (self.commands / 'systmctl').mkdir()
        (self.commands / 'systemctl.txt').write_text('not executable')
        os.mkfifo(self.commands / 'systmctls')
        names, complete = engine.discover_commands(str(self.commands) + ':.:relative')
        self.assertTrue(complete)
        self.assertEqual(names, {'systemctl'})
        self.assertFalse(self.marker.exists())
        with mock.patch.object(engine, 'MAX_DIRECTORY_ENTRIES', 1):
            self.assertIsNone(self.suggest('systmctl'))
            self.assertIsNone(self.suggest('chnage password matthew'))
        with mock.patch.object(engine, 'MAX_PATH_DIRECTORIES', 1):
            names, complete = engine.discover_commands('/usr/bin:/bin')
            self.assertFalse(complete)

    def test_shell_programs_substitutions_and_multiline_input_are_rejected(self):
        for phrase in ('check hardware; id', 'check hardware | cat', 'check hardware && id',
                       'change password $(id)', 'change password `id`', 'check hardware > x',
                       'check hardware\npasswd root', 'check hardware\rpasswd root',
                       'check hardware\u2028passwd root', 'check hardware\x00',
                       'change password ${USER}', 'change password "unterminated'):
            with self.subTest(phrase=phrase):
                result = self.cli_result(phrase.encode())
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
        self.assertFalse(self.marker.exists())

    def test_bounded_input_and_protocol_are_exact(self):
        result = self.cli_result(b'ssh copy di\n', '--shell')
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.decode().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual((lines[0], lines[2]), ('ssh-copy-id', 'suggestion'))
        for phrase, kind in ((b'change password', 'incomplete'),
                             (b'add matthew to root users', 'ambiguous')):
            result = self.cli_result(phrase, '--shell')
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.decode().splitlines()[0], '')
            self.assertEqual(result.stdout.decode().splitlines()[2], kind)
        result = self.cli_result(b'zqxv missing', '--shell')
        self.assertEqual((result.returncode, result.stdout), (1, b'\n\nnone\n'))
        result = self.cli_result(b'change password', '--json')
        self.assertEqual(json.loads(result.stdout)['command'], None)
        for phrase in (b'x' * 4097, b'\xff', b'word ' * 65):
            result = self.cli_result(phrase)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
        result = self.cli_result(b'check hardware', '--execute')
        self.assertEqual((result.returncode, result.stdout), (2, b''))

    def test_python_environment_cannot_inject_imported_code(self):
        poison = self.path / 'poison'
        poison.mkdir()
        for filename in ('json.py', 'sitecustomize.py'):
            (poison / filename).write_text(
                'from pathlib import Path\nPath(' + repr(str(self.marker)) + ').touch()\n')
        environment = dict(os.environ, PYTHONPATH=str(poison), PYTHONHOME=str(poison),
                           PATH=str(self.commands))
        result = self.cli_result(b'check hardware', environment=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['command'], 'kythos-hardware-status')
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
