#!/bin/sh
set -eu
umask 077

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
tpm_enrollment=$repo_root/config/includes.chroot/usr/local/sbin/kythos-enroll-tpm2
parser_library=$(mktemp)
trap 'rm -f -- "$parser_library"' EXIT HUP INT TERM

sed -n '/^read_live_pcr()$/,/^}$/p' "$tpm_enrollment" > "$parser_library"
test -s "$parser_library" || {
    printf '%s\n' 'FAIL: live PCR parser function is missing' >&2
    exit 1
}
# shellcheck disable=SC1090
. "$parser_library"

single_digit_value=0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
double_digit_value=0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
pcr_output="sha256:
  4 : $single_digit_value
  14: $double_digit_value"
failures=0

expect_value()
{
    label=$1
    expected=$2
    actual=$(printf '%s\n' "$pcr_output" | read_live_pcr "$label")
    if test "$actual" != "$expected"; then
        printf 'FAIL: PCR %s parsed as %s, expected %s\n' \
            "$label" "${actual:-<empty>}" "$expected" >&2
        failures=$((failures + 1))
    fi
}

expect_empty()
{
    label=$1
    actual=$(printf '%s\n' "$pcr_output" | read_live_pcr "$label")
    if test -n "$actual"; then
        printf 'FAIL: absent PCR %s parsed as %s\n' "$label" "$actual" >&2
        failures=$((failures + 1))
    fi
}

expect_value 4 "$single_digit_value"
expect_value 14 "$double_digit_value"
expect_empty 1
expect_empty 7

live_parser_calls=$(grep -F -c 'read_live_pcr "$measured_pcr"' \
    "$tpm_enrollment" || :)
if test "$live_parser_calls" -ne 2; then
    printf 'FAIL: expected two live PCR parser call sites, found %s\n' \
        "$live_parser_calls" >&2
    failures=$((failures + 1))
fi

test "$failures" -eq 0 || exit 1
printf '%s\n' 'TPM2 PCR-read parser tests passed.'
