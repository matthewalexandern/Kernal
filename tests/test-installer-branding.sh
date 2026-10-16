#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
filter="$repo_root/config/includes.installer/usr/lib/kythos/transform-installer-template"
wrapper="$repo_root/config/includes.installer/usr/lib/kythos/debconf-loadtemplate"
startup="$repo_root/config/includes.installer/usr/lib/debian-installer-startup.d/S19kythos-branding"

sh -n "$filter"
sh -n "$wrapper"
sh -n "$startup"

work=$(mktemp -d)
cleanup()
{
    rm -rf -- "$work"
}
trap cleanup EXIT HUP INT TERM

cat > "$work/input.templates" <<'EOF'
Template: debian-installer/main-menu-title
Type: text
Description: Debian installer main menu
Description-de.UTF-8: Debian-Installer --- Hauptmenu

Template: grub-installer/update-nvram
Type: boolean
Default: true
Description: Update NVRAM variables to automatically boot into Debian?
 GRUB can configure NVRAM so that it boots into Debian automatically.
	Keep https://www.debian.org/a/debian, deb.debian.org, README.Debian.gz,
	/usr/share/doc/README.Debian, debian-boot@lists.debian.org, and
	${DEBIAN_VENDOR};  Debian remains the visible operating-system identity.

Template: mirror/http/hostname
Type: string
Default: deb.debian.org
Description: Debian archive mirror hostname:
 Please enter the mirror from which Debian will be downloaded.

Template: example/choices
Type: select
Choices-C: debian, kythos
Choices: Debian, KythOS Kernal
Description: Keep machine-readable choices unchanged
EOF

"$filter" "$work/input.templates" "$work/output.templates"

grep -Fq 'Description: KythOS Kernal installer main menu' \
    "$work/output.templates"
grep -Fq 'Description-de.UTF-8: KythOS Kernal installer --- Hauptmenu' \
    "$work/output.templates"
grep -Fq 'Description: Update NVRAM variables to automatically boot into KythOS Kernal?' \
    "$work/output.templates"
grep -Fq ' boots into KythOS Kernal automatically.' "$work/output.templates"
cat > "$work/protected-expected" <<'EOF'
	Keep https://www.debian.org/a/debian, deb.debian.org, README.Debian.gz,
	/usr/share/doc/README.Debian, debian-boot@lists.debian.org, and
	${DEBIAN_VENDOR};  KythOS Kernal remains the visible operating-system identity.
EOF
grep -Fxf "$work/protected-expected" "$work/output.templates" >/dev/null

# Archive provenance, URLs, template identifiers, defaults, and choices are
# outside the explicit identity allowlist and must remain unchanged.
grep -Fq 'Template: debian-installer/main-menu-title' "$work/output.templates"
grep -Fq 'Default: deb.debian.org' "$work/output.templates"
grep -Fq 'Description: Debian archive mirror hostname:' "$work/output.templates"
grep -Fq ' Please enter the mirror from which Debian will be downloaded.' \
    "$work/output.templates"
grep -Fq 'Choices-C: debian, kythos' "$work/output.templates"
grep -Fq 'Choices: Debian, KythOS Kernal' "$work/output.templates"

# Exercise the wrapper with a stand-in native loader. The loader receives the
# original arguments and its status is returned without translation.
mkdir -p "$work/bin"
cat > "$work/bin/native" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" > "$KYTHOS_TEST_ARGUMENTS"
exit "${KYTHOS_TEST_STATUS:-0}"
EOF
chmod 0755 "$work/bin/native"

sed \
    -e "s#/usr/lib/cdebconf/debconf-loadtemplate#$work/bin/native#" \
    -e "s#/usr/lib/kythos/transform-installer-template#$filter#" \
    "$wrapper" > "$work/bin/wrapper"
chmod 0755 "$work/bin/wrapper"

cp "$work/input.templates" "$work/wrapped.templates"
KYTHOS_TEST_ARGUMENTS="$work/arguments" \
    "$work/bin/wrapper" --merge d-i "$work/wrapped.templates"
cat > "$work/expected-arguments" <<EOF
--merge
d-i
$work/wrapped.templates
EOF
cmp "$work/expected-arguments" "$work/arguments"
grep -Fq 'Description: KythOS Kernal installer main menu' \
    "$work/wrapped.templates"

set +e
KYTHOS_TEST_ARGUMENTS="$work/error-arguments" KYTHOS_TEST_STATUS=37 \
    "$work/bin/wrapper" d-i "$work/wrapped.templates"
status=$?
set -e
test "$status" -eq 37

printf '%s\n' 'installer branding transform tests passed'
