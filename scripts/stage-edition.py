#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Overlay one explicit edition onto an already-copied live-build config."""
import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    'edition_profile', str(ROOT / 'config/includes.chroot/usr/local/libexec/kythos-edition'))
spec = importlib.util.spec_from_loader(loader.name, loader)
profile_module = importlib.util.module_from_spec(spec)
loader.exec_module(profile_module)


def stage(destination, edition):
    selected = profile_module.profile(edition)
    destination = Path(destination).resolve(strict=True)
    if destination == ROOT / 'config' or ROOT in destination.parents:
        raise ValueError('Stage outside the source checkout, never into protected recipe files')
    if not (destination / 'package-lists').is_dir():
        raise ValueError('Destination must contain a staged live-build configuration')
    overlay = ROOT / 'config/editions' / edition
    if overlay.is_dir():
        for child in overlay.iterdir():
            if child.name not in {'package-lists', 'includes.chroot', 'includes.installer', 'hooks'}:
                raise ValueError('Unknown edition overlay directory: ' + child.name)
            shutil.copytree(child, destination / child.name, dirs_exist_ok=True, symlinks=True)
    # A desktop keeps its display stack after removing the installation UI.
    # Promote declared roots in the staging copy so live-only removal cannot
    # purge the installed desktop or conflict with protected installed roots.
    retained = set(selected['retain_live_packages'])
    for path in (destination / 'package-lists').glob('*.list.chroot_live'):
        lines = path.read_text().splitlines(keepends=True)
        path.write_text(''.join(line for line in lines
                                if not line.strip() or line.lstrip().startswith(('#', '!'))
                                or line.split()[0] not in retained))
    if retained:
        (destination / 'package-lists/edition-retained.list.chroot_install').write_text(
            '# Installed display stack retained from the shared live interface.\n' +
            '\n'.join(sorted(retained)) + '\n')
    shutil.rmtree(destination / 'editions', ignore_errors=True)
    share = destination / 'includes.chroot/usr/share/kythos'
    share.mkdir(parents=True, exist_ok=True)
    (share / 'build-edition').write_text(edition + '\n')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edition', default='base')
    parser.add_argument('destination', type=Path)
    options = parser.parse_args()
    try:
        print(json.dumps(stage(options.destination, options.edition), sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
