# Building and testing

## Supported builder

Use a clean Debian 13 amd64 environment. The builder needs root inside that
environment because live-build creates chroots and mounts filesystems. Do not
run the Ubuntu host's older live-build package against this recipe.

For an isolated build on the current workstation, use a disposable QEMU/KVM
guest installed from an official, signature-verified Debian 13 netinst ISO.
Give it at least 6 GiB RAM, 6 vCPUs, and a 64 GiB sparse disk. Transfer the
recipe and artifacts over loopback-bound SSH; do not share the host filesystem
with the guest. Delete the guest after evidence and artifacts are copied out.
The non-secret installer seed used for that builder is tracked at
`tools/qemu-builder/preseed.cfg`; its temporary SSH public key is appended only
during a build and is never committed.

## Build outputs

`scripts/build.sh` creates a new timestamped work directory for every run and
copies completed outputs to `artifacts/<timestamp>/`. Set `SOURCE_DATE_EPOCH`
to a reviewed source commit timestamp when producing a release. Debian mirrors
continue to move, so the evidence records resolved package versions even when
the source tree itself is unchanged. A nonempty live-build
`source/missing-source.txt` is copied into the evidence and fails the build.
The public release audit must still inventory every distributed binary and
installer component against its source; live-build's report does not cover all
temporary or installer-pool artifacts.

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
desktop environment in the installed base.
