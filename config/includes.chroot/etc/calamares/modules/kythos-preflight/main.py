# SPDX-License-Identifier: MIT
"""Validate the supported installation path before native disk jobs run."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

import libcalamares


def pretty_name():
    return "Checking the KythOS Kernal installation plan."


def validate_choice(choice, firmware):
    if not isinstance(choice, dict) or choice.get("install") not in ("erase", "manual", "alongside", "replace"):
        raise ValueError("Choose an installation layout. No disk changes were made.")
    if choice.get("swap") not in ("none", "file", "small", "suspend"):
        raise ValueError("The swap selection is invalid. No disk changes were made.")
    if firmware not in ("efi", "bios"):
        raise ValueError("Unsupported firmware mode. No disk changes were made.")


def run():
    try:
        firmware = libcalamares.globalstorage.value("firmwareType")
        validate_choice(libcalamares.globalstorage.value("partitionChoices"), firmware)
        version = subprocess.check_output(["/usr/bin/dpkg-query", "-W", "-f=${Version}", "calamares"], text=True).strip()
        provenance = json.loads(Path("/usr/share/kythos/calamares-partition-provenance.json").read_text())
        plugin_dir = Path("/usr/lib/kythos/calamares/modules")
        if version != "3.3.14-1" or provenance.get("required_runtime_package_version") != version:
            raise ValueError("The native partition module and Calamares versions differ. No disk changes were made.")
        for relative in ("partition/libcalamares_viewmodule_partition.so", "partition/module.desc"):
            expected = provenance.get("files", {}).get(relative)
            if not expected or hashlib.sha256((plugin_dir / relative).read_bytes()).hexdigest() != expected:
                raise ValueError("The native partition validation module is incomplete. No disk changes were made.")
        username = libcalamares.globalstorage.value("username")
        if (not isinstance(username, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username)
                or username in ("root", "nobody", "kythos-live")):
            raise ValueError("Choose an ordinary administrator name. No disk changes were made.")
        if libcalamares.globalstorage.value("autoLoginUser") not in (None, "", username):
            raise ValueError("The automatic login account is inconsistent. No disk changes were made.")
        if firmware == "efi" and Path("/sys/firmware/efi/fw_platform_size").read_text().strip() != "64":
            raise ValueError("This graphical installer requires 64-bit UEFI. No disk changes were made.")
        source = Path("/run/live/medium/live/filesystem.squashfs")
        if not source.is_file():
            raise ValueError("The live system image is unavailable. No disk changes were made.")
        if not Path("/usr/share/kythos/installer-live-packages").is_file():
            raise ValueError("The installer package manifest is missing. No disk changes were made.")
        for program in ("grub-install", "update-initramfs", "cryptsetup", "rsync"):
            if not shutil.which(program):
                raise ValueError("Required installer software is unavailable. No disk changes were made.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return ("Installation plan requires attention", str(error))
    return None
