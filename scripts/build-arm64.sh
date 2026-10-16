#!/bin/sh
# Build the common recipe natively inside an isolated Debian 13 ARM64 guest.
set -eu
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
if test "$#" -ne 0; then
    printf '%s\n' 'This entrypoint does not accept build overrides.' >&2
    exit 2
fi
if test "$(dpkg --print-architecture)" != arm64; then
    printf '%s\n' 'Run this entrypoint inside the Debian 13 ARM64 builder.' >&2
    exit 1
fi
export KYTHOS_ARCH=arm64
exec "$repo_root/scripts/build.sh" "$@"
