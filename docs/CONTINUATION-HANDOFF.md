# KythOS Kernal continuation handoff

Prepared 2026-10-16 16:16 EDT for continuing development in the cloud, on a Mac or on
another device. The private repository is
https://github.com/matthewalexandern/Kernal. Both architecture images and their
matching source media are uploaded and verified. The next acceptance task is
ARM64 boot and installation, followed by Parallels testing when available.

## Start the next session

Use this prompt in the next chat with the Kernal repository selected:

> Continue KythOS Kernal from the current GitHub main. Read AGENTS.md,
> docs/CONTINUATION-HANDOFF.md, docs/CLOUD-CONTINUATION.md and
> docs/SOURCE-SYNC.md first. Both cc472f5 architecture builds and the original
> 14 release assets are complete and verified. Start with ARM64 boot and
> installation acceptance on a separate blank test disk; record Parallels
> results separately. Preserve the retained local user VM and account. Keep
> image provenance truthful and share reviewed source commits through GitHub.

The verified source starting point before this handoff is
`e7f7e0f75ec5480e917967d18b0ef97849124b6c`. Fetch current `main` for later
handoff or source commits; the existing ISO bytes remain unchanged.

## Download the existing images and evidence

The release is private, draft and prerelease. Each new environment needs its
own GitHub authentication with access to this repository and draft.

- Release: https://github.com/matthewalexandern/Kernal/releases/tag/untagged-5cf042ef7cdf26cd7f7d
- Tag: `v0.1.0-preview-cc472f5`
- Release ID: `415294757`
- Original delivery: 14 files, 12,765,274,773 bytes.
- Original verification receipt:
  https://github.com/matthewalexandern/Kernal/blob/main/docs/deliveries/2026-10-16-cc472f5.json

The original 14 files were independently downloaded in full and SHA256
verified. A separate API check confirmed their asset IDs, sizes and digests.
They contain two direct binary ISOs, six ordered source ISO parts, a source
Git bundle, metadata and build evidence, complete ISO checksums and the
original preparation handoff. This continuation handoff and its checksum are
supplemental assets; they are outside the original 14-file `SHA256SUMS`.
The original `CLOUD-HANDOFF.md` describes preparation before upload; use the
verified receipt and this handoff for completed delivery status.

With GitHub CLI installed and authenticated, download into a new directory.
Allow at least 30 GiB free for downloads, extraction and source reconstruction.

```sh
gh release download v0.1.0-preview-cc472f5 \
  --repo matthewalexandern/Kernal --dir KythOS-cloud-delivery
cd KythOS-cloud-delivery
shasum -a 256 -c SHA256SUMS
shasum -a 256 -c KYTHOS-CONTINUATION-HANDOFF.md.sha256
```

On Linux, replace `shasum -a 256` with `sha256sum`. Follow the original
downloaded `CLOUD-HANDOFF.md` for `metadata.tar.gz` extraction, ordered source
part concatenation, `ISO-SHA256SUMS` and each architecture manifest check.
Keep AMD64 and ARM64 source media in separate directories: both reconstructed
source ISOs use the same original basename.

| Image | SHA256 |
| --- | --- |
| AMD64 binary | `06c0e9619de021daabd59b7e7f28ef5961aa4563a98aad7ad62f48001ea5ccf8` |
| ARM64 binary | `b27a511580222ecd16ec1806b385945dd2b67ab78ab9fa6a60c0ff4d69005646` |
| AMD64 complete source | `dbc1e92bcc8bda363c5198dc81968d4f2a898a2544c85f101cff0c70753982d4` |
| ARM64 complete source | `876d8c0008d37293bfa82c946de495cac5600e06eaa767f3bcd0fc88170c08e3` |

## Synchronize source across devices

Authenticate each device separately. Preserve any old checkout and clone into
a new path if it uses the original unpublished history:

```sh
git clone --branch main https://github.com/matthewalexandern/Kernal.git ~/Kernal-synced
cd ~/Kernal-synced
git config --local user.email 321331429+matthewalexandern@users.noreply.github.com
./scripts/sync-source.sh
```

Read `AGENTS.md` and `docs/SOURCE-SYNC.md`. Preserve the existing author name
and verify author and committer email overrides before committing. Old
`94cf361` bundles cannot fast-forward to the rewritten noreply history;
preserve them privately and bring only reviewed file changes into the fresh
checkout. Do not merge or push their old commits or backup refs.

Before each source task, synchronize a clean `main`. Use separate named
branches for simultaneous work. Review changes, stage exact paths, commit,
fetch and push normally. Do not force-push or run a background file mirror.
The other machine must fetch and verify its revision before starting work;
its checkout and Desktop transfer have not been observed here. Git sync does
not update an existing ISO or installed operating system.

The uploaded `Kernal-noreply-da48e63.bundle` is an offline snapshot at
`da48e63b5a72ec49631aa98bb5d078eb5d6d9582`. Clone it with `--branch main`, set
origin to GitHub, then fetch current source. It predates later delivery docs.

## Preserve image identity

Existing images were built from original source commit
`cc472f571c2784a105ee12e5df408275ef14fa37`. The published noreply equivalent is
`56a1b71c023beef9c6a2db4b57cb2c5d5ccd1516`; both have source tree
`37f88c56b3f569b64840df58cd24277eec09cfde`. Later documentation commits and the
bundle release target do not replace the original image source identity.
The mapping is in `docs/git-identity-map-2026-10-16.json`.

Both builds exited zero. Each architecture has 28 verified artifacts and
zero missing required source tuples. The real pair gate rehashed all 56
artifacts and passed. Build records are in
`docs/builds/2026-10-16-cc472f5/`. After reconstructing the original layout,
run from the source checkout:

```sh
./scripts/check-multiarch-pair.py \
  --amd64 /path/to/KythOS-cloud-delivery/amd64 \
  --arm64 /path/to/KythOS-cloud-delivery/arm64
```

## Acceptance status and next work

AMD64 passed a fresh QEMU/KVM encrypted Calamares UEFI and Secure Boot
installation, restart, unlock and login. Seven acceptance groups with 61
captures covered the installed baseline, command assistance, regular console
font and fixed header, kernel diagnostic routing, DHCP, hotplug and static
network retention.

ARM64 build and integrity passed. Boot, installation, Secure Boot, Parallels
and physical ARM hardware remain untested. Use the existing ARM64 ISO first:

1. Boot in an owned ARM64 Linux VM with UEFI and a separate blank test disk.
2. Exercise Calamares automatic whole-disk partitioning and mounting,
   complete installation, use its normal Finish and restart flow, detach the
   optical media for installed boot, then observe unlock and login.
3. Check the stock kernel and modules, networking, `sudo cy update`,
   `sudo kythos-security-status`, `kythos-hardware-status`, account tools,
   command assistance, terminal font/header and installed live-media cleanup.
4. Exercise Secure Boot with enrolled firmware separately, and encryption
   modes on their applicable platforms. Record exact image hash and results.
5. Test installation and restart in Parallels on Apple Silicon separately.
   Generic QEMU results do not establish Parallels compatibility.

Physical NVIDIA, Wi-Fi, TPM and FIDO2 operation still need acceptance.
Formal FIPS certification and STIG compliance are not established. Do not
promote these builds as certified or hardware validated from artifact checks.
See `docs/ARM64.md` for platform requirements and validation boundaries.

## Product direction to preserve

The user wants one minimal supported Debian foundation for four future
projects: desktop, server, hypervisor and a bare metal llama.cpp AI server.
Preserve supported kernels, complete driver modules, stability and automatic
hardware detection. These variants are product direction, not four completed
release images.

Keep the user-facing name `KythOS Kernal`, the `cy` package command and the
logo animation without text. Preserve upstream license, copyright, signed
metadata and technical identifiers where required. Keep the regular nonbold
console font and colored fixed header and hostname work covered by acceptance.
Retain IPv4, password SSH and the user's choice of no added password policy.
The desired installer includes Calamares, the separate custom wizard,
automatic whole-disk mounting and encryption choices; TPM and FIDO2 hardware
behavior and NVIDIA compatibility need direct testing. Review existing code
before changing those areas rather than treating this summary as acceptance.

## Future builds and local state

Use an isolated Debian 13 AMD64 builder and an isolated Debian 13 ARM64
builder, each with at least 64 GiB builder disk in addition to delivery files.
Native ARM64 on Apple Silicon or a cloud ARM64 instance avoids the prior
slow x86 emulation path. Follow `docs/BUILDING.md`, `docs/ARM64.md` and
`SNAPSHOT`; the cloud provider, host and credentials are not provisioned by
this handoff. Run inside the appropriate builder:

```sh
sudo env LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build.sh
# In the separate ARM64 builder:
sudo env LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build-arm64.sh
```

Pin both architectures to one reviewed clean source commit. Keep active build
inputs fixed, retain every normal source and installer gate, and verify the
new pair after both finish. No existing build needs restarting to use these
already completed ISOs.

On the original Ubuntu machine, the workspace is `/home/x/Kernal`. Keep the
retained user VM, the `matthew` account and password, builder keys, private
runtime evidence and frozen transfer exports intact. These local resources
and credentials were not uploaded. Keep ISO bytes and VM disks outside Git.
The user deleted the scheduled follow-up; leave it deleted. Continue only
explicitly requested work and keep delivery private unless public release is
authorized.
