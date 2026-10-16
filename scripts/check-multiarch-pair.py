#!/usr/bin/python3 -I
# SPDX-License-Identifier: MIT
"""Verify that complete amd64/arm64 artifacts share one clean source recipe."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


REQUIRED = {'build-provenance.txt', 'build-architecture-profile.json',
            'recipe-SHA256SUMS', 'source-coverage-audit.txt'}
SHARED = ('source_git_commit', 'debian_snapshot', 'source_date_epoch')


class PairError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PairError(message)


def checksum_manifest(raw, label):
    """Read GNU SHA256SUMS without evaluating or trusting its filenames."""
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise PairError(label + ': checksum manifest is not UTF-8') from exc
    entries = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line)
        require(match is not None, label + ': malformed checksum entry')
        expected, name = match.groups()
        path = PurePosixPath(name)
        require(bool(path.parts) and not path.is_absolute() and str(path) == name and
                all(part not in ('.', '..') for part in path.parts) and
                '\\' not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name),
                label + ': unsafe checksum path')
        require(name not in entries, label + ': duplicate checksum path')
        entries[name] = expected
    require(bool(entries), label + ': empty checksum manifest')
    return entries


class Artifacts:
    """Open manifest members below a fixed directory without following links."""
    def __init__(self, directory):
        self.path = Path(directory).absolute()
        # Reject symlinks in the selected directory itself or its ancestors.
        for component in (self.path, *self.path.parents):
            require(not component.is_symlink(), 'Artifact directory uses a symlink')
        self.descriptor = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.descriptor)

    def open(self, name):
        descriptor = os.dup(self.descriptor)
        try:
            parts = PurePosixPath(name).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            member = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=descriptor)
            try:
                require(stat.S_ISREG(os.fstat(member).st_mode), 'Artifact is not a regular file: ' + name)
                return os.fdopen(member, 'rb')
            except BaseException:
                os.close(member)
                raise
        finally:
            os.close(descriptor)

    def read(self, name, maximum=16 * 1024 * 1024):
        with self.open(name) as source:
            raw = source.read(maximum + 1)
        require(len(raw) <= maximum, 'Metadata is too large: ' + name)
        return raw

    def digest(self, name):
        result = hashlib.sha256()
        with self.open(name) as source:
            before = os.fstat(source.fileno())
            for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
                result.update(block)
            after = os.fstat(source.fileno())
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'Artifact changed during readback: ' + name)
        return result.hexdigest()


def properties(raw, label):
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeError as exc:
        raise PairError(label + ': metadata is not UTF-8') from exc
    result = {}
    for line in lines:
        # Provenance includes an indented upstream OS-release/tools section.
        if '=' not in line or line[:1].isspace():
            continue
        key, value = line.split('=', 1)
        require(key not in result, label + ': duplicate metadata key: ' + key)
        result[key] = value
    return result


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate architecture-profile JSON key')
        result[key] = value
    return result


def architecture_profile(raw, architecture):
    try:
        profile = json.loads(raw, object_pairs_hook=unique_json)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PairError(architecture + ': malformed architecture profile') from exc
    require(isinstance(profile, dict), architecture + ': architecture profile is not an object')
    boot = {'amd64': ('syslinux,grub-efi', 'x86_64-efi', 'x64', 'i386-pc'),
            'arm64': ('grub-efi', 'arm64-efi', 'aa64', None)}
    require(profile.get('architecture') == architecture and
            profile.get('kernel_flavour') == architecture and
            tuple(profile.get(key) for key in ('bootloaders', 'efi_target', 'efi_suffix', 'bios_target')) == boot[architecture],
            architecture + ': wrong architecture/boot profile')
    packages = profile.get('packages')
    require(isinstance(packages, list) and all(isinstance(name, str) for name in packages) and
            len(packages) == len(set(packages)) and
            {'linux-image-' + architecture, 'linux-headers-' + architecture,
             'grub-efi-' + architecture + '-signed'} <= set(packages),
            architecture + ': incomplete architecture package profile')


def verify_architecture(directory, architecture):
    artifacts = Artifacts(directory)
    try:
        manifest = artifacts.read('SHA256SUMS')
        entries = checksum_manifest(manifest, architecture)
        require(REQUIRED <= entries.keys(), architecture + ': incomplete artifact metadata')
        binaries = [name for name in entries if name.endswith('.hybrid.iso')]
        sources = [name for name in entries if name.endswith('-source.iso')]
        require(len(binaries) == len(sources) == 1, architecture + ': exactly one binary/source ISO pair must be declared')
        binary, source = binaries[0], sources[0]
        suffix = '-' + architecture + '.hybrid.iso'
        require(binary.endswith(suffix), architecture + ': binary ISO names the wrong architecture')
        image_name = binary[:-len(suffix)]
        require(bool(image_name) and source == image_name + '-source.iso', architecture + ': binary/source ISO names differ')
        # Reject incomplete copies and undeclared ISO files, without treating
        # independent transfer receipts as release payloads.
        for path in artifacts.path.iterdir():
            require(not path.name.endswith('.partial'), architecture + ': artifact transfer is incomplete')
            if path.name.endswith('.iso'):
                require(path.name in entries, architecture + ': undeclared ISO artifact')
        provenance = properties(artifacts.read('build-provenance.txt'), architecture)
        edition = provenance.get('edition', 'base')
        require(re.fullmatch(r'[a-z][a-z0-9-]*', edition) is not None,
                architecture + ': invalid edition identity')
        require(image_name.startswith('kythos-kernal-' + edition + '-'),
                architecture + ': ISO name differs from edition identity')
        require(provenance.get('source_git_state') == 'clean', architecture + ': source checkout was not clean')
        require(provenance.get('debian_architecture') == architecture, architecture + ': missing/wrong provenance architecture')
        require(re.fullmatch(r'[0-9a-f]{40}', provenance.get('source_git_commit', '')) is not None,
                architecture + ': missing/invalid source commit')
        snapshot = provenance.get('debian_snapshot', '')
        require(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z', snapshot) is not None,
                architecture + ': missing/invalid Debian snapshot')
        try:
            datetime.strptime(snapshot, '%Y%m%dT%H%M%SZ')
        except ValueError as exc:
            raise PairError(architecture + ': invalid Debian snapshot date') from exc
        require(re.fullmatch(r'0|[1-9][0-9]*', provenance.get('source_date_epoch', '')) is not None,
                architecture + ': missing/invalid source epoch')
        architecture_profile(artifacts.read('build-architecture-profile.json'), architecture)
        coverage = properties(artifacts.read('source-coverage-audit.txt'), architecture)
        require(coverage.get('missing_source_tuples') == '0', architecture + ': source coverage is incomplete')
        recipe = artifacts.read('recipe-SHA256SUMS')
        checksum_manifest(recipe, architecture + ' canonical recipe')
        for name, expected in entries.items():
            require(artifacts.digest(name) == expected, architecture + ': checksum mismatch: ' + name)
        require(artifacts.read('SHA256SUMS') == manifest, architecture + ': manifest changed during verification')
        return {'provenance': provenance, 'recipe': recipe, 'image_name': image_name, 'edition': edition,
                'summary': {'verified_artifacts': len(entries),
                            'binary_iso': {'file': binary, 'sha256': entries[binary]},
                            'source_iso': {'file': source, 'sha256': entries[source]}}}
    finally:
        artifacts.close()


def check_pair(amd64, arm64):
    require(Path(amd64).resolve() != Path(arm64).resolve(), 'Two distinct architecture artifact directories are required')
    left = verify_architecture(amd64, 'amd64')
    right = verify_architecture(arm64, 'arm64')
    for key in SHARED:
        require(left['provenance'][key] == right['provenance'][key], 'Architecture pair differs: ' + key)
    require(left['recipe'] == right['recipe'], 'Architecture pair differs: canonical recipe-SHA256SUMS')
    require(left['edition'] == right['edition'], 'Architecture pair differs: edition')
    require(left['image_name'] == right['image_name'], 'Architecture pair differs: image release name')
    return {'result': 'passed', **{key: left['provenance'][key] for key in SHARED},
            'edition': left['edition'],
            'recipe_sha256': hashlib.sha256(left['recipe']).hexdigest(),
            'architectures': {'amd64': left['summary'], 'arm64': right['summary']},
            'boot_validation': 'not_assessed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amd64', required=True, type=Path, help='Completed amd64 artifact directory')
    parser.add_argument('--arm64', required=True, type=Path, help='Completed arm64 artifact directory')
    arguments = parser.parse_args()
    try:
        result = check_pair(arguments.amd64, arguments.arm64)
    except (PairError, OSError, KeyError, TypeError) as exc:
        print('Multiarch pair rejected: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
