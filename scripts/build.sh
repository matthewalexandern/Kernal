#!/bin/bash
set -Eeuo pipefail
umask 022

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

if [[ $(id -u) -ne 0 ]]; then
    printf '%s\n' 'Run this build inside Debian 13 as root (for example: sudo ./scripts/build.sh).' >&2
    exit 1
fi

if [[ ! -r /etc/os-release ]]; then
    printf '%s\n' 'Cannot identify the build operating system.' >&2
    exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ ${ID:-} != debian || ${VERSION_CODENAME:-} != trixie ]]; then
    printf 'Unsupported builder: %s %s. Debian 13 trixie is required.\n' \
        "${ID:-unknown}" "${VERSION_CODENAME:-unknown}" >&2
    exit 1
fi

architecture=${KYTHOS_ARCH:-amd64}
case "$architecture" in
    amd64|arm64) ;;
    *) printf 'Unsupported build architecture: %s\n' "$architecture" >&2; exit 1 ;;
esac
if [[ $(dpkg --print-architecture) != "$architecture" ]]; then
    printf 'Build %s inside a matching Debian guest; cross-architecture chroots are not accepted.\n' \
        "$architecture" >&2
    exit 1
fi
export KYTHOS_ARCH=$architecture
edition=${KYTHOS_EDITION:-base}
edition_tool="$repo_root/config/includes.chroot/usr/local/libexec/kythos-edition"
"$edition_tool" --edition "$edition" >/dev/null
export KYTHOS_EDITION=$edition
profile_tool="$repo_root/config/includes.chroot/usr/local/libexec/kythos-architecture"
"$profile_tool" --arch "$architecture" >/dev/null

for command_name in lb debootstrap mksquashfs mount rsync unsquashfs xorriso; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Missing build command: %s\n' "$command_name" >&2
        exit 1
    }
done

verify_protected_directory_chain()
{
    local checked_directory=$1
    local directory_bits directory_mode directory_owner

    while :; do
        [[ -d $checked_directory && ! -L $checked_directory ]] || {
            printf 'Unsafe directory in privileged path: %s\n' \
                "$checked_directory" >&2
            exit 1
        }
        directory_owner=$(stat -Lc '%u' -- "$checked_directory")
        directory_mode=$(stat -Lc '%a' -- "$checked_directory")
        directory_bits=$((8#$directory_mode))
        if [[ $directory_owner -ne 0 || $((directory_bits & 0022)) -ne 0 ]]; then
            printf 'Privileged path is not root-owned and protected: %s\n' \
                "$checked_directory" >&2
            exit 1
        fi
        [[ $checked_directory == / ]] && break
        checked_directory=$(dirname -- "$checked_directory")
    done
}

create_trusted_directory()
{
    local directory=$1

    if [[ ! -e $directory && ! -L $directory ]]; then
        mkdir -m 0700 -- "$directory"
    fi
    verify_protected_directory_chain "$directory"
}

"$repo_root/scripts/validate-source.sh"

run_id=$(date -u +%Y%m%dT%H%M%SZ)
trusted_root=/var/lib/kythos-builder
create_trusted_directory "$trusted_root"
create_trusted_directory "$trusted_root/builds"
create_trusted_directory "$trusted_root/artifacts"
build_root=$(readlink -m -- \
    "${KYTHOS_BUILD_ROOT:-"$trusted_root/builds/$run_id"}")
artifact_root=$(readlink -m -- \
    "${KYTHOS_ARTIFACT_ROOT:-"$trusted_root/artifacts/$run_id"}")
version=$(cat "$repo_root/VERSION")
snapshot=$(cat "$repo_root/SNAPSHOT")
image_name="kythos-kernal-${edition}-${version}"
if [[ ! $snapshot =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
    printf '%s\n' 'SNAPSHOT must contain a UTC snapshot.debian.org timestamp.' >&2
    exit 1
fi

if [[ $build_root == / || $artifact_root == / \
    || $build_root == "$artifact_root" \
    || $build_root/ == "$artifact_root/"* \
    || $artifact_root/ == "$build_root/"* ]]; then
    printf '%s\n' \
        'Build and artifact roots must be distinct, non-root, non-overlapping paths.' >&2
    exit 1
fi

verify_protected_directory_chain "$(dirname -- "$build_root")"
verify_protected_directory_chain "$(dirname -- "$artifact_root")"
mkdir -m 0700 -- "$build_root" \
    || { printf 'Refusing build directory: %s\n' "$build_root" >&2; exit 1; }
mkdir -m 0700 -- "$artifact_root" \
    || { printf 'Refusing artifact directory: %s\n' "$artifact_root" >&2; exit 1; }
verify_protected_directory_chain "$build_root"
verify_protected_directory_chain "$artifact_root"

cache_seed=none
cache_seed_scope=none
cache_seed_manifest="$artifact_root/download-cache-seed-SHA256SUMS"
: > "$cache_seed_manifest"
if [[ -n ${KYTHOS_CACHE_SEED:-} ]]; then
    if [[ ! -d $KYTHOS_CACHE_SEED ]]; then
        printf 'KYTHOS_CACHE_SEED is not a directory: %s\n' \
            "$KYTHOS_CACHE_SEED" >&2
        exit 1
    fi
    cache_seed=$(readlink -f -- "$KYTHOS_CACHE_SEED")
    verify_protected_directory_chain "$cache_seed"
    unsafe_cache_entry=$(find "$cache_seed" \
        -maxdepth 2 -type f -name '*.deb' \
        \( ! -user root -o -perm /022 \) -print -quit)
    if [[ -n $unsafe_cache_entry ]]; then
        printf 'Unsafe ownership or mode in cache seed: %s\n' \
            "$unsafe_cache_entry" >&2
        exit 1
    fi
    cache_seed_scope=package-archives-only
    install -d -m 0755 \
        "$build_root/cache/packages.bootstrap" \
        "$build_root/cache/packages.chroot" \
        "$build_root/cache/packages.binary"
    for cache_directory in packages.bootstrap packages.chroot packages.binary; do
        [[ -d $cache_seed/$cache_directory ]] || continue
        verify_protected_directory_chain "$cache_seed/$cache_directory"
        while IFS= read -r -d '' cached_package; do
            package_architecture=$(dpkg-deb -f "$cached_package" Architecture)
            if [[ $package_architecture != all && $package_architecture != "$architecture" ]]; then
                continue
            fi
            cp -a --reflink=auto "$cached_package" \
                "$build_root/cache/$cache_directory/"
        done < <(find "$cache_seed/$cache_directory" -maxdepth 1 \
            -type f -name '*.deb' -print0)
    done
    (
        cd "$build_root/cache"
        find packages.bootstrap packages.chroot packages.binary \
            -type f -name '*.deb' -print0 2>/dev/null \
            | LC_ALL=C sort -z | xargs -0 -r sha256sum
    ) > "$cache_seed_manifest"
fi

cp -a "$repo_root/auto" "$repo_root/LICENSE" "$repo_root/NOTICE" \
    "$repo_root/SNAPSHOT" "$repo_root/VERSION" "$build_root/"
# Development imports must never add host Python bytecode to the image.
rsync -a --exclude='__pycache__/' --exclude='*.py[cod]' \
    "$repo_root/config/" "$build_root/config/"
python3 "$repo_root/scripts/stage-edition.py" --edition "$edition" \
    "$build_root/config" > "$artifact_root/build-edition-profile.json"
# A release build may start from a checkout owned by an unprivileged account.
# Normalize the copied image recipe so no builder UID or private umask leaks
# into the live filesystem or installer overlay.
chown -R 0:0 "$build_root/auto" "$build_root/config" \
    "$build_root/LICENSE" "$build_root/NOTICE" "$build_root/SNAPSHOT" "$build_root/VERSION"
chmod -R u=rwX,go=rX "$build_root/auto" "$build_root/config"
chmod 0644 "$build_root/LICENSE" "$build_root/NOTICE" "$build_root/SNAPSHOT" "$build_root/VERSION"
install -d -m 0755 "$build_root/config/includes.chroot/usr/share/kythos"
install -m 0644 "$repo_root/VERSION" \
    "$build_root/config/includes.chroot/usr/share/kythos/version"
printf '%s\n' "$architecture" \
    > "$build_root/config/includes.chroot/usr/share/kythos/build-architecture"
"$profile_tool" --arch "$architecture" \
    > "$artifact_root/build-architecture-profile.json"
"$profile_tool" --arch "$architecture" --packages \
    > "$build_root/config/package-lists/architecture.list.chroot_install"
chmod 0644 \
    "$build_root/config/includes.chroot/usr/share/kythos/build-architecture" \
    "$build_root/config/package-lists/architecture.list.chroot_install"
# Record package roots before the chroot stage resolves the live-only
# dependency closure. Priority-standard utilities are protected by that hook.
for package_scope in live base; do
    case "$package_scope" in
        live) package_suffix=chroot_live ;;
        base) package_suffix=chroot_install ;;
    esac
    awk '!/^[[:space:]]*(#|!|$)/ { print $1 }' \
        "$build_root"/config/package-lists/*.list."$package_suffix" \
        | LC_ALL=C sort -u \
        > "$build_root/config/includes.chroot/usr/share/kythos/installer-$package_scope-package-roots"
    chmod 0644 "$build_root/config/includes.chroot/usr/share/kythos/installer-$package_scope-package-roots"
done
install -d -m 0755 \
    "$build_root/config/includes.chroot/usr/share/doc/kythos-kernal" \
    "$build_root/config/includes.binary"
install -m 0644 "$repo_root/LICENSE" \
    "$build_root/config/includes.chroot/usr/share/doc/kythos-kernal/copyright"
install -m 0644 "$repo_root/LICENSE" \
    "$build_root/config/includes.binary/LICENSE"
install -m 0644 "$repo_root/LICENSE" "$artifact_root/LICENSE"
install -m 0644 "$repo_root/NOTICE" \
    "$build_root/config/includes.chroot/usr/share/doc/kythos-kernal/NOTICE"
install -m 0644 "$repo_root/NOTICE" "$build_root/config/includes.binary/NOTICE"
install -m 0644 "$repo_root/NOTICE" "$artifact_root/NOTICE"
install -o root -g root -m 0755 \
    "$repo_root/scripts/audit-source-coverage.sh" \
    "$build_root/audit-source-coverage.sh"

# Keep the editable branding inputs beside the live-build recipe in the source
# ISO.  The checked-in PNGs under config/ are rendered outputs; these files are
# the canonical art, its provenance, the deterministic renderer, and the
# license needed to reproduce those outputs.
source_recipe_root="$build_root/config/includes.source/kythos-recipe"
required_source_recipe_files=(
    assets/branding/IMAGEGEN-PROMPT.md
    assets/branding/kythos-mark-white.svg
    assets/branding/kythos-boot-source.png
    assets/branding/kythos-installer-banner-source.png
    assets/branding/kythos-mark-cyan-source.png
    scripts/render-branding.py
    scripts/stage-edition.py
    scripts/build.sh
    scripts/build-arm64.sh
    scripts/check-multiarch-pair.py
    scripts/build-calamares-partition.sh
    scripts/validate-source.sh
    patches/calamares/0001-validate-proposed-boot-and-swap-layout.patch
    patches/calamares/README.md
    patches/calamares/COPYING
    LICENSE
    NOTICE
    docs/BRANDING.md
    docs/NETWORKING.md
    docs/ARM64.md
    config/includes.chroot/usr/share/kythos/architecture-profiles.json
    config/includes.chroot/usr/local/libexec/kythos-architecture
    config/includes.chroot/usr/share/kythos/edition-profiles.json
    config/includes.chroot/usr/local/libexec/kythos-edition
    docs/COMMAND-SUGGESTIONS.md
    docs/CONSOLE.md
    config/includes.installer/etc/lsb-release
    config/includes.installer/usr/lib/debian-installer-startup.d/S19kythos-branding
    config/includes.installer/usr/lib/kythos/debconf-loadtemplate
    config/includes.installer/usr/lib/kythos/transform-installer-template
    config/includes.chroot/etc/update-motd.d/10-uname
    config/includes.chroot/etc/profile.d/50-kythos-path.sh
    config/includes.chroot/etc/NetworkManager/system-connections/90-kythos-automatic-ethernet.nmconnection
    config/hooks/live/025-network-defaults.hook.chroot
    config/hooks/live/026-shell-suggestions.hook.chroot
    config/hooks/live/027-console-header.hook.chroot
    config/includes.chroot/etc/profile.d/55-kythos-console.sh
    config/includes.chroot/usr/local/libexec/kythos-console-session
    config/includes.chroot/usr/local/libexec/kythos-kernel-console
    config/includes.chroot/usr/lib/systemd/system/kythos-kernel-console.service
    config/includes.chroot/usr/local/bin/kythos-console
    config/includes.chroot/usr/share/kythos/console-tmux.conf
    config/includes.chroot/etc/profile.d/60-kythos-suggestions.sh
    config/includes.chroot/usr/local/libexec/kythos-command-suggest
    config/includes.chroot/usr/local/bin/kythos-help
    config/includes.chroot/etc/apt/apt.conf.d/91-kythos-command-index
    config/includes.chroot/usr/share/man/man1/kythos-help.1
    config/includes.chroot/usr/share/man/man8/cy.8
    config/includes.chroot/usr/share/kythos/command-intents.json
    tests/test-installer-branding.sh
    tests/test-login-branding.sh
    tests/test-calamares-core.py
    tests/test-setup-wizard.py
    tests/test-installer-removal-plan.py
    tests/test-fido2-login.py
    tests/test-hardware-status.py
    tests/test-cy-help.py
    tests/test-network-defaults.py
    tests/test-architecture.py
    tests/test-multiarch-pair.py
    tests/test-command-suggest.py
    tests/test-command-index.py
    tests/test-command-suggestions-bash.py
    tests/test-console-header.py
    tests/test-kernel-console.py
    tests/calamares-storage-policy.cpp
)
for required_source_recipe_file in "${required_source_recipe_files[@]}"
do
    [[ -f $repo_root/$required_source_recipe_file \
        && ! -L $repo_root/$required_source_recipe_file ]] || {
        printf 'Missing or unsafe source-recipe file: %s\n' \
            "$required_source_recipe_file" >&2
        exit 1
    }
done
# Preserve a complete editable recipe, including every script and test needed
# to rebuild it. Only these reviewed source trees enter this payload; Git,
# local builds, caches, credentials and VM state are never copied.
install -d -m 0755 "$source_recipe_root"
for source_directory in auto config scripts tests assets docs tools patches; do
    rsync -a --exclude='__pycache__/' --exclude='*.py[cod]' \
        "$repo_root/$source_directory/" "$source_recipe_root/$source_directory/"
done
for source_file in LICENSE NOTICE README.md SECURITY.md SNAPSHOT VERSION; do
    install -m 0644 "$repo_root/$source_file" "$source_recipe_root/$source_file"
done
chown -R 0:0 "$source_recipe_root"
chmod -R u=rwX,go=rX "$source_recipe_root"
(
    cd "$source_recipe_root"
    find LICENSE NOTICE README.md SECURITY.md SNAPSHOT VERSION \
        auto assets scripts docs config tests tools patches -type f -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum --check SHA256SUMS
)

(
    cd "$repo_root"
    {
        find auto config scripts tests patches \( -type f -o -type l \) \
            ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' -print0
        printf '%s\0' \
            assets/branding/IMAGEGEN-PROMPT.md \
            assets/branding/kythos-mark-white.svg \
            assets/branding/kythos-boot-source.png \
            assets/branding/kythos-installer-banner-source.png \
            assets/branding/kythos-mark-cyan-source.png \
            tools/qemu-builder/preseed.cfg
        printf 'LICENSE\0NOTICE\0docs/BRANDING.md\0SNAPSHOT\0VERSION\0'
    } | LC_ALL=C sort -z | xargs -0 sha256sum
) > "$artifact_root/recipe-SHA256SUMS"

dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' \
    | LC_ALL=C sort > "$artifact_root/builder-packages.tsv"

git_commit=unavailable
git_state=not-a-git-worktree
if command -v git >/dev/null 2>&1 \
    && git -c safe.directory="$repo_root" -C "$repo_root" \
        rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git -c safe.directory="$repo_root" -C "$repo_root" \
        rev-parse --verify HEAD >/dev/null 2>&1; then
        git_commit=$(git -c safe.directory="$repo_root" -C "$repo_root" rev-parse HEAD)
    else
        git_commit=unborn
    fi
    if test -z "$(git -c safe.directory="$repo_root" -C "$repo_root" status --porcelain)"; then
        git_state=clean
    else
        git_state=dirty
    fi
fi

if [[ -z ${SOURCE_DATE_EPOCH:-} ]]; then
    if [[ $git_state == clean && $git_commit =~ ^[0-9a-f]{40}$ ]]; then
        SOURCE_DATE_EPOCH=$(git -c safe.directory="$repo_root" -C "$repo_root" \
            show -s --format=%ct "$git_commit")
    else
        printf '%s\n' \
            'Set SOURCE_DATE_EPOCH, or build from a clean Git commit.' >&2
        exit 1
    fi
fi
if [[ ! $SOURCE_DATE_EPOCH =~ ^[0-9]+$ ]]; then
    printf '%s\n' 'SOURCE_DATE_EPOCH must be a decimal Unix timestamp.' >&2
    exit 1
fi
export SOURCE_DATE_EPOCH

# Use an authenticated, exact Debian source package for the small native
# partition validation change. Build dependencies must already be installed
# in this dedicated Debian guest; this does not install packages on a host.
native_root="$build_root/native-calamares"
install -d -m 0755 "$native_root/source" "$native_root/output"
(
    cd "$native_root/source"
    apt-get -o Acquire::Retries=5 --only-source source calamares=3.3.14-1
)
"$repo_root/scripts/build-calamares-partition.sh" \
    "$native_root/source/calamares-3.3.14" "$native_root/output" \
    2>&1 | tee "$artifact_root/calamares-partition-build.log"
native_image_root="$build_root/config/includes.chroot/usr/lib/kythos/calamares/modules"
install -d -m 0755 "$native_image_root"
cp -a "$native_root/output/partition" "$native_image_root/"
install -m 0644 "$native_root/output/provenance.json" \
    "$build_root/config/includes.chroot/usr/share/kythos/calamares-partition-provenance.json"
install -m 0644 "$native_root/output/provenance.json" \
    "$artifact_root/calamares-partition-provenance.json"
# The source ISO's standard package closure contains the exact upstream source;
# the editable patch, build script, policy test and GPL license are above.
install -d -m 0755 "$build_root/config/includes.chroot/usr/share/doc/kythos-calamares-partition"
install -m 0644 "$repo_root/patches/calamares/COPYING" \
    "$build_root/config/includes.chroot/usr/share/doc/kythos-calamares-partition/COPYING"
install -m 0644 "$repo_root/patches/calamares/README.md" \
    "$build_root/config/includes.chroot/usr/share/doc/kythos-calamares-partition/README"

{
    printf 'run_id=%s\n' "$run_id"
    printf 'source_date_epoch=%s\n' "$SOURCE_DATE_EPOCH"
    printf 'source_git_commit=%s\n' "$git_commit"
    printf 'source_git_state=%s\n' "$git_state"
    printf 'debian_snapshot=%s\n' "$snapshot"
    printf 'debian_architecture=%s\n' "$architecture"
    printf 'edition=%s\n' "$edition"
    printf 'builder_execution=%s\n' "${KYTHOS_BUILDER_EXECUTION:-unspecified}"
    printf 'snapshot_debian=%s\n' \
        "https://snapshot.debian.org/archive/debian/$snapshot/"
    printf 'snapshot_debian_security=%s\n' \
        "https://snapshot.debian.org/archive/debian-security/$snapshot/"
    printf 'download_cache_seed=%s\n' "$cache_seed"
    printf 'download_cache_seed_scope=%s\n' "$cache_seed_scope"
    printf 'builder_kernel=%s\n' "$(uname -srvmo)"
    printf '%s\n' 'builder_os_release:'
    sed 's/^/  /' /etc/os-release
    printf '%s\n' 'build_tools:'
    dpkg-query -W -f='  ${binary:Package}\t${Version}\n' \
        live-build debootstrap squashfs-tools xorriso
} > "$artifact_root/build-provenance.txt"

cd "$build_root"
lb config
cp -a config "$artifact_root/live-build-config"
(
    cd "$artifact_root"
    find live-build-config -type f -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "$artifact_root/live-build-config-SHA256SUMS"

lb build 2>&1 | tee "$artifact_root/build.log"

expected_binary_iso="$build_root/${image_name}-${architecture}.hybrid.iso"
expected_source_iso="$build_root/${image_name}-source.iso"
for expected_iso in "$expected_binary_iso" "$expected_source_iso"; do
    if [[ ! -f $expected_iso ]]; then
        printf 'Required ISO was not produced: %s\n' "$expected_iso" >&2
        exit 1
    fi
done

missing_source_report="$build_root/source/missing-source.txt"
if [[ -f $missing_source_report ]]; then
    cp -a "$missing_source_report" \
        "$artifact_root/live-build-missing-source.txt"
else
    : > "$artifact_root/live-build-missing-source.txt"
fi
if [[ -s $artifact_root/live-build-missing-source.txt ]]; then
    printf '%s\n' \
        'live-build reported binary packages without matching downloaded source.' >&2
    exit 1
fi

source_recipe_audit_root=$(mktemp -d \
    "$build_root/.source-recipe-audit.XXXXXXXXXX")
cleanup_source_recipe_audit()
{
    rm -rf -- "$source_recipe_audit_root"
}
trap cleanup_source_recipe_audit EXIT HUP INT TERM
xorriso -osirrox on -indev "$expected_source_iso" \
    -extract /live/config/includes.source/kythos-recipe \
    "$source_recipe_audit_root/kythos-recipe" >/dev/null 2>&1 || {
    printf '%s\n' 'Source ISO lacks the KythOS branding recipe.' >&2
    exit 1
}
(
    cd "$source_recipe_audit_root/kythos-recipe"
    sha256sum --check SHA256SUMS
)
while IFS= read -r -d '' staged_source
do
    relative_staged_source=${staged_source#"$source_recipe_root/"}
    cmp -s -- "$staged_source" \
        "$source_recipe_audit_root/kythos-recipe/$relative_staged_source" || {
        printf 'Source ISO branding recipe differs: %s\n' \
            "$relative_staged_source" >&2
        exit 1
    }
done < <(find "$source_recipe_root" -type f -print0 | LC_ALL=C sort -z)
cleanup_source_recipe_audit
trap - EXIT HUP INT TERM

"$build_root/audit-source-coverage.sh" \
    "$expected_binary_iso" "$expected_source_iso" "$artifact_root"

snapshot_metadata_directory="$build_root/snapshot-InRelease"
snapshot_metadata_sums="$build_root/snapshot-InRelease-SHA256SUMS"
[[ -d $snapshot_metadata_directory && -s $snapshot_metadata_sums ]] || {
    printf '%s\n' 'Source hook did not preserve signed snapshot metadata.' >&2
    exit 1
}
cp -a "$snapshot_metadata_sums" "$artifact_root/"
while IFS= read -r -d '' snapshot_metadata_file; do
    cp -a "$snapshot_metadata_file" "$artifact_root/"
done < <(find "$snapshot_metadata_directory" -maxdepth 1 \
    -type f -name '*InRelease' -print0)

while IFS= read -r -d '' output
do
    cp -a "$output" "$artifact_root/"
done < <(find "$build_root" -maxdepth 1 -type f \
    \( -name '*.iso' -o -name '*.img' -o -name '*.contents' \
       -o -name '*.packages' -o -name '*.files' -o -name '*.buildinfo' \
       -o -name '*.zsync' \) -print0)

(
    cd "$artifact_root"
    # SHA256SUMS is excluded from its own input set before the redirection
    # creates it, so there is no read/write overlap.
    # shellcheck disable=SC2094
    find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\0' \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum > SHA256SUMS
    # shellcheck disable=SC2094
    sha256sum --check SHA256SUMS
)

printf 'KythOS Kernal artifacts: %s\n' "$artifact_root"
