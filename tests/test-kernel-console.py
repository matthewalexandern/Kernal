#!/usr/bin/python3
"""Mock VT ioctls completely; never open or alter the host's consoles."""
from contextlib import contextmanager
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/includes.chroot/usr/local/libexec/kythos-kernel-console'
loader = importlib.machinery.SourceFileLoader('kernel_console', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)


class Routing(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='kythos-kernel-console-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.cmdline = self.root / 'cmdline'
        self.cmdline.write_text('quiet splash')
        self.boot_id = self.root / 'boot-id'
        self.boot_id.write_text('00000000-0000-0000-0000-000000000001\n')
        self.units = self.root / 'systemd'
        self.units.mkdir()
        self.route = 0
        self.allocated = False
        self.opened = []
        self.ioctls = []
        self.intros = []
        self.after_set = None
        self.before_second_get = None
        self.get_count = 0

        @contextmanager
        def no_lock():
            yield

        @contextmanager
        def fake_device(number):
            self.opened.append(number)
            yield number

        actual_fstat = os.fstat

        def root_file_info(descriptor):
            info = actual_fstat(descriptor)
            return SimpleNamespace(st_mode=info.st_mode, st_uid=0)

        for name, value in (('STATE_DIR', self.state), ('CMDLINE', self.cmdline),
                            ('BOOT_ID', self.boot_id), ('LIVE_MEDIUM', self.root / 'no-live-medium'),
                            ('SYSTEMD_ROOTS', (self.units,)), ('state_lock', no_lock),
                            ('console_device', fake_device)):
            patch = mock.patch.object(helper, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        for patch in (mock.patch.object(helper.os, 'geteuid', return_value=0),
                      mock.patch.object(helper.os, 'fstat', side_effect=root_file_info),
                      mock.patch.object(helper.fcntl, 'ioctl', side_effect=self.ioctl),
                      mock.patch.object(helper, 'write_intro', side_effect=lambda fd: self.intros.append(fd))):
            patch.start()
            self.addCleanup(patch.stop)

    def ioctl(self, descriptor, request, argument, mutate=True):
        self.ioctls.append((descriptor, request, list(argument)))
        self.assertEqual(descriptor, 0)
        if request == helper.VT_GETSTATE:
            argument[2] = (1 << 12) if self.allocated else 1
            return 0
        self.assertEqual(request, helper.TIOCLINUX)
        if argument[0] == helper.GET_REDIRECT:
            self.get_count += 1
            if self.get_count == 2 and self.before_second_get is not None:
                self.route = self.before_second_get
            argument[0] = self.route
            return 0
        self.assertEqual(list(argument), [helper.SET_REDIRECT, argument[1]])
        self.route = argument[1]
        if self.after_set is not None:
            self.route = self.after_set
        return 0

    def ownership(self):
        return self.state / 'state.json'

    def setters(self):
        return [call for call in self.ioctls if call[1] == helper.TIOCLINUX and call[2][0] == helper.SET_REDIRECT]

    def test_unused_vt_redirect_is_owned_idempotent_and_explicitly_restorable(self):
        self.assertEqual(helper.run('apply'), {'status': 'redirected', 'redirect': 12})
        self.assertEqual(self.opened, [0, 12])
        self.assertEqual(self.intros, [12])
        self.assertEqual(stat.S_IMODE(self.ownership().stat().st_mode), 0o600)
        self.assertEqual(helper.run('apply'), {'status': 'already-owned', 'redirect': 12})
        self.assertEqual(helper.run('status'), {'status': 'owned', 'redirect': 12})
        self.assertEqual(len(self.setters()), 1)
        self.assertEqual(helper.run('restore'), {'status': 'restored', 'redirect': 0})
        self.assertFalse(self.ownership().exists())
        self.assertEqual([call[2] for call in self.setters()], [[11, 12], [11, 0]])

    def test_existing_administrator_redirect_is_preserved_even_if_it_is_twelve(self):
        for target in (3, 12):
            self.route = target
            self.assertEqual(helper.run('apply'), {'status': 'skipped-existing-redirect', 'redirect': target})
        self.assertEqual(self.intros, [])
        self.assertEqual(self.setters(), [])
        self.assertFalse(self.ownership().exists())

    def test_allocated_or_configured_vt_is_not_opened_or_written(self):
        self.allocated = True
        self.assertEqual(helper.run('apply')['status'], 'skipped-allocated-tty12')
        self.assertNotIn(12, self.opened)
        self.allocated = False
        self.cmdline.write_text('quiet console=tty12,115200')
        self.assertEqual(helper.run('apply')['status'], 'skipped-configured-tty12')
        self.cmdline.write_text('quiet splash')
        enabled = self.units / 'getty.target.wants'
        enabled.mkdir()
        (enabled / 'getty@tty12.service').symlink_to('/not-required-to-exist')
        self.assertEqual(helper.run('apply')['status'], 'skipped-configured-tty12')
        self.assertEqual(self.intros, [])
        self.assertEqual(self.setters(), [])

    def test_later_administrator_changes_are_preserved_by_apply_and_restore(self):
        helper.run('apply')
        self.route = 0
        self.assertEqual(helper.run('apply')['status'], 'preserved-administrator-redirect')
        self.route = 7
        self.assertEqual(helper.run('restore'), {'status': 'preserved-administrator-redirect', 'redirect': 7})
        self.assertEqual(self.route, 7)
        self.assertFalse(self.ownership().exists())
        self.assertEqual(len(self.setters()), 1)

    def test_redirect_changed_during_allocation_is_not_overwritten(self):
        self.before_second_get = 5
        self.assertEqual(helper.run('apply'), {'status': 'preserved-concurrent-redirect', 'redirect': 5})
        self.assertEqual(self.route, 5)
        self.assertFalse(self.ownership().exists())
        self.assertEqual(self.setters(), [])

    def test_redirect_changed_after_set_is_not_rolled_back_over_admin_choice(self):
        self.after_set = 8
        self.assertEqual(helper.run('apply'), {'status': 'preserved-concurrent-redirect', 'redirect': 8})
        self.assertEqual(self.route, 8)
        self.assertEqual(len(self.setters()), 1)
        self.assertFalse(self.ownership().exists())

    def test_write_failure_cannot_change_kernel_routing(self):
        with mock.patch.object(helper, 'write_state', side_effect=OSError('fixture state write failure')):
            with self.assertRaises(OSError):
                helper.run('apply')
        self.assertEqual(self.route, 0)
        self.assertEqual(self.setters(), [])

    def test_failed_setter_removes_pending_state_when_route_remains_zero(self):
        with mock.patch.object(helper, 'set_redirect', side_effect=OSError('fixture ioctl failure')):
            with self.assertRaises(OSError):
                helper.run('apply')
        self.assertEqual(self.route, 0)
        self.assertFalse(self.ownership().exists())

    def test_restore_without_valid_ownership_never_changes_redirect(self):
        self.route = 12
        self.assertEqual(helper.run('restore')['status'], 'skipped-unowned')
        self.ownership().write_text('[]')
        self.ownership().chmod(0o600)
        with self.assertRaises(ValueError):
            helper.run('restore')
        self.assertEqual(self.route, 12)
        self.assertEqual(self.setters(), [])

    def test_live_boot_and_nonroot_never_open_consoles(self):
        self.cmdline.write_text('boot=live quiet')
        self.assertEqual(helper.run('apply')['status'], 'skipped-live')
        self.assertEqual(self.opened, [])
        with mock.patch.object(helper.os, 'geteuid', return_value=1000):
            with self.assertRaises(ValueError):
                helper.run('apply')
        self.assertEqual(self.opened, [])


class Safety(unittest.TestCase):
    def test_private_runtime_lock_is_exclusive_and_rejects_linked_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual_fstat = os.fstat

            def root_info(descriptor):
                info = actual_fstat(descriptor)
                return SimpleNamespace(st_mode=info.st_mode, st_uid=0)

            with mock.patch.object(helper, 'STATE_DIR', root), \
                    mock.patch.object(helper.Path, 'lstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0)), \
                    mock.patch.object(helper.os, 'fstat', side_effect=root_info):
                with helper.state_lock():
                    with self.assertRaises(BlockingIOError):
                        with helper.state_lock():
                            self.fail('concurrent helper acquired lock')
                lock = root / 'lock'
                lock.unlink()
                lock.symlink_to(root / 'another-file')
                with self.assertRaises(OSError):
                    with helper.state_lock():
                        self.fail('linked lock accepted')

    def test_fixed_intro_handles_partial_writes_without_console_ioctls(self):
        output = bytearray()

        def partial(descriptor, value):
            self.assertEqual(descriptor, 123)
            count = min(7, len(value))
            output.extend(value[:count])
            return count

        with mock.patch.object(helper.os, 'write', side_effect=partial):
            helper.write_intro(123)
        self.assertEqual(bytes(output), helper.INTRO)

    def test_device_path_flags_and_exact_character_identity(self):
        valid = SimpleNamespace(st_mode=stat.S_IFCHR | 0o620, st_uid=0, st_rdev=os.makedev(4, 12))
        with mock.patch.object(helper.os, 'open', return_value=123) as opened, \
                mock.patch.object(helper.os, 'fstat', return_value=valid), \
                mock.patch.object(helper.os, 'close') as closed:
            with helper.console_device(12) as descriptor:
                self.assertEqual(descriptor, 123)
            path, flags = opened.call_args.args
            self.assertEqual(path, '/dev/tty12')
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_NOCTTY)
            closed.assert_called_once_with(123)
        for info in (SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0, st_rdev=0),
                     SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=1000, st_rdev=os.makedev(4, 12)),
                     SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=0, st_rdev=os.makedev(4, 1)),
                     SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=0, st_rdev=os.makedev(5, 12))):
            with mock.patch.object(helper.os, 'open', return_value=123), \
                    mock.patch.object(helper.os, 'fstat', return_value=info), \
                    mock.patch.object(helper.os, 'close'):
                with self.assertRaises(ValueError):
                    with helper.console_device(12):
                        self.fail('wrong device accepted')

    def test_ioctl_wire_format_and_vt_allocation_bit(self):
        calls = []

        def fake(descriptor, request, argument, mutate):
            calls.append((descriptor, request, list(argument), mutate))
            if request == helper.VT_GETSTATE:
                argument[2] = 1 << 12
                return 0
            if argument[0] == 17:
                argument[0] = 12
            return 0

        with mock.patch.object(helper.fcntl, 'ioctl', side_effect=fake):
            self.assertEqual(helper.get_redirect(456), 12)
            helper.set_redirect(456, 0)
            self.assertTrue(helper.target_allocated(456))
        self.assertEqual(calls[0], (456, 0x541C, [17], True))
        self.assertEqual(calls[1], (456, 0x541C, [11, 0], True))
        self.assertEqual(calls[2][1], 0x5603)

    def test_state_rejects_symlinks_fifo_permissions_and_other_boots(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(helper, 'STATE_DIR', Path(directory)):
            root = Path(directory)
            path = root / 'state.json'
            path.symlink_to(root / 'elsewhere')
            with self.assertRaises(OSError):
                helper.read_state('fixture-boot')
            path.unlink()
            os.mkfifo(path)
            with self.assertRaises(ValueError):
                helper.read_state('fixture-boot')
            path.unlink()
            path.write_text(json.dumps({'schema_version': 1, 'boot_id': 'other-boot',
                                        'previous_redirect': 0, 'redirect': 12}))
            path.chmod(0o600)
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
            with mock.patch.object(helper.os, 'fstat', return_value=info):
                with self.assertRaises(ValueError):
                    helper.read_state('fixture-boot')
            for mode, uid in ((0o644, 0), (0o600, 1000)):
                with mock.patch.object(helper.os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=uid)):
                    with self.assertRaises(ValueError):
                        helper.read_state('other-boot')

    def test_state_directory_is_never_a_symlink_or_group_accessible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'private'
            private.mkdir()
            linked = root / 'linked'
            linked.symlink_to(private)
            with mock.patch.object(helper, 'STATE_DIR', linked):
                with self.assertRaises(ValueError):
                    with helper.state_lock():
                        self.fail('symlink state directory accepted')
            with mock.patch.object(helper, 'STATE_DIR', private), \
                    mock.patch.object(helper.Path, 'lstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=0)):
                with self.assertRaises(ValueError):
                    with helper.state_lock():
                        self.fail('group-accessible state directory accepted')


if __name__ == '__main__':
    unittest.main()
