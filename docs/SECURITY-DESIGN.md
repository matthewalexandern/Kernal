# KythOS Kernal security design

## Trust base

KythOS uses Debian 13 packages fetched through HTTPS and authenticated by
Debian archive signatures. The image keeps Debian's signed stock kernel and
module packages. Secure Boot is explicitly required during image assembly;
the build must fail if signed UEFI boot packages are unavailable.

Secure Boot authenticates the installed boot chain. Release checksums must
also be signed because Secure Boot does not authenticate a downloaded ISO.

## Common controls

- AppArmor remains enabled on installed systems using supported kernel and
  package profiles. Experimental blanket profiles are excluded. The stock
  service intentionally skips the ephemeral live overlay; release evidence
  records that live-session exception instead of presenting it as enforced.
- Audit rules record changes to identity, sudo, APT, firewall, policy, and
  kernel module state without blocking those operations.
- nftables drops unsolicited inbound traffic. Loopback, established traffic,
  ICMP/ICMPv6, DHCP replies, outbound traffic, and forwarding remain usable.
  Editions own the forwarding and inbound exceptions required by their roles.
  Starting, reloading, or stopping the service only changes the KythOS-owned
  table; it does not flush tables installed by libvirt or container engines.
- The unattended updater installs authenticated stable and security
  updates without forcing an automatic reboot or removing fallback kernels.
- Persistent compressed journals have bounded disk and time retention.
- Conservative sysctl settings reduce kernel pointer and log exposure and
  reject redirects/source routing. Reverse-path filtering is untouched so
  bridges, containers, asymmetric routing, and multihoming keep working.

## Compatibility boundaries

The common base does not disable kernel modules, USB, user namespaces,
virtualization extensions, packet-forwarding capability, core dumps, kexec,
or debugging tools. Those controls can break a desktop, container host,
hypervisor, or AI profiling workload and require edition-level testing.

Software-only encrypted LVM protects powered-off data, but its classic
unencrypted `/boot` cannot authenticate the initramfs passphrase prompt. An
attacker with physical write access can replace that prompt and capture the
passphrase on the next normal boot. Operators must verify the boot files from
trusted media after a device leaves their control.

The base installs SSH with ordinary user password and public-key
authentication, while prohibiting root and empty-password login. It opens no
inbound service port; editions add explicit rules. The no-complexity/no-expiry
password choice is a documented STIG deviation. NVIDIA drivers remain
edition-selected and require DKMS/MOK enrollment under Secure Boot.

Optional FIDO2 local-console login uses a root-owned credential mapping and a
PAM include scoped to `login`. Enrollment requires physical presence plus a
key PIN or built-in verification, and a real authentication using only the
new credential before activation. Password authentication remains the fallback.
The common PAM stack and SSH do not gain server-side security-key prompts.
Authentication configuration changes are covered by the existing PAM and
security-directory audit watches. Disk encryption is configured separately.

The optional TPM2 unlock policy measures the UEFI boot path, GRUB commands,
kernel command line, kernel, initramfs, and MOK state. A changed measurement
blocks automatic key release. Enrollment requires the parsed event log to
replay to every selected live PCR, checks GRUB kernel and initramfs events, and
compares the boot files to the snapshot created before the required reboot.
Recovery material is written only to a direct disk or partition backed by one
detected removable or external physical disk on a different backing device;
composite storage is rejected. The material is flushed before the helper
reports success. The classic
shim and GRUB path does not
authenticate the separate initramfs before it can ask for a fallback secret,
so an unexpected passphrase prompt is treated as a physical-tampering event;
the operator must power off and inspect the boot files from trusted media.

The bundled OpenSSL FIPS provider configuration is opt-in and self-tested. It
does not globally change cryptography and is not a claim that the complete
operating system or Debian's rebuilt provider has a CMVP certificate. See the
compliance document for the exact boundary and STIG deviations.

The raw pre-release image installs KythOS policy files directly into the filesystem.
Before the first supported public release, those files must move into a
versioned `kythos-base-config` Debian package delivered from a signed APT
repository so installed systems can receive policy fixes and verify ownership.

## Release evidence

Every release needs the binary ISO, corresponding source ISO, build log,
live-build configuration dump, live-image package manifest, a separately
captured installed-system package manifest, checksums, signed tag, and a
detached signature over the checksum file. Release validation must also check
that every distributed binary has corresponding source where its license
requires it.
