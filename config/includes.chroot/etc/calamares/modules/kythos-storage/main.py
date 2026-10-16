# SPDX-License-Identifier: MIT
"""Reconcile actual native partition results with the validated pending plan.

Only nonsecret mount/encryption identities are exported. The native partition
plugin validates the pending layout before disk jobs; this is a defensive
post-partition check using the real UUIDs created by those jobs.
"""
import re
import libcalamares


def pretty_name():
    return "Checking boot and encryption layout."


def topology(partitions, firmware, backing_identities=None, fully_encrypted=None, swap_backing_identities=None):
    if not isinstance(partitions, list):
        raise ValueError("No partition result is available.")
    roots = [p for p in partitions if p.get("mountPoint") == "/"]
    boots = [p for p in partitions if p.get("mountPoint") == "/boot"]
    if len(roots) != 1 or len(boots) > 1:
        raise ValueError("Exactly one root filesystem is required.")
    root, boot = roots[0], boots[0] if boots else None
    if not root.get("fs"):
        raise ValueError("The root filesystem type is unavailable.")
    identities = set(backing_identities or [])
    backing = [p for p in partitions if p.get("kythosBackingIdentity") in identities]
    if identities and {p.get("kythosBackingIdentity") for p in backing} != identities:
        raise ValueError("The proposed root backing did not match the resulting devices.")
    if "luksMapperName" in root and root not in backing:
        backing.append(root)
    root_crypto = [p for p in backing if "luksMapperName" in p]
    swap_backing = [p for p in partitions if p.get("kythosBackingIdentity") in set(swap_backing_identities or [])]
    if root_crypto and not boot:
        raise ValueError("Root depends on encryption and requires a separate public /boot.")
    if boot and "luksMapperName" in boot:
        raise ValueError("The signed boot chain requires unencrypted boot files.")
    if firmware == "efi":
        esp = [p for p in partitions if p.get("mountPoint") == "/boot/efi"]
        if len(esp) != 1 or esp[0].get("fs") != "fat32" or "luksMapperName" in esp[0]:
            raise ValueError("A separate unencrypted FAT32 EFI system partition is required.")
    swaps = [p for p in partitions if p.get("claimed") and p.get("fs") in ("linuxswap", "swap")]
    if root_crypto and not swap_backing and any("luksMapperName" not in p for p in swaps):
        raise ValueError("Selected swap must remain encrypted with root storage.")
    # The native plugin also checks inherited LVM encryption before formatting.
    mappings = []
    for partition in partitions:
        if "luksMapperName" not in partition:
            continue
        if not (partition.get("mountPoint") or partition in root_crypto or partition in swap_backing or partition in swaps):
            continue
        name, uuid = partition.get("luksMapperName"), partition.get("luksUuid")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", name):
            raise ValueError("An encryption mapping is invalid.")
        if not isinstance(uuid, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", uuid):
            raise ValueError("An encryption UUID is invalid.")
        mappings.append({"name": name, "uuid": uuid,
                         "early": partition in root_crypto or partition in swap_backing or partition in swaps})
    swap_devices = []
    for partition in swaps:
        if "luksMapperName" in partition:
            swap_devices.append("/dev/mapper/" + partition["luksMapperName"])
        elif partition.get("uuid"):
            swap_devices.append("UUID=" + partition["uuid"])
        elif partition.get("device"):
            swap_devices.append(partition["device"])
    return {"encrypted": bool(root_crypto) if fully_encrypted is None else bool(fully_encrypted),
            "root_requires_crypto": bool(root_crypto), "firmware": firmware,
            "root_filesystem": root["fs"], "crypt_mappings": mappings,
            "swap_devices": swap_devices}


def run():
    try:
        result = topology(libcalamares.globalstorage.value("partitions"),
                          libcalamares.globalstorage.value("firmwareType"),
                          libcalamares.globalstorage.value("kythosRootBackingIdentities"),
                          libcalamares.globalstorage.value("kythosRootFullyEncrypted"),
                          libcalamares.globalstorage.value("kythosSwapBackingIdentities"))
        choice = libcalamares.globalstorage.value("partitionChoices")
        if not isinstance(choice, dict) or choice.get("swap") not in ("none", "file", "small", "suspend"):
            raise ValueError("The selected swap layout is unavailable.")
        result["swap"] = choice["swap"]
        libcalamares.globalstorage.insert("kythosStorage", result)
    except (TypeError, ValueError) as error:
        return ("The partition result failed validation", str(error))
    return None
