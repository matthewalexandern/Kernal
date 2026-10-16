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

python3 - "$repo_root" <<'PY'
import os
from pathlib import Path
import pty
import subprocess
import sys

root = Path(sys.argv[1])
issue = root / "config/includes.chroot/etc/issue"
assert issue.read_text() == "KythOS Kernal 2027 | https://kythos.ai \\l\n"
assert (root / "config/includes.chroot/etc/issue.net").read_text() == "KythOS Kernal 2027 | https://kythos.ai\n"
# Render through the real agetty issue parser, using only a private test PTY.
# --show-issue uses its synthetic tty1 context and exits without login/PAM.
master, slave = pty.openpty()
try:
    rendered = subprocess.run(
        ["/usr/sbin/agetty", "--show-issue", "--issue-file", str(issue)],
        stdin=slave, capture_output=True, text=True, timeout=5, check=True)
finally:
    os.close(slave)
    os.close(master)
assert rendered.stdout == "KythOS Kernal 2027 | https://kythos.ai tty1\n", rendered.stdout

profile = root / "config/includes.chroot/etc/profile.d/50-kythos-path.sh"
normal = "/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
admin = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
script = '. "$1"; first=$PATH; . "$1"; test "$first" = "$PATH"; printf "%s\\n" "$PATH"; command -v useradd'
for initial in (normal, admin):
    result = subprocess.run(
        ["/bin/sh", "-ec", script, "kythos-path-test", str(profile)],
        env={"PATH": initial}, capture_output=True, text=True, check=True)
    path, useradd = result.stdout.splitlines()
    expected = initial if initial == admin else normal + ":/usr/local/sbin:/usr/sbin:/sbin"
    assert path == expected, path
    assert useradd == "/usr/sbin/useradd", useradd
PY

printf '%s\n' 'login branding tests passed'
