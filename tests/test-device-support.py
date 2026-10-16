#!/usr/bin/python3
"""Exercise launcher execution and device observations without using host devices."""

import importlib.machinery
import importlib.util
import configparser
import io
import json
import os
from pathlib import Path
import pty
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "config/includes.chroot/usr/local/bin"
DESKTOP = REPO / "config/editions/desktop"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


wifi = load("wifi", BIN / "kythos-wifi")
smartcard = load("smartcard", BIN / "kythos-smartcard-status")
vm = load("vm", BIN / "kythos-vm-status")
integration = load("smartcard_integration", DESKTOP / "includes.chroot/usr/local/libexec/kythos-configure-smartcards")


def put(root, relative, content=""):
    path = root / relative.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def result(output="", code=0, error=""):
    return {"returncode": code, "output": output, "error": error}


class WifiTests(unittest.TestCase):
    def select(self, mode="auto", environment=None, interactive=True, missing=(), devices="ethernet\nwifi",
               radio="enabled:enabled"):
        calls = []

        def probe(arguments):
            calls.append(arguments)
            return devices if arguments[-2:] == ["device", "status"] else radio

        chosen = wifi.select_manager(mode, environment or {}, interactive,
                                     find=lambda name: None if name in missing else "/fixture/" + name,
                                     probe=probe)
        self.assertEqual(calls, [["/fixture/nmcli", "--terse", "--fields", "TYPE", "device", "status"],
                                 ["/fixture/nmcli", "--terse", "--fields", "WIFI-HW,WIFI", "general"]])
        return chosen

    def test_exact_case_sensitive_symlink(self):
        link = BIN / "WiFi"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "kythos-wifi")
        self.assertEqual(link.resolve(), (BIN / "kythos-wifi").resolve())
        self.assertTrue(os.access(link, os.X_OK))

    def test_tty_default_and_override(self):
        self.assertEqual(self.select(), ["/fixture/nmtui", "connect"])
        self.assertEqual(self.select("tty", {"DISPLAY": ":0"}), ["/fixture/nmtui", "connect"])

    def test_graphical_x11_and_wayland(self):
        for environment in ({"DISPLAY": ":0"}, {"WAYLAND_DISPLAY": "wayland-0"}):
            self.assertEqual(self.select(environment=environment, interactive=False), ["/fixture/nm-connection-editor"])

    def test_missing_graphical_manager_falls_back_with_explanation(self):
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.select(environment={"DISPLAY": ":0"}, missing=("nm-connection-editor",)),
                             ["/fixture/nmtui", "connect"])
        self.assertIn("terminal interface", output.getvalue())

    def test_missing_dependencies_and_noninteractive_errors(self):
        for options, message in (({"missing": ("nmcli",)}, "Missing nmcli"),
                                 ({"missing": ("nmtui",)}, "Missing nmtui"),
                                 ({"interactive": False}, "interactive TTY"),
                                 ({"mode": "gui"}, "No graphical display"),
                                 ({"mode": "gui", "environment": {"DISPLAY": ":0"},
                                   "missing": ("nm-connection-editor",)}, "Graphical Wi-Fi manager is missing")):
            with self.subTest(options=options), self.assertRaisesRegex(wifi.LaunchError, message):
                self.select(**options)

    def test_no_adapter_and_radio_states(self):
        for options, message in (({"devices": "ethernet\nloopback"}, "No Wi-Fi adapter"),
                                 ({"radio": "disabled:disabled"}, "blocked by hardware"),
                                 ({"radio": "enabled:disabled"}, "radio is disabled"),
                                 ({"radio": "unknown:enabled"}, "Cannot determine"),
                                 ({"radio": ""}, "Cannot determine")):
            with self.subTest(options=options), self.assertRaisesRegex(wifi.LaunchError, message):
                self.select(**options)

    def test_daemon_error_and_timeout_are_actionable(self):
        with patch.object(wifi.subprocess, "run", return_value=subprocess.CompletedProcess([], 10, "", "denied")):
            with self.assertRaisesRegex(wifi.LaunchError, "permissions"):
                wifi.query(["nmcli"])
        with patch.object(wifi.subprocess, "run", side_effect=subprocess.TimeoutExpired("nmcli", 5)):
            with self.assertRaisesRegex(wifi.LaunchError, "NetworkManager did not answer"):
                wifi.query(["nmcli"])

    def test_exact_symlink_launches_real_executable_fixtures(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = '''#!/usr/bin/python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ["KYTHOS_FIXTURE_LOG"], "a") as log:
    log.write(json.dumps([name, *sys.argv[1:]]) + "\\n")
if name == "nmcli":
    print("wifi" if sys.argv[-2:] == ["device", "status"] else "enabled:enabled")
'''
            for name in ("nmcli", "nm-connection-editor", "nmtui"):
                executable = put(directory, name, fixture)
                executable.chmod(0o755)
            log = directory / "commands.jsonl"
            environment = {"PATH": str(directory), "LC_ALL": "C", "KYTHOS_FIXTURE_LOG": str(log), "DISPLAY": ":fixture"}
            process = subprocess.run([str(BIN / "WiFi")], env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(log.read_text().splitlines()[-1]), ["nm-connection-editor"])
            master, slave = pty.openpty()
            try:
                process = subprocess.run([str(BIN / "WiFi"), "--tty"], env=environment,
                                         stdin=slave, stdout=slave, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(process.returncode, 0, process.stderr)
            finally:
                os.close(master)
                os.close(slave)
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(commands[-1], ["nmtui", "connect"])
            self.assertEqual(len(commands), 6)
            self.assertFalse(any(word in ("up", "modify", "on", "off", "--ask") for command in commands for word in command))


class SmartCardTests(unittest.TestCase):
    def test_reader_slots_and_explicit_public_certificates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = put(root, "/usr/lib/aarch64-linux-gnu/pkcs11/opensc-pkcs11.so")
            calls = []

            def run(command):
                calls.append(command)
                return result("Nr. Card Features Name\n 0 Yes USB Test reader\n" if command[-1] == "--list-readers"
                              else "Certificate Object; type = X.509\n" if command[-1] == "cert" else "Slot 0\n")

            report = smartcard.collect(root=root, find=lambda name: "/fixture/" + name, run=run)
            self.assertEqual(report["reader_status"], "readers-detected")
            self.assertEqual(report["readers_observed"], 1)
            self.assertEqual(report["module"], str(module))
            self.assertEqual(report["authentication"], "not-tested")
            self.assertEqual(report["signing"], "not-tested")
            self.assertNotIn("certificates", report["probes"])
            report = smartcard.collect(True, root, find=lambda name: "/fixture/" + name, run=run)
            self.assertIn("certificates", report["probes"])
            self.assertEqual(calls[-1], ["/fixture/pkcs11-tool", "--module", str(module), "--list-objects", "--type", "cert"])
            self.assertFalse(any(word in ("--pin", "--login", "--sign", "--write-object", "--init-token")
                                 for command in calls for word in command))

    def test_no_readers_and_no_dependencies_remain_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = smartcard.collect(root=root, find=lambda _: None)
            self.assertEqual(report["reader_status"], "unavailable")
            self.assertIsNone(report["readers_observed"])
            self.assertIn("Missing OpenSC", report["probes"]["slots"]["error"])
            report = smartcard.collect(root=root, find=lambda name: "/fixture/" + name,
                                       run=lambda _: result("No smart card readers found.\n"))
            self.assertEqual(report["reader_status"], "no-readers-detected")
            self.assertEqual(report["readers_observed"], 0)

    def test_timeout_and_terminal_control_characters(self):
        with patch.object(smartcard.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 8)):
            self.assertIsNone(smartcard.probe(["test"])["returncode"])
        self.assertEqual(smartcard.safe_terminal("Name\x1b[31m\x07\n"), "Name?[31m?\n")

    def test_multiarch_configuration_is_repeatable_and_preserves_policy(self):
        for architecture in ("x86_64-linux-gnu", "aarch64-linux-gnu"):
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                module = f"/usr/lib/{architecture}/pkcs11/opensc-pkcs11.so"
                put(root, module)
                policy_file = put(root, "/etc/firefox/policies/policies.json",
                                  json.dumps({"policies": {"DisableTelemetry": True}}))
                self.assertEqual(integration.configure(root, [module]), module)
                policy = json.loads(policy_file.read_text())
                self.assertTrue(policy["policies"]["DisableTelemetry"])
                self.assertEqual(policy["policies"]["SecurityDevices"]["Add"]["OpenSC"], module)
                definition = root / "etc/pkcs11/modules/opensc.module"
                self.assertIn("module: " + module, definition.read_text())
                original = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
                integration.configure(root, [module])
                self.assertEqual(original, {path.relative_to(root): path.read_bytes()
                                            for path in root.rglob("*") if path.is_file()})

    def test_vendor_p11_registration_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so"
            put(root, module)
            vendor = put(root, "/usr/share/p11-kit/modules/opensc-pkcs11.module", "module: opensc-pkcs11.so\n")
            integration.configure(root, [module])
            self.assertFalse((root / "etc/pkcs11/modules/opensc.module").exists())
            self.assertEqual(vendor.read_text(), "module: opensc-pkcs11.so\n")

    def test_incomplete_or_conflicting_configuration_fails_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "module is missing"):
                integration.configure(root, [])
            self.assertFalse((root / "etc").exists())
            module = "/usr/lib/aarch64-linux-gnu/opensc-pkcs11.so"
            put(root, module)
            definition = put(root, "/etc/pkcs11/modules/opensc.module", "disable-in: all\n")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                integration.configure(root, [module])
            self.assertEqual(definition.read_text(), "disable-in: all\n")
            definition.unlink()
            policy = put(root, "/etc/firefox/policies/policies.json", "invalid JSON")
            with self.assertRaises(ValueError):
                integration.configure(root, [module])
            self.assertEqual(policy.read_text(), "invalid JSON")
            self.assertFalse(definition.exists())


class DesktopDisplayTests(unittest.TestCase):
    def test_live_installer_owns_display_and_installed_desktop_is_enabled_offline(self):
        dropin = DESKTOP / "includes.chroot/etc/systemd/system/lightdm.service.d/60-kythos-live.conf"
        configuration = configparser.ConfigParser()
        configuration.read(dropin)
        self.assertEqual(configuration["Unit"]["ConditionPathExists"], "!/run/live/medium")
        self.assertEqual(configuration["Unit"]["ConditionKernelCommandLine"], "!boot=live")
        hook = DESKTOP / "hooks/live/031-desktop-display.hook.chroot"
        calls = [shlex.split(line) for line in hook.read_text().splitlines() if line.startswith("systemctl ")]
        self.assertEqual(calls, [["systemctl", "enable", "lightdm.service"]])
        self.assertTrue(os.access(hook, os.X_OK))

    @unittest.skipUnless(shutil.which("systemctl") and shutil.which("systemd-analyze"),
                         "Native systemd offline tools unavailable")
    def test_systemd_live_media_guard_and_offline_display_manager_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            medium = root / "run/live/medium"
            condition = "ConditionPathExists=!" + str(medium)
            # Native condition evaluation, with a temporary runtime-path fixture.
            installed = subprocess.run(["systemd-analyze", "condition", condition], capture_output=True, timeout=5)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            medium.mkdir(parents=True)
            live = subprocess.run(["systemd-analyze", "condition", condition], capture_output=True, timeout=5)
            self.assertNotEqual(live.returncode, 0)
            put(root, "/usr/lib/systemd/system/lightdm.service",
                "[Unit]\nDescription=Display manager fixture\n[Service]\nExecStart=/usr/bin/true\n"
                "[Install]\nAlias=display-manager.service\n")
            enabled = subprocess.run(["systemctl", "--root", str(root), "enable", "lightdm.service"],
                                     capture_output=True, timeout=5)
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            self.assertEqual(os.readlink(root / "etc/systemd/system/display-manager.service"),
                             "/usr/lib/systemd/system/lightdm.service")
            status = subprocess.run(["systemctl", "--root", str(root), "is-enabled", "lightdm.service"],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(status.stdout.strip(), "enabled")


class VmTests(unittest.TestCase):
    def test_virtio_channel_and_renderer_observations_do_not_claim_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root, "/sys/class/dmi/id/sys_vendor", "QEMU\n")
            put(root, "/sys/class/drm/card0-Virtual-1/status", "connected\n")
            put(root, "/sys/class/drm/card0-Virtual-1/modes", "1920x1080\n1280x800\n")
            put(root, "/dev/virtio-ports/com.redhat.spice.0")
            put(root, "/dev/virtio-ports/org.qemu.guest_agent.0")
            calls = []

            def run(command, timeout=5):
                calls.append(command)
                if command[0].endswith("systemd-detect-virt"):
                    return result("qemu\n")
                if command[0].endswith("kythos-hardware-status"):
                    return result(json.dumps({"graphics": [{"name": "card0", "driver": "virtio_gpu"}]}))
                return result("OpenGL renderer string: llvmpipe\n")

            report = vm.collect(root, {"DISPLAY": ":fixture", "XDG_SESSION_TYPE": "x11"},
                                find=lambda name: "/fixture/" + name, run=run, machine="aarch64")
            self.assertEqual(report["guest_architecture"], "aarch64")
            self.assertEqual(report["virtualization"], "qemu")
            self.assertEqual(report["graphics"][0]["driver"], "virtio_gpu")
            self.assertEqual(report["connectors"][0]["modes"], ["1920x1080", "1280x800"])
            self.assertTrue(report["channels"]["spice"])
            self.assertTrue(report["channels"]["qemu_guest_agent"])
            self.assertEqual(report["host_architecture"], "not-observable-from-guest")
            self.assertEqual(report["acceptance"]["apple_host"], "not-tested")
            self.assertEqual(report["acceptance"]["display_resize"], "not-tested")
            self.assertEqual(report["acceptance"]["gpu_acceleration"], "not-tested")
            self.assertEqual(report["acceptance"]["physical_gpu_passthrough"], "not-established")
            self.assertTrue(all("--current" in call or call[-1] in
                                ("--vm", "--json", "-B", "qemu-guest-agent.service", "spice-vdagentd.service")
                                for call in calls))

    def test_unknown_host_and_missing_probes_are_not_invented(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = vm.collect(Path(temporary), {}, find=lambda _: None, machine="x86_64")
            self.assertEqual(report["virtualization"], "unknown")
            self.assertEqual(report["dmi"], {})
            self.assertEqual(report["graphics"], [])
            self.assertFalse(report["channels"]["spice"])
            self.assertNotIn("xrandr", report["probes"])
            self.assertEqual(report["host_operating_system"], "not-observable-from-guest")

    def test_wayland_display_scope_and_invalid_hardware_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = vm.collect(Path(temporary), {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"},
                                find=lambda name: "/fixture/" + name, run=lambda *a, **k: result("bad JSON"))
            self.assertEqual(report["virtualization"], "unknown")
            self.assertIn("unreadable", report["probes"]["graphics_error"])
            self.assertIn("Xwayland", report["probes"]["display_scope"])


if __name__ == "__main__":
    unittest.main()
