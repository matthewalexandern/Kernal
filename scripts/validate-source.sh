#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
errors=0

fail()
{
    printf 'ERROR: %s\n' "$*" >&2
    errors=$((errors + 1))
}

check_contains()
{
    file=$1
    value=$2
    grep -Fq -- "$value" "$file" || fail "$file is missing: $value"
}

for script in \
    "$repo_root/auto/config" \
    "$repo_root/scripts/build.sh" \
    "$repo_root/scripts/validate-source.sh" \
    "$repo_root/config/hooks/live/010-enable-security.hook.chroot" \
    "$repo_root/config/hooks/live/090-record-manifest.hook.chroot" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status"
do
    case "$script" in
        */build.sh) bash -n "$script" || fail "shell syntax failed: $script" ;;
        *) sh -n "$script" || fail "shell syntax failed: $script" ;;
    esac
    test -x "$script" || fail "script is not executable: $script"
done

config="$repo_root/auto/config"
check_contains "$config" "--distribution trixie"
check_contains "$config" "--archive-areas 'main contrib non-free non-free-firmware'"
check_contains "$config" "--apt-secure true"
check_contains "$config" "--apt-recommends true"
check_contains "$config" "--firmware-chroot true"
check_contains "$config" "--firmware-binary true"
check_contains "$config" "--linux-packages linux-image"
check_contains "$config" "--debian-installer live"
check_contains "$config" "--uefi-secure-boot enable"
check_contains "$config" "--source true"
check_contains "$config" "--ignore-system-defaults"
check_contains "$config" 'audit=1 audit_backlog_limit=8192'
# These are deliberately literal shell expressions required in auto/config.
# shellcheck disable=SC2016
check_contains "$config" 'version=$(cat "$repo_root/VERSION")'
# shellcheck disable=SC2016
check_contains "$config" '--image-name "kythos-kernal-base-${version}"'

version=$(cat "$repo_root/VERSION")
printf '%s\n' "$version" \
    | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([.+~-][0-9A-Za-z.+~-]+)?$' \
    || fail 'VERSION does not contain a valid release version'

test -f "$repo_root/config/includes.chroot/etc/systemd/system/nftables.service.d/60-kythos-stop.conf" \
    || fail 'nftables service stop override is required'
check_contains \
    "$repo_root/config/includes.chroot/etc/systemd/system/nftables.service.d/60-kythos-stop.conf" \
    'nft destroy table inet kythos_filter'

test -f "$repo_root/config/package-lists/live.list.chroot" \
    || fail 'tracked live.list.chroot is required'
test -f "$repo_root/config/package-lists/live.list.chroot_live" \
    || fail 'live-only package list is required'

tmp_packages=$(mktemp)
trap 'rm -f "$tmp_packages"' EXIT HUP INT TERM

for list in "$repo_root"/config/package-lists/*.list.*
do
    awk '!/^[[:space:]]*(#|!|$)/ { print $1 }' "$list"
done | LC_ALL=C sort > "$tmp_packages"

duplicates=$(uniq -d "$tmp_packages" || true)
test -z "$duplicates" || fail "duplicate explicit packages: $duplicates"

if command -v nft >/dev/null 2>&1 && test "$(id -u)" -eq 0; then
    nft --check \
        --includepath "$repo_root/config/includes.chroot/etc" \
        --file "$repo_root/config/includes.chroot/etc/nftables.conf" \
        || fail 'nftables configuration failed syntax validation'
fi

if test -r /etc/os-release; then
    # shellcheck disable=SC1091
    . /etc/os-release
    if test "${ID:-}" = debian && test "${VERSION_CODENAME:-}" = trixie; then
        while IFS= read -r package
        do
            apt-cache show "$package" >/dev/null 2>&1 \
                || fail "package unavailable in Debian 13: $package"
        done < "$tmp_packages"
    fi
fi

test "$errors" -eq 0 || exit 1
printf '%s\n' 'KythOS Kernal source validation passed.'
