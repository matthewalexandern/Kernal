#!/usr/bin/env python3
"""Bounded tests for the installer's disk-write and target-cleanup boundaries."""
from copy import deepcopy
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import stat
import sys
sys.dont_write_bytecode = True
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHROOT = ROOT / "config/includes.chroot"
MODULES = CHROOT / "etc/calamares/modules"
LIBEXEC = CHROOT / "usr/local/libexec"
sys.modules.setdefault("libcalamares", types.SimpleNamespace())


def module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    result = importlib.util.module_from_spec(spec)
    loader.exec_module(result)
    return result


preflight = module("kythos_preflight", MODULES / "kythos-preflight/main.py")
storage = module("kythos_storage", MODULES / "kythos-storage/main.py")
grub = module("kythos_grub", LIBEXEC / "kythos-calamares-grub-install")
target = module("kythos_target", LIBEXEC / "kythos-calamares-target")
stage = module("kythos_target_stage", MODULES / "kythos-target/main.py")


class PlanTests(unittest.TestCase):
    def test_all_native_partition_and_swap_choices_remain_available(self):
        for firmware in ("bios", "efi"):
            for install in ("erase", "manual", "alongside", "replace"):
                for swap in ("none", "file", "small", "suspend"):
                    preflight.validate_choice({"install": install, "swap": swap}, firmware)
        for choice in (None, {}, {"install": "invalid", "swap": "none"},
                       {"install": "erase", "swap": "invalid"}):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                preflight.validate_choice(choice, "efi")

    def test_rejected_choice_never_reaches_any_target_or_program_call(self):
        values = {"partitionChoices": {"install": "invalid", "swap": "file"}, "firmwareType": "efi"}
        api = types.SimpleNamespace(globalstorage=types.SimpleNamespace(value=values.get))
        with patch.object(preflight, "libcalamares", api), patch.object(preflight.shutil, "which") as program:
            result = preflight.run()
        self.assertIn("No disk changes were made", result[1])
        program.assert_not_called()


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.partitions = [
            {"mountPoint": "/boot/efi", "fs": "fat32", "claimed": True},
            {"mountPoint": "/boot", "fs": "ext4", "claimed": True},
            {"mountPoint": "/", "fs": "ext4", "claimed": True,
             "luksMapperName": "luks-root", "luksUuid": "8bba8ee0-153f-4d65-af3c-96d701ba76df",
             "luksPassphrase": "SENSITIVE_TEST_VALUE_DO_NOT_COPY"},
        ]

    def test_encrypted_result_does_not_export_the_passphrase(self):
        result = storage.topology(self.partitions, "efi")
        self.assertTrue(result["encrypted"])
        self.assertNotIn("SENSITIVE_TEST_VALUE", json.dumps(result))
        self.assertEqual(result["crypt_mappings"][0]["name"], "luks-root")
        self.assertTrue(result["crypt_mappings"][0]["early"])

    def test_plain_bios_and_foreign_swap(self):
        self.partitions[-1] = {"mountPoint": "/", "fs": "ext4", "claimed": True}
        self.partitions.append({"mountPoint": "", "fs": "linuxswap", "claimed": False})
        result = storage.topology(self.partitions[1:], "bios")
        self.assertFalse(result["encrypted"])
        self.assertEqual(result["crypt_mappings"], [])

    def test_plain_manual_root_can_contain_boot_and_choose_filesystem(self):
        result = storage.topology([{"mountPoint": "/", "fs": "btrfs", "claimed": True}], "bios")
        self.assertFalse(result["encrypted"])
        self.assertEqual(result["root_filesystem"], "btrfs")

    def test_encrypted_lvm_backing_is_reconciled_without_any_passphrase(self):
        pv = {"mountPoint": "", "fs": "lvm2 pv", "claimed": True,
              "kythosBackingIdentity": "/dev/vda:123456", "luksMapperName": "luks-pv",
              "luksUuid": "8bba8ee0-153f-4d65-af3c-96d701ba76df", "luksPassphrase": "SENSITIVE"}
        root = {"mountPoint": "/", "fs": "ext4", "claimed": True}
        result = storage.topology([self.partitions[0], self.partitions[1], root, pv], "efi", ["/dev/vda:123456"], True)
        self.assertTrue(result["encrypted"])
        self.assertTrue(result["root_requires_crypto"])
        self.assertEqual(result["crypt_mappings"], [{"name": "luks-pv", "uuid": pv["luksUuid"], "early": True}])
        self.assertNotIn("SENSITIVE", json.dumps(result))

    def test_native_encrypted_swap_partition_is_supported(self):
        swap = {"mountPoint": "", "fs": "linuxswap", "claimed": True,
                "luksMapperName": "luks-swap", "luksUuid": "8bba8ee0-153f-4d65-af3c-96d701ba76df"}
        result = storage.topology(self.partitions + [swap], "efi")
        self.assertIn("/dev/mapper/luks-swap", result["swap_devices"])
        self.assertTrue(next(mapping for mapping in result["crypt_mappings"] if mapping["name"] == "luks-swap")["early"])

    def test_rejects_encrypted_boot_missing_boot_plaintext_swap_and_invalid_efi(self):
        cases = []
        encrypted_boot = deepcopy(self.partitions)
        encrypted_boot[1]["luksMapperName"] = "bad-boot"
        cases.append(encrypted_boot)
        cases.append([self.partitions[0], self.partitions[2]])
        cases.append(self.partitions + [{"fs": "linuxswap", "mountPoint": "", "claimed": True}])
        bad_efi = deepcopy(self.partitions)
        bad_efi[0]["fs"] = "ext4"
        cases.append(bad_efi)
        bad_mapping = deepcopy(self.partitions)
        bad_mapping[2]["luksMapperName"] = "$(bad)"
        cases.append(bad_mapping)
        for partitions in cases:
            with self.subTest(partitions=partitions), self.assertRaises(ValueError):
                storage.topology(partitions, "efi")


class SignedBootTests(unittest.TestCase):
    def test_native_bios_no_bootloader_choice_is_preserved(self):
        self.assertFalse(stage.bootloader_requested("bios", None))
        self.assertFalse(stage.bootloader_requested("bios", {"installPath": None}))
        self.assertTrue(stage.bootloader_requested("bios", {"installPath": "/dev/vda"}))
        self.assertTrue(stage.bootloader_requested("efi", None))

    def test_efi_installs_signed_shim_in_both_paths(self):
        arguments = grub.grub_arguments(["--target=x86_64-efi", "--efi-directory=/boot/efi",
                                          "--bootloader-id=kythos", "--force"])
        self.assertIn("--uefi-secure-boot", arguments)
        self.assertIn("--force-extra-removable", arguments)
        self.assertNotIn("--force", arguments)

    def test_bios_never_forces_blocklist_installation(self):
        self.assertEqual(grub.grub_arguments(["--target=i386-pc", "--recheck", "--force", "/dev/nvme0n1"]),
                         ["--target=i386-pc", "--recheck", "/dev/nvme0n1"])

    def test_no_arbitrary_boot_options_or_paths(self):
        for args in (["--target=x86_64-efi", "--no-uefi-secure-boot"],
                     ["--target=i386-pc", "--recheck", "--force", "--no-nvram"],
                     ["--target=i386-pc", "--recheck", "--force", "/dev/../etc/passwd"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                grub.grub_arguments(args)


class TargetTests(unittest.TestCase):
    def test_refuses_running_host_context_before_any_file_mutation(self):
        identity = types.SimpleNamespace(st_dev=1, st_ino=2)
        with patch.object(target.os, "geteuid", return_value=0), patch.object(target.os, "stat", return_value=identity):
            with self.assertRaisesRegex(ValueError, "outside the mounted installer target"):
                target.verify_chroot_context()

    def test_crypttab_root_is_prompted_and_included_in_initramfs(self):
        uuid = "8bba8ee0-153f-4d65-af3c-96d701ba76df"
        data = {"encrypted": True, "crypt_mappings": [{"name": "luks-root", "uuid": uuid, "early": True}]}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "crypttab"
            path.write_text("# generated\nluks-root UUID=" + uuid + " none\n")
            target.configure_crypttab(data, path)
            self.assertIn("none\tluks,initramfs", path.read_text())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            path.write_text("luks-root UUID=" + uuid + " /crypto_keyfile.bin luks\n")
            with self.assertRaises(ValueError):
                target.configure_crypttab(data, path)

    def test_no_plaintext_key_or_protected_package_can_be_removed(self):
        for package in ("sudo", "linux-image-6.12.0-amd64", "linux-headers-amd64", "firmware-nvidia-graphics",
                        "grub2-common", "grub-efi-amd64-signed", "shim-signed", "auditd", "python3.13-minimal",
                        "nftables", "openssh-server", "cryptsetup-initramfs", "network-manager"):
            self.assertTrue(target.protected_package(package), package)
            with self.assertRaises(ValueError):
                target.removal_plan_packages("Purg " + package + " [1.0]")
        self.assertEqual(target.removal_plan_packages("Purg calamares [3.3.14]\nRemv openbox [3.6]\n"),
                         ["calamares", "openbox"])

    def test_python_embedding_library_can_be_removed_but_runtime_cannot(self):
        for package in ("libpython3.13", "libpython3.13:amd64"):
            self.assertFalse(target.protected_package(package), package)
            self.assertEqual(target.removal_plan_packages("Purg " + package + " [3.13]\n"), [package])
        for package in ("libpython3-stdlib", "libpython3.13-stdlib", "libpython3.13-minimal",
                        "libpython3.13-minimal:amd64", "python3-minimal", "python3.13-minimal"):
            self.assertTrue(target.protected_package(package), package)
            with self.assertRaises(ValueError):
                target.removal_plan_packages("Purg " + package + " [3.13]\n")

    def test_local_automatic_login_is_optional_and_off_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "getty@tty1.service.d/autologin.conf"
            data = {"username": "alice", "autologin": False}
            target.configure_autologin(data, path)
            self.assertFalse(path.exists())
            target.verify_autologin(data, path)
            data["autologin"] = True
            target.configure_autologin(data, path)
            self.assertEqual(path.read_text(), target.autologin_contents("alice"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            metadata = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
            with patch.object(Path, "lstat", return_value=metadata):
                target.verify_autologin(data, path)
            data["autologin"] = False
            with self.assertRaises(ValueError):
                target.verify_autologin(data, path)
            target.configure_autologin(data, path)
            self.assertFalse(path.exists())

    def test_local_automatic_login_cannot_inject_a_service_or_use_root(self):
        for username in ("root", "nobody", "kythos-live", "--root", "alice\nExecStart=/bin/false", "$(bad)"):
            with self.subTest(username=username), self.assertRaises(ValueError):
                target.autologin_contents(username)

    def test_native_sequence_and_auth_configuration(self):
        import yaml
        settings = yaml.safe_load((CHROOT / "etc/calamares/settings.conf").read_text())
        jobs = next(step["exec"] for step in settings["sequence"] if "exec" in step)
        self.assertLess(jobs.index("kythos-preflight"), jobs.index("partition"))
        self.assertLess(jobs.index("kythos-target"), jobs.index("initramfs"))
        self.assertLess(jobs.index("initramfs"), jobs.index("bootloader"))
        self.assertLess(jobs.index("bootloader"), jobs.index("kythos-verify"))
        self.assertNotIn("luksbootkeyfile", jobs)
        users = yaml.safe_load((MODULES / "users.conf").read_text())
        self.assertFalse(users["setRootPassword"])
        self.assertEqual(users["passwordRequirements"], {"minLength": 1, "maxLength": -1})
        boot = yaml.safe_load((MODULES / "bootloader.conf").read_text())
        self.assertFalse(boot["installEFIFallback"])
        partition = yaml.safe_load((MODULES / "partition.conf").read_text())
        self.assertTrue(partition["allowManualPartitioning"])
        boot_layout = next(item for item in partition["partitionLayout"] if item["mountPoint"] == "/boot")
        self.assertEqual(boot_layout["minSize"], "1G")
        self.assertNotIn("maxSize", boot_layout)


if __name__ == "__main__":
    unittest.main()
