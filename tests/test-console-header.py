#!/usr/bin/python3
"""Private PTY/native tmux checks. Never open a physical Linux console."""

import errno
import contextlib
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import shlex
import socket
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
WRAPPER = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-console-session'
CONFIG = ROOT / 'config/includes.chroot/usr/share/kythos/console-tmux.conf'
PROFILE = ROOT / 'config/includes.chroot/etc/profile.d/55-kythos-console.sh'
CLI = ROOT / 'config/includes.chroot/usr/local/bin/kythos-console'
loader = importlib.machinery.SourceFileLoader('console_session', str(WRAPPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
console = importlib.util.module_from_spec(spec)
loader.exec_module(console)
cli_loader = importlib.machinery.SourceFileLoader('console_cli', str(CLI))
cli_spec = importlib.util.spec_from_loader(cli_loader.name, cli_loader)
cli = importlib.util.module_from_spec(cli_spec)
cli_loader.exec_module(cli)


def native_tools():
    # Optional source-tree fixture; image validation separately requires tmux.
    tools = ROOT / '.build/tmux-native-tools'
    extracted = tools / 'extracted-setup-wizard'
    binary = extracted / 'usr/bin/tmux'
    environment = dict(os.environ)
    if binary.is_file():
        metadata = json.loads((tools / 'apt-download-metadata.json').read_text())
        for package in metadata['packages']:
            package_file = tools / package['filename']
            if hashlib.sha256(package_file.read_bytes()).hexdigest() != package['sha256']:
                raise AssertionError('native package hash changed')
        environment['LD_LIBRARY_PATH'] = str(extracted / 'usr/lib/x86_64-linux-gnu')
        return str(binary), environment
    binary = shutil.which('tmux')
    return binary, environment


class ConsoleGuards(unittest.TestCase):
    def eligible(self, environment=None, tty='/dev/tty1', output_tty=None, live=False):
        environment = {'TERM': 'linux'} if environment is None else environment
        with mock.patch.object(console, 'live_boot', return_value=live), \
                mock.patch.object(console.os, 'isatty', return_value=True), \
                mock.patch.object(console.os, 'ttyname', side_effect=[tty, output_tty or tty]):
            return console.eligible(environment)

    def test_only_local_linux_vt_is_eligible_and_live_boot_is_excluded(self):
        self.assertTrue(self.eligible())
        self.assertTrue(self.eligible(tty='/dev/tty12'))
        for tty in ('/dev/tty0', '/dev/tty', '/dev/tty1evil', '/dev/pts/1'):
            self.assertFalse(self.eligible(tty=tty))
        self.assertFalse(self.eligible(output_tty='/dev/tty2'))
        self.assertFalse(self.eligible(live=True))
        for extra in ({'SSH_CONNECTION': 'remote'}, {'SSH_CLIENT': 'remote'}, {'SSH_TTY': '/dev/pts/1'},
                      {'TMUX': '/private/socket'}, {'TERM': 'xterm-256color'}, {'TERM': 'dumb'},
                      {'KYTHOS_CONSOLE_HEADER': '0'}):
            self.assertFalse(self.eligible(dict({'TERM': 'linux'}, **extra)))
        with mock.patch.object(console.os, 'isatty', return_value=False):
            self.assertFalse(console.eligible({'TERM': 'linux'}))
        self.assertTrue(console.live_boot('quiet boot=live components', False))
        self.assertTrue(console.live_boot('quiet', True))
        self.assertFalse(console.live_boot('quiet root=UUID=fixture', False))

    def test_profile_is_inert_for_noninteractive_shell_and_applies_default_prompt(self):
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c',
                                 'PS1=sentinel; . "$1"; printf "%s" "$PS1"', 'test', str(PROFILE)],
                                capture_output=True, text=True, timeout=5, env=dict(os.environ, TERM='linux'))
        self.assertEqual((result.returncode, result.stdout), (0, 'sentinel'))
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-i', '-c',
                                 '. "$1"; printf "%s" "$PS1"', 'test', str(PROFILE)],
                                capture_output=True, text=True, timeout=5,
                                env=dict(os.environ, TERM='xterm', KYTHOS_CONSOLE_HEADER='0'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, r'\u@\[\e[34m\]\h\[\e[0m\]:\w\$ ')

    def test_color_uses_only_per_vt_linux_sequence_with_opt_out(self):
        with mock.patch.object(console.os, 'write') as write:
            console.apply_console_color({})
            write.assert_called_once_with(1, b'\x1b]P49eafff')
            write.reset_mock()
            console.apply_console_color({'KYTHOS_CONSOLE_COLOR': '0'})
            write.assert_not_called()
        with mock.patch.object(console.os, 'write', side_effect=OSError(errno.ENOTTY, 'fixture')):
            console.apply_console_color({})

    def test_failure_falls_back_to_bash_without_reentry_and_signal_does_not(self):
        with mock.patch.object(console, 'eligible', return_value=True), \
                mock.patch.object(console, 'run_session', side_effect=OSError('fixture')), \
                mock.patch.object(console.os, 'execve') as execute, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            console.main([])
            self.assertIn('continuing with Bash', error.getvalue())
            executable, arguments, environment = execute.call_args.args
            self.assertEqual((executable, arguments), ('/bin/bash', ['/bin/bash', '-l']))
            self.assertEqual(environment['KYTHOS_CONSOLE_HEADER'], '0')
        with mock.patch.object(console, 'eligible', return_value=True), \
                mock.patch.object(console, 'run_session', side_effect=console.SessionInterrupted(signal.SIGTERM)), \
                mock.patch.object(console.os, 'execve') as execute:
            self.assertEqual(console.main([]), 128 + signal.SIGTERM)
            execute.assert_not_called()
        with mock.patch.object(console, 'eligible', return_value=True), \
                mock.patch.object(console, 'run_session', return_value=console.RAW_REQUESTED), \
                mock.patch.object(console.os, 'execve') as execute:
            self.assertEqual(console.main([]), 0)
            executable, arguments, environment = execute.call_args.args
            self.assertEqual((executable, arguments), ('/bin/bash', ['/bin/bash', '-l']))
            self.assertEqual(environment['KYTHOS_CONSOLE_HEADER'], '0')

    def test_raw_cli_requires_private_managed_socket_and_pins_detach_client(self):
        directory = Path(tempfile.mkdtemp(prefix='kythos-console-', dir='/tmp'))
        self.addCleanup(shutil.rmtree, directory)
        connection = socket.socket(socket.AF_UNIX)
        self.addCleanup(connection.close)
        socket_path = directory / 'socket'
        connection.bind(str(socket_path))
        socket_path.chmod(0o600)
        environment = {'TMUX': str(socket_path) + ',123,0', 'TMUX_PANE': '%0'}
        self.assertEqual(cli.private_socket(environment), (str(socket_path), '%0'))
        success = subprocess.CompletedProcess([], 0, b'', b'')
        managed = subprocess.CompletedProcess([], 0, b'1\t1\tkythos\t1\t1\t1\t/dev/tty2\n', b'')
        with mock.patch.object(cli, 'tmux_call', side_effect=[managed, success, success]) as call:
            self.assertEqual(cli.raw(environment), 0)
            self.assertEqual(call.call_args_list[-2].args[1], ['set-option', '-g', '@kythos_raw', '1'])
            self.assertEqual(call.call_args_list[-1].args[1], ['detach-client', '-t', '/dev/tty2'])
        unmanaged = subprocess.CompletedProcess([], 0, b'0\t1\tother\t1\t1\t1\t/dev/tty2\n', b'')
        with mock.patch.object(cli, 'tmux_call', return_value=unmanaged) as call:
            with self.assertRaises(ValueError): cli.raw(environment)
            self.assertEqual(call.call_count, 1, 'ordinary tmux must not be detached')
        for reply in (b'1\t2\tkythos\t1\t1\t1\t/dev/tty2\n',
                      b'1\t1\tkythos\t1\t1\t2\t/dev/tty2\n'):
            with mock.patch.object(cli, 'tmux_call', return_value=subprocess.CompletedProcess([], 0, reply, b'')) as call:
                with self.assertRaises(ValueError): cli.raw(environment)
                self.assertEqual(call.call_count, 1, 'shared sessions/clients must not be destroyed')
        directory.chmod(0o755)
        with self.assertRaises(ValueError): cli.private_socket(environment)
        directory.chmod(0o700)
        with mock.patch.object(cli.os, 'geteuid', return_value=os.getuid() + 1):
            with self.assertRaisesRegex(ValueError, 'original console login user'):
                cli.private_socket(environment)
        for value in ('/tmp/tmux-1000/default,123,0', str(socket_path) + ',evil,0',
                      str(socket_path) + '/../socket,123,0'):
            with self.assertRaises(ValueError):
                cli.private_socket(dict(environment, TMUX=value))

    def test_header_cli_rechecks_raw_terminal_and_drops_only_disable_flag(self):
        environment = {'TERM': 'linux', 'KYTHOS_CONSOLE_HEADER': '0', 'UNCHANGED': 'value'}
        success = subprocess.CompletedProcess([], 0)
        with mock.patch.object(cli.subprocess, 'run', return_value=success) as call, \
                mock.patch.object(cli.os, 'execve') as execute:
            self.assertEqual(cli.header(environment), 0)
            passed = call.call_args.kwargs
            self.assertIsNone(passed['stdin'])
            self.assertIsNone(passed['stdout'], 'eligibility must see the real original terminal')
            self.assertNotIn('KYTHOS_CONSOLE_HEADER', passed['env'])
            self.assertEqual(execute.call_args.args, (cli.WRAPPER, [cli.WRAPPER], {'TERM': 'linux', 'UNCHANGED': 'value'}))
        with mock.patch.object(cli.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                mock.patch.object(cli.os, 'execve') as execute:
            with self.assertRaisesRegex(ValueError, 'raw local Linux console'):
                cli.header(dict(environment, SSH_CONNECTION='remote'))
            execute.assert_not_called()


class Screen:
    """Small test-only ASCII VT model for tmux's outer Linux-console stream."""
    def __init__(self, rows, columns):
        self.resize(rows, columns)
        self.pending = ''

    def resize(self, rows, columns):
        self.rows, self.columns = rows, columns
        self.lines = [[' '] * columns for _ in range(rows)]
        self.row = self.column = 0
        self.top, self.bottom = 0, rows - 1
        self.saved = (0, 0)

    def scroll(self):
        if self.row > self.bottom:
            self.lines.pop(self.top)
            self.lines.insert(self.bottom, [' '] * self.columns)
            self.row = self.bottom

    def feed(self, data):
        text = self.pending + data.decode('ascii', errors='ignore')
        self.pending = ''
        offset = 0
        while offset < len(text):
            character = text[offset]
            if character == '\x1b':
                if text.startswith('\x1b]P', offset):
                    if len(text) - offset < 10:
                        self.pending = text[offset:]
                        break
                    offset += 10
                    continue
                match = re.match(r'\x1b\[([0-9;? >:=!]*)([@-~])', text[offset:])
                if match:
                    raw, operation = match.groups()
                    numbers = [int(n) if n else 0 for n in raw.lstrip('? >:=!').split(';')]
                    self.csi(operation, numbers, raw.startswith('?'))
                    offset += len(match[0])
                    continue
                if offset + 1 == len(text):
                    self.pending = text[offset:]
                    break
                code = text[offset + 1]
                if code == '[':
                    self.pending = text[offset:]
                    break
                if code in ']P_':
                    ending = re.search(r'\x07|\x1b\\', text[offset + 2:])
                    if ending is None:
                        self.pending = text[offset:]
                        break
                    offset += 2 + ending.end()
                    continue
                if code in '()':
                    if offset + 2 == len(text):
                        self.pending = text[offset:]
                        break
                    offset += 3
                    continue
                if code == '7': self.saved = (self.row, self.column)
                if code == '8': self.row, self.column = self.saved
                if code in 'DE': self.row += 1; self.scroll()
                if code == 'M': self.row = max(self.top, self.row - 1)
                if code == 'c': self.resize(self.rows, self.columns)
                offset += 2
                continue
            if character == '\r': self.column = 0
            elif character == '\n': self.row += 1; self.scroll()
            elif character == '\b': self.column = max(0, self.column - 1)
            elif character == '\t': self.column = min(self.columns - 1, (self.column // 8 + 1) * 8)
            elif ord(character) >= 32 and ord(character) != 127:
                if self.column >= self.columns:
                    self.column = 0; self.row += 1; self.scroll()
                self.lines[self.row][self.column] = character
                self.column += 1
            offset += 1

    def csi(self, code, n, private):
        value = n[0] or 1
        if code in 'Hf': self.row, self.column = value - 1, (n[1] or 1) - 1 if len(n) > 1 else 0
        elif code == 'G': self.column = value - 1
        elif code == 'd': self.row = value - 1
        elif code == 'A': self.row -= value
        elif code == 'B': self.row += value
        elif code == 'C': self.column += value
        elif code == 'D': self.column -= value
        elif code == 'r':
            self.top, self.bottom = value - 1, (n[1] or self.rows) - 1 if len(n) > 1 else self.rows - 1
            # Linux DECSTBM also homes the cursor (DECOM is off here).
            self.row = self.column = 0
        elif code == 'J':
            if n[0] in (2, 3): self.lines = [[' '] * self.columns for _ in range(self.rows)]
            elif n[0] == 0:
                self.lines[self.row][self.column:] = [' '] * (self.columns - self.column)
                for row in range(self.row + 1, self.rows): self.lines[row] = [' '] * self.columns
        elif code == 'K':
            start, end = (0, self.column + 1) if n[0] == 1 else (0, self.columns) if n[0] == 2 else (self.column, self.columns)
            self.lines[self.row][start:end] = [' '] * (end - start)
        elif code == 'P': self.lines[self.row][self.column:] = self.lines[self.row][self.column + value:] + [' '] * value
        elif code == 'L':
            for _ in range(value): self.lines.pop(self.bottom); self.lines.insert(self.row, [' '] * self.columns)
        elif code == 'M':
            for _ in range(value): self.lines.pop(self.row); self.lines.insert(self.bottom, [' '] * self.columns)
        self.row = max(0, min(self.row, self.rows - 1))
        self.column = max(0, min(self.column, self.columns - 1))


class NativeViewport(unittest.TestCase):
    def setUp(self):
        self.binary, self.environment = native_tools()
        if not self.binary:
            self.skipTest('tmux not installed and authenticated extracted native fixture unavailable')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.attributes = termios.tcgetattr(self.slave)
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 100, 0, 0))
        self.environment.update(TERM='linux', HOME=str(self.work), HISTFILE='/dev/null', PS1='TEST> ')
        for name in ('TMUX', 'SSH_CONNECTION', 'SSH_CLIENT', 'SSH_TTY', 'BASH_ENV'):
            self.environment.pop(name, None)
        script = self.work / 'session.py'
        script.write_text('import importlib.machinery, os\n'
                          'm = importlib.machinery.SourceFileLoader("console", ' + repr(str(WRAPPER)) + ').load_module()\n'
                          'm.runtime_parent = lambda: ' + repr(str(self.work)) + '\n'
                          'result = m.run_session(tmux=' + repr(self.binary) + ', config=' + repr(str(CONFIG)) +
                          ', shell=("/bin/bash", "--noprofile", "--norc"))\n'
                          'if result == m.RAW_REQUESTED:\n'
                          '    environment = dict(os.environ, KYTHOS_CONSOLE_HEADER="0", PS1="RAW> ")\n'
                          '    os.execve("/bin/bash", ["/bin/bash", "--noprofile", "--norc"], environment)\n'
                          'raise SystemExit(result)\n')
        self.cli = self.work / 'kythos-console'
        self.cli.write_text(CLI.read_text().replace("TMUX = '/usr/bin/tmux'", 'TMUX = ' + repr(self.binary))
                            .replace("WRAPPER = '/usr/local/libexec/kythos-console-session'", 'WRAPPER = ' + repr(str(WRAPPER)))
                            .replace("Path('/tmp')", 'Path(' + repr(str(self.work)) + ')'))
        self.cli.chmod(0o755)

        def controlling_pty():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self.process = subprocess.Popen(['/usr/bin/python3', '-I', str(script)], stdin=self.slave,
                                        stdout=self.slave, stderr=self.slave, env=self.environment,
                                        preexec_fn=controlling_pty, close_fds=True)
        self.addCleanup(self.stop)
        self.screen = Screen(24, 100)
        self.stream = bytearray()
        self.socket = None
        self.wait_for(lambda: bool(list(self.work.glob('kythos-console-*/socket'))))
        self.socket = str(next(self.work.glob('kythos-console-*/socket')))
        self.wait_for(lambda: b'TEST> ' in self.stream)

    def stop(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=5)

    def drain(self, timeout=0.05):
        while select.select([self.master], [], [], timeout)[0]:
            try: data = os.read(self.master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO: return
                raise
            if not data: return
            self.stream.extend(data)
            self.screen.feed(data)
            timeout = 0.01

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.drain()
            if predicate(): return
            if self.process.poll() is not None:
                self.fail('native console exited: ' + self.stream.decode(errors='replace')[-2000:])
        self.fail('native console timed out: ' + self.stream.decode(errors='replace')[-2000:])

    def query(self, *arguments):
        result = subprocess.run([self.binary, '-S', self.socket, *arguments], env=self.environment,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def assert_header(self):
        expected = 'KythOS Kernal 2027 | https://kythos.ai ' + Path(os.ttyname(self.slave)).name
        self.assertEqual(''.join(self.screen.lines[0]).rstrip(), expected)

    def send(self, command):
        self.stream.clear()
        os.write(self.master, command.encode() + b'\n')
        self.wait_for(lambda: b'TEST> ' in self.stream)
        self.drain(0.1)

    def test_native_viewport_pins_header_through_clear_scroll_alternate_screen_and_resize(self):
        self.assertIn(b'\x1b]P49eafff', self.stream)
        self.assertIn(b'\x1b[34m', self.stream)
        self.assertNotIn(b'\x1b[1m', self.stream, 'bright header must not request bold intensity')
        self.assert_header()
        self.assertNotIn('bold', self.query('show-options', '-gv', 'status-style'))
        self.assertEqual(self.query('display-message', '-p', '#{pane_height}:#{client_height}'), '23:24')
        self.assertEqual(self.query('show-options', '-gv', 'status-position'), 'top')
        self.assertEqual(self.query('show-options', '-gv', 'prefix'), 'None')
        self.assertEqual(self.query('list-keys', '-T', 'root'), '')
        prefix = subprocess.run([self.binary, '-S', self.socket, 'list-keys', '-T', 'prefix'],
                                env=self.environment, capture_output=True, text=True, timeout=5)
        self.assertIn(prefix.returncode, (0, 1))
        self.assertEqual(prefix.stdout, '')
        if prefix.returncode:
            self.assertEqual(prefix.stderr.strip(), "table prefix doesn't exist")
        self.send('clear')
        self.assert_header()
        self.send("for ((i=0;i<80;i++)); do printf 'scroll line %s\\n' \"$i\"; done")
        self.assert_header()
        self.send("printf '\\033[?1049h\\033[2J\\033[HFull screen app\\n'")
        self.assert_header()
        self.send("printf '\\033[?1049l'")
        self.assert_header()
        self.screen.resize(30, 110)
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 110, 0, 0))
        os.killpg(self.process.pid, signal.SIGWINCH)
        self.wait_for(lambda: self.query('display-message', '-p', '#{pane_height}:#{client_height}') == '29:30')
        self.query('refresh-client', '-S')
        self.drain(0.2)
        self.assert_header()
        os.write(self.master, b'exit\n')
        self.process.wait(timeout=5)
        self.assertEqual(self.process.returncode, 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.attributes)
        self.assertEqual(list(self.work.glob('kythos-console-*')), [])

    def test_real_top_after_clear_and_scroll_preserves_header_during_updates_and_exit(self):
        if not Path('/usr/bin/top').is_file():
            self.skipTest('packaged procps top is unavailable')
        self.screen.resize(50, 160)
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 160, 0, 0))
        os.killpg(self.process.pid, signal.SIGWINCH)
        self.wait_for(lambda: self.query('display-message', '-p', '#{pane_height}:#{client_height}') == '49:50')
        for _ in range(2):
            self.send("clear; for ((i=1;i<=140;i++)); do printf '%s\\n' \"$i\"; done; command -v top")
            self.assert_header()
            self.stream.clear()
            os.write(self.master, b'/usr/bin/top -d 0.1\n')
            self.wait_for(lambda: 'top - ' in self.query('capture-pane', '-p'))
            self.assert_header()
            for _refresh in range(4):
                self.drain(0.1)
                self.assert_header()
            os.write(self.master, b'q')
            self.wait_for(lambda: b'TEST> ' in self.stream)
            self.drain(0.1)
            self.assert_header()

    def test_signal_cleans_only_owned_server_and_restores_terminal(self):
        unrelated = str(self.work / 'unrelated.socket')
        result = subprocess.run([self.binary, '-S', unrelated, '-f', str(CONFIG), 'new-session',
                                 '-d', '-s', 'unrelated', '/bin/sleep', '30'], env=self.environment,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            self.process.send_signal(signal.SIGTERM)
            self.process.wait(timeout=5)
            self.assertEqual(list(self.work.glob('kythos-console-*')), [])
            self.assertEqual(termios.tcgetattr(self.slave), self.attributes)
            result = subprocess.run([self.binary, '-S', self.socket, 'list-sessions'], env=self.environment,
                                    capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            result = subprocess.run([self.binary, '-S', unrelated, 'list-sessions'], env=self.environment,
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, 'unrelated private server must stay alive')
        finally:
            subprocess.run([self.binary, '-S', unrelated, 'kill-server'], env=self.environment,
                           capture_output=True, timeout=5)

    def test_raw_cli_returns_to_original_outer_pty_and_closes_only_managed_viewport(self):
        inner_tty = self.query('display-message', '-p', '#{pane_tty}')
        original_tty = os.ttyname(self.slave)
        self.assertNotEqual(inner_tty, original_tty)
        unrelated = str(self.work / 'unrelated.socket')
        result = subprocess.run([self.binary, '-S', unrelated, '-f', str(CONFIG), 'new-session',
                                 '-d', '-s', 'unrelated', '/bin/sleep', '30'], env=self.environment,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            self.stream.clear()
            os.write(self.master, (shlex.quote(str(self.cli)) + ' raw\n').encode())
            self.wait_for(lambda: b'RAW> ' in self.stream)
            self.assertEqual(list(self.work.glob('kythos-console-*')), [])
            self.stream.clear()
            os.write(self.master, b"printf '__RAW_TTY__'; /usr/bin/tty; printf '__RAW_ENV__%s|%s\\n' \"$KYTHOS_CONSOLE_HEADER\" \"${TMUX-unset}\"; printf '__RAW_UID__'; id -u\n")
            self.wait_for(lambda: b'__RAW_ENV__0|unset' in self.stream)
            self.assertIn(('__RAW_TTY__' + original_tty).encode(), self.stream)
            self.assertIn(('__RAW_UID__' + str(os.getuid())).encode(), self.stream)
            self.stream.clear()
            os.write(self.master, (shlex.quote(str(self.cli)) + ' header\n').encode())
            self.wait_for(lambda: b'Header mode requires a raw local Linux console' in self.stream)
            result = subprocess.run([self.binary, '-S', unrelated, 'list-sessions'], env=self.environment,
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, 'raw transition must not affect another server')
            os.write(self.master, b'exit 0\n')
            self.process.wait(timeout=5)
            self.assertEqual(self.process.returncode, 0)
            self.assertEqual(termios.tcgetattr(self.slave), self.attributes)
        finally:
            subprocess.run([self.binary, '-S', unrelated, 'kill-server'], env=self.environment,
                           capture_output=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
