# SPDX-License-Identifier: MIT
"""Copy one allowlisted nonsecret appearance choice into the installed system."""

import os
from pathlib import Path
import stat
import tempfile

import libcalamares


CHOICES = frozenset(('dark', 'light', 'monochrome', 'blue', 'teal', 'high-contrast'))
PREFERENCE = Path('/home/kythos-live/.config/kythos/terminal-theme')


def pretty_name():
    return 'Setting the terminal appearance.'


def read_choice(path=PREFERENCE):
    # The live user may edit this preference. Treat it as data, never execute it
    # or copy an arbitrary file. Bound reads and reject symlinks/special files.
    try:
        for parent in path.parents:
            if parent.is_symlink():
                return 'dark'
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                return 'dark'
            raw = source.read(65)
        if len(raw) > 64:
            return 'dark'
        value = raw.decode('ascii').strip()
        return value if value in CHOICES else 'dark'
    except (OSError, UnicodeError):
        return 'dark'


def install_choice(target, choice):
    target = Path(target)
    if (not target.is_absolute() or target == Path('/') or
            choice not in CHOICES or target.is_symlink()):
        raise ValueError('The installer target or terminal theme is invalid.')
    directory = target / 'etc/kythos'
    for parent in (directory.parent, directory):
        if parent.is_symlink():
            raise ValueError('The target theme configuration is a symbolic link.')
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.terminal-theme-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='ascii') as output:
            output.write(choice + '\n')
            os.fchmod(output.fileno(), 0o644)
        os.replace(temporary, directory / 'terminal-theme')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run():
    target = libcalamares.globalstorage.value('rootMountPoint')
    try:
        if not isinstance(target, str) or not target:
            raise ValueError('The installer target is unavailable.')
        install_choice(target, read_choice())
    except (OSError, ValueError) as error:
        return ('Terminal appearance could not be saved', str(error))
    return None
