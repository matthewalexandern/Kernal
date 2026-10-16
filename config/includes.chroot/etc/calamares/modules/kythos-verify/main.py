# SPDX-License-Identifier: MIT
"""A successful installer must include a bootable, locked-down target."""
import libcalamares


def pretty_name():
    return "Verifying the installed system."


def run():
    libcalamares.utils.check_target_env_call(
        ["/usr/local/libexec/kythos-calamares-target", "verify"])
    return None
