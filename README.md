# KythOS Kernal™ 2027

https://kythos.ai

KythOS Kernal is a Debian 13 (`trixie`) derivative. The **0.2.0** source line
adds white branding, installed-system SSH access, offline command assistance,
terminal navigation and appearance, a Wi-Fi launcher, and a separate desktop
profile. The requested product year is 2027; the software version is 0.2.0.
The stock `linux-image-amd64` or `linux-image-arm64` kernel and complete packaged
module tree remain intact.

The default target is the console **base** edition on **amd64 and ARM64**.
The optional **desktop** profile retains XFCE and adds graphical networking,
smart-card integration, and virtual-machine desktop components. Each selected
edition is built as its own ISO; the normal boot menu has no edition selector.
Server, hypervisor, and AI-server workloads remain product directions rather
than finished edition profiles. Profile/architecture combinations in the
recipe are not evidence that matching images have been built or tested.

This is a pre-release implementation candidate. See the
[0.2.0 change and acceptance matrix](docs/2027-CHANGES.md) for completed source
work, evidence boundaries, and outstanding ISO/VM/hardware checks. Existing
0.1.0 images remain unchanged and do not contain these changes. A supported
public release also requires a signed KythOS APT repository and a versioned
base-config package so installed systems receive KythOS policy updates.

## Recipe capabilities

- Stock signed kernel, complete modules, CPU microcode, and broad firmware
  coverage, with license-gated legacy payloads kept on an explicit user
  acceptance path.
- BIOS and UEFI paths on amd64, and UEFI on ARM64, with matching signed
  shim/GRUB/kernel components. Secure Boot requires separate boot acceptance.
- Crisp white shield artwork preserving the original 9:06 hand geometry,
  with small product text in the lower-right of the normal boot screen.
  Plymouth keeps diagnostics and recovery accessible. Calamares and a native setup
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
- SSH installed and enabled on installed systems, with inbound TCP port 22
  allowed on IPv4 and IPv6. Root/empty-password login remains prohibited.
  Each installation generates its own host keys. The temporary live installer
  account remains local-only; the SSH service does not run in that session.
- An explicit SSH key workflow defaults to RSA 4096, preserves existing keys,
  and installs the selected public key with `ssh-copy-id -i`. Modern RSA SHA-2
  authentication is used without enabling obsolete SHA-1 signatures.
- Optional FIDO2 key login at the local console, with verified enrollment and
  the account password retained for recovery. SSH supports native security-key
  public keys independently.
- Opt-in OpenSSL FIPS-provider tooling and initial STIG-derived hardening with
  a partial mapping to selected Ubuntu 24.04 controls. The baseline has not
  been assessed or approved as a STIG baseline, and the provider is not
  represented as formally validated.
- NVIDIA headers, DKMS, MOK, firmware, and detection tooling without forcing a
  single driver family onto incompatible GPUs.
- Offline command assistance discovers installed executables and current-shell
  names/completion metadata, grounds explanations in local documentation and
  available installed-version evidence, and previews corrections. F1 inspects
  the current line; ordinary completion remains available. Proposals never
  execute automatically, and uncertain syntax receives an explicit limitation.
- White foreground on a dark background, a dynamic actual-terminal banner,
  and dark/light/monochrome/blue/teal/high-contrast appearance choices during
  installation and afterward. The original console font is retained, with a
  readable `[TM]` trademark fallback.
- Persistent shared Bash history, Up/Down recall and Ctrl+R search, with custom
  bindings preserved. Managed-console output scrollback is separate and opens
  with Shift+PageUp or `kythos-console scrollback`.
- A case-sensitive PATH symlink named exactly `WiFi`, opening the graphical
  NetworkManager editor in a desktop session or `nmtui` on a TTY, with useful
  adapter/radio/dependency diagnostics.
- Kernel diagnostics on a dedicated text console, keeping driver errors
  available without scrolling the login terminal's header.
- No installed desktop, hypervisor, AI runtime, proprietary NVIDIA driver, or
  custom kernel in the common base. The installation interface is removed
  from installed targets.

The baseline leaves kernel modules, user namespaces, virtualization, network
forwarding capability, outbound traffic, and bridge support available. Each
edition adds only the additional inbound/forwarding rules and packages it needs.
The desktop profile adds OpenSC/PCSC/CCID/p11-kit and Firefox PKCS#11
registration without requiring a smart card for login. Its Mesa/virtual-display
drivers and guest agents provide applicable integration components; they do
not establish Apple-host acceleration, resizing, or physical GPU passthrough.

## Build

Build in a matching Debian 13 guest with root privileges, `live-build`, `debootstrap`,
`squashfs-tools`, `xorriso`, and `rsync`:

These bootstrap commands run on a standard Debian build host. Use `cy` for
interactive package management inside the installed KythOS system.

```sh
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso rsync python3-pil python3-yaml python3-jsonschema build-essential patch
sudo apt build-dep calamares
sudo ./scripts/build.sh
# On a matching ARM64 Debian guest:
sudo ./scripts/build-arm64.sh
# Optional separate desktop image, on a matching amd64 guest:
sudo env KYTHOS_EDITION=desktop ./scripts/build.sh
# On a matching ARM64 guest instead:
sudo env KYTHOS_EDITION=desktop ./scripts/build-arm64.sh
```

The build produces a hybrid binary ISO, a corresponding source ISO, exact
binary-to-source coverage evidence, package manifests, a configuration dump,
logs, licenses, and SHA-256 checksums. See
[BUILDING.md](docs/BUILDING.md) and the [ARM64 workflow](docs/ARM64.md) for
architecture-specific prerequisites, isolated builders, edition selection,
and acceptance. Both architecture builds must use the same reviewed clean
source commit. These commands describe the build workflow, not completed
0.2.0 artifacts.

## Installation

Choose **Install KythOS Kernal™ 2027 (Calamares)** in the boot menu. A separate
KythOS setup guide shows detected hardware and explains the installation
choices, then starts Calamares. The guide does not collect or save passwords,
accounts, partition selections, or an installation plan; it saves only the
selected terminal appearance. Enter installation choices in Calamares and
review its summary before installation.

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
ordinary user. This option does not change SSH authentication or enable root
login. All accounts still receive a nonempty password for authentication and sudo.

**Start KythOS Kernal™ 2027** opens the live console. Run `kythos-installer` there
to open the setup guide, or use `kythos-install` from the graphical session
to open Calamares directly. Boot the separate desktop ISO when an installed
GUI is wanted. Existing recovery and troubleshooting installer entries remain.

## Daily use

Connect to the installed account from another machine:

```sh
ssh USER@TARGET_ADDRESS
```

SSH starts automatically after installation. Check network reachability, VM
NAT/forwarding, and `systemctl status ssh.service` if a connection fails.
`sudo kythos-enable-ssh` both enables and starts it on a running installed
system; `--offline` only enables it for an image/chroot. The helper preserves
the live-installer service guard and does not expose its temporary account.
See [SSH and key setup](docs/ENCRYPTION-SSH-CY.md).

Generate and install user keys as separate actions:

```sh
kythos-ssh generate
kythos-ssh install --public-key ~/.ssh/id_rsa.pub USER@TARGET_ADDRESS
# Explicit alternative for a new identity:
kythos-ssh generate --type ed25519
```

The default generation is RSA 4096 and never overwrites an existing key.
Installation previews the selected fingerprint and `ssh-copy-id -i` command
before asking for confirmation. Missing keys prompt a generation offer; they
are not silently generated and installed together.

```sh
WiFi
WiFi --tty
kythos-theme --list
kythos-theme teal
kythos-assist --explain 'ls --all ./documents | grep invoice > matches.txt'
kythos-assist --complete 'systemctl --no'
kythos-assist --intent 'show network interfaces'
kythos-assist --diagnose --status 127 'missing-tool argument'
```

Use Up/Down for command history and Ctrl+R for reverse search in the default
Bash editing mode. Use the terminal's native output scrollback, or
Shift+PageUp in the managed local console; q/Esc returns from that view.
Assistance works offline, never runs an inspected command to obtain help, and
does not send shell data to an AI service. Local documentation may be absent
or incomplete; the helper reports uncertainty rather than inventing flags.

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

The base deliberately retains Debian's complete architecture-specific kernel
modules and firmware discovery. A successful VM boot cannot prove physical device support.
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
- [Console appearance and navigation](docs/CONSOLE.md)
- [Wi-Fi launcher](docs/WIFI.md)
- [Desktop smart cards](docs/SMART-CARDS.md)
- [Apple-hosted virtualization and graphics](docs/APPLE-VIRTUALIZATION.md)
- [0.2.0 changes and acceptance matrix](docs/2027-CHANGES.md)
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
