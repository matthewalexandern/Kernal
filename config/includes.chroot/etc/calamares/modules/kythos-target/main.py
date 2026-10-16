# SPDX-License-Identifier: MIT
"""Pass only nonsecret topology to the fixed target finalizer."""
import json
import os
from pathlib import Path
import re

import libcalamares


def pretty_name():
    return "Preparing the installed KythOS Kernal common base."


def bootloader_requested(firmware, bootloader):
    return firmware == "efi" or isinstance(bootloader, dict) and bool(bootloader.get("installPath"))


def run():
    target = libcalamares.globalstorage.value("rootMountPoint")
    topology = libcalamares.globalstorage.value("kythosStorage")
    if not target or target == "/" or not isinstance(topology, dict):
        return ("Target configuration failed", "The installer target is unavailable.")
    username = libcalamares.globalstorage.value("username")
    if not isinstance(username, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        return ("Target configuration failed", "The administrator account name is invalid.")
    automatic_user = libcalamares.globalstorage.value("autoLoginUser")
    if automatic_user not in (None, "", username):
        return ("Target configuration failed", "The automatic login account is invalid.")
    topology = dict(topology, username=username, autologin=automatic_user == username)
    bootloader = libcalamares.globalstorage.value("bootLoader")
    topology["install_bootloader"] = bootloader_requested(topology["firmware"], bootloader)
    target_dir = Path(target) / "var/lib/kythos"
    target_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    marker = target_dir / "calamares-target"
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write("KythOS Calamares target v1\n")
    receipt = target_dir / "calamares-storage.json"
    descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(topology, output, sort_keys=True)
        output.write("\n")
    libcalamares.utils.check_target_env_call(
        ["/usr/local/libexec/kythos-calamares-target", "configure"])
    return None
