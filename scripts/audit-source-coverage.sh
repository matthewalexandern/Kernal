#!/bin/bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 3 ]]; then
    printf 'Usage: %s BINARY_ISO SOURCE_ISO OUTPUT_DIRECTORY\n' "$0" >&2
    exit 2
fi
if [[ $(id -u) -ne 0 ]]; then
    printf '%s\n' 'Source coverage audit must run as root.' >&2
    exit 1
fi

binary_iso=$(readlink -f -- "$1")
source_iso=$(readlink -f -- "$2")
output_directory=$(readlink -f -- "$3")
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
license_file=$script_directory/LICENSE
notice_file=$script_directory/NOTICE
for required_file in "$binary_iso" "$source_iso"; do
    [[ -f $required_file ]] || {
        printf 'Missing ISO: %s\n' "$required_file" >&2
        exit 1
    }
done
[[ -f $license_file ]] || {
    printf 'Missing canonical KythOS license: %s\n' "$license_file" >&2
    exit 1
}
[[ -f $notice_file ]] || {
    printf 'Missing canonical KythOS notice: %s\n' "$notice_file" >&2
    exit 1
}
[[ -d $output_directory && ! -L $output_directory ]] || {
    printf 'Unsafe audit output directory: %s\n' "$output_directory" >&2
    exit 1
}

for command_name in dpkg-deb dpkg-query mount sha256sum unsquashfs umount; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Missing audit command: %s\n' "$command_name" >&2
        exit 1
    }
done

audit_root=$(mktemp -d "$output_directory/.source-audit.XXXXXXXXXX")
binary_mount=$audit_root/binary
source_mount=$audit_root/source
status_directory=$audit_root/dpkg
mkdir -m 0700 "$binary_mount" "$source_mount" "$status_directory"
binary_mounted=false
source_mounted=false
cleanup()
{
    cleanup_status=$?
    if [[ $source_mounted == true ]]; then
        umount -- "$source_mount" || :
    fi
    if [[ $binary_mounted == true ]]; then
        umount -- "$binary_mount" || :
    fi
    rm -rf -- "$audit_root"
    return "$cleanup_status"
}
trap cleanup EXIT HUP INT TERM

mount -o loop,ro -- "$binary_iso" "$binary_mount"
binary_mounted=true
mount -o loop,ro -- "$source_iso" "$source_mount"
source_mounted=true

cmp -s "$license_file" "$binary_mount/LICENSE" || {
    printf '%s\n' 'Binary ISO license differs from the project license.' >&2
    exit 1
}
cmp -s "$license_file" "$source_mount/LICENSE" || {
    printf '%s\n' 'Source ISO license differs from the project license.' >&2
    exit 1
}
unsquashfs -cat "$binary_mount/live/filesystem.squashfs" \
    usr/share/doc/kythos-kernal/copyright > "$audit_root/installed-license"
cmp -s "$license_file" "$audit_root/installed-license" || {
    printf '%s\n' 'Installed KythOS license differs from the project license.' >&2
    exit 1
}
for image_mount in "$binary_mount" "$source_mount"; do
    cmp -s "$notice_file" "$image_mount/NOTICE" || {
        printf '%s\n' 'ISO attribution notice differs from the project notice.' >&2
        exit 1
    }
done
unsquashfs -cat "$binary_mount/live/filesystem.squashfs" \
    usr/share/doc/kythos-kernal/NOTICE > "$audit_root/installed-notice"
cmp -s "$notice_file" "$audit_root/installed-notice" || {
    printf '%s\n' 'Installed attribution notice differs from the project notice.' >&2
    exit 1
}

grep -Eq '^KythOS Kernal [^[:space:]]+ amd64 Binary$' \
    "$binary_mount/.disk/info" || {
    printf '%s\n' 'Binary ISO disk identity is not KythOS.' >&2
    exit 1
}
grep -Eq '^KythOS Kernal [^[:space:]]+ amd64 source$' \
    "$source_mount/.disk/info" || {
    printf '%s\n' 'Source ISO disk identity is not KythOS.' >&2
    exit 1
}
unsquashfs -cat "$binary_mount/live/filesystem.squashfs" etc/os-release \
    > "$audit_root/etc-os-release"
unsquashfs -cat "$binary_mount/live/filesystem.squashfs" usr/lib/os-release \
    > "$audit_root/usr-lib-os-release"
cmp -s "$audit_root/etc-os-release" "$audit_root/usr-lib-os-release" || {
    printf '%s\n' 'The two installed OS identity files differ.' >&2
    exit 1
}
grep -Fxq 'ID=kythos' "$audit_root/etc-os-release" \
    && grep -Fxq 'ID_LIKE=debian' "$audit_root/etc-os-release" \
    && grep -Fxq 'NAME="KythOS Kernal"' "$audit_root/etc-os-release" \
    && grep -Fxq 'IMAGE_ID=kythos-live' "$audit_root/etc-os-release" || {
    printf '%s\n' 'Installed OS identity fields are incomplete.' >&2
    exit 1
}
case "${SOURCE_DATE_EPOCH:-}" in
    ''|*[!0-9]*)
        printf '%s\n' 'SOURCE_DATE_EPOCH is unavailable to the image audit.' >&2
        exit 1
        ;;
esac
expected_build_id=$(date -u -d "@$SOURCE_DATE_EPOCH" +%Y%m%dT%H%M%SZ)
grep -Fxq "BUILD_ID=\"$expected_build_id\"" "$audit_root/etc-os-release" || {
    printf '%s\n' 'Installed BUILD_ID differs from SOURCE_DATE_EPOCH.' >&2
    exit 1
}
unsquashfs -cat "$binary_mount/live/filesystem.squashfs" \
    etc/dpkg/origins/kythos > "$audit_root/dpkg-origin"
grep -Fxq 'Vendor: KythOS' "$audit_root/dpkg-origin" \
    && grep -Fxq 'Parent: Debian' "$audit_root/dpkg-origin" || {
    printf '%s\n' 'Installed dpkg derivative identity is incomplete.' >&2
    exit 1
}

source_manifest=$source_mount/binary-source-manifest.tsv
required_manifest=$source_mount/required-source-tuples.tsv
[[ -f $source_manifest && -f $required_manifest ]] || {
    printf '%s\n' 'Source ISO lacks the KythOS source coverage manifests.' >&2
    exit 1
}
expected_header=$'kind\tbinary_or_path\tbinary_version\tsource\tsource_version\tsha256'
[[ $(head -n 1 "$source_manifest") == "$expected_header" ]] || {
    printf '%s\n' 'Source coverage manifest header is invalid.' >&2
    exit 1
}

expected_pool=$audit_root/expected-pool.tsv
actual_pool=$audit_root/actual-pool.tsv
awk -F '\t' '$1 == "iso-pool"' "$source_manifest" \
    | LC_ALL=C sort -u > "$expected_pool"
: > "$actual_pool"
while IFS= read -r -d '' binary_package; do
    package_name=$(dpkg-deb -f "$binary_package" Package)
    binary_version=$(dpkg-deb -f "$binary_package" Version)
    source_field=$(dpkg-deb -f "$binary_package" Source 2>/dev/null || true)
    if [[ -n $source_field ]]; then
        source_name=${source_field%%[[:space:]]*}
        if [[ $source_field == *' ('*')' ]]; then
            source_version=${source_field#* (}
            source_version=${source_version%)}
        else
            source_version=$(sed 's/+b[0-9][0-9]*$//' <<< "$binary_version")
        fi
    else
        source_name=$package_name
        source_version=$(sed 's/+b[0-9][0-9]*$//' <<< "$binary_version")
    fi
    package_path=${binary_package#"$binary_mount"/}
    package_sha256=$(sha256sum "$binary_package")
    package_sha256=${package_sha256%% *}
    printf 'iso-pool\t%s\t%s\t%s\t%s\t%s\n' \
        "$package_path" "$binary_version" "$source_name" \
        "$source_version" "$package_sha256" >> "$actual_pool"
done < <(find "$binary_mount/pool" "$binary_mount/pool-udeb" -type f \
    \( -name '*.deb' -o -name '*.udeb' \) -print0)
LC_ALL=C sort -u -o "$actual_pool" "$actual_pool"
cmp -s "$expected_pool" "$actual_pool" || {
    diff -u "$expected_pool" "$actual_pool" >&2 || :
    printf '%s\n' 'Binary ISO pool differs from its source manifest.' >&2
    exit 1
}

live_squashfs=$binary_mount/live/filesystem.squashfs
[[ -f $live_squashfs ]] || {
    printf '%s\n' 'Binary ISO lacks the live SquashFS image.' >&2
    exit 1
}
unsquashfs -cat "$live_squashfs" var/lib/dpkg/status \
    > "$status_directory/status"
expected_live=$audit_root/expected-live.tsv
actual_live=$audit_root/actual-live.tsv
awk -F '\t' '$1 == "live-root"' "$source_manifest" \
    | LC_ALL=C sort -u > "$expected_live"
dpkg-query --admindir="$status_directory" -W \
    -f='live-root\t${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\t-\n' \
    | LC_ALL=C sort -u > "$actual_live"
cmp -s "$expected_live" "$actual_live" || {
    diff -u "$expected_live" "$actual_live" >&2 || :
    printf '%s\n' 'Live filesystem package set differs from its source manifest.' >&2
    exit 1
}

derived_required=$audit_root/derived-required.tsv
provided_sources=$audit_root/provided-source.tsv
missing_sources=$audit_root/missing-source.tsv
verified_source_payloads=$audit_root/verified-source-payloads.txt
: > "$verified_source_payloads"
awk -F '\t' 'NR > 1 { print $4 "\t" $5 }' "$source_manifest" \
    | LC_ALL=C sort -u > "$derived_required"
cmp -s "$required_manifest" "$derived_required" || {
    printf '%s\n' 'Required-source tuple manifest is inconsistent.' >&2
    exit 1
}
while IFS= read -r -d '' dsc; do
    source_name=$(sed -n 's/^Source: //p' "$dsc")
    source_version=$(sed -n 's/^Version: //p' "$dsc")
    [[ -n $source_name && -n $source_version ]] || {
        printf 'Invalid Debian source control file: %s\n' "$dsc" >&2
        exit 1
    }
    printf '%s\t%s\n' "$source_name" "$source_version"

    dsc_checksums=$audit_root/dsc-checksums.tsv
    if ! awk '
        $1 == "Checksums-Sha256:" { in_checksums=1; next }
        in_checksums && /^[[:space:]]/ {
            if (NF != 3) exit 2
            print $1 "\t" $2 "\t" $3
            next
        }
        in_checksums { exit }
    ' "$dsc" > "$dsc_checksums"; then
        printf 'Invalid Checksums-Sha256 stanza: %s\n' "$dsc" >&2
        exit 1
    fi
    [[ -s $dsc_checksums ]] || {
        printf 'Missing Checksums-Sha256 stanza: %s\n' "$dsc" >&2
        exit 1
    }
    while IFS=$'\t' read -r expected_hash expected_size source_filename; do
        [[ $expected_hash =~ ^[0-9a-f]{64}$ \
            && $expected_size =~ ^[0-9]+$ \
            && -n $source_filename \
            && $source_filename != */* \
            && $source_filename != . \
            && $source_filename != .. ]] || {
            printf 'Unsafe source payload record in %s: %s\n' \
                "$dsc" "$source_filename" >&2
            exit 1
        }
        source_payload=$(dirname -- "$dsc")/$source_filename
        [[ -f $source_payload \
            && $(stat -Lc '%s' -- "$source_payload") == "$expected_size" \
            && $(sha256sum "$source_payload" | awk '{ print $1 }') \
                == "$expected_hash" ]] || {
            printf 'Missing or corrupt source payload for %s: %s\n' \
                "$dsc" "$source_filename" >&2
            exit 1
        }
        printf '%s\n' "$source_payload" >> "$verified_source_payloads"
    done < "$dsc_checksums"
done < <(find "$source_mount" -type f -name '*.dsc' -print0) \
    | LC_ALL=C sort -u > "$provided_sources"
source_payload_count=$(wc -l < "$verified_source_payloads")
[[ $source_payload_count -gt 0 ]] || {
    printf '%s\n' 'No source payload files were verified.' >&2
    exit 1
}
comm -23 "$derived_required" "$provided_sources" > "$missing_sources"
if [[ -s $missing_sources ]]; then
    printf '%s\n' 'Source ISO lacks exact source/version tuples:' >&2
    cat "$missing_sources" >&2
    exit 1
fi

cp "$source_manifest" "$output_directory/binary-source-manifest.tsv"
cp "$required_manifest" "$output_directory/required-source-tuples.tsv"
{
    printf 'binary_pool_packages=%s\n' "$(wc -l < "$actual_pool")"
    printf 'live_root_packages=%s\n' "$(wc -l < "$actual_live")"
    printf 'required_source_tuples=%s\n' "$(wc -l < "$derived_required")"
    printf 'provided_source_tuples=%s\n' "$(wc -l < "$provided_sources")"
    printf 'source_payload_files_verified=%s\n' "$source_payload_count"
    printf '%s\n' 'missing_source_tuples=0'
} > "$output_directory/source-coverage-audit.txt"
{
    printf 'binary_disk_info=%s\n' "$(cat "$binary_mount/.disk/info")"
    printf 'source_disk_info=%s\n' "$(cat "$source_mount/.disk/info")"
    printf 'build_id=%s\n' "$expected_build_id"
    printf '%s\n' 'os_id=kythos'
    printf '%s\n' 'os_id_like=debian'
    printf '%s\n' 'dpkg_vendor=KythOS'
    printf '%s\n' 'dpkg_parent=Debian'
    printf '%s\n' 'license_copies=verified'
} > "$output_directory/image-identity-audit.txt"

umount -- "$source_mount"
source_mounted=false
umount -- "$binary_mount"
binary_mounted=false
trap - EXIT HUP INT TERM
rm -rf -- "$audit_root"
printf '%s\n' 'Binary/source ISO coverage audit passed.'
