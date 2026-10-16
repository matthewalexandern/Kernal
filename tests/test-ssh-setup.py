#!/usr/bin/python3
"""SSH lifecycle/key workflow contracts plus a real unprivileged RSA connection.

The loopback daemon uses only ephemeral files and a high port. No host account,
service, firewall, or authorized_keys file is modified.
"""
import base64
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import pwd
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CHROOT = ROOT / "config/includes.chroot"


def module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    result = importlib.util.module_from_spec(spec)
    loader.exec_module(result)
    return result


service = module("ssh_service", CHROOT / "usr/local/sbin/kythos-enable-ssh")
helper = module("ssh_helper", CHROOT / "usr/local/bin/kythos-ssh")
target = module("ssh_target", CHROOT / "usr/local/libexec/kythos-calamares-target")


def public_fixture(path):
    algorithm = b"ssh-ed25519"
    blob = struct.pack(">I", len(algorithm)) + algorithm + struct.pack(">I", 32) + b"x" * 32
    path.write_text("ssh-ed25519 " + base64.b64encode(blob).decode() + " fixture\n")
    return path


class LifecycleTests(unittest.TestCase):
    def test_running_installed_machine_starts_and_enables_daemon_and_firewall(self):
        run = Mock()
        self.assertTrue(service.enable(run=run, active=True, live=False))
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["/usr/sbin/nft", "--check", "--file", "/etc/nftables.conf"])
        self.assertIn(["/usr/bin/systemctl", "enable", "--now", "ssh.service"], commands)
        self.assertLess(commands.index(["/usr/bin/systemctl", "disable", "--now", "ssh.socket"]),
                        commands.index(["/usr/bin/systemctl", "enable", "--now", "ssh.service"]))
        self.assertIn(["/usr/bin/systemctl", "reload", "nftables.service"], commands)

    def test_image_chroot_offline_and_live_never_start_services_or_touch_host_firewall(self):
        for kwargs in ({"active": False, "live": False}, {"active": True, "live": False, "offline": True},
                       {"active": True, "live": True}):
            with self.subTest(kwargs=kwargs):
                run = Mock()
                self.assertFalse(service.enable(run=run, **kwargs))
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(commands, [["/usr/bin/systemctl", "--root=/", "disable", "ssh.socket"],
                                            ["/usr/bin/systemctl", "--root=/", "enable", "ssh.service"]])

    def test_invalid_firewall_stops_before_service_changes(self):
        run = Mock(side_effect=subprocess.CalledProcessError(1, "nft"))
        with self.assertRaises(subprocess.CalledProcessError):
            service.enable(run=run, active=True, live=False)
        self.assertEqual(run.call_count, 1)

    def test_missing_or_different_proc_root_is_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertFalse(service.running_system(root, root / "missing", root))
            child = root / "child"
            child.mkdir()
            self.assertFalse(service.running_system(root, child, root))
            self.assertTrue(service.running_system(root, root, root))

    def test_image_has_no_keys_and_both_installers_enable_ssh(self):
        self.assertFalse(list((CHROOT / "etc/ssh").glob("ssh_host_*_key*")))
        dropin = (CHROOT / "etc/systemd/system/ssh.service.d/60-kythos-live.conf").read_text()
        self.assertIn("ConditionPathExists=!/run/live/medium", dropin)
        self.assertIn("ConditionPathExists=!/run/live/overlay", dropin)
        self.assertIn("ExecStartPre=/usr/bin/ssh-keygen -A", dropin)
        for path in (ROOT / "config/hooks/live/030-configure-authentication.hook.chroot",
                     ROOT / "config/includes.installer/usr/lib/finish-install.d/93kythos-live-cleanup"):
            self.assertIn("kythos-enable-ssh --offline", path.read_text())
        policy = (CHROOT / "etc/nftables.d/kythos-input.nft").read_text()
        self.assertIn("tcp dport 22 accept", policy)

    def test_target_discards_copied_host_identity_but_preserves_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            ssh = Path(temp)
            for name in ("ssh_host_rsa_key", "ssh_host_rsa_key.pub", "ssh_host_ed25519_key.backup", "sshd_config"):
                (ssh / name).write_text("temporary fixture")
            (ssh / "ssh_host_ecdsa_key").symlink_to(ssh / "missing")
            target.remove_ssh_host_keys(ssh)
            self.assertEqual([path.name for path in ssh.iterdir()], ["sshd_config"])

    def test_unexpected_host_key_directory_fails_instead_of_recursive_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            ssh = Path(temp)
            (ssh / "ssh_host_rsa_key").mkdir()
            with self.assertRaises(ValueError):
                target.remove_ssh_host_keys(ssh)
            self.assertTrue((ssh / "ssh_host_rsa_key").is_dir())


class KeyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(mode=0o700)
        quiet = patch("sys.stdout", new=io.StringIO())
        quiet.start()
        self.addCleanup(quiet.stop)

    def test_default_generate_is_rsa4096_and_never_installs_anything(self):
        run = Mock()
        helper.generate(run=run, home=self.home)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][1:], ["-t", "rsa", "-b", "4096", "-f", str(self.ssh / "id_rsa")])
        self.assertNotIn("-N", run.call_args.args[0])

    def test_explicit_algorithm_and_file_are_preserved(self):
        run = Mock()
        path = self.ssh / "another-key"
        helper.generate("ed25519", str(path), "chosen comment", run=run)
        self.assertEqual(run.call_args.args[0][1:], ["-t", "ed25519", "-f", str(path), "-C", "chosen comment"])

    def test_existing_private_public_and_dangling_symlink_never_overwritten(self):
        for name in ("id_rsa", "id_rsa.pub"):
            for symlink in (False, True):
                path = self.ssh / name
                if symlink:
                    path.symlink_to(self.home / "nonexistent")
                else:
                    path.write_text("keep exactly")
                run = Mock()
                with self.assertRaisesRegex(ValueError, "preserved"):
                    helper.generate(run=run, home=self.home)
                run.assert_not_called()
                self.assertTrue(os.path.lexists(path))
                path.unlink()

    def test_install_uses_explicit_chosen_public_key_and_correct_command_no_sha1(self):
        public_fixture(self.ssh / "id_rsa.pub")
        intended = public_fixture(self.ssh / "chosen key.pub")
        run = Mock()
        self.assertEqual(helper.install("test@[2001:db8::1]", str(intended), 2222, True, run=run), 0)
        command = run.call_args.args[0]
        self.assertEqual(Path(command[0]).name, "ssh-copy-id")
        self.assertEqual(command[1:3], ["-i", str(intended)])
        self.assertEqual(command[-4:], ["-p", "2222", "--", "test@[2001:db8::1]"])
        self.assertIn("PubkeyAcceptedAlgorithms=-ssh-rsa", command)
        self.assertNotIn("+ssh-rsa", " ".join(command))

    def test_multiple_keys_require_explicit_selection(self):
        public_fixture(self.ssh / "id_rsa.pub")
        public_fixture(self.ssh / "id_ed25519.pub")
        run = Mock()
        with self.assertRaisesRegex(ValueError, "Several public keys"):
            helper.install("server", yes=True, home=self.home, run=run)
        run.assert_not_called()

    def test_missing_key_offers_generation_without_connecting(self):
        run = Mock()
        with patch.object(sys.stdin, "isatty", return_value=False):
            self.assertEqual(helper.install("server", yes=True, home=self.home, run=run), 2)
        run.assert_not_called()

    def test_interactive_generation_offer_stays_separate_from_installation(self):
        run = Mock()
        with patch.object(sys.stdin, "isatty", return_value=True):
            self.assertEqual(helper.install("server", home=self.home, run=run, prompt=lambda _: "yes"), 2)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(Path(run.call_args.args[0][0]).name, "ssh-keygen")

    def test_install_decline_or_unconfirmed_batch_never_connects(self):
        chosen = public_fixture(self.ssh / "id_rsa.pub")
        for interactive in (True, False):
            run = Mock()
            with patch.object(sys.stdin, "isatty", return_value=interactive):
                self.assertEqual(helper.install("server", str(chosen), run=run, prompt=lambda _: "no"), 2)
            self.assertEqual(run.call_count, 1)  # local fingerprint only

    def test_private_malformed_multiple_or_eval_unsafe_public_paths_rejected(self):
        for content in ("-----BEGIN OPENSSH PRIVATE KEY-----\n", "ssh-rsa INVALID\n", "ssh-ed25519 eHh4\n"):
            path = self.ssh / "bad.pub"
            path.write_text(content)
            with self.assertRaises(ValueError):
                helper.public_key(path)
        key = public_fixture(self.ssh / "multiple.pub")
        key.write_text(key.read_text() * 2)
        with self.assertRaises(ValueError):
            helper.public_key(key)
        key = public_fixture(self.ssh / "$(touch dangerous).pub")
        with self.assertRaisesRegex(ValueError, "metacharacters"):
            helper.public_key(key)

    def test_option_injection_and_invalid_port_are_rejected(self):
        for value in ("-oProxyCommand=bad", "user@host\ncommand", "user@host other", "host\x00bad"):
            with self.assertRaises(Exception):
                helper.destination(value)
        for value in ("0", "65536", "-1", "text"):
            with self.assertRaises(Exception):
                helper.port(value)

    def test_fifo_public_key_is_rejected_without_blocking_explicit_or_automatic_selection(self):
        fifo = self.ssh / "id_rsa.pub"
        os.mkfifo(fifo, 0o600)
        command = [sys.executable, str(CHROOT / "usr/local/bin/kythos-ssh"), "install", "--yes", "server"]
        explicit = subprocess.run(command + ["--public-key", str(fifo)], capture_output=True, text=True, timeout=15)
        self.assertEqual(explicit.returncode, 1)
        self.assertIn("regular file", explicit.stderr)
        automatic = subprocess.run(command, env=dict(os.environ, HOME=str(self.home)), capture_output=True, text=True, timeout=15)
        self.assertEqual(automatic.returncode, 2)
        self.assertIn("No suitable public key", automatic.stdout)


@unittest.skipUnless(shutil.which("sshd") and shutil.which("ssh") and shutil.which("ssh-keygen"),
                     "OpenSSH server/client binaries unavailable")
class NativeSSHTests(unittest.TestCase):
    def test_rsa4096_sha2_login_and_unique_host_keys_with_packaged_daemon(self):
        with tempfile.TemporaryDirectory(prefix="kythos-ssh-test-") as temp:
            root = Path(temp)
            client = root / "client"
            host = root / "host"
            other_host = root / "other-host"
            # Native ARM64 checks also run under full-system TCG in builders;
            # prime generation is variable and materially slower there.
            keygen_timeout = 120 if os.uname().machine == "aarch64" else 30
            subprocess.run(["ssh-keygen", "-q", "-t", "rsa", "-b", "4096", "-N", "", "-f", str(client)], check=True, timeout=keygen_timeout)
            for path in (host, other_host):
                subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True, timeout=15)
            self.assertNotEqual(host.with_suffix(".pub").read_text().split()[1], other_host.with_suffix(".pub").read_text().split()[1])
            fingerprint = subprocess.check_output(["ssh-keygen", "-lf", str(client) + ".pub"], text=True)
            self.assertTrue(fingerprint.startswith("4096 "), fingerprint)
            policy = CHROOT / "etc/ssh/sshd_config.d/10-kythos-authentication.conf"
            effective = subprocess.run([shutil.which("sshd"), "-T", "-f", str(policy), "-h", str(host)], text=True, capture_output=True)
            self.assertEqual(effective.returncode, 0, effective.stderr)
            settings = dict(line.split(" ", 1) for line in effective.stdout.splitlines() if " " in line)
            for name, expected in (("permitrootlogin", "no"), ("permitemptypasswords", "no"),
                                   ("passwordauthentication", "yes"), ("pubkeyauthentication", "yes")):
                self.assertEqual(settings[name], expected)
            for name in ("hostkeyalgorithms", "pubkeyacceptedalgorithms"):
                self.assertNotIn("ssh-rsa", settings[name].split(","))
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            config = root / "sshd_config"
            # The root-run builder needs PAM to permit public-key auth to its
            # password-locked account. Root access is enabled only for this
            # ephemeral loopback daemon; production policy is asserted above.
            root_runner = os.getuid() == 0
            fixture_pam = "yes" if root_runner else "no"
            fixture_root = "prohibit-password" if root_runner else "no"
            config.write_text(f"Port {port}\nListenAddress 127.0.0.1\nHostKey {host}\nPidFile {root / 'pid'}\n"
                              f"AuthorizedKeysFile {client}.pub\nStrictModes no\nUsePAM {fixture_pam}\nPermitRootLogin {fixture_root}\n"
                              "PasswordAuthentication no\nPubkeyAuthentication yes\nPubkeyAcceptedAlgorithms rsa-sha2-512,rsa-sha2-256\nLogLevel DEBUG1\n")
            log = root / "sshd.log"
            with log.open("w") as output:
                daemon = subprocess.Popen([shutil.which("sshd"), "-D", "-e", "-f", str(config)], stdout=output, stderr=output)
                try:
                    ready = False
                    for _ in range(100):
                        if daemon.poll() is not None:
                            break
                        try:
                            with socket.create_connection(("127.0.0.1", port), timeout=.1):
                                ready = True
                                break
                        except OSError:
                            time.sleep(.02)
                    self.assertTrue(ready, log.read_text())
                    host_type, host_blob = host.with_suffix(".pub").read_text().split()[:2]
                    known = root / "known_hosts"
                    known.write_text(f"[127.0.0.1]:{port} {host_type} {host_blob}\n")
                    result = subprocess.run(["ssh", "-F", "/dev/null", "-vv", "-p", str(port), "-i", str(client),
                                             "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "PubkeyAcceptedAlgorithms=rsa-sha2-512",
                                             "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known}",
                                             pwd.getpwuid(os.getuid()).pw_name + "@127.0.0.1", "printf 'KYTHOS_RSA_SHA2_OK\\n'"],
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr + "\n" + log.read_text())
                    self.assertEqual(result.stdout.strip(), "KYTHOS_RSA_SHA2_OK")
                    self.assertIn("rsa-sha2-512", result.stderr)
                finally:
                    daemon.terminate()
                    try:
                        daemon.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        daemon.kill()
                        daemon.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
