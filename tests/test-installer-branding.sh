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

Template: cdrom/suite
Type: select
Choices-C: trixie
Default: trixie
Description: Debian version to install

Template: grub-installer/only_debian
Type: boolean
Default: true
Description: Install the bootloader?
Description-de.UTF-8: Diese Installation von Debian ist das einzige Betriebssystem.

Template: network-console/login
Type: note
Description-cs.UTF-8: instalace Debianu, s Debianem a debian-installeru
Description-fi.UTF-8: Debianiin, Debianin
Description-ku.UTF-8: Debianê
Description-de.UTF-8: Debian-Installers
Description-sv.UTF-8: Debiansystemet
 Keep DebianIdentifier, DebianSystemIdentifier, Debian_Identifier, boot_debian, and ${DEBIAN_VENDOR}.
Description-nn.UTF-8: Set inn Debian-installeringsmediet
Description-sv.UTF-8: medan Debian installeras.
Description-zh_TW.UTF-8: 更新NVRAM變數以自動啟動到Debian？
Description-ko.UTF-8: debian-installer는
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
grep -Fxq 'Description: KythOS Kernal version to install' "$work/output.templates"
grep -Fxq 'Choices-C: trixie' "$work/output.templates"
grep -Fxq 'Default: trixie' "$work/output.templates"
grep -Fxq 'Description-de.UTF-8: Diese Installation von KythOS Kernal ist das einzige Betriebssystem.' \
    "$work/output.templates"
grep -Fxq 'Description-cs.UTF-8: instalace KythOS Kernal, s KythOS Kernal a KythOS Kernal installer' \
    "$work/output.templates"
grep -Fxq 'Description-fi.UTF-8: KythOS Kernal, KythOS Kernal' "$work/output.templates"
grep -Fxq 'Description-ku.UTF-8: KythOS Kernal' "$work/output.templates"
grep -Fxq 'Description-de.UTF-8: KythOS Kernal installer' "$work/output.templates"
grep -Fxq 'Description-sv.UTF-8: KythOS Kernal systemet' "$work/output.templates"
grep -Fxq 'Description-nn.UTF-8: Set inn KythOS Kernal-installeringsmediet' \
    "$work/output.templates"
grep -Fxq 'Description-sv.UTF-8: medan KythOS Kernal installeras.' \
    "$work/output.templates"
grep -Fxq 'Description-zh_TW.UTF-8: 更新NVRAM變數以自動啟動到KythOS Kernal？' \
    "$work/output.templates"
grep -Fxq 'Description-ko.UTF-8: KythOS Kernal installer는' "$work/output.templates"
grep -Fq ' Keep DebianIdentifier, DebianSystemIdentifier, Debian_Identifier, boot_debian, and ${DEBIAN_VENDOR}.' \
    "$work/output.templates"

# Repeated template loads must not duplicate the product name or alter fields.
"$filter" "$work/output.templates" "$work/output-again.templates"
cmp "$work/output.templates" "$work/output-again.templates"

# Set only an editable fallback, not netcfg/hostname which forces the value
# over a network-provided name. The installer must still show the prompt.
preseed="$repo_root/config/includes.installer/preseed.cfg"
grep -Fxq 'd-i netcfg/get_hostname string kythos' "$preseed"
grep -Fxq 'd-i netcfg/get_hostname seen false' "$preseed"
if grep -Eq '^d-i netcfg/hostname[[:space:]]' "$preseed"; then
    printf '%s\n' 'installer hostname must remain editable' >&2
    exit 1
fi

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

# Execute the startup hook in an isolated path fixture. The optional log page
# changes its two headings while keeping machine paths and source URLs intact.
mkdir -p "$work/startup/usr/bin"
cat > "$work/startup/usr/bin/httpd" <<'EOF'
#!/bin/sh
echo "<title>Debian-installer logs and screenshots</title>"
echo "<b>Debian-installer logs and screenshots</b>"
echo "/var/log/debian-installer https://www.debian.org/"
EOF
sed \
    -e "s#/usr/lib/cdebconf/debconf-loadtemplate#$work/bin/native#g" \
    -e "s#/usr/lib/kythos/debconf-loadtemplate#$work/bin/wrapper#g" \
    -e "s#/usr/bin/debconf-loadtemplate#$work/startup/usr/bin/debconf-loadtemplate#g" \
    -e "s#/usr/bin/httpd#$work/startup/usr/bin/httpd#g" \
    "$startup" > "$work/bin/startup"
sh "$work/bin/startup"
test "$(readlink "$work/startup/usr/bin/debconf-loadtemplate")" = "$work/bin/wrapper"
test "$(grep -Fc 'KythOS Kernal installer logs and screenshots' "$work/startup/usr/bin/httpd")" -eq 2
grep -Fxq 'echo "/var/log/debian-installer https://www.debian.org/"' \
    "$work/startup/usr/bin/httpd"

printf '%s\n' 'installer branding transform tests passed'
