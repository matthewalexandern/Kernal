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

for command_name in lb debootstrap mksquashfs xorriso rsync; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Missing build command: %s\n' "$command_name" >&2
        exit 1
    }
done

"$repo_root/scripts/validate-source.sh"

run_id=$(date -u +%Y%m%dT%H%M%SZ)
build_root=${KYTHOS_BUILD_ROOT:-"$repo_root/.build/$run_id"}
artifact_root=${KYTHOS_ARTIFACT_ROOT:-"$repo_root/artifacts/$run_id"}
version=$(cat "$repo_root/VERSION")
image_name="kythos-kernal-base-${version}"

if [[ -e $build_root || -e $artifact_root ]]; then
    printf '%s\n' 'Refusing to reuse an existing build or artifact directory.' >&2
    exit 1
fi

install -d -m 0755 "$build_root" "$artifact_root"
cp -a "$repo_root/auto" "$repo_root/config" "$repo_root/VERSION" "$build_root/"
install -d -m 0755 "$build_root/config/includes.chroot/usr/share/kythos"
install -m 0644 "$repo_root/VERSION" \
    "$build_root/config/includes.chroot/usr/share/kythos/version"

(
    cd "$repo_root"
    {
        find auto config scripts -type f -print0
        printf 'VERSION\0'
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

export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(date -u +%s)}

{
    printf 'run_id=%s\n' "$run_id"
    printf 'source_date_epoch=%s\n' "$SOURCE_DATE_EPOCH"
    printf 'source_git_commit=%s\n' "$git_commit"
    printf 'source_git_state=%s\n' "$git_state"
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

expected_binary_iso="$build_root/${image_name}-amd64.hybrid.iso"
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
