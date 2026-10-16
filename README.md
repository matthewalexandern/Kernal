# KythOS Kernal

KythOS Kernal is the security-first Debian 13 (`trixie`) compatible common
base for four planned editions: desktop, server, hypervisor, and bare-metal AI
server. It uses the signed stock `linux-image-amd64` kernel and complete
packaged module tree. It does not compile, trim, or rename the Linux kernel.

The current target is the raw amd64 base. Edition-specific applications and
services come later. This pre-release line is a buildable prototype; a supported public
release also requires a signed KythOS APT repository and a versioned base-config
package so installed systems receive KythOS policy updates.

## Base guarantees

- Stock signed kernel, complete modules, CPU microcode, and broad firmware
  coverage, with license-gated legacy payloads kept on an explicit user
  acceptance path.
- BIOS and UEFI boot, with signed shim/GRUB/kernel support for Secure Boot.
- Text-free KythOS boot artwork, including an animated cyan mark during the
  installed-system Plymouth stage, plus graphical and text installer paths.
- Software-passphrase encrypted installation and an optional, recovery-safe
  TPM2 enrollment command for an installed LUKS2 system.
- AppArmor on installed systems, audit logging, authenticated package sources,
  automatic security updates, persistent journals, AIDE, and a default-deny
  inbound nftables policy.
- Wired and wireless networking, common filesystems, LVM, software RAID,
  NVMe tooling, Bluetooth, and signed `fwupd` support.
- Password-capable SSH with root and empty-password login prohibited. The
  common firewall keeps port 22 closed until an edition explicitly opens it.
- Opt-in OpenSSL FIPS-provider tooling and initial STIG-derived hardening with
  a partial mapping to selected Ubuntu 24.04 controls. The baseline has not
  been assessed or approved as a STIG baseline, and the provider is not
  represented as formally validated.
- NVIDIA headers, DKMS, MOK, firmware, and detection tooling without forcing a
  single driver family onto incompatible GPUs.
- No desktop, hypervisor, AI runtime, proprietary NVIDIA driver, or custom
  kernel in the common base.

The baseline leaves kernel modules, user namespaces, virtualization, network
forwarding capability, outbound traffic, and bridge support available. Each
edition adds only the inbound and forwarding rules and packages it needs.

## Build

Build in Debian 13 amd64 with root privileges, `live-build`, `debootstrap`,
`squashfs-tools`, `xorriso`, and `rsync`:

```sh
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso rsync python3-pil
sudo ./scripts/build.sh
```

The build produces a hybrid binary ISO, a corresponding source ISO, exact
binary-to-source coverage evidence, package manifests, a configuration dump,
logs, licenses, and SHA-256 checksums. See
[BUILDING.md](docs/BUILDING.md) for the isolated builder and test workflow.

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
- [Building and testing](docs/BUILDING.md)
- [Release checklist](docs/RELEASE-CHECKLIST.md)
- [Security reporting](SECURITY.md)

KythOS-owned build scripts and documentation are released under the MIT
license. Debian packages and firmware retain their upstream licenses.

KythOS Kernal is not affiliated with or endorsed by **Debian**. **Debian** is a
registered trademark owned by Software in the Public Interest, Inc.
