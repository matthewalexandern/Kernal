#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
policy=$repo_root/config/includes.chroot/usr/local/libexec/kythos-recovery-topology.awk
failures=0

expect_accept()
{
    test_name=$1
    source_type=$2
    topology=$3
    forward_topology=${4-"TYPE=\"$source_type\""}
    if ! printf '%s\n' "$topology" \
        | awk -v "source_type=$source_type" \
            -v "forward_topology=$forward_topology" -f "$policy"; then
        printf 'FAIL: rejected safe topology: %s\n' "$test_name" >&2
        failures=$((failures + 1))
    fi
}

expect_reject()
{
    test_name=$1
    source_type=$2
    topology=$3
    forward_topology=${4-"TYPE=\"$source_type\""}
    if printf '%s\n' "$topology" \
        | awk -v "source_type=$source_type" \
            -v "forward_topology=$forward_topology" -f "$policy"; then
        printf 'FAIL: accepted unsafe topology: %s\n' "$test_name" >&2
        failures=$((failures + 1))
    fi
}

expect_accept 'USB partition' part \
    'TYPE="part" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"'
expect_accept 'removable SD disk' disk \
    'TYPE="disk" RM="1" TRAN="mmc"'
expect_accept 'FireWire disk' disk \
    'TYPE="disk" RM="0" TRAN="firewire"'

expect_reject 'internal NVMe partition' part \
    'TYPE="part" RM="0" TRAN="nvme"
TYPE="disk" RM="0" TRAN="nvme"'
expect_reject 'mixed USB and internal RAID' raid1 \
    'TYPE="raid1" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"
TYPE="disk" RM="0" TRAN="sata"'
expect_reject 'two external members' raid1 \
    'TYPE="raid1" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"
TYPE="disk" RM="1" TRAN="mmc"'
expect_reject 'device mapper over USB' crypt \
    'TYPE="crypt" RM="0" TRAN=""
TYPE="part" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"'
expect_reject 'direct partition with two parents' part \
    'TYPE="part" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"
TYPE="disk" RM="0" TRAN="sata"'
expect_reject 'partition is an active RAID member' part \
    'TYPE="part" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"' \
    'TYPE="part"
TYPE="raid1"'
expect_reject 'partition has active encryption and LVM holders' part \
    'TYPE="part" RM="0" TRAN=""
TYPE="disk" RM="0" TRAN="usb"' \
    'TYPE="part"
TYPE="crypt"
TYPE="lvm"'
expect_reject 'whole disk has partition children' disk \
    'TYPE="disk" RM="0" TRAN="usb"' \
    'TYPE="disk"
TYPE="part"'
expect_reject 'missing physical disk' part \
    'TYPE="part" RM="1" TRAN="usb"'
expect_reject 'malformed topology record' part \
    'TYPE="part" RM="0"
TYPE="disk" RM="0" TRAN="usb"'

test "$failures" -eq 0 || exit 1
printf '%s\n' 'Recovery topology policy tests passed.'
