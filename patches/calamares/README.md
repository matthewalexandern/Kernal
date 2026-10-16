# Native Calamares partition validation

This overlay builds only the native partition plugin from Debian's exact
`calamares 3.3.14-1` source, with the included GPL-3.0-or-later patch. Debian's
packaged files are retained. The overlay is loaded first from
`/usr/lib/kythos/calamares/modules/partition` on the live image and removed
from the installed system.

All native manual, erase, alongside and replacement choices remain available.
The patch checks the proposed in-memory storage model before disk jobs run:

- A plain root may contain its own boot files.
- Root depending on LUKS needs a separate unencrypted boot filesystem for the
  supported signed GRUB chain.
- Selected swap must be fully encrypted when root depends on encryption.
- Existing and proposed LVM backing physical volumes are followed recursively.
  Unknown or cyclic backing stops the plan with a visible explanation.

The native page displays the reason and disables Next only for an invalid
plan. A second check at partition job-queue construction returns only a
failure job if an invalid plan bypasses the page. Native firmware, size,
filesystem and partition-table checks remain in place. No passwords are read,
copied or logged. Root backing is represented by public disk/sector identities;
the final native partition results add the matching identity for reconciliation.

The guided layout suggests 2 GiB for boot, with a 1 GiB guided minimum. It
imposes no maximum; manual partitioning chooses its own sizes. These defaults
do not restrict the size of the root filesystem.

## Build in the disposable Debian 13 guest

Use authenticated configured Debian package sources. Fetch the exact source
and install its build dependencies **inside the guest**:

```sh
apt-get update
apt-get build-dep calamares
apt-get install build-essential patch python3-yaml python3-jsonschema
apt-get source calamares=3.3.14-1
scripts/build-calamares-partition.sh ./calamares-3.3.14 ./native-partition-output
```

The input source directory is copied before applying the patch. The script
uses Debian's Qt6/CMake configuration and hardening flags, builds the
`calamares_viewmodule_partition` target, runs the standalone policy test,
and rejects embedded build-directory library search paths. It does not
compile or install software on the physical development host.

Output contains `partition/libcalamares_viewmodule_partition.so`, matching
`partition/module.desc`, hashes and `provenance.json`. The live image stores
the provenance at `/usr/share/kythos/calamares-partition-provenance.json`.
Before disk jobs, KythOS checks the exact runtime package version and both
module hashes. A newer Calamares version requires a reviewed rebuild of this
overlay; do not silently reuse the old binary.

The binary build proves compilation and policy-test results. It does not
prove an installed system boots; full plain/manual and encrypted installed
boot tests are separate acceptance gates. The source image must include the
corresponding Debian source, this patch, the build script and test. Upstream
copyright notices and the accompanying `COPYING` are preserved.
