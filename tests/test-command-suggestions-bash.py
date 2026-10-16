#!/usr/bin/python3
"""Exercise real Bash/Readline through a private PTY; never change the host shell."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/includes.chroot/etc/profile.d/60-kythos-suggestions.sh'
ENGINE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest'
CATALOGUE = ROOT / 'config/includes.chroot/usr/share/kythos/command-intents.json'
BASH = os.environ.get('KYTHOS_TEST_BASH') or shutil.which('bash')


class Terminal:
    def __init__(self, directory, before='', after=''):
        self.directory = Path(directory)
        self.state_path = self.directory / 'readline-state'
        self.log = self.directory / 'executed.jsonl'
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'fake-command'
        fake.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                        f'with open({str(self.log)!r}, "a") as f: '
                        'f.write(json.dumps(sys.argv) + "\\n")\n')
        fake.chmod(0o755)
        for name in ('ssh', 'ssh-copy-id', 'cy', 'passwd', 'usermod', 'adduser', 'sudo', 'ip'):
            (self.bin / name).symlink_to(fake.name)
        engine = self.directory / 'engine'
        engine.write_text(ENGINE.read_text().replace(
            "Path('/usr/share/kythos/command-intents.json')", f'Path({str(CATALOGUE)!r})'))
        engine.chmod(0o755)
        profile = self.directory / 'suggestions.sh'
        profile.write_text(PROFILE.read_text().replace('/usr/local/libexec/kythos-command-suggest', str(engine)))
        self.profile = profile
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 160, 0, 0))

        def controlling_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        env = dict(os.environ, TERM='xterm', INPUTRC='/dev/null',
                   HISTFILE=str(self.directory / 'history'),
                   PATH=f'{self.bin}:/usr/bin:/bin', PS1='__PTY__> ', PS2='__MORE__> ')
        env.pop('KYTHOS_SUGGESTIONS', None)
        self.process = subprocess.Popen([BASH, '--noprofile', '--norc', '-i'],
                                        stdin=slave, stdout=slave, stderr=slave,
                                        cwd=self.directory, env=env,
                                        preexec_fn=controlling_terminal)
        os.close(slave)
        self.master = master
        self.transcript = bytearray()
        self.wait_for(b'__PTY__> ')
        # A private test-only bind-x observes the actual edit buffer without Enter.
        capture = ("__test_capture() { builtin printf '%s\\n%s\\n' "
                   f'"$READLINE_LINE" "$READLINE_POINT" > {shlex.quote(str(self.state_path))}; }}; '
                   "bind -x '\"\\e[98~\": __test_capture'")
        try:
            self.command('PS1="__PTY__> "; ' + capture + '; ' + before +
                         ('; ' if before else '') + f'source {shlex.quote(str(profile))}' +
                         ('; ' + after if after else ''))
        except BaseException:
            self.close()
            raise

    def read(self, timeout=0.15):
        chunks = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.master], [], [], max(0, deadline - time.monotonic()))
            if not readable:
                break
            try:
                chunk = os.read(self.master, 65536)
            except OSError:
                break
            if not chunk:
                break
            chunks.extend(chunk)
        self.transcript.extend(chunks)
        return bytes(chunks)

    def send(self, data):
        os.write(self.master, data.encode() if isinstance(data, str) else data)

    def wait_for(self, needle, timeout=4):
        result = bytearray()
        deadline = time.monotonic() + timeout
        while needle not in result and time.monotonic() < deadline:
            result.extend(self.read(0.05))
        if needle not in result:
            raise AssertionError(f'Missing {needle!r}; terminal: {result!r}')
        return bytes(result)

    def command(self, command):
        self.send(command + "; builtin printf '\\n__COMMAND_DONE__\\n'\n")
        output = self.wait_for(b'\r\n__COMMAND_DONE__\r\n')
        return output + self.read(0.05)

    def state(self):
        self.state_path.unlink(missing_ok=True)
        self.send(b'\x1b[98~')
        deadline = time.monotonic() + 3
        while not self.state_path.exists() and time.monotonic() < deadline:
            self.read(0.03)
        if not self.state_path.exists():
            raise AssertionError(f'Readline snapshot failed: {bytes(self.transcript[-3000:])!r}')
        line, point = self.state_path.read_text().splitlines()
        return line, int(point)

    def cancel(self):
        self.send(b'\x03')
        self.wait_for(b'__PTY__> ')

    def executions(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=2)
        os.close(self.master)


@unittest.skipUnless(BASH, 'Bash is required for the native Readline PTY tests')
class BashSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kythos-readline-')
        self.shells = []

    def tearDown(self):
        for shell in self.shells:
            shell.close()
        self.temp.cleanup()

    def shell(self, before='', after=''):
        directory = Path(self.temp.name) / f'shell-{len(self.shells)}'
        directory.mkdir()
        shell = Terminal(directory, before, after)
        self.shells.append(shell)
        return shell

    def test_preview_second_tab_accepts_and_only_enter_executes(self):
        shell = self.shell()
        shell.send('sshcopyid 192.0.2.10\t')
        preview = shell.wait_for(b'Suggested: ssh-copy-id 192.0.2.10 [Tab/Right to use]')
        self.assertIn(b'Suggested:', preview)
        self.assertEqual(shell.state(), ('sshcopyid 192.0.2.10', len('sshcopyid 192.0.2.10')))
        self.assertEqual(shell.executions(), [])
        shell.send('\t')
        self.assertEqual(shell.state(), ('ssh-copy-id 192.0.2.10', len('ssh-copy-id 192.0.2.10')))
        self.assertEqual(shell.executions(), [])
        shell.send('\n')
        shell.wait_for(b'__PTY__> ')
        self.assertEqual(shell.executions()[0][1:], ['192.0.2.10'])
        self.assertTrue(shell.executions()[0][0].endswith('/ssh-copy-id'))

    def test_right_accepts_preview_and_otherwise_moves_normally(self):
        shell = self.shell()
        shell.send('sshcopyid 192.0.2.11\t')
        shell.wait_for(b'Suggested:')
        shell.send(b'\x1b[C')
        self.assertEqual(shell.state()[0], 'ssh-copy-id 192.0.2.11')
        self.assertEqual(shell.executions(), [])
        shell.cancel()
        shell.send('abc\x01\x1b[C')
        self.assertEqual(shell.state(), ('abc', 1))

    def test_f1_describes_any_installed_command_without_editing_or_running(self):
        shell = self.shell()
        (shell.bin / 'fresh-tool').symlink_to('fake-command')
        line = 'fresh-tool --some-option exact-target'
        shell.send(line + '\x1bOP')
        output = shell.wait_for(b'fresh-tool - installed command')
        self.assertIn(b'No packaged manual metadata', output + shell.read(0.1))
        self.assertEqual(shell.state(), (line, len(line)))
        self.assertEqual(shell.executions(), [])
        shell.cancel()
        shell.send('read -r exact_variable\x1b[[A')
        shell.wait_for(b'read: read')
        self.assertEqual(shell.state()[0], 'read -r exact_variable')
        self.assertEqual(shell.executions(), [])

    def test_f1_preserves_user_bindings_and_does_not_inspect_function_bodies(self):
        shell = self.shell("bind '\"\\eOP\": \"user-f1\"'")
        shell.send('\x1bOP')
        self.assertEqual(shell.state()[0], 'user-f1')
        shell.cancel()
        shell.command('function private_fixture { ip must-not-run; }; alias fixture_alias="ip must-not-run"')
        shell.send('private_fixture\x1b[[A')
        output = shell.wait_for(b'private_fixture is a shell function.')
        self.assertNotIn(b'must-not-run', output)
        self.assertEqual(shell.state()[0], 'private_fixture')
        self.assertEqual(shell.executions(), [])

    def test_filename_and_programmable_completion_use_native_tab(self):
        shell = self.shell()
        (shell.directory / 'unique-completion-target').touch()
        shell.send('cat unique-comp\t')
        self.assertEqual(shell.state()[0], 'cat unique-completion-target ')
        shell.cancel()
        shell.command("_complete_fixture() { COMPREPLY=(native-${COMP_KEY}); }; complete -F _complete_fixture fixturecmd")
        shell.send('fixturecmd na\t')
        self.assertEqual(shell.state()[0], 'fixturecmd native-9 ')

    def test_repeated_native_completion_lists_ambiguous_filenames(self):
        shell = self.shell()
        for name in ('ambiguous-one', 'ambiguous-two'):
            (shell.directory / name).touch()
        shell.send('cat ambiguous-\t\t')
        output = shell.wait_for(b'ambiguous-two')
        self.assertIn(b'ambiguous-one', output)
        self.assertIn(b'ambiguous-two', output)
        self.assertEqual(shell.state()[0], 'cat ambiguous-')
        self.assertEqual(shell.executions(), [])

    def test_incomplete_target_is_feedback_only(self):
        shell = self.shell()
        shell.send('change password\t')
        feedback = shell.read(0.5)
        self.assertNotIn(b'Suggested:', feedback)
        self.assertIn(b'user', feedback.lower())
        self.assertEqual(shell.state()[0], 'change password')
        self.assertEqual(shell.executions(), [])

    def test_history_and_stale_preview_preserve_native_behavior(self):
        shell = self.shell()
        shell.command('printf history-marker')
        shell.send('sshcopyid 192.0.2.12\t')
        shell.wait_for(b'Suggested:')
        shell.send(b'\x1b[A')
        self.assertTrue(shell.state()[0].startswith('printf history-marker;'))
        shell.send(b'\x1b[B')
        self.assertEqual(shell.state()[0], 'sshcopyid 192.0.2.12')
        shell.send('3\x1b[C')
        self.assertEqual(shell.state()[0], 'sshcopyid 192.0.2.123')
        self.assertEqual(shell.executions(), [])

    def test_quoted_argument_stays_literal_on_acceptance(self):
        shell = self.shell()
        shell.send("cy search 'two words'\t")
        # The valid command remains ordinary completion with its quotes intact.
        shell.read(0.3)
        self.assertEqual(shell.state()[0], "cy search 'two words'")
        shell.cancel()
        shell.send("cy serach 'two words'\t")
        shell.wait_for(b'Suggested: cy search')
        shell.send('\t')
        self.assertEqual(shell.state()[0], "cy search 'two words'")
        self.assertEqual(shell.executions(), [])
        shell.send('\n')
        shell.wait_for(b'__PTY__> ')
        self.assertEqual(shell.executions()[0][1:], ['search', 'two words'])

    def test_unicode_quoted_argument_accepts_at_end_of_buffer(self):
        shell = self.shell()
        shell.send("cy serach 'café tools'\t")
        shell.wait_for(b'Suggested: cy search')
        shell.send('\t')
        command = "cy search 'café tools'"
        self.assertEqual(shell.state(), (command, len(command)))
        self.assertEqual(shell.executions(), [])

    def test_user_alias_and_function_completion_take_precedence(self):
        shell = self.shell()
        shell.command("alias sshcopyid='printf alias'; function change { :; }; "
                      "_user_complete() { COMPREPLY=(user-result); }; "
                      "complete -F _user_complete sshcopyid change")
        shell.send('sshcopyid na\t')
        self.assertEqual(shell.state()[0], 'sshcopyid user-result ')
        shell.cancel()
        shell.send('change na\t')
        self.assertEqual(shell.state()[0], 'change user-result ')
        shell.cancel()
        shell.send("'change' na\t")
        self.assertNotIn(b'Suggested:', shell.read(0.2))

    def test_source_guard_and_later_custom_binding_are_preserved(self):
        shell = self.shell()
        shell.command(f'bind -p > before-p; bind -s > before-s; bind -X > before-X; source {shlex.quote(str(shell.profile))}; '
                      'bind -p > after-p; bind -s > after-s; bind -X > after-X')
        for kind in ('p', 's', 'X'):
            self.assertEqual((shell.directory / f'before-{kind}').read_text(),
                             (shell.directory / f'after-{kind}').read_text())
        shell.command("bind '\"\\C-i\": \"my-custom-tab\"'; kythos_suggestions_off")
        shell.send('\t')
        self.assertEqual(shell.state()[0], 'my-custom-tab')

    def test_off_restores_exact_bindings_and_does_not_export_guard(self):
        shell = self.shell("bind -p > before-p; bind -s > before-s; bind -X > before-X")
        shell.command("export -p > exports; kythos_suggestions_off; bind -p > after-p; bind -s > after-s; bind -X > after-X")
        for kind in ('p', 's', 'X'):
            self.assertEqual((shell.directory / f'before-{kind}').read_text(),
                             (shell.directory / f'after-{kind}').read_text())
        self.assertNotIn('__kythos_suggestions_loaded', (shell.directory / 'exports').read_text())

    def test_disabled_vi_and_custom_tab_bindings_are_untouched(self):
        for before in ('KYTHOS_SUGGESTIONS=0', 'set -o vi',
                       "bind '\"\\C-i\": \"custom-value\"'",
                       "bind -x '\"\\C-i\": printf custom-callback'"):
            with self.subTest(before=before):
                shell = self.shell(before + '; bind -p > before-p; bind -s > before-s; bind -X > before-X')
                shell.command('bind -p > after-p; bind -s > after-s; bind -X > after-X')
                for kind in ('p', 's', 'X'):
                    self.assertEqual((shell.directory / f'before-{kind}').read_text(),
                                     (shell.directory / f'after-{kind}').read_text())

    def test_custom_keymap_is_unchanged(self):
        shell = self.shell('bind "set keymap emacs-meta"; bind -v > before-v; bind -s > before-s',
                           'bind -v > after-v; bind -s > after-s; bind "set keymap emacs"')
        for kind in ('v', 's'):
            self.assertEqual((shell.directory / f'before-{kind}').read_text(),
                             (shell.directory / f'after-{kind}').read_text())

    def test_noninteractive_and_nonbash_have_no_effect(self):
        for executable in (BASH, shutil.which('dash')):
            if not executable:
                continue
            result = subprocess.run([executable, '-c', f'. {shlex.quote(str(PROFILE))}; printf untouched'],
                                    text=True, capture_output=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'untouched', ''))


if __name__ == '__main__':
    unittest.main()
