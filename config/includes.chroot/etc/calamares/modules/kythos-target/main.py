# SPDX-License-Identifier: MIT
"""Pass only nonsecret topology to the fixed target finalizer."""
import json
import os
from pathlib import Path
import re
import subprocess

import libcalamares


def pretty_name():
    return "Preparing the installed KythOS Kernal common base."


def bootloader_requested(firmware, bootloader):
    return firmware == "efi" or isinstance(bootloader, dict) and bool(bootloader.get("installPath"))


def storage_boolean(value):
    # Calamares 3.3.14 tests py::int_ before py::bool_ when inserting
    # Python dictionaries into QVariant storage: bools return as 0/1.
    # Normalize that exact API representation; keep the on-disk schema strict.
    if type(value) not in (bool, int) or value not in (0, 1):
        raise ValueError("An encryption flag is invalid.")
    return bool(value)


def storage_receipt(topology, username, autologin, firmware_bootloader):
    result = dict(topology, username=username, autologin=autologin)
    for field in ("encrypted", "root_requires_crypto"):
        result[field] = storage_boolean(result[field])
    mappings = result["crypt_mappings"]
    if not isinstance(mappings, list) or any(not isinstance(mapping, dict) for mapping in mappings):
        raise ValueError("The encryption mappings are invalid.")
    result["crypt_mappings"] = [dict(mapping, early=storage_boolean(mapping["early"]))
                                for mapping in mappings]
    result["install_bootloader"] = bootloader_requested(result["firmware"], firmware_bootloader)
    return result


def finalizer_error(error):
    # The fixed helper emits one nonsecret diagnostic. Never expose arbitrary
    # subprocess output, global storage, account passwords or encryption keys.
    output = error.output if isinstance(error.output, str) else ""
    prefix = "KythOS Kernal target finalization failed: "
    for line in reversed(output.splitlines()):
        if line.startswith(prefix):
            return line[:600]
    return "The target configuration command failed (exit status {}).".format(error.returncode)


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
    bootloader = libcalamares.globalstorage.value("bootLoader")
    try:
        topology = storage_receipt(topology, username, automatic_user == username, bootloader)
    except (KeyError, TypeError, ValueError) as error:
        return ("Target configuration failed", str(error))
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
    try:
        libcalamares.utils.check_target_env_call(
            ["/usr/local/libexec/kythos-calamares-target", "configure"])
    except subprocess.CalledProcessError as error:
        return ("Target configuration failed", finalizer_error(error))
    return None
