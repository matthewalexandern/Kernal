#!/usr/bin/python3
"""Read-only sysfs fixtures and bounded subprocess tests; never touch a device."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "config/includes.chroot/usr/local/bin/kythos-hardware-status"
loader = importlib.machinery.SourceFileLoader("kythos_hardware", str(TOOL))
spec = importlib.util.spec_from_loader(loader.name, loader)
hardware = importlib.util.module_from_spec(spec)
loader.exec_module(hardware)


def put(root, relative, value):
    path = root / relative.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return path


def bind(root, device, driver_name, module_name):
    device.mkdir(parents=True, exist_ok=True)
    driver = root / "sys/test-drivers" / driver_name
    driver.mkdir(parents=True, exist_ok=True)
    (device / "driver").symlink_to(driver)
    if module_name and not (driver / "module").exists():
        module = root / "sys/module" / module_name
        module.mkdir(parents=True, exist_ok=True)
        (driver / "module").symlink_to(module)


class HardwareFixtures(unittest.TestCase):
    def test_transport_drm_nic_storage_and_unbound_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root, "/proc/sys/kernel/osrelease", "6.12-test\n")
            pci = root / "sys/bus/pci/devices/0000:00:02.0"
            put(root, str(pci.relative_to(root) / "class"), "0x030000")
            put(root, str(pci.relative_to(root) / "vendor"), "0x1af4")
            put(root, str(pci.relative_to(root) / "device"), "0x1050")
            bind(root, pci, "virtio-pci", "virtio_pci")
            actual_gpu = root / "sys/devices/virtio0"
            bind(root, actual_gpu, "virtio_gpu", "virtio_gpu")
            card = root / "sys/class/drm/card0"
            card.mkdir(parents=True)
            (card / "device").symlink_to(actual_gpu)
            nic = root / "sys/bus/pci/devices/0000:01:00.0"
            put(root, str(nic.relative_to(root) / "class"), "0x020000")
            put(root, str(nic.relative_to(root) / "vendor"), "0x10ec")
            put(root, str(nic.relative_to(root) / "device"), "0x8168")
            put(root, str(nic.relative_to(root) / "modalias"), "pci:v000010ECd00008168")
            actual_nic = root / "sys/devices/virtio1"
            bind(root, actual_nic, "virtio_net", "virtio_net")
            net = root / "sys/class/net/ens3"
            put(root, str(net.relative_to(root) / "operstate"), "up")
            (net / "device").symlink_to(actual_nic)
            controller = root / "sys/devices/virtio2"
            bind(root, controller, "virtio_blk", "virtio_blk")
            disk = root / "sys/block/vda"
            disk.mkdir(parents=True)
            (disk / "device").symlink_to(controller)
            calls = []

            def runner(arguments, timeout):
                calls.append(arguments)
                if arguments[0] == "/usr/sbin/modprobe":
                    self.assertEqual(arguments[1], "--resolve-alias")
                    return 0, "r8169\nbad;name\n", ""
                self.assertEqual(arguments[0], "/usr/bin/journalctl")
                return 0, "Kernel started without firmware failures.\n", ""

            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            report = hardware.collect_hardware(root, runner)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(report["pci"][0]["driver"], "virtio-pci")
            self.assertEqual(report["graphics"][0]["driver"], "virtio_gpu")
            self.assertEqual(report["graphics"][0]["module"], "virtio_gpu")
            self.assertEqual(report["network"][0]["driver"], "virtio_net")
            self.assertEqual(report["storage"][0]["driver"], "virtio_blk")
            self.assertEqual(report["pci"][1]["status"], "unbound")
            self.assertEqual(report["pci"][1]["candidate_modules"], ["r8169"])
            self.assertEqual(report["summary"]["relevant_unbound"], 1)
            self.assertEqual(len([args for args in calls if args[0] == "/usr/sbin/modprobe"]), 1)
            self.assertIn("not proof", report["note"])

    def test_unreadable_journal_and_no_alias_match_stay_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "sys/bus/pci/devices/0000:01:00.0"
            put(root, str(device.relative_to(root) / "class"), "0x020000")
            put(root, str(device.relative_to(root) / "modalias"), "pci:v000010ECd00008168")
            calls = []

            def runner(arguments, timeout):
                calls.append(arguments)
                return 1, "", "Permission denied or no module index"

            report = hardware.collect_hardware(root, runner)
            self.assertEqual(report["firmware"]["status"], "unavailable")
            self.assertEqual(report["firmware"]["possible_failures"], [])
            self.assertEqual(report["pci"][0]["alias_probe"], "unavailable")
            self.assertEqual(report["pci"][0]["candidate_modules"], [])
            self.assertTrue(all(args[0] != "/usr/sbin/modprobe" or args[1] == "--resolve-alias" for args in calls))

    def test_firmware_failures_are_bounded_observations_and_nvidia_reuses_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root, "/proc/sys/kernel/osrelease", "6.12-test")
            (root / "lib/modules/6.12-test/build").mkdir(parents=True)
            gpu = root / "sys/bus/pci/devices/0000:01:00.0"
            for name, value in (("class", "0x030000"), ("vendor", "0x10de"), ("device", "0x1234")):
                put(root, str(gpu.relative_to(root) / name), value)
            bind(root, gpu, "nouveau", "nouveau")

            def runner(arguments, timeout):
                if arguments[0] == "/usr/local/sbin/kythos-nvidia-readiness":
                    return 0, "KythOS NVIDIA readiness\nNVIDIA kernel module not installed\n", ""
                self.assertEqual(arguments[0], "/usr/bin/journalctl")
                return 0, "\n".join(f"driver firmware missing file {number}" for number in range(40)) + "\nfirmware loaded later", ""

            report = hardware.collect_hardware(root, runner)
            self.assertEqual(report["nvidia"]["drivers"], ["nouveau"])
            self.assertTrue(report["nvidia"]["matching_headers"])
            self.assertIn("not installed", report["nvidia"]["details"])
            self.assertEqual(report["firmware"]["status"], "possible-issues")
            self.assertEqual(len(report["firmware"]["possible_failures"]), 25)
            self.assertIn("recovered", report["firmware"]["scope"])
            self.assertIn("Firmware journal", hardware.format_report(report))

    def test_invalid_alias_never_reaches_a_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root, "/sys/bus/pci/devices/0000:01:00.0/class", "0x020000")
            put(root, "/sys/bus/pci/devices/0000:01:00.0/modalias", "--config /tmp/evil")
            calls = []

            def runner(arguments, timeout):
                calls.append(arguments)
                return 0, "Kernel started", ""

            report = hardware.collect_hardware(root, runner)
            self.assertEqual(report["pci"][0]["alias_probe"], "not-checked")
            self.assertFalse(any(args[0] == "/usr/sbin/modprobe" for args in calls))

    def test_usb_ids_and_vendor_specific_module_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root, "/sys/bus/usb/devices/1-2/idVendor", "0bda")
            put(root, "/sys/bus/usb/devices/1-2/idProduct", "c82c")
            put(root, "/sys/bus/usb/devices/1-2:1.0/bInterfaceClass", "ff")
            put(root, "/sys/bus/usb/devices/1-2:1.0/modalias", "usb:v0BDApC82Cd0100")

            def runner(arguments, timeout):
                if arguments[0] == "/usr/sbin/modprobe":
                    self.assertEqual(arguments[1:], ["--resolve-alias", "usb:v0BDApC82Cd0100"])
                    return 0, "rtw88_8822cu\n", ""
                return 1, "", "Journal unavailable"

            report = hardware.collect_hardware(root, runner)
            self.assertEqual(report["usb"][0]["id"], "0bda:c82c")
            self.assertEqual(report["usb"][0]["kind"], "vendor-specific")
            self.assertEqual(report["usb"][0]["candidate_modules"], ["rtw88_8822cu"])

    def test_many_unbound_devices_do_not_spawn_unbounded_probes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for number in range(20):
                prefix = f"/sys/bus/pci/devices/0000:00:{number:02x}.0"
                put(root, prefix + "/class", "0x020000")
                put(root, prefix + "/modalias", f"pci:v00001234d{number:08X}")
            calls = []

            def runner(arguments, timeout):
                if arguments[0] == "/usr/sbin/modprobe":
                    calls.append(arguments)
                return 0, "candidate\n", ""

            report = hardware.collect_hardware(root, runner)
            self.assertEqual(len(calls), 16)
            self.assertEqual(sum(d["alias_probe"] == "not-checked" for d in report["pci"]), 4)


class ProbeBoundaries(unittest.TestCase):
    def test_timeout_terminates_only_the_probe_group(self):
        class Process:
            pid = 12345
            calls = 0

            def communicate(self, timeout):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired("fixed-read-only-probe", timeout)
                return "", ""

        process = Process()
        with patch.object(hardware.subprocess, "Popen", return_value=process) as popen, \
                patch.object(hardware.os, "killpg") as kill:
            result = hardware.run_readonly(["/usr/bin/journalctl", "--boot"], 1)
        self.assertIsNone(result[0])
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_probe_output_is_bounded(self):
        class Process:
            returncode = 0

            def communicate(self, timeout):
                return "x" * 200000, "e" * 5000

        with patch.object(hardware.subprocess, "Popen", return_value=Process()):
            code, output, error = hardware.run_readonly(["/usr/bin/journalctl", "--boot"], 1)
        self.assertEqual(code, 0)
        self.assertEqual(len(output), 131072)
        self.assertEqual(len(error), 2048)

    def test_cli_rejects_non_readonly_options(self):
        result = subprocess.run([sys.executable, TOOL, "--install-drivers"], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
