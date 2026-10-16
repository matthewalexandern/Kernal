#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
header="$repo_root/config/includes.chroot/etc/update-motd.d/10-uname"
sh -n "$header"
test -x "$header"

work=$(mktemp -d)
cleanup()
{
    rm -rf -- "$work"
}
trap cleanup EXIT HUP INT TERM

# A kernel package may include an upstream vendor in uname -v. The login
# presentation must show real release/architecture fields and never request
# or rewrite that build-provenance field.
mkdir "$work/bin"
cat > "$work/bin/uname" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$KYTHOS_TEST_UNAME_CALLS"
case "$*" in
    -s) printf '%s\n' Linux ;;
    -r) printf '%s\n' 6.12.test+vendor-amd64 ;;
    -m) printf '%s\n' x86_64 ;;
    *) printf '%s\n' 'unexpected uname field' >&2; exit 1 ;;
esac
EOF
chmod 0755 "$work/bin/uname"
PATH="$work/bin:$PATH" KYTHOS_TEST_UNAME_CALLS="$work/uname-calls" \
    "$header" > "$work/header"
printf '%s\n' 'Kernel: Linux 6.12.test+vendor-amd64 (x86_64)' > "$work/expected"
cmp "$work/expected" "$work/header"
printf '%s\n' -s -r -m > "$work/expected-calls"
cmp "$work/expected-calls" "$work/uname-calls"

# Verify it is executable through the real login fragment dispatcher.
run-parts --test "$(dirname -- "$header")" | grep -Fxq "$header"

printf '%s\n' 'login branding tests passed'
