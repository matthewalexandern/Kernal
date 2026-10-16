# Encryption, SSH, and `cy`

## Full-disk encryption choices

Calamares offers native guided and manual partitioning, optional LUKS2 root
encryption, and swap choices. Manual partitioning lets you edit sizes and
mount points. **Use entire disk** automatically creates, formats, and mounts
the required partitions on the selected disk and erases all data there.
With encrypted root, use a separate unencrypted `/boot` and
encrypted swap, a swap file inside encrypted root, or no swap. The EFI System
Partition also remains unencrypted. The guided `/boot` size is a suggestion;
it does not fix the sizes in the manual editor. The native partition module
validates boot and swap constraints before executing disk jobs.

The advanced graphical and text installers also offer guided encrypted LVM.
For software-only encryption, choose a nonempty passphrase and do not run
TPM enrollment after installation. An encrypted LVM volume can contain root
and swap while `/boot` and the EFI System Partition remain outside it.

Software-only mode protects data at rest after a powered-off device is lost or
stolen, but it does not authenticate the unencrypted boot files or the
initramfs passphrase prompt. A physical attacker who can modify `/boot` can
replace that prompt and capture the passphrase on the next ordinary boot. Use
trusted recovery media to verify or restore the EFI System Partition and
`/boot` after the device leaves your control. The optional measured TPM2 path
below adds a boot-state signal, but the classic separate-initramfs design still
requires the unexpected-prompt handling described later in this document.

TPM2 unlock is an optional post-install step. KythOS uses Debian 13's packaged
Clevis TPM2 support and `clevis-initramfs`, which is the `initramfs-tools`
integration used by this image. Enrollment never removes the installer
passphrase. It first creates and verifies a separate 256-bit recovery key, then
adds a measured TPM2 binding and backs up the final LUKS2 header.

KythOS does not use a PCR-7-only convenience binding. The policy uses the
SHA-256 bank and PCRs 4, 7, 8, 9, and 14. On the signed shim and GRUB path,
those measurements cover the boot applications, Secure Boot policy, GRUB
commands and kernel command line, files GRUB reads such as the kernel and
initramfs, and shim/MOK state. Enrollment fails if PCR 8 or 9 is unmeasured or
missing from the TPM event log. It also replays the event log and requires its
SHA-256 values for every bound PCR to match the live TPM, plus explicit GRUB
command, kernel, and initramfs events.

Identify the LUKS container carefully:

```sh
sudo cryptsetup status cryptroot
sudo blkid -t TYPE=crypto_LUKS -o device
```

Prepare the measured boot artifacts, reboot, and unlock once with the normal
LUKS passphrase:

```sh
sudo kythos-enroll-tpm2 --prepare
sudo reboot
```

Preparation records a content and metadata digest of `/boot` and a separately
mounted EFI System Partition, excluding only GRUB's mutable `grubenv`. The
enrollment command compares that snapshot after reboot and immediately around
the sealing operation. It fails closed when a configured boot filesystem is
not mounted or the snapshot changed.

After reboot, mount removable media below a root-owned path and ensure every directory in
the path is owned by root and is not writable by a group or other users. This
allows the helper to pin the checked directory and block device for the entire
transaction. All recovery writes and flushes use those open references, so an
unmount, remount, or reused device path cannot redirect an in-progress write.
For example:

```sh
sudo install -d -o root -g root -m 0700 /mnt/kythos-recovery
sudo mount /dev/sdX1 /mnt/kythos-recovery
sudo chown root:root /mnt/kythos-recovery
sudo chmod go-w /mnt/kythos-recovery
sudo kythos-enroll-tpm2 /dev/nvme0n1p3 \
  /mnt/kythos-recovery/kythos-root-recovery.key
```

The command requires a LUKS2 volume, a working TPM2, enabled UEFI Secure Boot,
the EFI System Partition mounted at `/boot/efi`, and an event log whose replay
matches the live TPM and shows the required SHA-256 GRUB measurements. The
recovery destination must be a separately mounted, read-write block filesystem
on a direct disk or partition backed by exactly one physical disk. That disk
must be reported by the kernel as removable, USB, or FireWire storage. An SD
card qualifies through its removable-device flag; internal eMMC does not
qualify merely because its transport is MMC. Device-mapper, LVM, MD RAID, and
other composite or multi-device recovery filesystems are refused, even when
one or all members are external. The recovery disk must not share a backing
device with the LUKS volume. This
prevents a missing USB mount from silently placing the key on the system disk.
The helper flushes both recovery files and the block device before success;
unmount the filesystem cleanly before removing it.

Only one KythOS TPM enrollment transaction can operate on a LUKS device at a
time. The helper holds a device-specific lock from validation through commit or
rollback. Do not run separate `cryptsetup` or `clevis` mutation commands against
that volume while enrollment is in progress; those tools do not participate in
the KythOS transaction lock.

The measured policy is intentionally strict. Firmware, db/dbx, shim, GRUB,
kernel, initramfs, GRUB configuration, kernel command-line, and MOK changes can
send the next boot to the passphrase prompt. This includes some NVIDIA DKMS or
MOK changes. After making such a change, use the passphrase to boot, then run:

```sh
sudo kythos-enroll-tpm2 --prepare
sudo reboot
# Unlock this boot with the passphrase, remount the offline recovery media,
# then reseal every existing Clevis TPM slot to the verified new measurements.
sudo kythos-enroll-tpm2 --rebind /dev/nvme0n1p3 \
  /mnt/kythos-recovery/kythos-root-recovery.key
```

Treat a passphrase prompt that you did not expect as a boot-integrity alarm.
PCR binding prevents the TPM from automatically releasing its key after the
measured boot state changes, but the classic signed shim and GRUB path does not
authenticate its separate initramfs before that initramfs can display a
prompt. An attacker with physical write access could replace it with a fake
prompt. Power off instead of entering any passphrase, boot trusted recovery
media, and inspect or restore the EFI System Partition and `/boot`. Enter a
fallback passphrase only when you initiated the measured change or have
verified the boot files from trusted media.

Before changing any LUKS key or Clevis slot, the helper writes and flushes a
temporary pre-operation header backup to the recovery media. Any later command,
measurement, policy, or snapshot failure triggers an automatic restoration of
that complete header, including a multi-slot rebind that failed part way
through. Cleanup ignores further termination signals while it restores the
header, and header publication is an atomic no-replace operation. The temporary
rollback file is removed only after the final header backup and recovery key are
durable. If automatic restoration itself fails, the helper preserves both the
rollback header and recovery key and prints their path for recovery from trusted
media.

The rebind operation also uses Clevis's per-edit backup/restore path, verifies
each resealed slot by unsealing it under the current PCR state, and writes a new
offline LUKS header backup. Enter an existing passphrase if the old TPM policy
can no longer unseal. Store every generated header backup and the recovery key
offline. Anyone who obtains the recovery key and disk can decrypt the system.

Before relying on automatic unlock, verify the recovery material and retain a
second copy in a physically separate secure location:

```sh
sudo cryptsetup open --test-passphrase --disable-external-tokens \
  --key-file /mnt/kythos-recovery/kythos-root-recovery.key \
  /dev/nvme0n1p3
```

Debian's installer documents guided encrypted LVM in its
[installation guide](https://www.debian.org/releases/trixie/amd64/ch06s03.en.html),
and Debian describes `clevis-initramfs` as its early-boot LUKS integration in
the [package record](https://packages.debian.org/trixie/clevis-initramfs).

## FIDO2 local login

The installed common base includes an optional FIDO2 authentication path for
local console login. A password remains available for recovery, sudo, and
password SSH. Enrollment is performed on the installed system with a physical
authenticator; it is not available in the live installer:

```sh
sudo kythos-fido-login enroll USER
# For an authenticator with built-in verification, such as a biometric sensor:
sudo kythos-fido-login enroll USER --verification uv
sudo kythos-fido-login status USER
```

The default requires the key's PIN and physical presence. Enrollment registers
a credential, proves that newly registered credential through a temporary PAM
service, and only then activates the root-owned mapping and local-login PAM
include. Failed enrollment leaves password login in place. Register a spare
key by repeating enrollment. Keep the recovery password available.

To remove a user's mappings or restore the pre-enrollment login configuration:

```sh
sudo kythos-fido-login disable USER
sudo kythos-fido-login recover
```

This console login setting does not unlock an encrypted disk. TPM2 disk
unlock is configured separately as described above. Local-device PAM prompts
are not added to SSH; use OpenSSH's `ed25519-sk` or `ecdsa-sk` public keys for
security-key SSH authentication. `kythos-fido-login ssh-guide` prints the
client-side commands.

## SSH password behavior

OpenSSH is installed and enabled. Ordinary users may authenticate with a
nonempty password or a public key over IPv4 or IPv6. Root login and empty
password authentication are disabled. KythOS does not force composition,
length, rotation, expiration, or password history rules.

The common firewall still has no inbound SSH exception. A server or other
edition must deliberately add `tcp dport 22 accept` to
`/etc/nftables.d/kythos-input.nft` before remote clients can connect. This
keeps the shared image closed while allowing the same SSH configuration to be
used when an edition opens the port.

## Package management with `cy`

Use `cy` for interactive package management:

```sh
cy help
cy search package-name
cy show package-name
cy list --installed
sudo cy update
sudo cy install package-name
sudo cy full-upgrade
sudo cy remove package-name
```

`cy` passes arguments directly to the packaged `/usr/bin/apt` implementation
without shell evaluation. It refuses command-line switches that bypass package
authentication or permit removal of essential or held packages. It also
refuses alternate APT configuration files and inline configuration overrides,
which could indirectly disable those protections. Local `.deb` paths and
package URI operands are rejected because they do not inherit repository
signature verification. An administrator must verify local-package origin and
integrity through a separate deliberate workflow. The `apt` binary remains
installed because system services and third-party package scripts depend on
the standard Debian interface; `cy` is the KythOS operator command.

`cy`, `cy help`, and `cy --help` display KythOS command examples. Version and
package output retain the real backend and repository provenance. In an
authenticated root shell, use `cy update` without another `sudo`.

## Administrator command lookup

Login shells include `/usr/local/sbin`, `/usr/sbin`, and `/sbin` so commands
such as `useradd` can be found from an ordinary account. Creating or changing
accounts still requires administrator permission, for example
`sudo useradd --create-home account-name`. `sudo su` remains available to a
sudo-authorized administrator; `sudo -i` also opens a root login shell.
The root account stays locked for direct password login. A PATH change does
not grant privileges or change authentication policy.
