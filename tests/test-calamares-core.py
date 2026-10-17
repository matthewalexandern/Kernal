#!/usr/bin/env python3
"""Bounded tests for the installer's disk-write and target-cleanup boundaries."""
from copy import deepcopy
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
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
    def test_edition_boot_keeps_base_console_and_explicitly_enables_desktop(self):
        for selected in ('multi-user.target', 'graphical.target'):
            with self.subTest(selected=selected), patch.object(target, 'installed_boot_target', return_value=selected), \
                    patch.object(target, 'command') as commands:
                target.configure_edition_boot()
                expected = ([['/usr/bin/systemctl', 'enable', 'lightdm.service']]
                            if selected == 'graphical.target' else [])
                expected.append(['/usr/bin/systemctl', 'set-default', selected])
                self.assertEqual([call.args[0] for call in commands.call_args_list], expected)

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
                                          "--bootloader-id=kythos", "--force"], architecture="amd64")
        self.assertIn("--uefi-secure-boot", arguments)
        self.assertIn("--force-extra-removable", arguments)
        self.assertNotIn("--force", arguments)

    def test_bios_never_forces_blocklist_installation(self):
        self.assertEqual(grub.grub_arguments(["--target=i386-pc", "--recheck", "--force", "/dev/nvme0n1"], architecture="amd64"),
                         ["--target=i386-pc", "--recheck", "/dev/nvme0n1"])

    def test_no_arbitrary_boot_options_or_paths(self):
        for args in (["--target=x86_64-efi", "--no-uefi-secure-boot"],
                     ["--target=i386-pc", "--recheck", "--force", "--no-nvram"],
                     ["--target=i386-pc", "--recheck", "--force", "/dev/../etc/passwd"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                grub.grub_arguments(args, architecture="amd64")

    def test_arm64_uses_signed_aa64_chain_and_rejects_bios(self):
        arguments = grub.grub_arguments(["--target=arm64-efi", "--efi-directory=/boot/efi",
                                          "--bootloader-id=kythos", "--force"], architecture="arm64")
        self.assertEqual(arguments[0], "--target=arm64-efi")
        self.assertIn("--uefi-secure-boot", arguments)
        self.assertIn("--force-extra-removable", arguments)
        for invalid in (["--target=i386-pc", "--recheck", "--force", "/dev/vda"],
                        ["--target=x86_64-efi", "--efi-directory=/boot/efi", "--bootloader-id=kythos", "--force"]):
            with self.assertRaises(ValueError):
                grub.grub_arguments(invalid, architecture="arm64")


class TargetTests(unittest.TestCase):
    def test_live_purge_finds_native_manifest_name_with_qualified_dpkg_status(self):
        calls = []

        def command(arguments, capture=False):
            calls.append(arguments)
            if arguments[:2] == ["/usr/bin/dpkg-query", "-W"]:
                return "qml6-module-qtqml-workerscript:" + target.ARCHITECTURE["architecture"] + "\tinstalled\n"
            if arguments[:3] == ["/usr/bin/apt-get", "-s", "-y"]:
                return "Purg qml6-module-qtqml-workerscript:" + target.ARCHITECTURE["architecture"] + " [6.8.2]\n"
            if arguments[:3] == ["/usr/bin/apt-get", "-y", "--no-install-recommends"]:
                return None
            raise AssertionError("Unexpected package command: " + repr(arguments))

        with patch.object(target, "manifest_packages",
                          return_value=["qml6-module-qtqml-workerscript"]), \
                patch.object(target, "command", side_effect=command):
            target.purge_live_packages()

        self.assertEqual(
            calls[-1],
            ["/usr/bin/apt-get", "-y", "--no-install-recommends", "purge", "--",
             "qml6-module-qtqml-workerscript"],
        )

    def test_actual_calamares_boolean_roundtrip_reaches_strict_receipt_reader(self):
        # The real 3.3.14 QVariant bridge stores Python bools as integer 0/1.
        # Exercise the producer, API representation, file writer and consumer.
        def variant_roundtrip(value):
            if type(value) is bool:
                return int(value)
            if isinstance(value, list):
                return [variant_roundtrip(item) for item in value]
            if isinstance(value, dict):
                return {key: variant_roundtrip(item) for key, item in value.items()}
            return value

        firmwares = ("efi", "bios") if target.ARCHITECTURE["bios_target"] else ("efi",)
        for firmware in firmwares:
            for encrypted in (False, True):
                with self.subTest(firmware=firmware, encrypted=encrypted), tempfile.TemporaryDirectory() as temporary:
                    root = {"mountPoint": "/", "fs": "ext4", "claimed": True}
                    if encrypted:
                        root.update(luksMapperName="luks-root", luksUuid="8bba8ee0-153f-4d65-af3c-96d701ba76df")
                    partitions = [{"mountPoint": "/boot", "fs": "ext4", "claimed": True}, root]
                    if firmware == "efi":
                        partitions.insert(0, {"mountPoint": "/boot/efi", "fs": "fat32", "claimed": True})
                    topology = variant_roundtrip(dict(storage.topology(partitions, firmware), swap="file"))
                    values = {"rootMountPoint": temporary, "kythosStorage": topology,
                              "username": "tester", "autoLoginUser": None,
                              "bootLoader": {"installPath": "/dev/vda"}}
                    receipts = []

                    def target_call(arguments):
                        self.assertEqual(arguments, ["/usr/local/libexec/kythos-calamares-target", "configure"])
                        metadata = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
                        with patch.object(target, "STATE_DIR", Path(temporary) / "var/lib/kythos"), \
                                patch.object(Path, "lstat", return_value=metadata):
                            receipts.append(target.read_topology())

                    api = types.SimpleNamespace(globalstorage=types.SimpleNamespace(value=values.get),
                                                utils=types.SimpleNamespace(check_target_env_call=target_call))
                    with patch.object(stage, "libcalamares", api):
                        self.assertIsNone(stage.run())
                    self.assertEqual(len(receipts), 1)
                    self.assertEqual(receipts[0]["firmware"], firmware)
                    self.assertIs(receipts[0]["encrypted"], encrypted)
                    self.assertIs(receipts[0]["root_requires_crypto"], encrypted)
                    if encrypted:
                        self.assertIs(receipts[0]["crypt_mappings"][0]["early"], True)
                    self.assertEqual(type(topology["encrypted"]), int)  # GS was not mutated.

    def test_receipt_boolean_normalization_rejects_other_values(self):
        for value in (None, "true", "0", 2, -1, [], {}, 0.0, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                stage.storage_boolean(value)

    def test_only_the_fixed_finalizer_diagnostic_is_presented(self):
        error = subprocess.CalledProcessError(1, "fixed command", output=(
            "SENSITIVE_TEST_VALUE_DO_NOT_SHOW\n"
            "KythOS Kernal target finalization failed: Invalid installer storage receipt.\n"))
        self.assertEqual(stage.finalizer_error(error),
                         "KythOS Kernal target finalization failed: Invalid installer storage receipt.")
        error.output = "SENSITIVE_TEST_VALUE_DO_NOT_SHOW"
        self.assertEqual(stage.finalizer_error(error), "The target configuration command failed (exit status 1).")

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
        self.assertFalse(partition["showNotEncryptedBootMessage"])
        locale = yaml.safe_load((MODULES / "locale.conf").read_text())
        self.assertEqual((locale["region"], locale["zone"]), ("Atlantic", "Reykjavik"))
        self.assertFalse(locale["useSystemTimezone"])


class InstalledAptTests(unittest.TestCase):
    def sources(self, directory, name, contents):
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def test_actual_live_build_source_becomes_signed_online_sources_without_rewriting_them(self):
        live = "deb [trusted=yes] file:/run/live/medium trixie main contrib non-free non-free-firmware\n"
        online = ("deb https://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware\n"
                  "#deb-src https://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware\n"
                  "deb https://security.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware\n"
                  "deb https://deb.debian.org/debian/ trixie-updates main contrib non-free non-free-firmware\n")
        with tempfile.TemporaryDirectory() as directory:
            path = self.sources(directory, "sources.list", live + online)
            path.chmod(0o640)
            with self.assertRaisesRegex(ValueError, "active live-media"):
                target.verify_installed_apt_sources(Path(directory))
            target.configure_installed_apt_sources(Path(directory))
            self.assertEqual(path.read_text(), online)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            target.verify_installed_apt_sources(Path(directory))
            before = path.stat().st_ino
            target.configure_installed_apt_sources(Path(directory))
            self.assertEqual(path.stat().st_ino, before)  # A second run makes no edits.

    def test_only_live_boot_mounts_are_removed_from_one_line_sources(self):
        remove = ("deb-src [arch=amd64 signed-by=/keys/live.gpg] file:///run/live/medium/debian trixie main\n"
                  "deb file://localhost/lib/live/mount/medium trixie main\n"
                  "deb file:/run/live/%6dedium/./pool trixie main\n")
        preserve = ("# deb file:/run/live/medium trixie main\n"
                    "deb [signed-by=/keys/vendor.gpg] https://example.test/run/live/medium stable main # vendor\n"
                    "deb file:/run/live/medium-backup trixie main\n"
                    "deb file:/srv/local-repository ./\n"
                    "deb file://repository-host/run/live/medium trixie main\n"
                    "deb cdrom:[KythOS installer]/ trixie main\n"
                    "unknown-source /run/live/medium kept-as-is\n")
        self.assertEqual(target.installed_apt_list(remove + preserve), preserve)

    def test_mixed_deb822_retains_online_uris_signing_keys_comments_and_unknown_fields(self):
        before = ("# vendor and installer share suite settings\r\n"
                  "Types: deb deb-src\r\n"
                  "URIs: file:/run/live/medium https://deb.debian.org/debian/\r\n"
                  " https://mirror.example.test/debian/\r\n"
                  " file:///lib/live/mount/medium/pool\r\n"
                  "# retained comment between fields\r\n"
                  "Suites: trixie trixie-updates\r\n"
                  "Components: main non-free-firmware\r\n"
                  "X-Vendor-Note: keep this exactly\r\n"
                  "Signed-By:\r\n"
                  " -----BEGIN PGP PUBLIC KEY BLOCK-----\r\n"
                  " .\r\n"
                  " retained-key-material\r\n"
                  " -----END PGP PUBLIC KEY BLOCK-----\r\n")
        expected = before.replace("URIs: file:/run/live/medium https://", "URIs: https://").replace(
            " file:///lib/live/mount/medium/pool\r\n", "")
        self.assertEqual(target.installed_apt_deb822(before), expected)

    def test_deb822_live_only_stanzas_are_removed_and_disabled_stanzas_preserved(self):
        live = "# old installation source\nTypes: deb\nURIs: file:/run/live/medium\nSuites: trixie\nComponents: main\n"
        disabled = "Types: deb\nURIs: file:/run/live/medium\nEnabled:\n no\nSuites: trixie\nComponents: main\n"
        online = "Types: deb\nURIs:\n https://security.debian.org/debian-security/\nSuites: trixie-security\nComponents: main\n"
        self.assertEqual(target.installed_apt_deb822(live + "\n" + disabled + "\n" + online),
                         "# old installation source\n\n" + disabled + "\n" + online)
        mixed = "Types: deb\nURIs: file:/run/live/medium\n https://deb.debian.org/debian/\nSuites: trixie\nComponents: main\n"
        self.assertEqual(target.installed_apt_deb822(mixed), mixed.replace("URIs: file:/run/live/medium", "URIs:"))

    def test_ambiguous_deb822_prevents_all_edits_instead_of_losing_unknown_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.sources(directory, "sources.list", "deb file:/run/live/medium trixie main\n")
            contents = "Types: deb\nURIs: file:/run/live/medium\nURIs: https://example.test/debian\nSuites: trixie\nComponents: main\n"
            other = self.sources(directory, "sources.list.d/vendor.sources", contents)
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                target.configure_installed_apt_sources(Path(directory))
            self.assertIn("file:/run/live/medium", first.read_text())
            self.assertEqual(other.read_text(), contents)

    def test_unknown_files_and_online_symlinks_stay_untouched_and_live_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disabled = self.sources(root, "sources.list.d/vendor.list.disabled", "deb file:/run/live/medium trixie main\n")
            online = self.sources(root, "vendor-original", "deb [signed-by=/key.gpg] https://example.test/ stable main\n")
            link = root / "sources.list.d/vendor.list"
            link.symlink_to(online)
            target.configure_installed_apt_sources(root)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.read_bytes(), online.read_bytes())
            self.assertIn("file:/run/live/medium", disabled.read_text())
            online.write_text("deb file:/run/live/medium trixie main\n")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                target.configure_installed_apt_sources(root)
            self.assertTrue(link.is_symlink())
            self.assertIn("file:/run/live/medium", online.read_text())


if __name__ == "__main__":
    unittest.main()
