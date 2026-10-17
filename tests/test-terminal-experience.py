#!/usr/bin/python3
"""Real Bash PTYs, theme files, and installer preference boundary fixtures."""

import fcntl
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import types
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
INCLUDES = ROOT / 'config/includes.chroot'
HISTORY = INCLUDES / 'etc/profile.d/54-kythos-history.sh'
THEME = INCLUDES / 'usr/local/bin/kythos-theme'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


theme = load('terminal_theme', THEME)
with mock.patch.dict(sys.modules, libcalamares=types.SimpleNamespace()):
    installer = load('installer_theme', INCLUDES / 'etc/calamares/modules/kythos-terminaltheme/main.py')


class BashPty:
    def __init__(self, directory, term='xterm-256color', extra=''):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 120, 0, 0))
        rc = directory / ('bashrc-' + str(self.slave))
        rc.write_text('PS1="__READY__ "\n' + extra + '\n. ' + repr(str(HISTORY)) + '\n')
        environment = {name: os.environ[name] for name in ('PATH', 'LANG', 'LC_ALL') if name in os.environ}
        environment.update(HOME=str(directory), TERM=term, HISTFILE=str(directory / 'history'),
                           KYTHOS_TEST_SECRET='test-value-never-in-history')

        def controlling_pty():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self.process = subprocess.Popen(['/bin/bash', '--noprofile', '--rcfile', str(rc), '-i'],
                                        stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                        env=environment, cwd=directory, preexec_fn=controlling_pty)
        self.receive()

    def receive(self):
        output = bytearray()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.1)[0]:
                output.extend(os.read(self.master, 65536))
                if b'__READY__ ' in output:
                    return bytes(output)
            if self.process.poll() is not None:
                break
        raise AssertionError('Bash prompt unavailable: ' + output.decode(errors='replace'))

    def send(self, value):
        os.write(self.master, value if isinstance(value, bytes) else value.encode() + b'\n')
        return self.receive()

    def close(self):
        if self.process.poll() is None:
            os.write(self.master, b'exit\n')
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=3)
        os.close(self.master)
        os.close(self.slave)


class ShellHistoryTests(unittest.TestCase):
    def test_cursor_history_and_incremental_search_on_vt_and_gui_terminal_protocols(self):
        for terminal in ('linux', 'xterm-256color'):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                shell = BashPty(directory, terminal)
                try:
                    shell.send("printf 'alpha\\n' >> result")
                    shell.send("printf 'beta\\n' >> result")
                    shell.send(b'\x1b[A\x1b[A\x1b[B\r')
                    shell.send(b'\x12alpha\r')
                finally:
                    shell.close()
                self.assertEqual((directory / 'result').read_text().splitlines(),
                                 ['alpha', 'beta', 'beta', 'alpha'])

    def test_live_sessions_append_import_persist_and_never_log_expanded_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first, second = BashPty(directory), BashPty(directory)
            try:
                first.send('printf first-session >> result')
                second.send(':')  # prompt imports the first session's input
                self.assertIn(b'first-session', second.send('history'))
                second.send('printf second-session >> result')
                first.send(':')
                self.assertIn(b'second-session', first.send('history'))
                first.send('printf "%s" "$KYTHOS_TEST_SECRET" > /dev/null')
                first.send(' printf hidden-entry > /dev/null')
            finally:
                first.close()
                second.close()
            stored = (directory / 'history').read_text()
            self.assertIn('first-session', stored)
            self.assertIn('second-session', stored)
            self.assertEqual(stored.count('printf first-session >> result'), 1)
            self.assertEqual(stored.count('printf second-session >> result'), 1)
            self.assertIn('$KYTHOS_TEST_SECRET', stored)
            self.assertNotIn('test-value-never-in-history', stored)
            self.assertNotIn('hidden-entry', stored)
            third = BashPty(directory)
            try:
                self.assertIn(b'first-session', third.send('history'))
                self.assertIn(b'second-session', third.send('history'))
            finally:
                third.close()

    def test_existing_bindings_prompt_hooks_and_exit_status_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shell = BashPty(directory, extra='bind \'"\\e[A": "MY-CUSTOM-BINDING"\'\n'
                           'PROMPT_COMMAND=(\'last_status=$?\')\n. ' + repr(str(HISTORY)))
            try:
                self.assertIn(b'MY-CUSTOM-BINDING', shell.send('bind -s'))
                shell.send('false')
                self.assertIn(b'__STATUS__1', shell.send('printf "__STATUS__%s\\n" "$last_status"'))
                hooks = shell.send('declare -p PROMPT_COMMAND')
                self.assertEqual(hooks.count(b'[0]="_kythos_history_sync"'), 1)
                self.assertIn(b'last_status=\\$?', hooks)
            finally:
                shell.close()


class AppearanceTests(unittest.TestCase):
    def test_all_palettes_and_user_preference_apply_without_shell_interpretation(self):
        choices = theme.themes()
        self.assertEqual(set(choices), installer.CHOICES)
        self.assertEqual(choices['dark']['foreground'], '#ffffff')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            preference = directory / 'terminal-theme'
            theme.save_preference('teal', preference)
            self.assertEqual(theme.read_preference(preference, choices), 'teal')
            self.assertEqual(preference.stat().st_mode & 0o777, 0o600)
            preference.write_text('dark; touch unwanted\n')
            self.assertIsNone(theme.read_preference(preference, choices))
            preference.write_text('dark' + ' ' * 100)
            self.assertIsNone(theme.read_preference(preference, choices))
            preference.unlink()
            preference.symlink_to('/etc/passwd')
            self.assertIsNone(theme.read_preference(preference, choices))
        self.assertEqual(theme.escape_sequence(choices['dark'], 'dumb'), '')
        self.assertIn('\x1b]P7ffffff', theme.escape_sequence(choices['dark'], 'linux'))
        self.assertNotIn('P4', theme.escape_sequence(choices['dark'], 'linux'))
        self.assertIn('\x1b]11;#003333', theme.escape_sequence(choices['teal'], 'xterm-256color'))
        for name, palette in choices.items():
            with self.subTest(theme=name):
                sequence = theme.escape_sequence(palette, 'xterm-256color')
                self.assertIn('\x1b]10;' + palette['foreground'], sequence)
                self.assertIn('\x1b]11;' + palette['background'], sequence)
                self.assertTrue(sequence.endswith('\x1b[39;49m'))
                self.assertNotIn('\x1b[37;40m', sequence)
                self.assertNotIn('\x1b[30;47m', sequence)

    def test_real_palette_cli_keeps_redirection_plain_and_rejects_unknown_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ, XDG_CONFIG_HOME=temporary)
            result = subprocess.run([THEME, 'blue'], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('\x1b', result.stdout)
            result = subprocess.run([THEME, '--show'], env=environment, capture_output=True, text=True)
            self.assertEqual(result.stdout, 'blue\n')
            result = subprocess.run([THEME, '$(touch unwanted)'], env=environment, capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_palette_cli_emits_the_selected_palette_on_actual_terminal_ptys(self):
        for terminal in ('linux', 'xterm-256color'):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                shell = BashPty(directory, terminal)
                try:
                    output = shell.send(str(THEME) + ' teal')
                    expected = b'\x1b]P0003333' if terminal == 'linux' else b'\x1b]11;#003333\x07'
                    self.assertIn(expected, output)
                    if terminal != 'linux':
                        self.assertIn(b'\x1b[39;49m', output)
                        self.assertNotIn(b'\x1b[37;40m', output)
                    self.assertEqual((directory / '.config/kythos/terminal-theme').read_text(), 'teal\n')
                finally:
                    shell.close()

    def test_installer_defaults_and_persists_only_a_valid_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            preference = directory / 'live-choice'
            self.assertEqual(installer.read_choice(preference), 'dark')
            preference.write_text('high-contrast\n')
            self.assertEqual(installer.read_choice(preference), 'high-contrast')
            target = directory / 'target'
            target.mkdir()
            installer.install_choice(target, installer.read_choice(preference))
            self.assertEqual((target / 'etc/kythos/terminal-theme').read_text(), 'high-contrast\n')
            preference.write_text('light\x1b[31m')
            self.assertEqual(installer.read_choice(preference), 'dark')
            with self.assertRaises(ValueError):
                installer.install_choice(Path('/'), 'dark')
            with self.assertRaises(ValueError):
                installer.install_choice(target, 'not-a-theme')

    def test_login_banner_uses_agetty_terminal_escape_and_preserves_debian_notice(self):
        issue = (INCLUDES / 'etc/issue').read_text()
        self.assertIn('terminal: \\l', issue)
        self.assertNotIn('tty1', issue)
        self.assertIn('[TM]', issue)
        self.assertIn('Debian', (INCLUDES / 'etc/motd').read_text())


if __name__ == '__main__':
    unittest.main()
