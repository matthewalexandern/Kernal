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
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/includes.chroot/etc/profile.d/60-kythos-suggestions.sh'
ENGINE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest'
CATALOGUE = ROOT / 'config/includes.chroot/usr/share/kythos/command-intents.json'
BASH = os.environ.get('KYTHOS_TEST_BASH') or shutil.which('bash')


class Terminal:
    SNAPSHOT_DONE = b'__KYTHOS_STATE_DONE__'

    def __init__(self, directory, before='', after=''):
        self.process = None
        self.master = None
        self._slave = None
        self.pending = bytearray()
        self.transcript = bytearray()
        self._capture_ready = False
        self._command_number = 0
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
        def controlling_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        env = dict(os.environ, TERM='xterm', INPUTRC='/dev/null',
                   HISTFILE=str(self.directory / 'history'),
                   PATH=f'{self.bin}:/usr/bin:/bin', PS1='__PTY__> ', PS2='__MORE__> ')
        env.pop('KYTHOS_SUGGESTIONS', None)
        try:
            self.master, self._slave = pty.openpty()
            fcntl.ioctl(self._slave, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 160, 0, 0))
            self.process = subprocess.Popen([BASH, '--noprofile', '--norc', '-i'],
                                            stdin=self._slave, stdout=self._slave, stderr=self._slave,
                                            cwd=self.directory, env=env,
                                            preexec_fn=controlling_terminal)
            os.close(self._slave)
            self._slave = None
            self.wait_for(b'__PTY__> ')
            # The terminator proves printf finished; file creation alone does
            # not mean the snapshot contents have arrived yet.
            capture = ("__test_capture() { builtin printf '%s\\0%s\\0"
                       + self.SNAPSHOT_DONE.decode() + "\\0' "
                       + f'"$READLINE_LINE" "$READLINE_POINT" > {shlex.quote(str(self.state_path))}; }}; '
                       + "bind -x '\"\\e[98~\": __test_capture'")
            self.command('PS1="__PTY__> "; ' + capture + '; ' + before +
                         ('; ' if before else '') + f'source {shlex.quote(str(profile))}' +
                         ('; ' + after if after else ''))
            self._capture_ready = True
        except BaseException:
            self.close()
            raise

    def _read_raw(self, timeout):
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

    def read(self, timeout=0.15):
        chunks = bytes(self.pending)
        self.pending.clear()
        return chunks + self._read_raw(timeout)

    def send(self, data):
        os.write(self.master, data.encode() if isinstance(data, str) else data)

    def wait_for(self, needle, timeout=4):
        deadline = time.monotonic() + timeout
        while True:
            position = self.pending.find(needle)
            if position >= 0:
                end = position + len(needle)
                result = bytes(self.pending[:end])
                del self.pending[:end]
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            incoming = self._read_raw(min(0.05, remaining))
            self.pending.extend(incoming)
            if not incoming and self.process is not None and self.process.poll() is not None:
                break
        raise AssertionError(f'Missing {needle!r}; {self.diagnostic()}')

    def diagnostic(self):
        status = self.process.poll() if self.process is not None else None
        return f'process status: {status}; terminal: {bytes(self.transcript[-3000:])!r}'

    def command(self, command):
        self._command_number += 1
        marker = f'__COMMAND_DONE_{self._command_number}__'
        self.send(command + "; builtin printf '\\n" + marker + "\\n'\n")
        output = self.wait_for(b'\r\n' + marker.encode() + b'\r\n')
        return output + self.read(0.05)

    def state(self):
        self.state_path.unlink(missing_ok=True)
        self.send(b'\x1b[98~')
        deadline = time.monotonic() + 3
        terminator = b'\0' + self.SNAPSHOT_DONE + b'\0'
        while time.monotonic() < deadline:
            try:
                raw = self.state_path.read_bytes()
            except FileNotFoundError:
                raw = b''
            if terminator in raw:
                fields = raw.split(b'\0')
                if len(fields) != 4 or fields[2] != self.SNAPSHOT_DONE or fields[3] or not fields[1].isdigit():
                    raise AssertionError(f'Malformed completed Readline snapshot: {raw!r}; {self.diagnostic()}')
                return fields[0].decode('utf-8', errors='surrogateescape'), int(fields[1])
            if self.process is not None and self.process.poll() is not None:
                break
            self.read(min(0.03, max(0, deadline - time.monotonic())))
        raise AssertionError(f'Readline snapshot failed: {self.diagnostic()}')

    def cancel(self):
        self.send(b'\x03')
        self.wait_for(b'__PTY__> ')
        if self._capture_ready:
            snapshot = self.state()
            if snapshot != ('', 0):
                raise AssertionError(f'Ctrl-C did not clear the edit buffer: {snapshot!r}; {self.diagnostic()}')

    def executions(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def close(self):
        try:
            if self.process is not None and self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    self.process.wait(timeout=2)
        finally:
            self.process = None
            for key in ('master', '_slave'):
                descriptor = getattr(self, key)
                if descriptor is not None:
                    setattr(self, key, None)
                    os.close(descriptor)


class HarnessSynchronizationTests(unittest.TestCase):
    def terminal(self):
        shell = Terminal.__new__(Terminal)
        shell.master = 500
        shell._slave = None
        shell.pending = bytearray()
        shell.transcript = bytearray()
        shell.process = mock.Mock()
        shell.process.poll.return_value = None
        return shell

    def test_wait_preserves_a_second_sentinel_from_the_same_read(self):
        shell = self.terminal()
        raw = b'prefix<FIRST>between<SECOND>suffix'
        with mock.patch.object(select, 'select', side_effect=[([500], [], []), ([], [], [])]), \
                mock.patch.object(os, 'read', return_value=raw) as read:
            self.assertEqual(shell.wait_for(b'<FIRST>'), b'prefix<FIRST>')
            self.assertEqual(shell.wait_for(b'<SECOND>'), b'between<SECOND>')
            self.assertEqual(shell.read(timeout=0), b'suffix')
        read.assert_called_once()
        self.assertEqual(shell.transcript, raw)

    def test_snapshot_waits_for_complete_contents_after_file_creation(self):
        shell = self.terminal()
        with tempfile.TemporaryDirectory() as directory:
            shell.state_path = Path(directory) / 'snapshot'
            shell.send = mock.Mock(side_effect=lambda _: shell.state_path.write_bytes(b'line\0'))
            complete = b'line\0' + b'4\0' + shell.SNAPSHOT_DONE + b'\0'
            shell.read = mock.Mock(side_effect=lambda _: shell.state_path.write_bytes(complete))
            self.assertEqual(shell.state(), ('line', 4))
            shell.read.assert_called_once()

    def test_completed_snapshot_with_malformed_point_is_rejected(self):
        shell = self.terminal()
        with tempfile.TemporaryDirectory() as directory:
            shell.state_path = Path(directory) / 'snapshot'
            completed = b'line\0invalid\0' + shell.SNAPSHOT_DONE + b'\0'
            shell.send = mock.Mock(side_effect=lambda _: shell.state_path.write_bytes(completed))
            with self.assertRaisesRegex(AssertionError, 'Malformed completed Readline snapshot'):
                shell.state()

    def test_spawn_failure_closes_both_pty_descriptors(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(pty, 'openpty', return_value=(500, 501)), \
                mock.patch.object(fcntl, 'ioctl'), \
                mock.patch.object(subprocess, 'Popen', side_effect=OSError('fixture spawn failure')), \
                mock.patch.object(os, 'close') as close:
            with self.assertRaisesRegex(OSError, 'fixture spawn failure'):
                Terminal(directory)
            self.assertEqual(close.call_args_list, [mock.call(500), mock.call(501)])

    def test_initial_prompt_failure_closes_process_and_pty(self):
        process = mock.Mock(pid=12345)
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(pty, 'openpty', return_value=(500, 501)), \
                mock.patch.object(fcntl, 'ioctl'), \
                mock.patch.object(subprocess, 'Popen', return_value=process), \
                mock.patch.object(Terminal, 'wait_for', side_effect=AssertionError('missing initial prompt')), \
                mock.patch.object(os, 'killpg') as kill, \
                mock.patch.object(os, 'close') as close:
            with self.assertRaisesRegex(AssertionError, 'missing initial prompt'):
                Terminal(directory)
            kill.assert_called_once_with(process.pid, signal.SIGTERM)
            process.wait.assert_called_once_with(timeout=0.2)
            self.assertEqual(close.call_args_list, [mock.call(501), mock.call(500)])

    def test_close_is_idempotent(self):
        shell = self.terminal()
        shell.process.pid = 12345
        with mock.patch.object(os, 'killpg') as kill, mock.patch.object(os, 'close') as close:
            shell.close()
            shell.close()
        kill.assert_called_once_with(12345, signal.SIGTERM)
        close.assert_called_once_with(500)


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
        output += shell.wait_for(b'No packaged manual metadata')
        self.assertIn(b'No packaged manual metadata', output)
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
        start = len(shell.transcript)
        shell.send('private_fixture\x1b[[A')
        shell.wait_for(b'private_fixture is a shell function.')
        self.assertEqual(shell.state()[0], 'private_fixture')
        self.assertNotIn(b'must-not-run', bytes(shell.transcript[start:]))
        self.assertEqual(shell.executions(), [])

    def test_explicit_assistance_discovers_shell_names_and_completion_without_execution(self):
        shell = self.shell()
        shell.command("function fixture_function { ip must-not-run; }; alias fixture_alias='ip must-not-run'; "
                      "complete -W 'alpha alpine beta' fixturecmd; "
                      "_dangerous_complete() { ip must-not-run; }; complete -F _dangerous_complete fixture_dynamic")
        output = shell.command("kythos-assist --complete fixture_")
        self.assertIn(b'fixture_function', output)
        self.assertIn(b'fixture_alias', output)
        output = shell.command("kythos-assist --complete 'fixturecmd al'")
        self.assertIn(b'Candidates: alpha alpine', output)
        output = shell.command("kythos-assist --complete 'fixture_dynamic a'")
        self.assertIn(b'dynamic shell completion is registered', output)
        self.assertEqual(shell.executions(), [])

    def test_f1_inspects_pipeline_without_running_or_opening_output(self):
        shell = self.shell()
        line = "ssh --unknown-option 'a | b' | ip 2> output-must-not-exist"
        shell.send(line + '\x1bOP')
        output = shell.wait_for(b'Pipeline/conditional:')
        output += shell.wait_for(b'Redirection 2>')
        self.assertIn(b'Redirection 2>', output)
        self.assertEqual(shell.state()[0], line)
        self.assertEqual(shell.executions(), [])
        self.assertFalse((shell.directory / 'output-must-not-exist').exists())

    def test_sensitive_arguments_are_not_duplicated_in_suggestion_preview(self):
        shell = self.shell()
        line = 'sshcopyid --password private-value-196'
        start = len(shell.transcript)
        shell.send(line + '\t')
        self.assertEqual(shell.state()[0], line)
        self.assertNotIn(b'Suggested:', bytes(shell.transcript[start:]))
        self.assertEqual(shell.executions(), [])

    def test_explicit_assistance_available_when_suggestions_disabled(self):
        shell = self.shell('KYTHOS_SUGGESTIONS=0')
        output = shell.command("kythos-assist --diagnose --status 127 'missing-command'")
        self.assertIn(b'Exit status 127', output)
        self.assertIn(b'not found', output)
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
        start = len(shell.transcript)
        shell.send('change password\t')
        shell.wait_for(b'Whose password? Specify the exact username')
        self.assertEqual(shell.state()[0], 'change password')
        feedback = bytes(shell.transcript[start:])
        self.assertNotIn(b'Suggested:', feedback)
        self.assertIn(b'user', feedback.lower())
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
        start = len(shell.transcript)
        shell.send("'change' na\t")
        shell.state()
        self.assertNotIn(b'Suggested:', bytes(shell.transcript[start:]))

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
