#!/usr/bin/python3
"""Artifact-consistency fixtures; fixture payloads are deliberately not ISOs."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts/check-multiarch-pair.py'
PROFILES = json.loads((ROOT / 'config/includes.chroot/usr/share/kythos/architecture-profiles.json').read_text())['architectures']
COMMIT = '1' * 40
SNAPSHOT = '20261016T000000Z'


class MultiarchPair(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directories = {}
        for architecture in ('amd64', 'arm64'):
            directory = self.root / architecture
            directory.mkdir()
            self.directories[architecture] = directory
            (directory / 'build-provenance.txt').write_text(
                f'source_git_commit={COMMIT}\nsource_git_state=clean\n'
                f'debian_snapshot={SNAPSHOT}\nsource_date_epoch=1792108800\n'
                f'debian_architecture={architecture}\n'
                'builder_os_release:\n  NAME="upstream provenance"\n')
            (directory / 'build-architecture-profile.json').write_text(
                json.dumps(dict(PROFILES[architecture], architecture=architecture)) + '\n')
            (directory / 'source-coverage-audit.txt').write_text('required_source_tuples=2\nmissing_source_tuples=0\n')
            (directory / 'recipe-SHA256SUMS').write_text(
                'a' * 64 + '  auto/config\n' + 'b' * 64 + '  config/common.txt\n')
            (directory / f'kythos-kernal-base-0.1.0-{architecture}.hybrid.iso').write_bytes(
                b'NONBOOTABLE TEST FIXTURE binary ' + architecture.encode())
            (directory / 'kythos-kernal-base-0.1.0-source.iso').write_bytes(
                b'NONBOOTABLE TEST FIXTURE source ' + architecture.encode())
            self.manifest(architecture)

    def manifest(self, architecture):
        directory = self.directories[architecture]
        files = sorted(p for p in directory.iterdir() if p.name != 'SHA256SUMS' and p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n' for path in files))

    def run_checker(self):
        return subprocess.run([str(CHECKER), '--amd64', str(self.directories['amd64']),
                               '--arm64', str(self.directories['arm64'])],
                              capture_output=True, text=True, timeout=10)

    def reject(self, message):
        result = self.run_checker()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout, '', 'a rejected pair must not emit a pass JSON')
        self.assertIn(message, result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def replace_property(self, architecture, key, value):
        path = self.directories[architecture] / 'build-provenance.txt'
        lines = path.read_text().splitlines()
        path.write_text('\n'.join(key + '=' + value if line.startswith(key + '=') else line for line in lines) + '\n')
        self.manifest(architecture)

    def test_matching_pair_reports_shared_source_and_independent_iso_digests(self):
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['result'], 'passed')
        self.assertEqual(report['source_git_commit'], COMMIT)
        self.assertEqual(report['debian_snapshot'], SNAPSHOT)
        self.assertEqual(report['source_date_epoch'], '1792108800')
        self.assertEqual(report['boot_validation'], 'not_assessed')
        self.assertEqual(report['recipe_sha256'], hashlib.sha256(
            (self.directories['amd64'] / 'recipe-SHA256SUMS').read_bytes()).hexdigest())
        for architecture in ('amd64', 'arm64'):
            info = report['architectures'][architecture]
            self.assertEqual(info['verified_artifacts'], 6)
            for kind in ('binary_iso', 'source_iso'):
                payload = self.directories[architecture] / info[kind]['file']
                self.assertEqual(info[kind]['sha256'], hashlib.sha256(payload.read_bytes()).hexdigest())

    def test_stale_source_commit_is_rejected_even_with_valid_artifact_hashes(self):
        self.replace_property('arm64', 'source_git_commit', '2' * 40)
        self.reject('source_git_commit')

    def test_separate_desktop_pair_requires_matching_edition_identity(self):
        for architecture, directory in self.directories.items():
            provenance = directory / 'build-provenance.txt'
            provenance.write_text(provenance.read_text() + 'edition=desktop\n')
            for original in list(directory.glob('*.iso')):
                original.rename(original.with_name(original.name.replace('-base-', '-desktop-')))
            self.manifest(architecture)
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['edition'], 'desktop')
        self.replace_property('arm64', 'edition', 'base')
        self.reject('ISO name differs from edition identity')

    def test_different_canonical_recipe_is_rejected_even_with_same_commit(self):
        path = self.directories['arm64'] / 'recipe-SHA256SUMS'
        path.write_text(path.read_text().replace('b' * 64, 'c' * 64))
        self.manifest('arm64')
        self.reject('canonical recipe-SHA256SUMS')

    def test_dirty_source_is_rejected(self):
        self.replace_property('arm64', 'source_git_state', 'dirty')
        self.reject('source checkout was not clean')

    def test_different_snapshot_and_epoch_are_both_rejected(self):
        for key, bad in (('debian_snapshot', '20261015T000000Z'), ('source_date_epoch', '1792108801')):
            path = self.directories['arm64'] / 'build-provenance.txt'
            original = path.read_text()
            self.replace_property('arm64', key, bad)
            self.reject(key)
            path.write_text(original)
            self.manifest('arm64')

    def test_corrupt_binary_and_source_isos_are_detected_by_readback(self):
        for name in ('kythos-kernal-base-0.1.0-arm64.hybrid.iso', 'kythos-kernal-base-0.1.0-source.iso'):
            path = self.directories['arm64'] / name
            original = path.read_bytes()
            path.write_bytes(b'corrupted after manifest')
            self.reject('checksum mismatch: ' + name)
            path.write_bytes(original)

    def test_missing_or_nonzero_source_coverage_never_passes(self):
        path = self.directories['arm64'] / 'source-coverage-audit.txt'
        for content in ('required_source_tuples=2\n', 'missing_source_tuples=1\n'):
            path.write_text(content)
            self.manifest('arm64')
            self.reject('source coverage is incomplete')
        path.unlink()
        self.manifest('arm64')
        self.reject('incomplete artifact metadata')

    def test_legacy_missing_architecture_and_wrong_provenance_arch_are_rejected(self):
        path = self.directories['amd64'] / 'build-provenance.txt'
        original = path.read_text()
        path.write_text('\n'.join(line for line in original.splitlines()
                                  if not line.startswith('debian_architecture=')) + '\n')
        self.manifest('amd64')
        self.reject('missing/wrong provenance architecture')
        path.write_text(original)
        self.replace_property('amd64', 'debian_architecture', 'arm64')
        self.reject('missing/wrong provenance architecture')

    def test_wrong_selected_profile_and_missing_profile_are_rejected(self):
        path = self.directories['arm64'] / 'build-architecture-profile.json'
        profile = json.loads(path.read_text())
        profile['architecture'] = 'amd64'
        path.write_text(json.dumps(profile))
        self.manifest('arm64')
        self.reject('wrong architecture/boot profile')
        path.unlink()
        self.manifest('arm64')
        self.reject('incomplete artifact metadata')

    def test_wrong_architecture_iso_extra_iso_and_missing_source_are_rejected(self):
        directory = self.directories['arm64']
        binary = directory / 'kythos-kernal-base-0.1.0-arm64.hybrid.iso'
        wrong = directory / 'kythos-kernal-base-0.1.0-amd64.hybrid.iso'
        binary.rename(wrong)
        self.manifest('arm64')
        self.reject('binary ISO names the wrong architecture')
        wrong.rename(binary)
        self.manifest('arm64')
        extra = directory / 'undeclared.iso'
        extra.write_bytes(b'extra')
        self.reject('undeclared ISO artifact')
        self.manifest('arm64')
        # An additional source ISO is also an invalid declared payload set.
        extra.rename(directory / 'extra-source.iso')
        self.manifest('arm64')
        self.reject('exactly one binary/source ISO pair')
        (directory / 'extra-source.iso').unlink()
        (directory / 'kythos-kernal-base-0.1.0-source.iso').unlink()
        self.manifest('arm64')
        self.reject('exactly one binary/source ISO pair')

    def test_symlink_iso_is_rejected_even_if_its_external_contents_match(self):
        path = self.directories['arm64'] / 'kythos-kernal-base-0.1.0-arm64.hybrid.iso'
        outside = self.root / 'outside-payload'
        path.rename(outside)
        path.symlink_to(outside)
        self.reject('Multiarch pair rejected')

    def test_manifest_path_traversal_and_duplicates_are_rejected(self):
        path = self.directories['arm64'] / 'SHA256SUMS'
        original = path.read_text()
        for name in ('../outside', '/tmp/outside', './build-provenance.txt', '.'):
            path.write_text(original + 'a' * 64 + '  ' + name + '\n')
            self.reject('unsafe checksum path')
        path.write_text(original + original.splitlines()[0] + '\n')
        self.reject('duplicate checksum path')

    def test_missing_payload_and_partial_copy_are_rejected(self):
        partial = self.directories['arm64'] / 'source.iso.partial'
        partial.write_bytes(b'partial')
        self.reject('artifact transfer is incomplete')
        partial.unlink()
        (self.directories['arm64'] / 'kythos-kernal-base-0.1.0-source.iso').unlink()
        self.reject('Multiarch pair rejected')


if __name__ == '__main__':
    unittest.main()
