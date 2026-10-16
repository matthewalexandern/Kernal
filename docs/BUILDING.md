# Building and testing

## Supported builder

Use a clean Debian 13 amd64 environment. The builder needs root inside that
environment because live-build creates chroots and mounts filesystems. Install
`python3-pil`, `python3-yaml` and `python3-jsonschema` as well as the live-build prerequisites because
source validation checks the installer configuration and re-renders the
checked-in branding in memory. Do not run the Ubuntu host's
older live-build package against this recipe.

The experimental [ARM64 pipeline](ARM64.md) uses the same source and package
lists through a shared architecture profile. It runs the normal build inside
a Debian 13 ARM64 guest with `scripts/build-arm64.sh`; the default entrypoint
and profile remain amd64. Architecture-specific packages are generated while
staging, and each artifact records its profile and exact source commit.

Enable authenticated `deb-src` entries in the Debian guest and install the
native partition module's build dependencies with `apt-get build-dep
calamares`, plus `build-essential` and `patch`. The build fetches the exact
Debian `calamares=3.3.14-1` source and builds only its partition module with
KythOS' pre-write layout checks. The override module has its own directory;
the packaged Calamares files are preserved. A different runtime Calamares
version requires review and a rebuild of the patch. The source ISO carries
the corresponding upstream source, patch, build script, test and GPL license.

For an isolated build on the current workstation, use a disposable QEMU/KVM
guest installed from an official, signature-verified Debian 13 netinst ISO.
Give it at least 6 GiB RAM, 6 vCPUs, and a 64 GiB sparse disk. Transfer the
recipe and artifacts over loopback-bound SSH; do not share the host filesystem
with the guest. Delete the guest after evidence and artifacts are copied out.
The non-secret installer seed used for that builder is tracked at
`tools/qemu-builder/preseed.cfg`; its temporary SSH public key is appended only
during a build and is never committed.

## Build outputs

Choose editions at build time, producing separate media. With no override the
common console base remains the default on both architectures:

```sh
sudo env KYTHOS_EDITION=base LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build.sh
sudo env KYTHOS_EDITION=desktop LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build.sh
# In the separate native ARM64 Debian guest:
sudo env KYTHOS_EDITION=base LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build-arm64.sh
```

`base` and `desktop` are the implemented profiles; unknown editions fail before
building. The desktop adds XFCE, LightDM, graphical networking and optional
smart-card/application integrations. Server, hypervisor and AI workloads remain
future edition work. There is no combined edition selector. Keep recovery and
advanced installation entries. Version 0.2.0 names binaries
`kythos-kernal-EDITION-0.2.0-ARCH.hybrid.iso`; each has corresponding source
media. Stage overlays into the fresh build directory, never into tracked common
configuration. Desktop display-stack roots move to installed package roots in
that staging copy so removing the live installer cannot remove the desktop.
LightDM is enabled for installed desktop boot and guarded against live boot.
The common base continues to use `multi-user.target`.

When a managed cloud egress proxy supplies a session CA, preserve TLS and APT
signature verification. Supply the existing combined trust bundle to builder
network tools and temporary chroot operations. Keep session proxy settings and
CA files outside the source checkout and outside final live/source image
payloads; inspect the completed images for residual build-only trust files.
The 2027 candidate preparation uses read-only per-command CA/config bind mounts
inside disposable builder chroots, removed when each command exits. Builder
credentials and trust bindings are runtime inputs, not product policy.

Container root is insufficient if its host kernel cannot check the firewall or
mount the image formats. Use a full matching Debian guest when those checks
fail; do not suppress source/image assertions to make a container pass. Track
physical backing storage for sparse VM disks and completed source media; a
virtual 64 GiB disk does not create physical capacity. Build architectures
sequentially when needed, verify copied artifacts before reclaiming only owned
temporary build directories, and retain both completed artifact sets.

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

For example, live-build can report its configured EFI selector `grub-efi` even
when that metapackage is not installed and has no version. The KythOS audit
accepts only that exact uninstalled placeholder after confirming the target
dpkg state and exact `grub2` source tuple coverage. Any real or unknown missing
row fails the source hook. The decision and covered tuple are retained in the
source ISO as `source-selection-notes.txt`.

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
4. Run Calamares plain BIOS and LUKS2 UEFI Secure Boot installations on
   disposable disks, exercise manual partition creation and pre-write layout
   checks, and test the advanced installer's encrypted-LVM path.
5. Boot the installed system and verify APT updates, AppArmor, auditd,
   nftables, networking, and the full module tree. Capture a fresh installed
   package manifest with `dpkg-query`; the manifest embedded in the ISO records
   the live image before installer-only packages are removed.
6. Confirm live-only packages, accounts, custom sudo rules and GUI launchers
   are absent from installed targets. Check read-only hardware diagnostics
   and the unenrolled FIDO2 state without altering host authentication.
7. On real hardware, test graphics, network, storage, audio, firmware,
   suspend/resume, signed NVIDIA modules and FIDO2 enrollment, login and
   recovery. A VM does not certify those physical-device paths.

Calamares and the separate Qt6 setup guide use a small live-only Xorg/Openbox
session. The primary install boot entry opens the guide as `kythos-live`;
only the fixed, argument-free Calamares privilege wrapper may elevate through
the live installer sudo rule. The generic live-config sudo and xinit
components are disabled, so they cannot add unrestricted sudo or an
independent graphical restart loop. Stock signed kernel modules and firmware
remain in both the live and installed systems.

During the build, common package roots and required/important/standard
packages are marked as manually installed. A simulated APT purge resolves the
live interface's full removable dependency set. The build refuses any plan
that includes common roots, essential packages, kernel, firmware or bootloader
packages. Calamares purges that fixed list without autoremove. The advanced
installer receives the same list and keeps its native package postprocessing;
the common roots remain explicitly installed. Custom live privileges,
profiles, accounts and interface files are also removed. The installed common
base therefore starts at a console rather than becoming a desktop edition.

The advanced graphical installer is retained for its accessibility and
additional storage workflows. Calamares also exposes native manual
partitioning, with sizes and mount points editable by the user. Its small
native source patch validates the in-memory boot and swap plan before any
partition job can execute. The advanced installer's header uses original KythOS
artwork through live-build's installer overlay. Debian Installer component,
copyright, source, and license notices remain available where required.
KythOS identity is written to both OS release files and both ISO disk labels.
The distinct dpkg vendor inherits from Debian; signed Debian repository Origin,
package copyright, and compatibility identifiers remain intact as provenance.
The KythOS MIT license and attribution NOTICE are included at both ISO roots
and in the installed system. OS identity files use local dpkg diversions so
base-files upgrades preserve KythOS Kernal branding. See
[BRANDING.md](BRANDING.md) for the display name and retained upstream interfaces.

## Regenerating boot artwork

The checked-in white shield is a self-contained SVG source at
`assets/branding/kythos-mark-white.svg`. Its monogram retains the original
9:06 geometry; source provenance is documented in [BRANDING.md](BRANDING.md).
Calamares uses the SVG directly. librsvg and Pillow render the bootloader,
Plymouth and Debian Installer PNG variants, including small lower-right
product text on boot backgrounds. These render tools run on the builder;
they do not enter the installed system.

```sh
sudo apt install python3-pil librsvg2-bin fonts-dejavu-core
python3 scripts/render-branding.py
python3 tests/test-boot-artwork.py
./scripts/validate-source.sh
```

The Plymouth theme displays supplied boot progress while it advances and a
moving activity segment otherwise. Password/question callbacks retain a
stable logo and readable white text. Esc uses Plymouth's normal details
switch; GRUB also offers an explicit diagnostics entry. Recovery and other
troubleshooting entries remain available.

For an isolated interpreter check on a Debian builder with Plymouth installed:

```sh
KYTHOS_PLYMOUTH_PLUGIN=/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)/plymouth/script.so \
    python3 tests/test-plymouth-runtime.py
```

That test uses the real script, image, label and sprite libraries with a fake
1280×720 window. It does not open a TTY or DRM device and is separate from the
required ISO/VM boot-presentation and encrypted-install checks.
