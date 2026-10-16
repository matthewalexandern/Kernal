# Continue KythOS Kernal on another machine

The source repository is private:
`https://github.com/matthewalexandern/Kernal.git`. The actual ISO delivery is
attached to this [private draft release](https://github.com/matthewalexandern/Kernal/releases/tag/untagged-5cf042ef7cdf26cd7f7d):

- Tag: `v0.1.0-preview-cc472f5`.
- Release ID: `415294757`.
- Package source bundle and release target:
  `da48e63b5a72ec49631aa98bb5d078eb5d6d9582`.

Each device or cloud environment needs its own authenticated GitHub access.
Viewing or downloading this draft requires draft access.

Delivery completed on 2026-10-16: all 14 assets (12,765,274,773 bytes) were
independently downloaded in full and SHA256 verified. A separate final API
check confirmed the same asset IDs, sizes and digests, and the remote version
tag points to the exact release target above. See the
[verified delivery receipt](deliveries/2026-10-16-cc472f5.json).

The [continuation handoff](CONTINUATION-HANDOFF.md) provides the next-chat
prompt, project constraints and ordered ARM64 acceptance tasks. Its release
copy `KYTHOS-CONTINUATION-HANDOFF.md` and separate `.sha256` are supplemental
assets outside the original 14-file delivery manifest. Both were independently
downloaded and hash verified; see the
[supplemental delivery receipt](deliveries/2026-10-16-handoff.json).

## Check and download the delivery

Check the release before downloading:

```sh
gh api repos/matthewalexandern/Kernal/releases/415294757 \
  --jq '{draft, prerelease, target_commitish, asset_count: (.assets | length), assets: [.assets[] | {name, state, size, digest}]}'
```

Require all 14 expected assets to have state `uploaded`, with the target above
and `draft: true`. If files are missing or still uploading, wait for delivery
to finish. The expected groups are:

| Assets | Count |
| --- | ---: |
| AMD64 and ARM64 bootable binary ISOs | 2 |
| Three ordered source-ISO parts per architecture | 6 |
| `Kernal-noreply-da48e63.bundle` and its checksum | 2 |
| `metadata.tar.gz` | 1 |
| `ISO-SHA256SUMS` | 1 |
| `CLOUD-HANDOFF.md` | 1 |
| `SHA256SUMS` | 1 |

Allow at least 30 GiB free for the downloads, extracted metadata, binary
copies and reassembled source ISOs. Download into a new directory:

```sh
gh release download v0.1.0-preview-cc472f5 \
  --repo matthewalexandern/Kernal --dir KythOS-cloud-delivery
cd KythOS-cloud-delivery
shasum -a 256 -c SHA256SUMS
```

On Linux, use `sha256sum -c SHA256SUMS`. Every listed file must pass. Then
follow the downloaded `CLOUD-HANDOFF.md` for extraction, ordered source-part
concatenation, `ISO-SHA256SUMS` checks and both original architecture manifests.
Keep AMD64 and ARM64 directories separate: their source ISOs have the same
original basename and different bytes.

The metadata archive supplies the installer gallery with 79 images, all 50
build-record files, the identity map and the passed pair report. Its canonical
architecture metadata plus the four reconstructed ISOs restore all 56 declared
build artifacts for the existing multiarch pair gate. Retain the delivery and
its checksums unchanged.

## Start a source checkout

Follow [SOURCE-SYNC.md](SOURCE-SYNC.md) for a fresh GitHub clone, repository-local
noreply identity and guarded source updates. Preserve any old checkout and
local edits. The original `94cf361` bundle belongs to the previous unpublished
history and cannot fast-forward to the rewritten shared `main`; bring only
reviewed file changes into new noreply commits.

The delivered main-only bundle is an offline source snapshot at `da48e63`.
The downloaded handoff gives its explicit `git clone --branch main` command.
Later source commits arrive through ordinary Git synchronization; they do not
change existing ISO bytes or update an installed OS.

## Image identity and validation scope

The four existing ISOs were built from original source commit
`cc472f571c2784a105ee12e5df408275ef14fa37`. The equivalent noreply source commit
is `56a1b71c023beef9c6a2db4b57cb2c5d5ccd1516`. Both have source tree
`37f88c56b3f569b64840df58cd24277eec09cfde`; the existing images retain their
original source identity. See the [identity map](git-identity-map-2026-10-16.json)
and [exact build records](builds/2026-10-16-cc472f5/README.md).

Both architecture builds, source closure and transfer checks passed. AMD64
passed a fresh QEMU/KVM encrypted Calamares UEFI/Secure Boot installation and
seven installed-system acceptance groups with 61 captures. ARM64 boot,
installation, Secure Boot, Parallels and physical hardware remain untested.
Physical NVIDIA, Wi-Fi, TPM and FIDO2 operation, formal FIPS certification and
STIG compliance are not established by these results.

## Build or test elsewhere

Use isolated native-architecture Debian 13 builders for future work: an AMD64
builder for AMD64 and an ARM64 builder for ARM64. Give each builder at least
the documented 64 GiB disk in addition to retained delivery files. Follow
[BUILDING.md](BUILDING.md), [ARM64.md](ARM64.md) and `SNAPSHOT` for dependencies
and authenticated package sources. Pin both builds to one reviewed clean
source commit and keep their active inputs fixed.

Inside the appropriate Debian builder, use an explicit build-process locale:

```sh
sudo env LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build.sh
# In the separate ARM64 builder:
sudo env LC_ALL=C.UTF-8 LANG=C.UTF-8 ./scripts/build-arm64.sh
```

Set the same variables in a systemd launcher and verify its actual child
environment. Preserve every normal source, native installer and image gate,
then run the multiarch pair gate on the completed artifacts. ARM64 installation
and Parallels acceptance are separate next tasks.

No cloud host or task is provisioned by this document. The delivery excludes
credentials, VM disks, private runtime fixtures and installed-user passwords.
The retained local user VM and account remain local state: preserve them and
do not recreate, reset or delete them from this handoff. New installation tests
use separate owned blank test disks. Keep artifact delivery private unless a
public release is explicitly authorized.
