#!/usr/bin/python3
"""Check both architecture selections without executing foreign binaries."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "config/includes.chroot/usr/local/libexec/kythos-architecture"


def profile(architecture):
    return json.loads(subprocess.check_output([str(TOOL), "--arch", architecture], text=True))


class ArchitectureTests(unittest.TestCase):
    def test_amd64_preserves_stock_kernel_microcode_and_both_boot_platforms(self):
        selected = profile("amd64")
        self.assertEqual(selected["bootloaders"], "syslinux,grub-efi")
        self.assertEqual(selected["efi_target"], "x86_64-efi")
        self.assertEqual(selected["bios_target"], "i386-pc")
        self.assertEqual(set(selected["packages"]), {
            "linux-image-amd64", "linux-headers-amd64", "amd64-microcode", "intel-microcode",
            "fwupd-amd64-signed", "grub-pc-bin", "grub-efi-amd64-bin",
            "grub-efi-amd64-signed", "shim-signed"})

    def test_arm64_has_aa64_uefi_and_native_stock_kernel(self):
        selected = profile("arm64")
        self.assertEqual(selected["bootloaders"], "grub-efi")
        self.assertEqual(selected["efi_target"], "arm64-efi")
        self.assertEqual(selected["efi_suffix"], "aa64")
        self.assertIsNone(selected["bios_target"])
        self.assertEqual(set(selected["packages"]), {"linux-image-arm64", "linux-headers-arm64",
            "fwupd-arm64-signed", "grub-efi-arm64-bin", "grub-efi-arm64-signed", "shim-signed"})

    def test_live_build_receives_the_selected_profile_and_default_is_amd64(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stub = directory / "lb"
            stub.write_text("#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ['KYTHOS_CAPTURE'],'w').write(json.dumps(sys.argv[1:]))\n")
            stub.chmod(0o755)
            for architecture in (None, "amd64", "arm64"):
                environment = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ["PATH"],
                                   KYTHOS_CAPTURE=str(directory / "arguments"))
                environment.pop("KYTHOS_ARCH", None)
                if architecture:
                    environment["KYTHOS_ARCH"] = architecture
                subprocess.run([str(ROOT / "auto/config")], env=environment, check=True, capture_output=True)
                arguments = json.loads((directory / "arguments").read_text())
                selected = profile(architecture or "amd64")
                for option, expected in (("--architecture", selected["architecture"]),
                                         ("--linux-flavours", selected["kernel_flavour"]),
                                         ("--bootloaders", selected["bootloaders"])):
                    self.assertEqual(arguments[arguments.index(option) + 1], expected)
                self.assertEqual(arguments[arguments.index("--uefi-secure-boot") + 1], "enable")
                self.assertEqual(arguments[arguments.index("--source") + 1], "true")

    def test_foreign_names_and_user_config_overrides_are_rejected(self):
        self.assertNotEqual(subprocess.run([str(TOOL), "--arch", "x86_64"], capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run([str(ROOT / "auto/config"), "--architecture", "arm64"],
                                          capture_output=True).returncode, 0)

    def test_package_roots_share_common_console_and_manual_tools(self):
        roots = set()
        for file in (ROOT / "config/package-lists").glob("*.list.chroot_install"):
            roots.update(line.strip().split()[0] for line in file.read_text().splitlines()
                         if line.strip() and not line.lstrip().startswith(("#", "!")))
        self.assertTrue({"bash-completion", "man-db", "manpages", "tmux"}.issubset(roots))
        for architecture in ("amd64", "arm64"):
            self.assertFalse(roots & set(profile(architecture)["packages"]))


if __name__ == "__main__":
    unittest.main()
