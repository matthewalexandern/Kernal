#!/bin/sh
# Build only the patched native partition plugin in the disposable Debian guest.
# Prerequisites IN THAT GUEST: apt-get build-dep calamares; build-essential;
# patch; python3-yaml; python3-jsonschema.
# Input: authenticated `apt-get source calamares=3.3.14-1` directory (Debian's
# source patches already applied by dpkg-source). The input is never modified.
# Usage: scripts/build-calamares-partition.sh SOURCE_DIRECTORY OUTPUT_DIRECTORY
set -eu
umask 022

if [ "$#" -ne 2 ]; then
    printf '%s\n' 'Usage: build-calamares-partition.sh SOURCE_DIRECTORY OUTPUT_DIRECTORY' >&2
    exit 2
fi

# Do not turn the physical development host into a package build environment.
. /etc/os-release
if [ "${ID:-}" != debian ] || [ "${VERSION_ID:-}" != 13 ]; then
    printf '%s\n' 'Run this build inside the dedicated Debian 13 build guest.' >&2
    exit 1
fi

recipe_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
source_dir=$(realpath -- "$1")
mkdir -p -- "$2"
output_dir=$(realpath -- "$2")
if [ "$source_dir" = "$output_dir" ] || [ ! -f "$source_dir/debian/changelog" ]; then
    printf '%s\n' 'A separate Debian source directory is required.' >&2
    exit 1
fi
source_version=$(dpkg-parsechangelog -l "$source_dir/debian/changelog" -S Version)
if [ "$source_version" != 3.3.14-1 ]; then
    printf '%s\n' 'The patch is pinned to Debian calamares 3.3.14-1; review newer source before rebuilding.' >&2
    exit 1
fi

work_dir=$(mktemp -d "$output_dir/build.XXXXXXXX")
cp -a "$source_dir" "$work_dir/source"
patch_file="$recipe_root/patches/calamares/0001-validate-proposed-boot-and-swap-layout.patch"
patch --batch --fuzz=0 -d "$work_dir/source" -p1 < "$patch_file"

python3 - "$recipe_root" "$work_dir/source" <<'PY'
from pathlib import Path
import jsonschema
import sys
import yaml

recipe, source = map(Path, sys.argv[1:])
count = 0
for config in sorted((recipe / 'config/includes.chroot/etc/calamares/modules').glob('*.conf')):
    schema = source / 'src/modules' / config.stem / (config.stem + '.schema.yaml')
    if schema.is_file():
        jsonschema.validate(yaml.safe_load(config.read_text()), yaml.safe_load(schema.read_text()))
        count += 1
if count != 13:
    raise SystemExit(f'Unexpected module schema coverage: {count}; expected 13')
print(f'Calamares native module schemas: {count} passed')
PY

export DEB_BUILD_MAINT_OPTIONS=hardening=+all
eval "$(dpkg-buildflags --export=sh)"
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(dpkg-parsechangelog -l "$source_dir/debian/changelog" -S Timestamp)

# Use Debian's Qt paths and configuration, with no baked-in build-directory
# RPATH. None of the unsafe/debug partition modes is enabled.
cmake -S "$work_dir/source" -B "$work_dir/cmake" \
    -DCMAKE_BUILD_TYPE=None -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_SKIP_RPATH=ON -DWEBVIEW_FORCE_WEBKIT=1 \
    -DKDE_INSTALL_USE_QT_SYS_PATHS=ON -DWITH_QT6=ON \
    -DBUILD_TESTING=OFF -DDEBUG_PARTITION_UNSAFE=OFF \
    -DDEBUG_PARTITION_SKIP=OFF
cmake --build "$work_dir/cmake" --target calamares_viewmodule_partition --parallel "${KYTHOS_BUILD_JOBS:-2}"

# Exercise the same pure policy compiled into the native page and job gate.
c++ -std=c++17 -Wall -Wextra -Werror \
    -I "$work_dir/source/src/modules/partition" \
    "$recipe_root/tests/calamares-storage-policy.cpp" -o "$work_dir/storage-policy-test"
"$work_dir/storage-policy-test"

module_dir="$work_dir/cmake/src/modules/partition"
install -d -m 0755 "$output_dir/partition"
install -m 0644 "$module_dir/libcalamares_viewmodule_partition.so" "$output_dir/partition/"
install -m 0644 "$module_dir/module.desc" "$output_dir/partition/"
if readelf -d "$output_dir/partition/libcalamares_viewmodule_partition.so" | grep -Eq 'RPATH|RUNPATH'; then
    printf '%s\n' 'The native module unexpectedly contains a build search path.' >&2
    exit 1
fi

python3 - "$output_dir" "$source_version" "$patch_file" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

output, version, patch = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
files = sorted((output / 'partition').iterdir())
hashes = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
provenance = {
    'source_package': 'calamares', 'source_version': version,
    'required_runtime_package_version': version, 'architecture': subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip(),
    'patch': str(patch.name), 'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
    'native_target': 'calamares_viewmodule_partition', 'policy_test': 'passed', 'files': hashes,
    'upstream_license': 'GPL-3.0-or-later', 'installed_boot_test': 'not-run-by-module-build',
}
(output / 'provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n')
(output / 'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name, digest in hashes.items()))
PY
printf '%s\n' "Patched native partition module: $output_dir/partition"
