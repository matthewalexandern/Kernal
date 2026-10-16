#!/usr/bin/python3
"""Exercise installed-command discovery and data-only manual metadata."""
import gzip
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest'
loader = importlib.machinery.SourceFileLoader('command_index', str(ENGINE))
spec = importlib.util.spec_from_loader(loader.name, loader)
engine = importlib.util.module_from_spec(spec)
loader.exec_module(engine)

MANUAL = r'''.TH FROBNICATE 1
.SH NAME
frobnicate \- inspect and organize local widgets
.SH SYNOPSIS
.B frobnicate
[OPTIONS] COMMAND [TARGET]
.SH OPTIONS
.TP
.BR --inspect =VALUE
Inspect a literal value.
.TP
.B --enable
Enable a feature.
.TP
.B --enabled
Show enabled features.
.SH COMMANDS
.HP \w'\fBfrobnicate\ inspect\fR\ 'u
.PP
\fBinspect\fR TARGET
Inspect the specified target.
.PP
\fBorganize\fR TARGET
Organize the specified target.
.SH EXAMPLES
.B example-not-a-subcommand
'''


class CommandIndex(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.marker = self.root / 'executed'
        for name in ('frobnicate', 'brand-new-tool'):
            path = self.bin / name
            path.write_text('#!/bin/sh\ntouch ' + shlex.quote(str(self.marker)) + '\n')
            path.chmod(0o755)
        self.man = self.root / 'man'
        (self.man / 'man1').mkdir(parents=True)
        with gzip.open(self.man / 'man1/frobnicate.1.gz', 'wt') as output:
            output.write(MANUAL)
        self.commands, complete = engine.discover_commands(str(self.bin))
        self.assertTrue(complete)
        self.index = engine.build_command_index(self.commands, self.man, path=str(self.bin))['commands']
        self.catalogue = engine.load_catalogue(ROOT / 'config/includes.chroot/usr/share/kythos/command-intents.json')

    def tearDown(self):
        self.assertFalse(self.marker.exists(), 'discovery or documentation must never execute inspected commands')

    def propose(self, phrase):
        return engine.suggest(phrase, self.catalogue, path=str(self.bin), index=self.index, root=False)

    def test_unlisted_executables_and_documented_options_are_discovered(self):
        self.assertEqual(set(self.index), self.commands)
        record = self.index['frobnicate']
        self.assertEqual(record['description'], 'inspect and organize local widgets')
        self.assertEqual(record['options'], ['--enable', '--enabled', '--inspect'])
        self.assertEqual(record['actions'], ['inspect', 'organize'])
        self.assertEqual(self.index['brand-new-tool']['description'], '')
        (self.bin / 'another-new-tool').write_text('#!/bin/sh\n')
        (self.bin / 'another-new-tool').chmod(0o755)
        result = self.propose('another-new-toool unchanged-target')
        self.assertEqual(shlex.split(result['command']), ['another-new-tool', 'unchanged-target'])

    def test_option_and_subcommand_corrections_preserve_every_value(self):
        result = self.propose("frobnicate --inspecct=literal-value 'a path with spaces' ''")
        self.assertEqual(shlex.split(result['command']), ['frobnicate', '--inspect=literal-value', 'a path with spaces', ''])
        result = self.propose('sudo frobnicate inspecct exact-target')
        self.assertEqual(shlex.split(result['command']), ['sudo', 'frobnicate', 'inspect', 'exact-target'])
        result = self.propose('sudo frobnicatte exact-target')
        self.assertEqual(shlex.split(result['command']), ['sudo', 'frobnicate', 'exact-target'])
        self.assertIsNone(self.propose('frobnicate --inspect=literal-value unchanged-target'))
        self.assertIsNone(self.propose('frobnicate -- --inspecct'))
        self.assertIsNone(self.propose('frobnicate --enabl'))
        self.assertIsNone(self.propose('frobnicate completely-unknown-target'))
        self.assertIsNone(self.propose('frobnicate --output --inspecct literal-target'))
        self.assertIsNone(self.propose('frobnicate --regexp --inspecct literal-target'))
        self.assertIsNone(self.propose('frobnicate inspecct unit[12]'))
        self.assertIsNone(self.propose('frobnicate --inspecct unit[12]'))

    def test_context_includes_metadata_but_never_runs_probe(self):
        text = engine.command_help('sudo frobnicate inspect target', path=str(self.bin), index=self.index)
        self.assertIn('Options: --enable --enabled --inspect', text)
        self.assertIn('Subcommands: inspect organize', text)
        self.assertIn('man frobnicate', text)
        text = engine.command_help('brand-new-tool', path=str(self.bin), index=self.index)
        self.assertIn('installed command', text)
        self.assertIn('No packaged manual metadata', text)
        text = engine.command_help('local widgets', path=str(self.bin), index=self.index)
        self.assertIn('frobnicate - inspect and organize local widgets', text)
        (self.bin / 'frobnicate').unlink()
        text = engine.command_help('local widgets', path=str(self.bin), index=self.index)
        self.assertNotIn('frobnicate -', text)

    def test_includes_and_symlinks_cannot_escape_packaged_man_root(self):
        alias = self.man / 'man1/alias.1.gz'
        with gzip.open(alias, 'wt') as output:
            output.write('.so man1/frobnicate.1\n')
        self.assertEqual(engine.read_manual(alias, self.man), MANUAL)
        outside = self.root / 'outside'
        outside.write_text('private contents')
        with gzip.open(alias, 'wt') as output:
            output.write('.so ' + str(outside) + '\n')
        self.assertEqual(engine.read_manual(alias, self.man), '')
        link = self.man / 'man1/link.1'
        link.symlink_to(outside)
        self.assertEqual(engine.read_manual(link, self.man), '')
        with gzip.open(alias, 'wt') as output:
            output.write('.so man1/alias.1\n')
        self.assertEqual(engine.read_manual(alias, self.man), '')
        with mock.patch.object(engine, 'MAX_MAN_BYTES', 10):
            self.assertEqual(engine.read_manual(self.man / 'man1/frobnicate.1.gz', self.man), '')

    def test_roff_macros_and_control_sequences_are_data_only(self):
        malicious = MANUAL + '\n.sy touch ' + str(self.marker) + '\n!touch ' + str(self.marker) + '\n'
        metadata = engine.manual_metadata(malicious)
        self.assertEqual(metadata['actions'], ['inspect', 'organize'])
        self.assertNotIn('\x1b', engine.plain_manual('description\x1b[31m\u202e'))
        self.assertNotIn('\u009b', engine.plain_manual('description\u009b31m'))

    def test_nested_mdoc_flag_declarations_exclude_layout_and_other_tools(self):
        text = '''.Sh NAME
.Nm new-tool
.Nd manage local widgets
.Sh SYNOPSIS
.Nm
.Op Fl f
.Op Fl n
.Op Fl s
.Op Fl x
.Op Fl i Op Ar identity_file
.Op Fl t Ar target_path
.Op Fl F Ar config
.Op Bo Fl o Ar option Bc ...
.Op Fl p Ar port
.Fl h | Fl ?
.Sh DESCRIPTION
.Bl -tag -width Ds
.It Fl i Op Ar identity_file
Read the identity file.
.It Fl f
Force the requested operation.
.It Fl n
Preview the operation.
.It Fl s
Use a file protocol.
.It Fl t Ar target_path
Use the specified path.
.It Fl p Ar port
Use the specified port.
.It Fl F Ar config , Fl o Ar option
Read options.
.El
Another tool supports -L and --not-our-option.
.Ql other-tool -A
.Sh EXAMPLES
.Op Fl z
'''
        metadata = engine.manual_metadata(text, 'new-tool')
        self.assertEqual(metadata['options'], ['-?', '-F', '-f', '-h', '-i', '-n', '-o', '-p', '-s', '-t', '-x'])
        self.assertEqual(metadata['actions'], [])

    def test_roff_option_declarations_exclude_prose_and_examples(self):
        text = MANUAL + '''\n.SH OPTIONS
.PP
Another command uses --not-our-option.
.PP
.B --ours
Use our option, like the separate tool's --not-our-option.
.SH EXAMPLES
.B --not-our-option
'''
        metadata = engine.manual_metadata(text, 'frobnicate')
        self.assertIn('--ours', metadata['options'])
        self.assertNotIn('--not-our-option', metadata['options'])

    def test_mdoc_command_syntax_excludes_option_values_and_styles(self):
        text = '''.Sh CLIENTS AND SESSIONS
.It Xo Ic attach-session
.Op Fl dErx
.Op Fl t Ar target-session
.Xc
.D1 Pq alias: Ic attach
Attach the session.
.Sh OPTIONS
.It Xo Ic activity-action
.Op Ic any | none | current | other
.Xc
Choose an action.
.It Xo Ic set-option
.Op Fl aFgopqsuUw
.Ar option Ar value
.Xc
.D1 Pq alias: Ic set
Set an option.
.Sh STYLES
.It Xo Ic acs ,
.Ic bright
.Xc
Set an attribute.
'''
        metadata = engine.manual_metadata(text, 'new-tool')
        self.assertEqual(metadata['actions'], ['attach-session', 'set-option'])

    def test_path_shadow_and_relative_executables_do_not_get_system_metadata(self):
        shadow = self.root / 'shadow'
        shadow.mkdir()
        (shadow / 'frobnicate').write_text('#!/bin/sh\n')
        (shadow / 'frobnicate').chmod(0o755)
        paths = str(shadow) + os.pathsep + str(self.bin)
        self.assertIsNone(engine.suggest('frobnicate --inspecct', self.catalogue, path=paths, index=self.index))
        help_text = engine.command_help('frobnicate', path=paths, index=self.index)
        self.assertNotIn('--inspect', help_text)
        # Empty and relative PATH entries participate in actual shell lookup.
        old = os.getcwd()
        try:
            os.chdir(shadow)
            for prefix in ('', '.'):
                paths = prefix + os.pathsep + str(self.bin)
                self.assertIsNone(engine.suggest('frobnicate --inspecct', self.catalogue, path=paths, index=self.index))
            (shadow / 'frobnicatte').write_text('#!/bin/sh\n')
            (shadow / 'frobnicatte').chmod(0o755)
            self.assertIsNone(engine.suggest('frobnicatte', self.catalogue, path=':' + str(self.bin), index=self.index))
            (shadow / 'frobnicatte').unlink()
            # Correcting into a shadow from the current directory is also declined.
            self.assertIsNone(engine.suggest('frobnicatte', self.catalogue, path=':' + str(self.bin), index=self.index))
        finally:
            os.chdir(old)
    def test_cache_rejects_untrusted_nonregular_and_malformed_content(self):
        cache = self.root / 'command-index.json'
        valid = {'schema_version': 1, 'commands': self.index}
        cache.write_text(json.dumps(valid))
        root_regular = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
        with mock.patch.object(engine.os, 'fstat', return_value=root_regular):
            self.assertEqual(engine.load_command_index(cache), self.index)
            for malformed in ([], None, 1, 'text', {}, {'schema_version': 2}, {'schema_version': 1, 'commands': []}):
                cache.write_text(json.dumps(malformed))
                self.assertEqual(engine.load_command_index(cache), {})
            cache.write_text('{broken')
            self.assertEqual(engine.load_command_index(cache), {})
            cache.write_text(json.dumps(valid))
            with mock.patch.object(engine, 'MAX_INDEX_BYTES', 10):
                self.assertEqual(engine.load_command_index(cache), {})
            unsafe = dict(valid, commands={'frobnicate': dict(self.index['frobnicate'], description='\u009b31m')})
            cache.write_text(json.dumps(unsafe))
            self.assertEqual(engine.load_command_index(cache), {})
        cache.write_text(json.dumps(valid))
        for mode, uid in ((stat.S_IFREG | 0o664, 0), (stat.S_IFREG | 0o646, 0), (stat.S_IFREG | 0o644, 1000)):
            with mock.patch.object(engine.os, 'fstat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid)):
                self.assertEqual(engine.load_command_index(cache), {})
        linked = self.root / 'linked-cache'
        linked.symlink_to(cache)
        self.assertEqual(engine.load_command_index(linked), {})
        fifo = self.root / 'fifo-cache'
        os.mkfifo(fifo)
        self.assertEqual(engine.load_command_index(fifo), {})
        self.assertEqual(engine.load_command_index(self.root), {})

    def test_index_refresh_observes_added_manuals_and_removed_commands(self):
        fresh = self.bin / 'another-new-tool'
        fresh.write_text('#!/bin/sh\ntouch ' + shlex.quote(str(self.marker)) + '\n')
        fresh.chmod(0o755)
        manual = self.man / 'man1/another-new-tool.1'
        manual.write_text(MANUAL.replace('frobnicate', 'another-new-tool'))
        names, complete = engine.discover_commands(str(self.bin))
        self.assertTrue(complete)
        first = engine.build_command_index(names, self.man, path=str(self.bin))['commands']
        self.assertIn('--inspect', first['another-new-tool']['options'])
        manual.write_text(MANUAL.replace('frobnicate', 'another-new-tool').replace('--inspect', '--review'))
        second = engine.build_command_index(names, self.man, path=str(self.bin))['commands']
        self.assertNotIn('--inspect', second['another-new-tool']['options'])
        self.assertIn('--review', second['another-new-tool']['options'])
        manual.unlink()
        self.assertNotIn('--review', engine.command_help('another-new-tool', path=str(self.bin), index=second))
        fresh.unlink()
        text = engine.command_help('another-new-tool', path=str(self.bin), index=second)
        self.assertNotIn('another-new-tool - inspect', text)

    def test_authentic_debian_manual_fixture_if_available(self):
        root = Path(os.environ.get('KYTHOS_TEST_MAN_ROOT', ROOT / '.build/command-index-review/debian-man'))
        if not (root / 'man1/ssh-copy-id.1.gz').exists():
            self.skipTest('Optional authenticated Debian manual fixture is unavailable')
        ssh = engine.manual_metadata(engine.read_manual(root / 'man1/ssh-copy-id.1.gz', root), 'ssh-copy-id')
        self.assertTrue({'-f', '-n', '-s', '-t', '-p', '-F', '-o'} <= set(ssh['options']))
        self.assertFalse({'-tag', '-width', '-L', '-A'} & set(ssh['options']))
        tmux = engine.manual_metadata(engine.read_manual(root / 'man1/tmux.1.gz', root), 'tmux')
        self.assertTrue({'attach-session', 'new-session'} <= set(tmux['actions']))
        self.assertFalse({'acs', 'activity-action', 'aggressive-resize'} & set(tmux['actions']))
        git = engine.manual_metadata(engine.read_manual(root / 'man1/git.1.gz', root), 'git')
        self.assertFalse({'--raw', '--unified', '-and-', '-file', '-hex'} & set(git['options']))

    def test_project_manuals_expose_canonical_package_command_and_help(self):
        root = ROOT / 'config/includes.chroot/usr/share/man'
        cy = engine.manual_metadata((root / 'man8/cy.8').read_text(), 'cy')
        self.assertIn('--simulate', cy['options'])
        self.assertIn('update', cy['actions'])
        self.assertIn('install', cy['actions'])
        self.assertEqual(cy['description'], 'manage authenticated distribution packages')
        helper = engine.manual_metadata((root / 'man1/kythos-help.1').read_text(), 'kythos-help')
        self.assertEqual(helper['description'], 'inspect installed commands and their local documentation')

    def test_broken_manual_symlink_does_not_abort_other_metadata(self):
        link = self.man / 'man1/brand-new-tool.1'
        link.symlink_to(link.name)
        self.assertEqual(engine.read_manual(link, self.man), '')
        index = engine.build_command_index(self.commands, self.man, path=str(self.bin))['commands']
        self.assertEqual(index['frobnicate']['actions'], ['inspect', 'organize'])
        self.assertEqual(index['brand-new-tool']['options'], [])


if __name__ == '__main__':
    unittest.main()
