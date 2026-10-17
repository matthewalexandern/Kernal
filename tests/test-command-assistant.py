#!/usr/bin/python3
"""Exercise offline shell assistance against disposable commands and manuals.

These tests intentionally make every discovered executable a trap: inspection,
completion and diagnosis must obtain their information without running it.
"""

from contextlib import ExitStack
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest'
CATALOGUE = ROOT / 'config/includes.chroot/usr/share/kythos/command-intents.json'
loader = importlib.machinery.SourceFileLoader('command_assistant', str(ENGINE))
spec = importlib.util.spec_from_loader(loader.name, loader)
engine = importlib.util.module_from_spec(spec)
loader.exec_module(engine)

MANUAL = r'''.TH WIDGET 1
.SH NAME
widget \- inspect local widgets without changing them
.SH SYNOPSIS
.B widget
[OPTIONS] COMMAND [TARGET]
.SH OPTIONS
.TP
.B --inspect
Inspect a target.
.TP
.B --output
Write results to a file.
.SH COMMANDS
.TP
.B inspect
Inspect the selected widget.
.TP
.B status
Show widget status.
'''


class OfflineAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = engine.load_catalogue(CATALOGUE)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.marker = self.root / 'executed'
        self.manual_root = self.root / 'man'
        (self.manual_root / 'man1').mkdir(parents=True)
        self.manual = self.manual_root / 'man1/widget.1'
        self.manual.write_text(MANUAL)
        self.executable('widget')
        self.executable('sink')
        self.executable('undocumented-tool')
        commands, complete = engine.discover_commands(str(self.bin))
        self.assertTrue(complete)
        self.index = engine.build_command_index(commands, self.manual_root,
                                               path=str(self.bin))['commands']

    def tearDown(self):
        self.assertFalse(self.marker.exists(),
                         'offline assistance must never execute inspected commands')

    def executable(self, name):
        target = self.bin / name
        target.write_text('#!/bin/sh\n/usr/bin/touch ' + shlex.quote(str(self.marker)) + '\n')
        target.chmod(0o755)
        return target

    def assist(self, line, mode='explain', **kwargs):
        """Reject process execution even if the fixture executable would fail."""
        with ExitStack() as stack:
            for name in ('run', 'Popen', 'call', 'check_call', 'check_output'):
                stack.enter_context(mock.patch.object(
                    subprocess, name, side_effect=AssertionError('unexpected process probe')))
            for name in ('system', 'popen'):
                stack.enter_context(mock.patch.object(
                    os, name, side_effect=AssertionError('unexpected shell probe')))
            result = engine.assist(line, mode=mode, path=str(self.bin), index=self.index,
                                   catalogue=self.catalogue, **kwargs)
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result.get('title'), str)
        self.assertIsInstance(result.get('lines'), list)
        self.assertTrue(all(isinstance(line, str) for line in result['lines']))
        self.assertIsInstance(result.get('candidates'), list)
        self.assertTrue(all(isinstance(item, str) for item in result['candidates']))
        self.assertTrue(result.get('proposal') is None or isinstance(result['proposal'], dict))
        self.assertFalse(self.marker.exists())
        return result

    @staticmethod
    def prose(result):
        return '\n'.join([result['title'], *result['lines']])

    def test_quoted_pipeline_and_redirection_are_inspected_as_data(self):
        line = "widget --inspect 'literal | value' | sink 'quoted > target' 2> 'error log'"
        parsed = engine.parse_shell_line(line)
        self.assertFalse(parsed['warnings'])
        self.assertEqual([part['argv'] for part in parsed['segments']], [
            ['widget', '--inspect', 'literal | value'], ['sink', 'quoted > target']])
        self.assertFalse(parsed['segments'][0]['redirections'])
        self.assertTrue(parsed['segments'][1]['redirections'])
        result = self.assist(line)
        self.assertRegex(self.prose(result).lower(), r'pipe|pipeline')
        self.assertRegex(self.prose(result).lower(), r'redirect|standard error|stderr')
        self.assertIsNone(result.get('proposal'))
        self.assertFalse((self.root / 'error log').exists())

    def test_literal_empty_and_quoted_arguments_keep_their_boundaries(self):
        parsed = engine.parse_shell_line("widget '' 'a path with spaces' \"literal $not_expanded\"")
        # Shell variables cannot be resolved safely offline; accepting the
        # structure must still carry a warning rather than claiming a value.
        self.assertTrue(parsed['warnings'])
        literal = engine.parse_shell_line("widget '' 'a path with spaces' 'literal | > text'")
        self.assertFalse(literal['warnings'])
        self.assertEqual(literal['segments'][0]['argv'],
                         ['widget', '', 'a path with spaces', 'literal | > text'])

    def test_escaped_numeric_argument_is_not_consumed_as_a_file_descriptor(self):
        parsed = engine.parse_shell_line(r'widget \2>out')
        self.assertFalse(parsed['warnings'])
        self.assertEqual(parsed['segments'][0]['argv'], ['widget', '2'])
        self.assertEqual(parsed['segments'][0]['redirections'],
                         [{'operator': '>', 'target': 'out'}])

    def test_descriptor_duplication_is_explained_as_duplication(self):
        result = self.assist('widget 2>&1')
        self.assertRegex(self.prose(result).lower(), r'duplicat|file descriptor|\bfd\b')
        self.assertNotIn('may create or truncate', self.prose(result))

    def test_substitution_and_unsupported_programs_warn_without_execution(self):
        quoted_marker = shlex.quote(str(self.marker))
        programs = (
            'widget $(/usr/bin/touch ' + quoted_marker + ')',
            'widget `/usr/bin/touch ' + quoted_marker + '`',
            'widget <(/usr/bin/touch ' + quoted_marker + ')',
            'widget ${PRIVATE_TOKEN}',
            "widget 'unterminated",
        )
        for line in programs:
            with self.subTest(line=line):
                self.assertTrue(engine.parse_shell_line(line)['warnings'])
                result = self.assist(line)
                self.assertIsNone(result.get('proposal'))
                self.assertRegex(self.prose(result).lower(),
                                 r'unsupported|cannot|not evaluat|unmatched|substitut|incomplete|expansion|outside.*inspection')

    def test_newly_installed_commands_appear_without_a_static_catalogue_entry(self):
        before = self.assist('newly-added', mode='complete')
        self.assertNotIn('newly-added-tool', before['candidates'])
        self.executable('newly-added-tool')
        after = self.assist('newly-added', mode='complete')
        self.assertIn('newly-added-tool', after['candidates'])
        inspected = self.assist('newly-added-tool')
        self.assertIn('newly-added-tool', self.prose(inspected))
        self.assertRegex(self.prose(inspected).lower(), r'installed|executable|path')

    def test_new_prefix_manual_is_available_without_a_system_index_refresh(self):
        local_manual = self.root / 'share/man/man1/newly-added-tool.1'
        local_manual.parent.mkdir(parents=True)
        self.executable('newly-added-tool')
        local_manual.write_text(MANUAL.replace('widget', 'newly-added-tool'))
        result = self.assist('newly-added-tool --inspect')
        self.assertIn('inspect local newly-added-tools', self.prose(result))
        self.assertIn('--inspect: Inspect a target.', self.prose(result))
        local_manual.write_text(local_manual.read_text().replace('--inspect', '--review'))
        result = self.assist('newly-added-tool --rev', mode='complete')
        self.assertIn('--review', result['candidates'])
        self.assertNotIn('--inspect', result['candidates'])

    def test_documented_subcommand_manual_supplies_contextual_flags(self):
        child = self.manual_root / 'man1/widget-inspect.1'
        child.write_text(MANUAL.replace('widget', 'widget-inspect').replace('--inspect', '--deep-review'))
        result = self.assist('widget inspect --deep-review')
        self.assertIn('man widget-inspect', self.prose(result))
        self.assertIn('--deep-review: Inspect a target.', self.prose(result))
        result = self.assist('widget inspect --deep', mode='complete')
        self.assertIn('--deep-review', result['candidates'])

    def test_unknown_documentation_and_flags_are_reported_as_uncertain(self):
        result = self.assist('widget --invented-option')
        self.assertRegex(self.prose(result).lower(),
                         r'unknown|not documented|unverified|cannot verify|uncertain|not in.*(?:manual|metadata)')
        self.assertIsNone(result.get('proposal'))
        result = self.assist('undocumented-tool --invented-option')
        self.assertRegex(self.prose(result).lower(),
                         r'no .*documentation|no .*manual|not.*documented|unavailable|unknown|unverified')
        self.assertNotIn('--invented-option', result['candidates'])

    def test_completion_includes_builtins_aliases_functions_and_keywords(self):
        shell = {
            'builtins': ['localbuiltin'], 'aliases': ['local-alias'],
            'functions': ['localfunction'], 'keywords': ['local-keyword'],
            'completions': {},
        }
        result = self.assist('local', mode='complete', shell=shell)
        self.assertTrue({'localbuiltin', 'local-alias', 'localfunction', 'local-keyword'}
                        <= set(result['candidates']))
        for name in ('localbuiltin', 'local-alias', 'localfunction'):
            inspected = self.assist(name, shell=shell)
            self.assertIn(name, self.prose(inspected))
            self.assertIsNone(inspected.get('proposal'))

    def test_completion_uses_local_flags_subcommands_and_static_shell_words(self):
        options = self.assist('widget --ins', mode='complete')
        self.assertIn('--inspect', options['candidates'])
        self.assertNotIn('--invented', options['candidates'])
        actions = self.assist('widget ins', mode='complete')
        self.assertIn('inspect', actions['candidates'])
        shell = {'builtins': [], 'aliases': [], 'functions': [], 'keywords': [],
                 'completions': {'widget': {'words': ['alpha', 'alpine', 'beta'],
                                            'dynamic': True}}}
        words = self.assist('widget al', mode='complete', shell=shell)
        self.assertTrue({'alpha', 'alpine'} <= set(words['candidates']))
        self.assertNotIn('beta', words['candidates'])

    def test_shell_overrides_do_not_inherit_external_command_flags_or_corrections(self):
        for kind in ('aliases', 'functions'):
            with self.subTest(kind=kind):
                shell = {kind: ['widget'],
                         'completions': {'widget': {'words': ['--internal'], 'dynamic': False}}}
                completed = self.assist('widget --in', mode='complete', shell=shell)
                self.assertIn('--internal', completed['candidates'])
                self.assertNotIn('--inspect', completed['candidates'])
                proposed = self.assist('widget --inspec', mode='intent', shell=shell)
                self.assertIsNone(proposed.get('proposal'))

    def test_static_completion_inspection_does_not_interpret_wordlist_expansions(self):
        marker = shlex.quote(str(self.marker))
        expression = '$(/usr/bin/touch ' + marker + '; printf internal-one internal-two) static'
        declaration = 'complete -W ' + shlex.quote(expression) + ' widget'
        raw = b'complete\0\0widget in\0completion:' + declaration.encode() + b'\0'
        mode, status, line, context = engine.context_protocol(raw)
        self.assertEqual((mode, status, line), ('complete', None, 'widget in'))
        self.assertEqual(context['completions']['widget']['words'], [])
        self.assertFalse(self.marker.exists())

    def test_typo_proposal_is_explicit_and_preserves_quoted_arguments(self):
        result = self.assist("widgt --inspect 'a path with spaces' ''", mode='intent')
        self.assertIsNotNone(result.get('proposal'))
        self.assertEqual(shlex.split(result['proposal']['command']),
                         ['widget', '--inspect', 'a path with spaces', ''])
        self.assertFalse(self.marker.exists())
        unchanged = self.assist("widget --inspect 'a path with spaces' ''", mode='intent')
        self.assertIsNone(unchanged.get('proposal'))

    def test_ssh_spelling_and_case_corrections_are_only_proposed(self):
        self.executable('ssh-copy-id')
        for spelling in ('sshcopyid', 'ssh-copy-Id'):
            with self.subTest(spelling=spelling):
                result = self.assist(spelling + ' user@192.0.2.10', mode='intent')
                self.assertIsNotNone(result.get('proposal'))
                self.assertEqual(shlex.split(result['proposal']['command']),
                                 ['ssh-copy-id', 'user@192.0.2.10'])
                self.assertFalse(self.marker.exists())

    def test_intent_search_uses_new_local_manuals_without_inventing_arguments(self):
        result = self.assist('inspect local widgets', mode='intent')
        self.assertIsNone(result.get('proposal'))
        self.assertIn('widget - inspect local widgets without changing them', self.prose(result))
        self.assertRegex(self.prose(result).lower(), r'lead|document|argument grammar')

    def test_diagnosis_distinguishes_exit_statuses_without_claiming_a_cause(self):
        expected = {
            126: r'permission|not executable|cannot execut',
            127: r'not found|path|missing command',
            1: r'failed|failure|non.?zero|generic|reported',
            130: r'interrupt|sigint|ctrl.?c',
        }
        for status, wording in expected.items():
            with self.subTest(status=status):
                result = self.assist('widget inspect local-target', mode='diagnose', status=status)
                self.assertRegex(self.prose(result).lower(), wording)
                self.assertIsNone(result.get('proposal'))

    def test_diagnosis_does_not_read_history_or_disclose_environment_secrets(self):
        private = self.root / 'private-history'
        secret = 'private-history-and-token-4da2d897'
        private.write_text('widget --password ' + secret + '\n')
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            self.assertNotEqual(path, private, 'assistance must not read command history')
            return original_open(path, *args, **kwargs)

        with mock.patch.dict(os.environ, {'HISTFILE': str(private), 'PRIVATE_API_TOKEN': secret}), \
                mock.patch.object(Path, 'open', new=guarded_open):
            result = self.assist('widget inspect local-target', mode='diagnose', status=1)
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn(str(private), json.dumps(result))

    def test_runtime_package_version_uses_only_trusted_fixed_reader(self):
        from types import SimpleNamespace
        regular_root = SimpleNamespace(st_uid=0, st_mode=0o100755)
        responses = [SimpleNamespace(returncode=0, stdout=b'coreutils: /usr/bin/ls\n'),
                     SimpleNamespace(returncode=0, stdout=b'coreutils 9.7-3')]
        with mock.patch.object(Path, 'stat', return_value=regular_root), \
                mock.patch.object(engine.subprocess, 'run', side_effect=responses) as query:
            self.assertEqual(engine.package_identity('/usr/bin/ls'), 'coreutils 9.7-3')
        self.assertEqual(query.call_count, 2)
        for call in query.call_args_list:
            self.assertEqual(call.args[0][0], '/usr/bin/dpkg-query')
            self.assertNotIn('--help', call.args[0])
            self.assertNotIn('--version', call.args[0])
            self.assertNotIn('shell', call.kwargs)
            self.assertEqual(call.kwargs['env'], {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        untrusted = SimpleNamespace(st_uid=1000, st_mode=0o100755)
        with mock.patch.object(Path, 'stat', return_value=untrusted), \
                mock.patch.object(engine.subprocess, 'run') as query:
            self.assertIsNone(engine.package_identity('/usr/bin/ls'))
            query.assert_not_called()

    def test_cli_json_inspects_without_executing_and_protocol_is_bounded(self):
        completed = subprocess.run([str(ENGINE), '--assist', '--json', '--diagnose', '--status', '127',
                                    'missing-unknown-command'], capture_output=True, text=True, timeout=3)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIn('Exit status 127', self.prose(result))
        self.assertIsNone(result['proposal'])
        for payload in (b'broken', b'x' * (engine.MAX_CONTEXT_BYTES + 1)):
            with self.assertRaises(ValueError):
                engine.context_protocol(payload)

    def test_standalone_cli_preserves_command_flags_and_literal_arguments(self):
        for arguments in (['--explain', 'ls', '--all'], ['--explain', '--', 'ls', '--all'],
                          ['--explain', 'ls', '--all', 'a path with spaces']):
            with self.subTest(arguments=arguments):
                completed = subprocess.run([str(ENGINE), '--assist', '--json', *arguments],
                                           capture_output=True, text=True, timeout=3)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertIn('ls -', self.prose(result))
                self.assertNotIn('unrecognized arguments', completed.stderr)

    def test_intent_compound_programs_report_uncertainty_without_tracebacks(self):
        for expression in ('sshcopyid host | cat', 'widget && sink', 'widget > output',
                           'widget &', ''):
            with self.subTest(expression=expression):
                result = self.assist(expression, mode='intent')
                self.assertIsNone(result['proposal'])
                self.assertRegex(self.prose(result), r'no command is proposed|needs explicit inspection')
                completed = subprocess.run([str(ENGINE), '--assist', '--json', '--intent', expression],
                                           capture_output=True, text=True, timeout=3)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIsNone(json.loads(completed.stdout)['proposal'])
                self.assertNotIn('Traceback', completed.stderr)

    def test_attached_short_credential_arguments_never_appear_in_previews(self):
        # Opaque values deliberately contain none of the detector's long-name
        # keywords, so a broad "secret" substring cannot make this pass.
        for option in ('-ualice:42efc', '-p4ca7a8e', '-HBearer:7ce'):
            line = 'widgt ' + option + ' https://example.invalid'
            with self.subTest(option=option):
                self.assertTrue(engine.sensitive_line(line))
                result = self.assist(line, mode='intent')
                self.assertIsNone(result['proposal'])
                self.assertNotIn(option, json.dumps(result))
                self.assertIsNone(engine.suggest(line, self.catalogue, path=str(self.bin), index=self.index))

    def test_wrapper_and_quoted_assignment_semantics_remain_literal(self):
        parsed = engine.parse_shell_line("'A=B' widget")
        self.assertEqual(engine.command_offset(parsed['segments'][0]['argv'],
                                               parsed['segments'][0]['quoted']), 0)
        shell = {'aliases': ['widget'], 'functions': ['widget']}
        result = self.assist('command widget --inspect', shell=shell)
        self.assertNotIn('is a shell', self.prose(result))
        result = self.assist('sudo widget --inspect', shell=shell)
        self.assertNotIn('is a shell', self.prose(result))

    def test_explanation_and_diagnosis_do_not_echo_typed_secrets(self):
        secret = 'private-typed-password-a91c678e'
        for mode in ('explain', 'diagnose'):
            for command in ('widget', 'widgt'):
                for arguments in ('--password ' + shlex.quote(secret),
                                  '--api-token=' + secret,
                                  '-u user:' + secret):
                    with self.subTest(mode=mode, command=command, arguments=arguments):
                        result = self.assist(command + ' ' + arguments, mode=mode, status=1)
                        self.assertNotIn(secret, json.dumps(result))
                        self.assertIsNone(result.get('proposal'))

    def test_legacy_suggestion_protocol_does_not_preview_credentials(self):
        for arguments in ('--password private-value', '--api-token=private-value',
                          '-u user:private-value', 'https://user:private-value@example.invalid'):
            with self.subTest(arguments=arguments):
                result = engine.suggest('widgt ' + arguments, self.catalogue,
                                        path=str(self.bin), index=self.index)
                self.assertIsNone(result)

    def test_file_signature_detects_replaced_executable_and_drops_stale_metadata(self):
        executable = self.bin / 'widget'
        signature = engine.file_signature(executable)
        self.assertIsNotNone(signature)
        self.assertEqual(signature, engine.file_signature(executable))
        self.assertIsNone(engine.file_signature(self.root / 'missing'))
        original = self.assist('widget --ins', mode='complete')
        self.assertIn('--inspect', original['candidates'])
        replacement = self.bin / '.replacement'
        replacement.write_text('#!/bin/sh\nexit 83\n')
        replacement.chmod(0o755)
        replacement.replace(executable)
        self.assertNotEqual(signature, engine.file_signature(executable))
        stale = self.assist('widget --ins', mode='complete')
        self.assertNotIn('--inspect', stale['candidates'])

    def test_changed_manual_does_not_leave_old_flags_in_assistance(self):
        original = self.assist('widget --ins', mode='complete')
        self.assertIn('--inspect', original['candidates'])
        self.manual.write_text(MANUAL.replace('--inspect', '--review'))
        stale = self.assist('widget --ins', mode='complete')
        self.assertNotIn('--inspect', stale['candidates'])
        commands, _ = engine.discover_commands(str(self.bin))
        self.index = engine.build_command_index(commands, self.manual_root,
                                               path=str(self.bin))['commands']
        fresh = self.assist('widget --rev', mode='complete')
        self.assertIn('--review', fresh['candidates'])

    def test_changed_manual_include_target_invalidates_cached_declarations(self):
        target = self.manual_root / 'man1/real-widget.1'
        target.write_text(MANUAL)
        self.manual.write_text('.so man1/real-widget.1\n')
        self.index = engine.build_command_index({'widget'}, self.manual_root,
                                               path=str(self.bin))['commands']
        self.assertIn('--inspect', self.assist('widget --ins', mode='complete')['candidates'])
        wrapper_signature = engine.file_signature(self.manual)
        target.write_text(MANUAL.replace('--inspect', '--review'))
        self.assertEqual(wrapper_signature, engine.file_signature(self.manual))
        self.assertNotIn('--inspect', self.assist('widget --ins', mode='complete')['candidates'])

    def test_unsigned_legacy_metadata_is_not_claimed_to_match_current_files(self):
        original = json.loads(json.dumps(self.index))
        for missing in ('executable_signature', 'manual_signature', 'manual_dependencies'):
            with self.subTest(missing=missing):
                self.index = json.loads(json.dumps(original))
                self.index['widget'].pop(missing)
                result = self.assist('widget --ins', mode='complete')
                self.assertNotIn('--inspect', result['candidates'])

    def test_malformed_identity_signatures_are_rejected_when_loading_index(self):
        cache = self.root / 'command-index.json'
        original = {'schema_version': 1, 'commands': self.index}
        root_regular = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
        for invalid in ([1, 2, 3, 4], [True, 2, 3, 4, 5], [1, 2, -3, 4, 5],
                        'not-a-signature', {'dev': 1}):
            with self.subTest(signature=invalid):
                value = json.loads(json.dumps(original))
                value['commands']['widget']['executable_signature'] = invalid
                cache.write_text(json.dumps(value))
                with mock.patch.object(engine.os, 'fstat', return_value=root_regular):
                    self.assertEqual(engine.load_command_index(cache), {})
        for invalid in (['not-a-pair'], [['relative/manual.1', [1, 2, 3, 4, 5]]],
                        [[str(self.manual), [False, 2, 3, 4, 5]]]):
            with self.subTest(dependencies=invalid):
                value = json.loads(json.dumps(original))
                value['commands']['widget']['manual_dependencies'] = invalid
                cache.write_text(json.dumps(value))
                with mock.patch.object(engine.os, 'fstat', return_value=root_regular):
                    self.assertEqual(engine.load_command_index(cache), {})

    def test_relative_path_shadow_does_not_inherit_packaged_command_metadata(self):
        shadow = self.root / 'shadow'
        shadow.mkdir()
        shadowed = shadow / 'widget'
        shadowed.write_text('#!/bin/sh\nexit 84\n')
        shadowed.chmod(0o755)
        old_directory = Path.cwd()
        try:
            os.chdir(shadow)
            result = engine.assist('widget --ins', mode='complete',
                                   path='.' + os.pathsep + str(self.bin),
                                   index=self.index, catalogue=self.catalogue)
        finally:
            os.chdir(old_directory)
        self.assertNotIn('--inspect', result['candidates'])


if __name__ == '__main__':
    unittest.main()
