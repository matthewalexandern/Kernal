#!/usr/bin/python3
"""Edition selection/staging must preserve the source and installed desktop."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_edition', ROOT / 'scripts/stage-edition.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def package_roots(directory, scope):
    return {line.split()[0] for file in directory.glob('*.list.' + scope)
            for line in file.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith(('#', '!'))}


class EditionTests(unittest.TestCase):
    def staged(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        config = Path(work.name) / 'config'
        shutil.copytree(ROOT / 'config', config, symlinks=True)
        return config

    def test_base_staging_preserves_console_and_omits_desktop_payload(self):
        config = self.staged()
        selected = stage.stage(config, 'base')
        self.assertEqual(selected['default_target'], 'multi-user.target')
        self.assertEqual((config / 'includes.chroot/usr/share/kythos/build-edition').read_text(), 'base\n')
        self.assertNotIn('xfce4', package_roots(config / 'package-lists', 'chroot_install'))
        self.assertFalse((config / 'editions').exists())

    def test_desktop_preserves_display_roots_while_removing_installer_only_tools(self):
        config = self.staged()
        original = (ROOT / 'config/package-lists/calamares.list.chroot_live').read_bytes()
        selected = stage.stage(config, 'desktop')
        installed = package_roots(config / 'package-lists', 'chroot_install')
        live = package_roots(config / 'package-lists', 'chroot_live')
        self.assertEqual(selected['default_target'], 'graphical.target')
        self.assertTrue({'xfce4', 'lightdm', *selected['retain_live_packages']} <= installed)
        self.assertFalse(live & installed)
        self.assertIn('calamares', live)
        self.assertNotIn('calamares', installed)
        self.assertEqual(original, (ROOT / 'config/package-lists/calamares.list.chroot_live').read_bytes())

    def test_unknown_edition_and_source_destination_are_rejected(self):
        config = self.staged()
        for edition in ('../../etc', 'all-in-one', 'unreviewed'):
            with self.subTest(edition=edition), self.assertRaises(ValueError):
                stage.stage(config, edition)
        with self.assertRaises(ValueError):
            stage.stage(ROOT / 'config', 'base')

    def test_iso_names_encode_edition_on_both_architectures(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            executable = directory / 'lb'
            executable.write_text('#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n')
            executable.chmod(0o755)
            for edition in ('base', 'desktop'):
                for architecture in ('amd64', 'arm64'):
                    environment = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ['PATH'],
                                       KYTHOS_ARCH=architecture, KYTHOS_EDITION=edition,
                                       CAPTURE=str(directory / 'arguments'))
                    subprocess.run([str(ROOT / 'auto/config')], env=environment, check=True, capture_output=True)
                    arguments = json.loads((directory / 'arguments').read_text())
                    self.assertEqual(arguments[arguments.index('--image-name') + 1],
                                     'kythos-kernal-' + edition + '-' + (ROOT / 'VERSION').read_text().strip())
                    self.assertEqual(arguments[arguments.index('--architecture') + 1], architecture)


if __name__ == '__main__':
    unittest.main()
