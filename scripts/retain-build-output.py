#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Retain a completed build output without overwriting an existing artifact."""
import argparse
import os
from pathlib import Path
import shutil
import stat


def retain(source, directory, mode='copy'):
    source, directory = Path(source), Path(directory)
    if mode not in ('copy', 'hardlink'):
        raise ValueError('Unknown artifact storage mode')
    if not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Only regular completed build outputs can be retained')
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Artifact destination must be an existing real directory')
    target = directory / source.name
    if target.exists() or target.is_symlink():
        raise ValueError('Refusing to overwrite an existing artifact: ' + str(target))
    if mode == 'hardlink':
        if source.stat().st_dev != directory.stat().st_dev:
            raise ValueError('Hardlink artifacts must share the build output filesystem')
        os.link(source, target, follow_symlinks=False)
    else:
        shutil.copy2(source, target, follow_symlinks=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('copy', 'hardlink'), default='copy')
    parser.add_argument('source', type=Path)
    parser.add_argument('directory', type=Path)
    options = parser.parse_args()
    try:
        retain(options.source, options.directory, options.mode)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
