#!/usr/bin/python3
"""FIDO2 enrollment transaction fixtures; no hardware success is simulated."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "config/includes.chroot/usr/local/sbin/kythos-fido-login"
FRAGMENT = REPO / "config/includes.chroot/etc/pam.d/kythos-fido2"
loader = importlib.machinery.SourceFileLoader("kythos_fido_login", str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = module
loader.exec_module(module)


PIN_CREDENTIAL = "abcdefgh,ABCDEFGHIJKLMNOP,es256,+presence+pin"
UV_CREDENTIAL = "ijklmnop,QRSTUVWXYZabcdef,eddsa,+presence+verification"


def fixture_layout(root: Path):
    pam = root / "etc/pam.d"
    security = root / "etc/security"
    run = root / "run/lock"
    pam.mkdir(parents=True)
    security.mkdir(parents=True)
    run.mkdir(parents=True)
    for directory in (pam, security, run):
        directory.chmod(0o755)
    login = pam / "login"
    login.write_text(
        "# service checks remain before passwordless FIDO\n"
        "auth requisite pam_nologin.so\n"
        "@include common-auth\n"
        "@include common-account\n",
        encoding="utf-8",
    )
    login.chmod(0o644)
    fragment = pam / "kythos-fido2"
    fragment.write_text(module.FRAGMENT_TEXT, encoding="utf-8")
    fragment.chmod(0o644)
    return module.Layout(
        mapping=security / "kythos-u2f-mappings",
        login=login,
        fragment=fragment,
        backup=pam / "login.kythos-password-recovery",
        lock=root / "run/kythos-fido-login.lock",
        owner_uid=os.geteuid(),
        owner_gid=os.getegid(),
    )


class MappingTests(unittest.TestCase):
    def test_secure_pin_and_uv_registrations_parse(self):
        pin = module.parse_mapping(
            "alice:" + PIN_CREDENTIAL,
            registration_user="alice", verification="pin",
        )
        uv = module.parse_mapping(
            "alice:" + UV_CREDENTIAL,
            registration_user="alice", verification="uv",
        )
        self.assertEqual(pin["alice"], [PIN_CREDENTIAL])
        self.assertEqual(uv["alice"], [UV_CREDENTIAL])

    def test_presence_only_and_wrong_user_are_rejected(self):
        with self.assertRaises(module.FidoLoginError):
            module.parse_mapping(
                "alice:abcdefgh,ABCDEFGHIJKLMNOP,es256,+presence",
                registration_user="alice", verification="pin",
            )
        with self.assertRaises(module.FidoLoginError):
            module.parse_mapping(
                "mallory:" + PIN_CREDENTIAL,
                registration_user="alice", verification="pin",
            )

    def test_merge_retains_other_users_and_multiple_keys(self):
        existing = "alice:" + PIN_CREDENTIAL + "\n"
        merged = module.merge_registration(
            existing, "alice:" + UV_CREDENTIAL, "alice", "uv"
        )
        self.assertEqual(
            merged,
            "alice:" + PIN_CREDENTIAL + ":" + UV_CREDENTIAL + "\n",
        )

    def test_recovery_password_must_be_nonempty_and_unlocked(self):
        self.assertTrue(module.password_hash_is_usable("$y$j9T$hash"))
        self.assertFalse(module.password_hash_is_usable(""))
        self.assertFalse(module.password_hash_is_usable("!$y$j9T$hash"))
        self.assertFalse(module.password_hash_is_usable("*"))


class PamTextTests(unittest.TestCase):
    def test_include_is_after_service_checks_and_before_password(self):
        original = (
            "auth requisite pam_nologin.so\n"
            "@include common-auth\n"
            "@include common-account\n"
        )
        enabled = module.enable_login_text(original)
        self.assertLess(enabled.index("pam_nologin"), enabled.index(module.INCLUDE_LINE))
        self.assertLess(enabled.index(module.INCLUDE_LINE), enabled.index("common-auth"))
        self.assertEqual(module.enable_login_text(enabled), enabled)
        self.assertEqual(module.disable_login_text(enabled), original)

    def test_missing_or_duplicated_password_stack_is_rejected(self):
        with self.assertRaises(module.FidoLoginError):
            module.enable_login_text("auth required pam_unix.so\n")
        with self.assertRaises(module.FidoLoginError):
            module.enable_login_text("@include common-auth\n@include common-auth\n")

    def test_packaged_fragment_has_fallback_control_and_no_bypass(self):
        text = FRAGMENT.read_text(encoding="utf-8")
        self.assertEqual(text, module.FRAGMENT_TEXT)
        self.assertIn("auth sufficient pam_u2f.so", text)
        self.assertIn("userpresence=1", text)
        self.assertIn("authfile=/etc/security/kythos-u2f-mappings", text)
        self.assertNotIn("nouserok", text)
        self.assertNotIn("alwaysok", text)
        self.assertNotIn("sshformat", text)


class TransactionTests(unittest.TestCase):
    def test_failed_verification_gate_never_enables_or_persists_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = fixture_layout(Path(directory))
            before = layout.login.read_text(encoding="utf-8")
            verification_attempts = []

            def registration(command):
                self.assertIn("--pin-verification", command)
                return 0, "alice:" + PIN_CREDENTIAL

            def rejected_verification(service, user):
                verification_attempts.append(service)
                self.assertTrue((layout.fragment.parent / service).is_file())
                self.assertEqual(user, "alice")
                return False

            with self.assertRaises(module.FidoLoginError):
                module.enroll_transaction(
                    layout, "alice", "pin", registration, rejected_verification
                )
            self.assertEqual(layout.login.read_text(encoding="utf-8"), before)
            self.assertEqual(len(verification_attempts), 1)
            self.assertFalse(layout.mapping.exists())
            self.assertFalse(layout.backup.exists())

    def test_existing_key_cannot_satisfy_new_registration_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = fixture_layout(Path(directory))
            layout.mapping.write_text("alice:" + PIN_CREDENTIAL + "\n")
            layout.mapping.chmod(0o600)
            before = layout.login.read_text(encoding="utf-8")
            verification_attempts = []

            def registration(_command):
                return 0, "alice:" + UV_CREDENTIAL

            def old_key_only_verifier(service, _user):
                verification_attempts.append(service)
                service_text = (layout.fragment.parent / service).read_text()
                candidate = Path(re.search(r"authfile=([^ ]+)", service_text).group(1))
                proof_mapping = candidate.read_text()
                self.assertEqual(proof_mapping, "alice:" + UV_CREDENTIAL + "\n")
                self.assertNotIn(PIN_CREDENTIAL, proof_mapping)
                return PIN_CREDENTIAL in proof_mapping

            with self.assertRaises(module.FidoLoginError):
                module.enroll_transaction(
                    layout, "alice", "uv", registration, old_key_only_verifier
                )
            self.assertEqual(layout.login.read_text(), before)
            self.assertEqual(len(verification_attempts), 1)
            self.assertEqual(layout.mapping.read_text(), "alice:" + PIN_CREDENTIAL + "\n")
            self.assertFalse(layout.backup.exists())

    def test_test_double_can_exercise_post_verification_atomic_activation(self):
        """This checks transaction ordering; it is not a physical-key claim."""
        with tempfile.TemporaryDirectory() as directory:
            layout = fixture_layout(Path(directory))
            layout.mapping.write_text("alice:" + PIN_CREDENTIAL + "\n")
            layout.mapping.chmod(0o600)

            def registration(_command):
                return 0, "alice:" + UV_CREDENTIAL

            def verification_test_double(service, user):
                service_text = (layout.fragment.parent / service).read_text()
                self.assertIn("auth required pam_u2f.so", service_text)
                self.assertIn(".kythos-u2f-candidate-", service_text)
                candidate = Path(re.search(r"authfile=([^ ]+)", service_text).group(1))
                self.assertEqual(candidate.read_text(), "alice:" + UV_CREDENTIAL + "\n")
                self.assertNotIn(PIN_CREDENTIAL, candidate.read_text())
                self.assertEqual(user, "alice")
                return True

            module.enroll_transaction(
                layout, "alice", "uv", registration, verification_test_double
            )
            self.assertIn(module.INCLUDE_LINE, layout.login.read_text())
            self.assertEqual(
                layout.mapping.read_text(),
                "alice:" + PIN_CREDENTIAL + ":" + UV_CREDENTIAL + "\n",
            )
            self.assertEqual(stat.S_IMODE(layout.mapping.stat().st_mode), 0o600)
            self.assertNotIn(module.INCLUDE_LINE, layout.backup.read_text())
            self.assertFalse(any(layout.fragment.parent.glob("kythos-fido-verify-*")))
            self.assertFalse(any(layout.mapping.parent.glob(".kythos-u2f-candidate-*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
