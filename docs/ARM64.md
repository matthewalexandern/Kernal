# ARM64 build and validation

ARM64 support is experimental. Package availability and recipe selection are
verified; an ARM64 image build, boot, installation and Parallels acceptance
remain required before compatibility can be declared.

The ARM64 pipeline uses this repository and the same source commit as amd64.
It selects the `arm64` profile in
`config/includes.chroot/usr/share/kythos/architecture-profiles.json`.
Common package lists, hardening, command tools, installer modules, patches,
branding and source audits remain shared. The builder generates the short
architecture package list while staging the build; there is no second recipe
or independently maintained copy of the common package lists.

The amd64 default retains its stock kernel, both vendor microcode packages,
BIOS boot and signed x86 EFI boot chain. ARM64 selects Debian's stock
`linux-image-arm64` and matching headers, signed ARM64 GRUB/shim and signed
ARM64 firmware updater. ARM64 media uses UEFI and `EFI/BOOT/BOOTAA64.EFI`;
the x86 BIOS path is rejected on ARM64. Complete packaged kernels and modules
remain intact.

## Build

Use a Debian 13 ARM64 guest with the dependencies in [BUILDING.md](BUILDING.md),
`grub-efi-arm64-bin`, `grub-efi-arm64-signed`, and `shim-signed`. Enable the
authenticated `deb` and `deb-src` snapshot sources from `SNAPSHOT`, install
`apt-get build-dep calamares=3.3.14-1`, and check out the exact reviewed clean
source commit. Then run:

```sh
sudo ./scripts/build-arm64.sh
```

The ordinary build script runs every source, native partition, image and
binary/source closure gate. It records the Debian architecture, selected
profile, exact source commit and clean state in the artifact evidence. ARM64
produces `kythos-kernal-base-VERSION-arm64.hybrid.iso` and the corresponding
source ISO. An amd64 builder is rejected by this entrypoint; foreign chroot
execution is not used as a substitute for an ARM64 guest.

A native ARM64 machine or an ARM64 virtual machine is the preferred builder.
On an x86 host, a disposable QEMU `virt` machine can run the complete ARM64
guest through TCG. QEMU's executable, libraries and AAVMF firmware can be
extracted from authenticated Debian packages into an owned user directory;
no host package installation or global binfmt registration is required.
Record `KYTHOS_BUILDER_EXECUTION=qemu-tcg` for such a build. Compilation under
TCG can take substantially longer than native ARM64 execution.

## Validation boundaries

Debian's pinned ARM64 package indexes must resolve every selected package
root, including Calamares, stock kernel/headers and signed AA64 boot components,
before the image build starts. Package-index availability alone is not a
successful image build or boot test.

For a generic virtual ARM64 target, boot the finished ISO under QEMU `virt`
with AAVMF UEFI, virtio disk/network and a fresh writable variables image.
Verify installation, reboot, stock modules, local login, networking, package
updates, the terminal viewport, and live-environment removal. Exercise the
signed chain separately with enrolled Secure Boot firmware; the presence of
signed files does not establish successful Secure Boot.

For Parallels on Apple Silicon, create an ARM64 Linux VM with UEFI and attach
the ARM64 ISO as optical media. Perform the same installation and reboot
checks inside Parallels and preserve their receipts. A QEMU test does not
establish Parallels compatibility, physical ARM support or Apple Silicon
bare-metal support. No such compatibility is claimed until the relevant
installation and reboot have been observed.

Upstream references:

- [Debian 13 ARM64 installation guide](https://www.debian.org/releases/trixie/arm64/)
- [Debian signed ARM64 GRUB package](https://packages.debian.org/trixie/grub-efi-arm64-signed)
- [QEMU ARM system emulator](https://www.qemu.org/docs/master/system/target-arm.html)
- [QEMU generic ARM virt machine](https://www.qemu.org/docs/master/system/arm/virt.html)

## amd64 and ARM64 release-pair gate

After both architecture builds have completed, check their artifact directories
together before releasing them:

```sh
./scripts/check-multiarch-pair.py \
  --amd64 /path/to/completed-amd64-artifacts \
  --arm64 /path/to/completed-arm64-artifacts
```

The gate requires the same clean source commit, Debian snapshot, source date
epoch, and byte-identical `recipe-SHA256SUMS` recorded from the canonical
repository. Architecture profiles and ISO names must match their respective
architectures. Both directories must contain a declared binary/source ISO pair
and a source audit reporting zero missing source tuples. Every artifact in
each complete `SHA256SUMS` manifest is independently read back and hashed;
symlink or escaping manifest paths, partial transfers, and corrupt payloads
are rejected.

On success the command prints one JSON record containing the shared provenance,
recipe hash, verified artifact counts, and both binary/source ISO digests. A
failed gate exits nonzero and does not emit a pass record. This is a release
consistency check; it does not establish that either platform boots, installs,
or works in Parallels. Keep those acceptance results separate.

Changes to common sources require new builds of both architectures from the
same reviewed commit, followed by this gate. The gate does not modify or update
an existing ISO in place. ARM64 remains experimental until its separate boot
and installation acceptance has passed.
