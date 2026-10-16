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
CODE = HOOK.read_text().split("python3 - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
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


if __name__ == "__main__":
    unittest.main()
