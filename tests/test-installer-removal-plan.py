#!/usr/bin/python3
"""Exercise the actual build-hook planner with isolated dpkg/APT fixtures."""
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "config/hooks/live/060-record-installer-packages.hook.chroot"
SOURCE_HOOK = ROOT / "config/hooks/live/005-add-grub2-source.hook.source"
FINISH_HOOK = (ROOT / "config/includes.installer/usr/lib/finish-install.d/"
               "93kythos-live-cleanup")
CLEAN_HELPER = (ROOT / "config/includes.chroot/usr/local/libexec/"
                "kythos-calamares-clean-live-files")
CODE = HOOK.read_text().split("python3 - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
SOURCE_REPORT_CODE = SOURCE_HOOK.read_text().split(
    "python3 - missing-source.txt <<'PY_REPORT'\n", 1
)[1].split("\nPY_REPORT\n", 1)[0]
BASE = "linux-image-amd64\npython3\nsudo\nsystemd-sysv\n"
LIVE = "calamares\nqml6-module-qtquick\n"
STATUS = "\n".join([
    "linux-image-amd64\tinstall ok installed\toptional\t",
    "python3\tinstall ok installed\toptional\t",
    "sudo\tinstall ok installed\toptional\t",
    "systemd-sysv\tinstall ok installed\timportant\t",
    "libc6:amd64\tinstall ok installed\toptional\tyes",
    "calamares\tinstall ok installed\toptional\t",
    "qml6-module-qtquick:amd64\tinstall ok installed\toptional\t",
    "libqt6quick6:amd64\tinstall ok installed\toptional\t",
]) + "\n"
VALID_PLAN = "Purg calamares [3.3.14-1]\nPurg qml6-module-qtquick:amd64 [6.8.2]\nRemv libqt6quick6:amd64 [6.8.2]\n"


class RemovalPlanTests(unittest.TestCase):
    def execute(self, plan=VALID_PLAN, base=BASE, live=LIVE):
        self.temp = tempfile.TemporaryDirectory(prefix="kythos-removal-test-")
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        (folder / "installer-base-package-roots").write_text(base)
        (folder / "installer-live-package-roots").write_text(live)
        calls = []

        def run(command, **options):
            calls.append(command)
            if command[0] == "dpkg-query":
                return subprocess.CompletedProcess(command, 0, STATUS)
            if command[:2] == ["apt-mark", "manual"]:
                return subprocess.CompletedProcess(command, 0, "")
            if command[:4] == ["apt-get", "--simulate", "--auto-remove", "purge"]:
                return subprocess.CompletedProcess(command, 0, plan)
            raise AssertionError("Unexpected package operation: " + repr(command))

        fake_pathlib = types.ModuleType("pathlib")
        fake_pathlib.Path = lambda value: folder if value == "/usr/share/kythos" else Path(value)
        with patch.dict(sys.modules, {"pathlib": fake_pathlib}), patch("subprocess.run", run):
            exec(compile(CODE, str(HOOK), "exec"), {"__name__": "__test__"})
        return folder, calls

    def test_freezes_dependency_closure_and_handles_multiarch(self):
        folder, calls = self.execute()
        self.assertEqual((folder / "installer-live-packages").read_text().splitlines(),
                         ["calamares", "libqt6quick6:amd64", "qml6-module-qtquick:amd64"])
        self.assertIn("libc6:amd64", calls[1])
        self.assertIn("sudo", calls[1])
        self.assertEqual(calls[-1][0:4], ["apt-get", "--simulate", "--auto-remove", "purge"])

    def test_refuses_removing_common_user_tools(self):
        with self.assertRaisesRegex(SystemExit, "common system"):
            self.execute(plan=VALID_PLAN + "Purg sudo [1.9]\n")

    def test_refuses_removing_essential_multiarch_dependency(self):
        with self.assertRaisesRegex(SystemExit, "common system"):
            self.execute(plan=VALID_PLAN + "Purg libc6:amd64 [2.41]\n")

    def test_refuses_unexpected_package_install(self):
        with self.assertRaisesRegex(SystemExit, "package installation"):
            self.execute(plan=VALID_PLAN + "Inst unexpected [1]\n")

    def test_refuses_missing_live_root(self):
        with self.assertRaisesRegex(SystemExit, "not installed"):
            self.execute(live=LIVE + "missing-gui\n")

    def test_refuses_partial_purge_plan(self):
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            self.execute(plan="Purg calamares [3.3.14-1]\n")

    def test_refuses_malformed_package_operand(self):
        with self.assertRaisesRegex(SystemExit, "malformed"):
            self.execute(plan=VALID_PLAN + "Purg ../../etc [1]\n")


class FinishInstallHookTests(unittest.TestCase):
    def test_advanced_installer_purges_manifest_before_removing_it(self):
        calls = []
        helpers = {
            "verify_chroot_context": lambda: calls.append("verify"),
            "purge_live_packages": lambda: calls.append("purge"),
            "remove_live_files": lambda: calls.append("remove"),
        }

        def record_unlink(path, missing_ok=False):
            calls.append("unlink:" + str(path))

        namespace = {"__name__": "__test__"}
        with patch("runpy.run_path", return_value=helpers) as loader, \
                patch.object(Path, "unlink", autospec=True, side_effect=record_unlink), \
                patch.object(sys, "argv", [str(CLEAN_HELPER)]):
            exec(compile(CLEAN_HELPER.read_text(), str(CLEAN_HELPER), "exec"), namespace)
            self.assertEqual(namespace["main"](), 0)

        loader.assert_called_once_with("/usr/local/libexec/kythos-calamares-target")
        self.assertEqual(calls[:3], ["verify", "purge", "remove"])
        self.assertEqual(
            calls[3:],
            [
                "unlink:/usr/local/libexec/kythos-calamares-target",
                "unlink:/usr/local/libexec/kythos-calamares-grub-install",
            ],
        )

    def test_advanced_installer_enables_ssh_and_selected_edition_boot_target(self):
        with tempfile.TemporaryDirectory(prefix="kythos-finish-hook-test-") as folder:
            folder = Path(folder)
            log = folder / "in-target.log"
            fake = folder / "in-target"
            fake.write_text(
                "#!/bin/sh\nset -eu\n"
                "printf '%s\\n' \"$*\" >> \"$KYTHOS_TEST_LOG\"\n"
                "case \"$*\" in\n"
                "  '/usr/bin/systemctl get-default'|'/usr/local/libexec/kythos-edition --get default_target') "
                "printf '%s\\n' \"$KYTHOS_TEST_TARGET\" ;;\n"
                "  '/usr/bin/systemctl is-enabled ssh.service') printf '%s\\n' enabled ;;\n"
                "esac\n")
            fake.chmod(0o755)
            runner = (
                "test() {\n"
                "    if [ \"$1\" = -x ] && [ \"$2\" = "
                "'/target/usr/local/libexec/kythos-calamares-clean-live-files' ]; then\n"
                "        return 0\n    fi\n    command test \"$@\"\n}\n. \"$1\"\n")
            for selected in ('multi-user.target', 'graphical.target'):
                with self.subTest(selected=selected):
                    log.unlink(missing_ok=True)
                    environment = {"PATH": f"{folder}:/usr/bin:/bin", "KYTHOS_TEST_LOG": str(log),
                                   "KYTHOS_TEST_TARGET": selected}
                    subprocess.run(["/bin/sh", "-eu", "-c", runner, "hook-test", str(FINISH_HOOK)],
                                   check=True, env=environment)
                    expected = ["/usr/local/libexec/kythos-calamares-clean-live-files",
                                "/usr/local/sbin/kythos-enable-ssh --offline",
                                "/usr/bin/systemctl is-enabled ssh.service",
                                "/usr/local/libexec/kythos-edition --get default_target"]
                    if selected == 'graphical.target':
                        expected.append('/usr/bin/systemctl enable lightdm.service')
                    expected += ["/usr/bin/systemctl set-default " + selected,
                                 "/usr/bin/systemctl get-default"]
                    self.assertEqual(log.read_text().splitlines(), expected)


class SourceReportTests(unittest.TestCase):
    HEADER = (
        'This file contains the list of binary packages that are installed on the "live"\n'
        'system (to which this source disc is a companion) for which a corresponding\n'
        'source package is not included on this disc. This may be because the binary\n'
        'package does not have a corresponding source package, or because the version of\n'
        'the source package available was not the same as that of the binary.\n\n'
    )
    PLACEHOLDER = 'un  grub-efi       <none>       <none>       (no description available)\n'

    def parse(self, contents):
        with tempfile.TemporaryDirectory(prefix="kythos-source-report-test-") as folder:
            report = Path(folder) / "missing-source.txt"
            report.write_text(contents)
            return subprocess.run(
                [sys.executable, "-", str(report)], input=SOURCE_REPORT_CODE,
                text=True, capture_output=True,
            )

    def test_accepts_only_header_or_exact_uninstalled_grub_efi_placeholder(self):
        self.assertEqual(self.parse(self.HEADER).stdout.strip(), "header-only")
        accepted = self.parse(self.HEADER + self.PLACEHOLDER)
        self.assertEqual(accepted.returncode, 0)
        self.assertEqual(accepted.stdout.strip(), "uninstalled-grub-efi")

    def test_rejects_real_or_unknown_missing_rows(self):
        for row in (
            "ii  real-package   1.0   amd64   Real package\n",
            "un  grub-efi <none> <none> (no description available)\n",
            self.PLACEHOLDER + "un  unknown <none> <none> (no description available)\n",
        ):
            with self.subTest(row=row):
                self.assertNotEqual(self.parse(self.HEADER + row).returncode, 0)


if __name__ == "__main__":
    unittest.main()
