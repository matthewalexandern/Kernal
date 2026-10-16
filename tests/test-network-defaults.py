#!/usr/bin/python3
"""Check the actual keyfile parser offline; never contact the host NM daemon."""
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config/includes.chroot/etc/NetworkManager/system-connections/90-kythos-automatic-ethernet.nmconnection"
NMCLI = os.environ.get("KYTHOS_TEST_NMCLI") or shutil.which("nmcli")


@unittest.skipUnless(NMCLI, "Native nmcli is unavailable; mandatory offline validation also runs in the image build hook")
class NativeKeyfileTests(unittest.TestCase):
    def read_native(self, text):
        return subprocess.run([NMCLI, "--offline", "connection", "modify", "connection.autoconnect", "true"],
                              input=text, text=True, capture_output=True, timeout=15)

    def test_native_parser_accepts_simultaneous_dhcp_profile_without_hardware_binding(self):
        result = self.read_native(PROFILE.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = configparser.ConfigParser(interpolation=None)
        parsed.read_string(result.stdout)
        self.assertEqual(parsed["connection"]["type"], "ethernet")
        self.assertEqual(parsed["connection"].getint("multi-connect"), 3)
        self.assertEqual(parsed["connection"].getint("autoconnect-priority"), -999)
        self.assertEqual(parsed["ipv4"]["method"], "auto")
        self.assertEqual(parsed["ipv6"]["method"], "auto")
        self.assertNotIn("interface-name", parsed["connection"])
        self.assertNotIn("mac-address", parsed["ethernet"])
        self.assertEqual(set(parsed["match"]["driver"].rstrip(";").split(";")), {"!veth", "!tun"})

    def test_native_parser_rejects_invalid_multi_connect_value(self):
        result = self.read_native(PROFILE.read_text().replace("multi-connect=3", "multi-connect=99"))
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
