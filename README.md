# KythOS Kernal

KythOS Kernal is the security-first Debian 13 (`trixie`) common base for four
planned editions: desktop, server, hypervisor, and bare-metal AI server. It
uses Debian's signed stock `linux-image-amd64` kernel and complete packaged
module tree. It does not compile, trim, or rename the Linux kernel.

The current target is the raw amd64 base. Edition-specific applications and
services come later. This pre-release line is a buildable prototype; a supported public
release also requires a signed KythOS APT repository and a versioned base-config
package so installed systems receive KythOS policy updates.

## Base guarantees

- Stock Debian kernel, modules, CPU microcode, and broad Debian firmware.
- BIOS and UEFI boot, with signed shim/GRUB/kernel support for Secure Boot.
- Graphical and text Debian installer with encrypted-storage support.
- AppArmor, audit logging, authenticated APT, automatic security updates,
  persistent journals, and a default-deny inbound nftables policy.
- Wired and wireless networking, common filesystems, LVM, software RAID,
  NVMe tooling, Bluetooth, and signed `fwupd` support.
- No remote login service, listening application, desktop, hypervisor, AI
  runtime, proprietary NVIDIA driver, or custom kernel in the common base.

The baseline leaves kernel modules, user namespaces, virtualization, network
forwarding capability, outbound traffic, and bridge support available. Each
edition adds only the inbound and forwarding rules and packages it needs.

## Build

Build in Debian 13 amd64 with root privileges, `live-build`, `debootstrap`,
`squashfs-tools`, `xorriso`, and `rsync`:

```sh
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso rsync
sudo ./scripts/build.sh
```

The build produces a hybrid binary ISO, a corresponding source ISO, a live
package manifest, a configuration dump, logs, and SHA-256 checksums under
`artifacts/`. See [BUILDING.md](docs/BUILDING.md) for the isolated builder and
test workflow.

## Validate the recipe

```sh
./scripts/validate-source.sh
```

After installation, inspect the common security controls with:

```sh
sudo kythos-security-status
```

## Scope and hardware support

The base deliberately retains Debian's complete amd64 kernel modules and
firmware discovery. A successful VM boot cannot prove physical device support.
Release acceptance therefore includes storage, networking, display, audio,
suspend/resume, firmware loading, and Secure Boot tests on real hardware.

The proprietary NVIDIA driver is an edition-level component. It needs a tested
Debian package branch plus DKMS/MOK signing under Secure Boot; it is not safe to
claim NVIDIA support from the base ISO alone.

## Project documents

- [Security design](docs/SECURITY-DESIGN.md)
- [Building and testing](docs/BUILDING.md)
- [Release checklist](docs/RELEASE-CHECKLIST.md)
- [Security reporting](SECURITY.md)

KythOS-owned build scripts and documentation are released under the MIT
license. Debian packages and firmware retain their upstream licenses.
