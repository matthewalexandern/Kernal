# Building and testing

## Supported builder

Use a clean Debian 13 amd64 environment. The builder needs root inside that
environment because live-build creates chroots and mounts filesystems. Install
`python3-pil` as well as the live-build prerequisites because source validation
re-renders the checked-in branding in memory. Do not run the Ubuntu host's
older live-build package against this recipe.

For an isolated build on the current workstation, use a disposable QEMU/KVM
guest installed from an official, signature-verified Debian 13 netinst ISO.
Give it at least 6 GiB RAM, 6 vCPUs, and a 64 GiB sparse disk. Transfer the
recipe and artifacts over loopback-bound SSH; do not share the host filesystem
with the guest. Delete the guest after evidence and artifacts are copied out.
The non-secret installer seed used for that builder is tracked at
`tools/qemu-builder/preseed.cfg`; its temporary SSH public key is appended only
during a build and is never committed.

## Build outputs

`scripts/build.sh` creates fresh root-only directories below
`/var/lib/kythos-builder/builds/` and copies completed outputs below
`/var/lib/kythos-builder/artifacts/`. A clean Git checkout uses its commit
timestamp as `SOURCE_DATE_EPOCH`; an unpacked reviewed recipe must supply that
value explicitly. The tracked `SNAPSHOT` pins bootstrap, chroot, security, and
Debian Installer downloads to immutable snapshot.debian.org archives. APT
signature verification stays enabled; only the archived Release file's expired
`Valid-Until` timestamp is ignored. The source-stage signed `InRelease` files
and their hashes are copied into the release evidence before live-build restores
the current update mirrors for installed systems.

The build performs an exact source audit in addition to live-build's own
`source/missing-source.txt` check. It inventories the live root, every `.deb`
and `.udeb` in the binary ISO, and cached binary-input packages whose bootloader
files are extracted into the image. It records each binary's exact source
package and version, downloads any missing corresponding source, and mounts the
finished binary and source ISOs to verify the manifests. Any missing tuple or
binary mismatch fails the build. The coverage report and manifests are release
artifacts.

For example, live-build can report the EFI metapackage `grub-efi` even though
its actual source package is `grub2`. The KythOS audit reads the authoritative
`Source` and `Version` fields from each binary, including binNMU handling,
instead of guessing from binary names. It clears live-build's report only when
the file is exactly its six-line header-only form; any reported package row
fails the source hook.

`KYTHOS_BUILD_ROOT` and `KYTHOS_ARTIFACT_ROOT` can select different locations,
but each destination's existing parent chain must be root-owned, contain no
symlink, and have no group or other write permission. The script creates each
final leaf atomically and refuses existing, root, equal, or overlapping paths.

An interrupted build's download cache can seed a new build without reusing a
chroot, installer image, package index, or generated image state. Point
`KYTHOS_CACHE_SEED` at the previous live-build `cache` directory. The cache
and all of its parent directories must remain root-owned and protected from
group or other writes. Only regular `.deb` files from
`packages.bootstrap`, `packages.chroot`, and `packages.binary` are copied.
Their checksums and the package-only scope are recorded:

```sh
sudo KYTHOS_CACHE_SEED=/path/to/previous-build/cache \
  ./scripts/build.sh
```

Release acceptance uses a clean no-seed build. The pinned archive and
normalized timestamps improve rebuildability, but KythOS does not claim
bit-for-bit reproducibility until two independent clean builds produce matching
artifact hashes.

## Redistributable firmware boundary

The recipe lists broad redistributable firmware coverage suitable for the
unattended amd64 live root instead of using live-build's automatic live-root
firmware discovery. Automatic discovery also selects `firmware-b43-installer` and
`firmware-b43legacy-installer`; their post-installation scripts download and
extract proprietary Broadcom payloads that the upstream firmware guidance says
distributions may not redistribute. The stock b43 kernel drivers remain in the
image. On hardware that requires those two payloads, the owner can install the
matching installer package after installation with:

```sh
sudo cy install firmware-b43-installer
# or, for the older driver family:
sudo cy install firmware-b43legacy-installer
```

This legal boundary affects out-of-box firmware for those legacy Broadcom
devices only. It does not remove any kernel driver or prevent the device owner
from enabling the hardware.

`firmware-ipw2x00` and `firmware-ivtv` contain their payloads, but their package
scripts require the recipient to read and accept separate Intel or Hauppauge
license terms. KythOS does not preaccept those terms for public-image users or
preinstall the packages in the unattended live root. The Debian Installer can
offer its signed firmware package pool interactively, and an installed-system
owner can explicitly run:

```sh
sudo cy install firmware-ipw2x00
sudo cy install firmware-ivtv
```

The corresponding stock kernel drivers remain present.

## Test sequence

1. Validate scripts, required options, package-list structure, and nftables
   syntax in the Debian builder.
2. Build the binary and source ISOs and verify their SHA-256 checksums.
3. Boot the binary ISO using legacy BIOS and UEFI Secure Boot.
4. Run both unencrypted and encrypted-LVM installations on disposable disks.
5. Boot the installed system and verify APT updates, AppArmor, auditd,
   nftables, networking, and the full module tree. Capture a fresh installed
   package manifest with `dpkg-query`; the manifest embedded in the ISO records
   the live image before installer-only packages are removed.
6. Test on physical hardware before making any driver-support claim.

The graphical installer is included for accessibility; it does not become a
desktop environment in the installed base. Its header uses original KythOS
artwork through live-build's installer overlay. Debian Installer component,
copyright, source, and license notices remain available where required.
KythOS identity is written to both OS release files and both ISO disk labels.
The distinct dpkg vendor inherits from Debian; signed Debian repository Origin,
package copyright, and compatibility identifiers remain intact as provenance.
The KythOS MIT license is included at both ISO roots and in the installed
system.

## Regenerating boot artwork

The release images already contain checked-in boot artwork. Pillow is used by
source validation and does not enter the live filesystem. When intentionally
updating the approved source mark, regenerate every derived image in one pass:

```sh
sudo apt install python3-pil
python3 scripts/render-branding.py
./scripts/validate-source.sh
```

The renderer never adds a product wordmark. Plymouth draws the trace, light
sweep, breathing glow, and handoff fade from the transparent logo. Its prompt
callbacks remain visible for encrypted-root passphrases and boot questions.
