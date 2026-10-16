#!/usr/bin/python3
"""Readiness fixtures and privilege-boundary tests; no host install or X server."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
INCLUDES = REPO / "config/includes.chroot"
WIZARD = INCLUDES / "usr/local/bin/kythos-setup"
loader = importlib.machinery.SourceFileLoader("kythos_setup", str(WIZARD))
spec = importlib.util.spec_from_loader(loader.name, loader)
setup = importlib.util.module_from_spec(spec)
loader.exec_module(setup)


def put(root, name, content, mode=0o644):
    path = root / name.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


class ReadinessTests(unittest.TestCase):
    def test_read_only_hardware_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run/live/medium").mkdir(parents=True)
            put(root, "/proc/cmdline", "quiet boot=live kythos.installer=1")
            put(root, "/proc/meminfo", "MemTotal:       8388608 kB\n")
            put(root, "/sys/block/vda/size", "134217728\n")
            put(root, "/sys/block/vda/device/model", "Test virtual disk\n")
            put(root, "/sys/block/loop0/size", "2048\n")
            put(root, "/sys/class/net/enp1s0/operstate", "up\n")
            put(root, "/sys/bus/pci/devices/0000:01:00.0/class", "0x030000\n")
            put(root, "/sys/bus/pci/devices/0000:01:00.0/vendor", "0x10de\n")
            variable = root / "sys/firmware/efi/efivars/SecureBoot-test"
            variable.parent.mkdir(parents=True)
            variable.write_bytes(b"\x07\0\0\0\x01")
            before = sorted((p.relative_to(root), p.read_bytes()) for p in root.rglob("*") if p.is_file())
            result = setup.collect_readiness(root)
            self.assertTrue(result["live"])
            self.assertEqual(result["memory_gib"], 8)
            self.assertEqual(result["secure_boot"], "Enabled")
            self.assertEqual(result["graphics"], ["NVIDIA"])
            self.assertEqual(result["disks"], [{"name": "vda", "gib": 64.0, "model": "Test virtual disk"}])
            self.assertEqual(result["interfaces"], [{"name": "enp1s0", "up": True}])
            after = sorted((p.relative_to(root), p.read_bytes()) for p in root.rglob("*") if p.is_file())
            self.assertEqual(before, after)

    def test_missing_sysfs_is_unknown_and_live_token_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run/live/overlay").mkdir(parents=True)
            put(root, "/proc/cmdline", "boot=live-other")
            result = setup.collect_readiness(root)
            self.assertFalse(result["live"])
            self.assertIsNone(result["memory_gib"])
            self.assertEqual(result["disks"], [])
            self.assertEqual(result["secure_boot"], "Not available in BIOS boot")


class LauncherTests(unittest.TestCase):
    def test_guard_requires_marker_and_exact_live_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = (INCLUDES / "usr/local/libexec/kythos-live-guard").read_text()
            for original in ("/run/live/medium", "/run/live/overlay", "/proc/cmdline"):
                source = source.replace(original, str(root / original.lstrip("/")))
            script = put(root, "/guard", source, 0o755)
            put(root, "/proc/cmdline", "boot=live")
            self.assertEqual(subprocess.run([script]).returncode, 1)
            (root / "run/live/medium").mkdir(parents=True)
            self.assertEqual(subprocess.run([script]).returncode, 0)
            put(root, "/proc/cmdline", "boot=live-bogus")
            self.assertEqual(subprocess.run([script]).returncode, 1)
            self.assertEqual(subprocess.run([script, "unexpected"]).returncode, 2)

    def test_launchers_reject_all_user_arguments(self):
        names = ("usr/local/bin/kythos-installer", "usr/local/bin/kythos-install",
                 "usr/local/sbin/kythos-installer-root", "usr/local/libexec/kythos-live-session")
        for name in names:
            with self.subTest(launcher=name):
                result = subprocess.run([INCLUDES / name, "--config", "/tmp/evil"], capture_output=True)
                self.assertEqual(result.returncode, 2)

    def test_root_launcher_sanitizes_environment_and_checks_live_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = (INCLUDES / "usr/local/sbin/kythos-installer-root").read_text()
            fake_id = put(root, "/fake-id", "#!/bin/sh\nprintf '0\\n'\n", 0o755)
            guard = put(root, "/guard", "#!/bin/sh\nexit 0\n", 0o755)
            auth = put(root, "/home/kythos-live/.Xauthority", "test fixture")
            settings = put(root, "/etc/calamares/settings.conf", "test fixture")
            record = root / "record.json"
            binary = put(root, "/calamares", "#!/usr/bin/python3\nimport json, os, pathlib, sys\n"
                         + f"pathlib.Path({str(record)!r}).write_text(json.dumps({{'argv':sys.argv[1:],'cwd':os.getcwd(),'env':dict(os.environ)}}))\n", 0o755)
            replacements = {"/usr/bin/id": str(fake_id), "/usr/local/libexec/kythos-live-guard": str(guard),
                            "/home/kythos-live/.Xauthority": str(auth),
                            "/etc/calamares/settings.conf": str(settings), "/usr/bin/calamares": str(binary)}
            for original, replacement in replacements.items():
                source = source.replace(original, replacement)
            script = put(root, "/root-launcher", source, 0o755)
            environment = dict(os.environ, QT_PLUGIN_PATH="/tmp/evil", PYTHONPATH="/tmp/evil",
                               XDG_CONFIG_HOME="/tmp/evil", DISPLAY="evil:99", HOME="/tmp/evil")
            result = subprocess.run([script], env=environment, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads(record.read_text())
            self.assertEqual(report["argv"], [])
            self.assertEqual(report["cwd"], "/")
            self.assertEqual(report["env"]["DISPLAY"], ":0")
            self.assertEqual(report["env"]["HOME"], "/root")
            for variable in ("QT_PLUGIN_PATH", "PYTHONPATH", "XDG_CONFIG_HOME"):
                self.assertNotIn(variable, report["env"])
            record.unlink()
            guard.write_text("#!/bin/sh\nexit 1\n")
            self.assertEqual(subprocess.run([script], capture_output=True).returncode, 1)
            self.assertFalse(record.exists())

    def test_boot_entry_runs_once_only_for_live_user_on_tty1_with_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guard = put(root, "/guard", "#!/bin/sh\nexit 0\n", 0o755)
            (root / "home/kythos-live").mkdir(parents=True)
            (root / "etc/profile.d").mkdir(parents=True)
            source = (INCLUDES / "usr/lib/live/config/1200-kythos-installer").read_text()
            source = source.replace("/usr/local/libexec/kythos-live-guard", str(guard))
            for path in ("/home/kythos-live", "/etc/profile.d/zz-kythos-installer.sh"):
                source = source.replace(path, str(root / path.lstrip("/")))
            component = put(root, "/component", source, 0o755)
            subprocess.run([component], check=True)
            profile = root / "etc/profile.d/zz-kythos-installer.sh"
            self.assertEqual(profile.stat().st_mode & 0o777, 0o644)
            identity = put(root, "/identity", "#!/bin/sh\nprintf 'kythos-live\\n'\n", 0o755)
            tty = put(root, "/tty", "#!/bin/sh\nprintf '/dev/tty1\\n'\n", 0o755)
            called = root / "called"
            launcher = put(root, "/launcher", f"#!/bin/sh\nprintf 'called\\n' >> '{called}'\n", 0o755)
            cmdline = put(root, "/proc/cmdline", "boot=live kythos.installer=1")
            source = profile.read_text().replace("id -un", str(identity)).replace("tty 2>/dev/null", str(tty))
            source = source.replace("/usr/local/bin/kythos-installer", str(launcher)).replace("/proc/cmdline", str(cmdline))
            profile.write_text(source)
            environment = dict(os.environ, DISPLAY="")
            subprocess.run(["/bin/sh", "-c", '. "$1"', "-", profile], env=environment, check=True)
            self.assertEqual(called.read_text(), "called\n")
            called.unlink()
            for commandline, user, terminal, display in (
                ("boot=live", "kythos-live", "/dev/tty1", ""),
                ("boot=live kythosXinstaller=1", "kythos-live", "/dev/tty1", ""),
                ("boot=live kythos.installer=1", "root", "/dev/tty1", ""),
                ("boot=live kythos.installer=1", "kythos-live", "/dev/ttyS0", ""),
                ("boot=live kythos.installer=1", "kythos-live", "/dev/tty1", ":0"),
            ):
                cmdline.write_text(commandline)
                identity.write_text(f"#!/bin/sh\nprintf '{user}\\n'\n")
                tty.write_text(f"#!/bin/sh\nprintf '{terminal}\\n'\n")
                subprocess.run(["/bin/sh", "-c", '. "$1"', "-", profile],
                               env=dict(environment, DISPLAY=display), check=True)
                self.assertFalse(called.exists())


try:
    from PyQt6.QtCore import QProcess
    from PyQt6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PyQt6 not available; run again in the live-image environment")
class NativeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.application = QApplication.instance() or QApplication(["test-setup-wizard"])

    def test_all_pages_and_no_host_install(self):
        info = setup.collect_readiness()
        info["live"] = False
        window = setup.build_window(info, start_hardware=False)
        window.show()
        self.application.processEvents()
        self.assertEqual(window.pages.count(), 4)
        self.assertFalse(window.back_button.isEnabled())
        for _ in range(3):
            window.next_action()
            self.application.processEvents()
        self.assertEqual(window.page_index, 3)
        self.assertEqual(window.next_button.text(), "Open installer")
        self.assertFalse(window.next_button.isEnabled())
        window.next_action()
        self.assertEqual(window.installer.state(), QProcess.ProcessState.NotRunning)
        window.close()

    def test_real_process_handoff_only_fixed_launcher(self):
        info = setup.collect_readiness()
        info["live"] = True
        window = setup.build_window(info, start_hardware=False)
        self.assertEqual(window.installer.program(), setup.INSTALL_LAUNCHER)
        self.assertEqual(window.installer.arguments(), [])
        # Substitute an inert test program on this in-memory QObject only.
        window.installer.setProgram("/usr/bin/true")
        window.change_page(3)
        window.next_action()
        self.assertTrue(window.installer.waitForStarted(1000))
        self.assertTrue(window.installer.waitForFinished(1000))
        self.application.processEvents()
        self.assertIn("installer has closed", window.status.text())
        self.assertTrue(window.next_button.isEnabled())
        window.close()

    def test_hardware_report_uses_actual_graphics_driver_and_preserves_unknown_journal(self):
        info = setup.collect_readiness()
        info["live"] = False
        window = setup.build_window(info, start_hardware=False)
        report = {"schema": 1, "mode": "read-only",
                  "graphics": [{"name": "card0", "driver": "virtio_gpu", "module": "virtio_gpu", "status": "bound"}],
                  "network": [], "storage": [], "pci": [], "usb": [], "nvidia": None,
                  "firmware": {"status": "unavailable", "scope": "Kernel journal could not be read.", "possible_failures": []}}
        window.hardware_output.extend(json.dumps(report).encode())
        window.hardware_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertIn("virtio_gpu", window.driver_details.text())
        self.assertIn("Unavailable", window.firmware_details.text())
        self.assertIn("could not be read", window.firmware_details.text())
        self.assertFalse(window.nvidia_button.isVisible())
        window.close()

    def test_hardware_timeout_and_oversized_output_fail_without_installing(self):
        info = setup.collect_readiness()
        info["live"] = False
        window = setup.build_window(info, start_hardware=False)
        # Substitute a harmless child to exercise actual cancellation.
        window.hardware_process.setProgram("/usr/bin/sleep")
        window.hardware_process.setArguments(["5"])
        window.refresh_hardware()
        self.assertTrue(window.hardware_process.waitForStarted(1000))
        window.hardware_timeout()
        window.hardware_process.waitForFinished(1000)
        self.assertIn("timed out", window.driver_details.text())
        self.assertEqual(window.installer.state(), QProcess.ProcessState.NotRunning)
        window.hardware_output.extend(b"x" * 524289)
        window.read_hardware_output()
        self.assertIn("size limit", window.driver_details.text())
        self.assertIn("unknown", window.firmware_details.text())
        self.assertEqual(window.installer.state(), QProcess.ProcessState.NotRunning)
        window.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
