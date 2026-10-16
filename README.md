# KythOS Kernal

KythOS Kernal is the security-first Debian 13 (`trixie`) compatible common
base for four planned editions: desktop, server, hypervisor, and bare-metal AI
server. It uses the signed stock `linux-image-amd64` kernel and complete
packaged module tree. It does not compile, trim, or rename the Linux kernel.

The current target is the raw amd64 base. Edition-specific applications and
services come later. This pre-release line is a buildable prototype; a supported public
release also requires a signed KythOS APT repository and a versioned base-config
package so installed systems receive KythOS policy updates.

An experimental [ARM64 build path](docs/ARM64.md) uses the same source and
common configuration, with architecture profiles selecting the stock kernel
and boot packages. ARM64 and Parallels installation acceptance are still
required before that image can be described as supported.

## Base guarantees

- Stock signed kernel, complete modules, CPU microcode, and broad firmware
  coverage, with license-gated legacy payloads kept on an explicit user
  acceptance path.
- BIOS and UEFI boot, with signed shim/GRUB/kernel support for Secure Boot.
- Text-free KythOS boot artwork, including an animated cyan mark during the
  installed-system Plymouth stage. Calamares and a separate native setup
  guide run in a temporary live graphical session; advanced graphical and
  text installer paths remain available.
- Software-passphrase encrypted installation and an optional, recovery-safe
  TPM2 enrollment command for an installed LUKS2 system.
- AppArmor on installed systems, audit logging, authenticated package sources,
  automatic security updates, persistent journals, AIDE, and a default-deny
  inbound nftables policy.
- Wired and wireless networking, common filesystems, LVM, software RAID,
  NVMe tooling, Bluetooth, and signed `fwupd` support.
- Managed Ethernet adapters, including USB adapters, automatically connect
  using DHCP. Configured static profiles take precedence. Wi-Fi uses DHCP
  after joining a configured network.
- Password-capable SSH with root and empty-password login prohibited. The
  common firewall keeps port 22 closed until an edition explicitly opens it.
- Optional FIDO2 key login at the local console, with verified enrollment and
  the account password retained for recovery. SSH supports native security-key
  public keys independently.
- Opt-in OpenSSL FIPS-provider tooling and initial STIG-derived hardening with
  a partial mapping to selected Ubuntu 24.04 controls. The baseline has not
  been assessed or approved as a STIG baseline, and the provider is not
  represented as formally validated.
- NVIDIA headers, DKMS, MOK, firmware, and detection tooling without forcing a
  single driver family onto incompatible GPUs.
- Original local command suggestions for interactive Bash: request a preview
  with Tab, accept it with Tab or Right Arrow, and execute with Enter. Installed
  command discovery and F1 contextual help use the system's local manuals;
  normal Bash completion remains available.
- A fixed local-console header and matching hostname color, with the command
  area sized separately so terminal applications retain their controls.
- Regular, nonbold console styling with the original text-console font.
- Kernel diagnostics on a dedicated text console, keeping driver errors
  available without scrolling the login terminal's header.
- No installed desktop, hypervisor, AI runtime, proprietary NVIDIA driver, or
  custom kernel in the common base. The installation interface is removed
  from installed targets.

The baseline leaves kernel modules, user namespaces, virtualization, network
forwarding capability, outbound traffic, and bridge support available. Each
edition adds only the inbound and forwarding rules and packages it needs.

## Build

Build in Debian 13 amd64 with root privileges, `live-build`, `debootstrap`,
`squashfs-tools`, `xorriso`, and `rsync`:

These bootstrap commands run on a standard Debian build host. Use `cy` for
interactive package management inside the installed KythOS system.

```sh
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso rsync python3-pil python3-yaml python3-jsonschema build-essential patch
sudo apt build-dep calamares
sudo ./scripts/build.sh
```

The build produces a hybrid binary ISO, a corresponding source ISO, exact
binary-to-source coverage evidence, package manifests, a configuration dump,
logs, licenses, and SHA-256 checksums. See
[BUILDING.md](docs/BUILDING.md) for the isolated builder and test workflow.

## Installation

Choose **Install KythOS Kernal (Calamares)** in the boot menu. A separate
KythOS setup guide shows detected hardware and explains the installation
choices, then starts Calamares. The guide does not collect or save passwords,
accounts, partition selections, or a simulated installation plan. Enter those
choices in Calamares and review its summary before installation.

Calamares exposes its native erase, alongside, replacement, and manual
partitioning choices when applicable to the detected disk. Manual partitioning
lets you create and edit filesystem sizes and mount points. **Use entire disk**
automatically creates, formats, and mounts the required partitions on the
selected disk, erasing all data on that disk. The guided layout
suggests a 2 GiB `/boot`; this is not the root filesystem size or a manual size
limit. Optional LUKS2 root encryption requires a separate unencrypted `/boot`
and encrypted swap, a swap file inside encrypted root, or no swap. A native
validation step checks the proposed layout before partition jobs begin.
The advanced graphical and text installers remain available for their
additional storage and accessibility workflows. TPM2 enrollment is optional
after installation.

The console-only common base requires login by default. Checking Calamares'
automatic-login option explicitly enables local tty1 login for the chosen
ordinary user; it does not open SSH or enable root login. All accounts still
receive a nonempty password for authentication and sudo.

**Start KythOS Kernal** opens the live console. Run `kythos-installer` there
to open the setup guide, or use `kythos-install` from the graphical session
to open Calamares directly. The four edition package sets are future work.

## Validate the recipe

```sh
./scripts/validate-source.sh
```

After installation, inspect the common security controls with:

```sh
sudo kythos-security-status
kythos-hardware-status
```

After installation, enroll and verify a physical FIDO2 key with
`sudo kythos-fido-login enroll USER`. Enrollment requests the key's PIN and
touch by default, then requires a real authentication before enabling it.

## Scope and hardware support

The base deliberately retains Debian's complete amd64 kernel modules and
firmware discovery. A successful VM boot cannot prove physical device support.
Release acceptance therefore includes storage, networking, display, audio,
suspend/resume, firmware loading, and Secure Boot tests on real hardware.

The proprietary NVIDIA driver is an edition-level component. The base includes
the prerequisites and a readiness command, but the exact packaged driver still
needs selection and a DKMS/MOK test on the target GPU. Legacy Broadcom b43
firmware whose license prohibits redistribution is installed by the device
owner after installation rather than embedded in the public ISO. Intel
`ipw2x00` and Hauppauge `ivtv` firmware also remain user-selected because their
packages require the recipient to accept separate license terms.

## Project documents

- [Security design](docs/SECURITY-DESIGN.md)
- [Compliance position and STIG map](docs/COMPLIANCE.md)
- [Encryption, SSH, and `cy`](docs/ENCRYPTION-SSH-CY.md)
- [NVIDIA driver path](docs/NVIDIA.md)
- [Network defaults](docs/NETWORKING.md)
- [Command suggestions](docs/COMMAND-SUGGESTIONS.md)
- [Console appearance](docs/CONSOLE.md)
- [Building and testing](docs/BUILDING.md)
- [Shared source on Ubuntu and Mac](docs/SOURCE-SYNC.md)
- [Cloud and different-device continuation](docs/CLOUD-CONTINUATION.md)
- [Identity and retained upstream references](docs/BRANDING.md)
- [Release checklist](docs/RELEASE-CHECKLIST.md)
- [Security reporting](SECURITY.md)

KythOS-owned build scripts and documentation are released under the MIT
license. The modified Calamares partition plugin and its patch retain
Calamares' GPL license. Packages and firmware retain their upstream licenses.

KythOS Kernal is not affiliated with or endorsed by **Debian**. **Debian** is a
registered trademark owned by Software in the Public Interest, Inc.
