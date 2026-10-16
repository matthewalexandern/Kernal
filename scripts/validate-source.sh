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
    "$repo_root/scripts/audit-source-coverage.sh" \
    "$repo_root/scripts/build.sh" \
    "$repo_root/scripts/build-calamares-partition.sh" \
    "$repo_root/scripts/render-branding.py" \
    "$repo_root/scripts/validate-source.sh" \
    "$repo_root/tests/test-recovery-topology.sh" \
    "$repo_root/tests/test-tpm2-pcrread-parser.sh" \
    "$repo_root/tests/test-installer-branding.sh" \
    "$repo_root/tests/test-login-branding.sh" \
    "$repo_root/config/hooks/live/005-add-grub2-source.hook.source" \
    "$repo_root/config/hooks/live/010-enable-security.hook.chroot" \
    "$repo_root/config/hooks/live/015-prepare-compliance.hook.chroot" \
    "$repo_root/config/hooks/live/020-enable-branding.hook.binary" \
    "$repo_root/config/hooks/live/020-enable-branding.hook.chroot" \
    "$repo_root/config/hooks/live/025-network-defaults.hook.chroot" \
    "$repo_root/config/hooks/live/026-shell-suggestions.hook.chroot" \
    "$repo_root/config/hooks/live/027-console-header.hook.chroot" \
    "$repo_root/config/hooks/live/030-configure-authentication.hook.chroot" \
    "$repo_root/config/hooks/live/060-record-installer-packages.hook.chroot" \
    "$repo_root/config/hooks/live/030-record-installer-packages.hook.binary" \
    "$repo_root/config/includes.installer/usr/lib/debian-installer-startup.d/S19kythos-branding" \
    "$repo_root/config/includes.installer/usr/lib/kythos/debconf-loadtemplate" \
    "$repo_root/config/includes.installer/usr/lib/kythos/transform-installer-template" \
    "$repo_root/config/includes.installer/usr/lib/finish-install.d/93kythos-live-cleanup" \
    "$repo_root/config/hooks/live/090-record-manifest.hook.chroot" \
    "$repo_root/config/includes.chroot/usr/local/bin/cy" \
    "$repo_root/config/includes.chroot/usr/local/bin/kythos-help" \
    "$repo_root/config/includes.chroot/usr/local/bin/kythos-installer" \
    "$repo_root/config/includes.chroot/usr/local/bin/kythos-install" \
    "$repo_root/config/includes.chroot/usr/local/libexec/kythos-live-guard" \
    "$repo_root/config/includes.chroot/usr/local/libexec/kythos-live-session" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-installer-root" \
    "$repo_root/config/includes.chroot/usr/lib/live/config/1200-kythos-installer" \
    "$repo_root/config/includes.chroot/etc/update-motd.d/10-uname" \
    "$repo_root/config/includes.chroot/usr/local/libexec/kythos-aide-initialize" \
    "$repo_root/config/includes.chroot/usr/local/libexec/kythos-refresh-fips-config" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-enroll-tpm2" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-fips-status" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-nvidia-readiness" \
    "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status"
do
    case "$script" in
        */render-branding.py)
            python3 - "$script" <<'PY' \
                || fail "Python syntax failed: $script"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY
            ;;
        */build.sh|*/audit-source-coverage.sh)
            bash -n "$script" || fail "shell syntax failed: $script"
            ;;
        *) sh -n "$script" || fail "shell syntax failed: $script" ;;
    esac
    test -x "$script" || fail "script is not executable: $script"
done

# This fragment is sourced only by interactive Bash, so validate it with Bash.
bash -n "$repo_root/config/includes.chroot/etc/profile.d/60-kythos-suggestions.sh" \
    || fail 'command suggestion Bash integration syntax failed'
bash -n "$repo_root/config/includes.chroot/etc/profile.d/55-kythos-console.sh" \
    || fail 'console Bash integration syntax failed'

# Compile without generating host-version bytecode in the image recipe.
python3 - "$repo_root" <<'PY' || fail 'Calamares or setup-guide syntax/configuration failed'
from pathlib import Path
import sys
import yaml
root = Path(sys.argv[1])
programs = [root / 'config/includes.chroot/usr/local/bin' / name
            for name in ('kythos-setup', 'kythos-hardware-status', 'kythos-console')]
programs.append(root / 'config/includes.chroot/usr/local/sbin/kythos-fido-login')
programs.append(root / 'config/includes.chroot/usr/local/libexec/kythos-command-suggest')
programs.append(root / 'config/includes.chroot/usr/local/libexec/kythos-console-session')
programs.append(root / 'config/includes.chroot/usr/local/libexec/kythos-architecture')
programs.append(root / 'scripts/check-multiarch-pair.py')
programs += sorted((root / 'config/includes.chroot/usr/local/libexec').glob('kythos-calamares-*'))
programs += sorted((root / 'config/includes.chroot/etc/calamares/modules').glob('kythos-*/*.py'))
for program in programs:
    compile(program.read_text(), str(program), 'exec')
for config in (root / 'config/includes.chroot/etc/calamares').rglob('*'):
    if config.suffix in ('.conf', '.desc') and not isinstance(yaml.safe_load(config.read_text()), dict):
        raise ValueError('Expected installer configuration map: ' + str(config))
PY
for installer_test in test-installer-removal-plan.py test-calamares-core.py test-setup-wizard.py test-fido2-login.py test-hardware-status.py test-cy-help.py test-network-defaults.py test-command-suggest.py test-command-index.py test-command-suggestions-bash.py test-console-header.py; do
    PYTHONDONTWRITEBYTECODE=1 python3 "$repo_root/tests/$installer_test" \
        || fail "installer test failed: $installer_test"
done
check_contains "$repo_root/auto/config" 'components live-config.nocomponents=sudo,xinit'
check_contains "$repo_root/config/bootloaders/grub-pc/grub.cfg" 'Install KythOS Kernal (Calamares)'
check_contains "$repo_root/config/bootloaders/grub-pc/grub.cfg" 'Advanced graphical installer'
check_contains "$repo_root/config/bootloaders/grub-pc/grub.cfg" 'Advanced text installer'
check_contains "$repo_root/config/includes.chroot/etc/sudoers.d/kythos-live-installer" \
    'kythos-installer-root ""'

security_status="$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status"
check_contains "$security_status" \
    "grep -q ' (enforce)$' /sys/kernel/security/apparmor/profiles"
if grep -Fq 'test -s /sys/kernel/security/apparmor/profiles' "$security_status"; then
    fail 'AppArmor securityfs state must be read, not tested by pseudo-file size'
fi

config="$repo_root/auto/config"
check_contains "$config" "--distribution trixie"
check_contains "$config" "--archive-areas 'main contrib non-free non-free-firmware'"
check_contains "$config" "--apt-secure true"
check_contains "$config" "--apt-options '--yes -o Acquire::Check-Valid-Until=false'"
check_contains "$config" "--apt-recommends true"
check_contains "$config" "--firmware-chroot false"
check_contains "$config" "--firmware-binary true"
check_contains "$config" "--linux-packages linux-image"
check_contains "$config" "--debian-installer live"
check_contains "$config" "--uefi-secure-boot enable"
check_contains "$config" "--source true"
check_contains "$config" "--ignore-system-defaults"
check_contains "$config" 'https://snapshot.debian.org/archive/debian/'
check_contains "$config" 'https://snapshot.debian.org/archive/debian-security/'
check_contains "$config" 'audit=1 audit_backlog_limit=8192'
check_contains "$repo_root/scripts/build.sh" 'find auto config scripts tests patches -type f'
check_contains "$repo_root/scripts/build.sh" "--exclude='__pycache__/'"
check_contains "$repo_root/scripts/build.sh" 'assets/branding/kythos-mark-cyan-source.png'
check_contains "$repo_root/scripts/build.sh" 'tools/qemu-builder/preseed.cfg'
check_contains "$repo_root/tools/qemu-builder/preseed.cfg" 'git live-build'
check_contains "$repo_root/tools/qemu-builder/preseed.cfg" 'python3-pil'

source_hook="$repo_root/config/hooks/live/005-add-grub2-source.hook.source"
check_contains "$source_hook" \
    '../binary/pool ../binary/pool-udeb ../cache/packages.binary'
check_contains "$source_hook" 'manifest_kind=binary-input'
check_contains "$source_hook" "-name '*.udeb'"
check_contains "$source_hook" 'chroot ../chroot dpkg-query -W'
check_contains "$source_hook" 'source_version=${source_field#* (}'
check_contains "$source_hook" "sed 's/+b[0-9][0-9]*$//'"
check_contains "$source_hook" 'apt-get -o Acquire::Retries=5 --only-source --download-only'
check_contains "$source_hook" '"$source_name=$source_version"'
check_contains "$source_hook" "sed -n 's/^Version: //p'"
check_contains "$source_hook" 'comm -23 "$required_tuples" "$provided_tuples"'
check_contains "$source_hook" 'binary-source-manifest.tsv'
check_contains "$source_hook" 'required-source-tuples.tsv'
check_contains "$source_hook" 'cp ../LICENSE LICENSE'
check_contains "$source_hook" 'cp ../NOTICE NOTICE'
check_contains "$source_hook" "placeholder = 'un  grub-efi       <none>       <none>       (no description available)'"
check_contains "$source_hook" 'test "$grub_efi_status" = not-installed'
check_contains "$source_hook" 'test -z "$grub_efi_version"'
check_contains "$source_hook" 'grub2_uncovered=$(comm -23'
check_contains "$source_hook" 'source-selection-notes.txt'
check_contains "$source_hook" 'snapshot_metadata_directory=../snapshot-InRelease'
check_contains "$source_hook" 'snapshot.debian.org_archive_debian-security_'

build_script="$repo_root/scripts/build.sh"
check_contains "$build_script" 'build_root=$(readlink -m --'
check_contains "$build_script" 'artifact_root=$(readlink -m --'
check_contains "$build_script" '$build_root == / || $artifact_root == /'
check_contains "$build_script" '$build_root/ == "$artifact_root/"*'
check_contains "$build_script" '$artifact_root/ == "$build_root/"*'
check_contains "$build_script" 'trusted_root=/var/lib/kythos-builder'
check_contains "$build_script" 'verify_protected_directory_chain'
check_contains "$build_script" 'mkdir -m 0700 -- "$build_root"'
check_contains "$build_script" 'mkdir -m 0700 -- "$artifact_root"'
check_contains "$build_script" 'Unsafe ownership or mode in cache seed'
check_contains "$build_script" 'cache_seed_scope=package-archives-only'
check_contains "$build_script" 'packages.bootstrap packages.chroot packages.binary'
check_contains "$build_script" \
    'verify_protected_directory_chain "$cache_seed/$cache_directory"'
check_contains "$build_script" '"$repo_root/SNAPSHOT"'
check_contains "$build_script" 'audit-source-coverage.sh'
check_contains "$build_script" 'snapshot-InRelease-SHA256SUMS'
check_contains "$build_script" \
    'Source hook did not preserve signed snapshot metadata.'
check_contains "$repo_root/scripts/audit-source-coverage.sh" \
    'source_payload_files_verified='
check_contains "$repo_root/scripts/audit-source-coverage.sh" \
    'Checksums-Sha256:'
installed_audit="$repo_root/config/includes.chroot/etc/default/grub.d/60-kythos-audit.cfg"
check_contains "$installed_audit" \
    'GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX audit=1 audit_backlog_limit=8192"'
if grep -R -E '^[[:space:]]*firmware-b43(legacy)?-installer([[:space:]]|$)' \
    "$repo_root/config/package-lists" >/dev/null 2>&1; then
    fail 'nonredistributable b43 installer firmware must not enter the image'
fi
if grep -R -E '^[[:space:]]*firmware-(ipw2x00|ivtv)([[:space:]]|$)' \
    "$repo_root/config/package-lists" >/dev/null 2>&1; then
    fail 'recipient-EULA firmware must not be preaccepted in the live image'
fi
# These are deliberately literal shell expressions required in auto/config.
# shellcheck disable=SC2016
check_contains "$config" 'version=$(cat "$repo_root/VERSION")'
# shellcheck disable=SC2016
check_contains "$config" '--image-name "kythos-kernal-base-${version}"'

version=$(cat "$repo_root/VERSION")
printf '%s\n' "$version" \
    | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([.+~-][0-9A-Za-z.+~-]+)?$' \
    || fail 'VERSION does not contain a valid release version'

os_release="$repo_root/config/includes.chroot/usr/lib/os-release"
check_contains "$os_release" "PRETTY_NAME=\"KythOS Kernal $version\""
check_contains "$os_release" 'ID=kythos'
check_contains "$os_release" 'ID_LIKE=debian'
check_contains "$os_release" 'VARIANT_ID=kythos'
check_contains "$os_release" "KYTHOS_VERSION_ID=\"$version\""
check_contains "$os_release" "VERSION=\"$version\""
check_contains "$os_release" 'NAME="KythOS Kernal"'
if grep -E '^(PRETTY_NAME|NAME|VERSION|VARIANT)=' "$os_release" | grep -qi debian; then
    fail 'visible OS identity still contains the parent distribution name'
fi

for branding_file in \
    "$repo_root/assets/branding/kythos-mark-cyan-source.png" \
    "$repo_root/assets/branding/kythos-boot-source.png" \
    "$repo_root/assets/branding/kythos-installer-banner-source.png" \
    "$repo_root/config/bootloaders/grub-pc/splash.png" \
    "$repo_root/config/bootloaders/grub-pc/grub.cfg" \
    "$repo_root/config/bootloaders/syslinux_common/splash.png" \
    "$repo_root/config/bootloaders/syslinux_common/live.cfg.in" \
    "$repo_root/config/includes.installer/usr/share/graphics/logo_debian.png" \
    "$repo_root/config/includes.installer/usr/share/graphics/logo_debian_dark.png" \
    "$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos-background.png" \
    "$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos-logo.png" \
    "$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos.plymouth" \
    "$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos.script"
do
    test -s "$branding_file" || fail "required branding file is empty or missing: $branding_file"
done
python3 "$repo_root/scripts/render-branding.py" --check \
    || fail 'checked-in branding does not match the approved source and renderer'
check_contains "$repo_root/config/bootloaders/grub-pc/grub.cfg" \
    'Start KythOS Kernal'
check_contains "$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos.plymouth" \
    'Name=KythOS Kernal'
plymouth_script="$repo_root/config/includes.chroot/usr/share/plymouth/themes/kythos/kythos.script"
check_contains "$plymouth_script" 'Image("kythos-logo.png")'
check_contains "$plymouth_script" 'Plymouth.SetRefreshRate('
check_contains "$plymouth_script" 'Plymouth.SetRefreshFunction('
check_contains "$plymouth_script" 'Plymouth.SetBootProgressFunction('
check_contains "$plymouth_script" 'Plymouth.SetQuitFunction('
check_contains "$plymouth_script" 'fun show_trace('
check_contains "$plymouth_script" 'fun show_sweep('
check_contains "$plymouth_script" 'fun show_breathing('
check_contains "$plymouth_script" 'fun show_handoff('
check_contains "$plymouth_script" 'Plymouth.SetDisplayPasswordFunction('
check_contains "$plymouth_script" 'Plymouth.SetDisplayQuestionFunction('
check_contains "$plymouth_script" 'Plymouth.SetDisplayMessageFunction('
if grep -Eq 'Image\.Text\([^)]*KythOS' "$plymouth_script"; then
    fail 'normal Plymouth branding must not render a KythOS wordmark'
fi
branding_hook="$repo_root/config/hooks/live/020-enable-branding.hook.chroot"
check_contains "$branding_hook" 'SOURCE_DATE_EPOCH must be a decimal Unix timestamp'
check_contains "$branding_hook" 'install -o root -g root -m 0644 "$os_release_temporary" /etc/os-release'
check_contains "$branding_hook" 'IMAGE_ID=kythos-live'
check_contains "$branding_hook" 'Parent: Debian'
check_contains "$branding_hook" 'dpkg-divert --local --add --no-rename'
check_contains "$branding_hook" '--divert /etc/os-release.debootstrap /etc/os-release'
check_contains "$branding_hook" 'for identity_file in /usr/lib/os-release /etc/os-release'
check_contains "$repo_root/NOTICE" \
    'Debian is a registered trademark owned by Software in the Public Interest, Inc.'
check_contains "$repo_root/scripts/build.sh" '"$repo_root/NOTICE" "$build_root/config/includes.binary/NOTICE"'
check_contains "$repo_root/scripts/audit-source-coverage.sh" 'installed-notice'
check_contains "$repo_root/config/hooks/live/020-enable-branding.hook.binary" \
    'KythOS Kernal %s %s Binary'
check_contains "$repo_root/config/hooks/live/020-enable-branding.hook.binary" \
    'version=$(cat ../VERSION)'
check_contains "$repo_root/config/hooks/live/020-enable-branding.hook.binary" \
    '> .disk/info'
cmp -s \
    "$repo_root/config/includes.installer/usr/share/graphics/logo_debian.png" \
    "$repo_root/config/includes.installer/usr/share/graphics/logo_debian_dark.png" \
    || fail 'light and dark installer banners must both carry KythOS branding'

test -f "$repo_root/config/includes.chroot/etc/systemd/system/nftables.service.d/60-kythos-stop.conf" \
    || fail 'nftables service stop override is required'
check_contains \
    "$repo_root/config/includes.chroot/etc/systemd/system/nftables.service.d/60-kythos-stop.conf" \
    'nft destroy table inet kythos_filter'

test -f "$repo_root/config/package-lists/live.list.chroot" \
    || fail 'tracked live.list.chroot is required'
test -f "$repo_root/config/package-lists/live.list.chroot_live" \
    || fail 'live-only package list is required'

access_packages="$repo_root/config/package-lists/access-encryption.list.chroot_install"
check_contains "$access_packages" 'openssh-server'
check_contains "$access_packages" 'clevis-initramfs'
check_contains "$access_packages" 'clevis-tpm2'

installer_preseed="$repo_root/config/includes.installer/preseed.cfg"
check_contains "$installer_preseed" 'd-i netcfg/get_hostname string KythOS'
check_contains "$installer_preseed" 'd-i netcfg/get_hostname seen false'
check_contains "$installer_preseed" 'd-i passwd/root-login boolean false'
check_contains "$installer_preseed" 'd-i user-setup/allow-password-weak boolean true'
installer_release="$repo_root/config/includes.installer/etc/lsb-release"
check_contains "$installer_release" 'DISTRIB_ID=KythOS'
check_contains "$installer_release" 'DISTRIB_DESCRIPTION="KythOS Kernal installer"'
check_contains "$installer_release" "DISTRIB_RELEASE=\"$version\""
check_contains "$installer_release" 'DISTRIB_CODENAME=trixie'
check_contains "$repo_root/config/includes.installer/usr/lib/debian-installer-startup.d/S19kythos-branding" \
    'ln -sfn "$wrapper" /usr/bin/debconf-loadtemplate'
"$repo_root/tests/test-installer-branding.sh" \
    || fail 'installer identity transform tests failed'
"$repo_root/tests/test-login-branding.sh" \
    || fail 'login identity presentation tests failed'

ssh_config="$repo_root/config/includes.chroot/etc/ssh/sshd_config.d/10-kythos-authentication.conf"
check_contains "$ssh_config" 'PasswordAuthentication yes'
check_contains "$ssh_config" 'PermitRootLogin no'
check_contains "$ssh_config" 'PermitEmptyPasswords no'
check_contains "$ssh_config" 'PermitUserEnvironment no'
check_contains "$ssh_config" 'DebianBanner no'

ssh_service_dropin="$repo_root/config/includes.chroot/etc/systemd/system/ssh.service.d/60-kythos-live.conf"
check_contains "$ssh_service_dropin" 'ConditionPathExists=!/run/live/medium'
check_contains "$ssh_service_dropin" 'ExecStartPre=/usr/bin/ssh-keygen -A'

authentication_hook="$repo_root/config/hooks/live/030-configure-authentication.hook.chroot"
check_contains "$authentication_hook" 'set_login_default PASS_MAX_DAYS -1'
check_contains "$authentication_hook" 'set_login_default PASS_MIN_DAYS 0'
check_contains "$authentication_hook" 'pam_unix.so minlen=1'
check_contains "$authentication_hook" 'pam_(cracklib|passwdqc|pwhistory|pwquality)'

cy="$repo_root/config/includes.chroot/usr/local/bin/cy"
check_contains "$cy" 'exec /usr/bin/apt -o APT::Cmd::Show-Update-Stats=false -o APT::Get::HideAutoRemove=true "$@"'
check_cy_rejects()
{
    if cy_output=$("$cy" "$@" --version 2>&1); then
        fail "cy accepted unsafe arguments: $*"
    else
        cy_status=$?
        test "$cy_status" -eq 2 \
            || fail "cy returned unexpected rejection status: $cy_status"
        printf '%s\n' "$cy_output" | grep -Eq '^cy: refusing ' \
            || fail 'cy rejection did not originate in the wrapper guard'
    fi
}
check_cy_rejects --allow-unauthenticated
check_cy_rejects --allow-unauthenticated=true
check_cy_rejects -o APT::Get::AllowUnauthenticated=true
check_cy_rejects -o apt::get::allowunauthenticated=true
check_cy_rejects -oAcquire::AllowInsecureRepositories=true
check_cy_rejects --option=acquire::allowdowngradetoinsecurerepositories=true
check_cy_rejects -c /tmp/untrusted-apt.conf
check_cy_rejects -qc/tmp/untrusted-apt.conf
check_cy_rejects -yqc/tmp/untrusted-apt.conf
check_cy_rejects -qoAcquire::AllowInsecureRepositories=true
check_cy_rejects --config-file=/tmp/untrusted-apt.conf
check_cy_rejects --Allow-Unauthenticated
check_cy_rejects --Force-Yes
check_cy_rejects --Allow-Remove-Essential
check_cy_rejects --Option=Acquire::AllowInsecureRepositories=true
check_cy_rejects --CONFIG-FILE=/tmp/untrusted-apt.conf
check_cy_rejects --with-source=/tmp/Packages install attacker-pkg
check_cy_rejects --WITH-SOURCE=/tmp/unsigned.changes install attacker-pkg
check_cy_rejects --with-source relative-Packages install attacker-pkg
check_cy_rejects --with-source unsigned.changes install attacker-pkg
check_cy_rejects ./untrusted.deb
check_cy_rejects ../untrusted.deb
check_cy_rejects /tmp/untrusted.deb
check_cy_rejects untrusted.deb
check_cy_rejects -- ./untrusted.deb
check_cy_rejects file:/tmp/untrusted.deb
check_cy_rejects https://example.invalid/untrusted.deb
if ! cy_output=$("$cy" -qq --version 2>&1); then
    fail 'cy rejected a safe short-option cluster'
else
    printf '%s\n' "$cy_output" | grep -Eq '^apt [0-9]' \
        || fail 'cy did not execute the packaged apt command'
fi
if cy_output=$(APT_CONFIG=/tmp/untrusted-apt.conf "$cy" --version 2>&1); then
    fail 'cy accepted the APT_CONFIG environment variable'
else
    cy_status=$?
    test "$cy_status" -eq 2 \
        || fail "cy returned unexpected APT_CONFIG rejection status: $cy_status"
    printf '%s\n' "$cy_output" | grep -Eq '^cy: refusing ' \
        || fail 'cy APT_CONFIG rejection did not originate in the wrapper guard'
fi

tpm_enrollment="$repo_root/config/includes.chroot/usr/local/sbin/kythos-enroll-tpm2"
check_contains "$tpm_enrollment" 'cryptsetup luksAddKey'
check_contains "$tpm_enrollment" '"pcr_ids":"4,7,8,9,14"'
check_contains "$tpm_enrollment" 'tpm2_pcrread'
check_contains "$tpm_enrollment" 'tpm2_eventlog'
check_contains "$tpm_enrollment" 'update-initramfs -u -k all'
check_contains "$tpm_enrollment" 'update-grub'
check_contains "$tpm_enrollment" 'prepared_boot_id'
check_contains "$tpm_enrollment" 'prepared_boot_digest'
check_contains "$tpm_enrollment" 'check_prepared_boot_state'
check_contains "$tpm_enrollment" 'tpm2_eventlog --eventlog-version=1'
check_contains "$tpm_enrollment" 'the event-log replay does not match live PCR'
check_contains "$tpm_enrollment" 'AlgorithmId:[[:space:]]*sha256'
check_contains "$tpm_enrollment" '/(grub_cmd:|kernel_cmdline:)/'
check_contains "$tpm_enrollment" '/(initrd|initramfs)/'
check_contains "$tpm_enrollment" 'check_recovery_media'
check_contains "$tpm_enrollment" 'check_pinned_recovery_media'
check_contains "$tpm_enrollment" 'findmnt --kernel=listmount'
check_contains "$tpm_enrollment" 'expected_recovery_mount_unique_id'
check_contains "$tpm_enrollment" 'recovery_fd_directory=/proc/$$/fd/8'
check_contains "$tpm_enrollment" 'recovery_fd_block=/proc/$$/fd/9'
check_contains "$tpm_enrollment" 'findmnt --evaluate -rn -o SOURCES'
check_contains "$tpm_enrollment" 'lsblk -dnro TYPE'
check_contains "$tpm_enrollment" 'lsblk -nP -o TYPE'
check_contains "$tpm_enrollment" 'lsblk -snP -o TYPE,RM,TRAN'
check_contains "$tpm_enrollment" 'kythos-recovery-topology.awk'
check_contains "$tpm_enrollment" 'shares a backing device with the LUKS volume'
check_contains "$tpm_enrollment" 'blockdev --flushbufs'
check_contains "$tpm_enrollment" 'clevis luks edit -f'
check_contains "$tpm_enrollment" 'clevis luks pass'
check_contains "$tpm_enrollment" 'cannot enumerate existing Clevis LUKS bindings'
check_contains "$tpm_enrollment" 'measured TPM enrollment requires the EFI System Partition mounted at /boot/efi'
check_contains "$tpm_enrollment" 'rollback_required=true'
check_contains "$tpm_enrollment" 'cryptsetup luksHeaderRestore --batch-mode'
check_contains "$tpm_enrollment" 'Temporary rollback header:'
check_contains "$tpm_enrollment" 'check_protected_directory_chain'
check_contains "$tpm_enrollment" 'recovery_file=$(readlink -m -- "$recovery_file")'
check_contains "$tpm_enrollment" 'flock -n 7'
check_contains "$tpm_enrollment" 'ignore_termination_signals'
check_contains "$tpm_enrollment" '.kythos-recovery-key.XXXXXXXXXX'
check_contains "$tpm_enrollment" "termination_signal_cleanup_action='trap"
check_contains "$tpm_enrollment" \
    'trap "$termination_signal_cleanup_action 158; exit 158" PWR'
check_contains "$tpm_enrollment" \
    'trap "$termination_signal_cleanup_action 144; exit 144" 16'
check_contains "$tpm_enrollment" \
    'trap - EXIT; cleanup'
check_contains "$tpm_enrollment" 'mv -T --update=none-fail'
check_contains "$tpm_enrollment" \
    'an unexpected boot passphrase prompt can indicate tampering'
check_contains "$tpm_enrollment" \
    'do not run cryptsetup, systemd-cryptenroll, or Clevis mutations'
"$repo_root/tests/test-tpm2-pcrread-parser.sh" \
    || fail 'TPM2 PCR-read parser tests failed'
test -s "$repo_root/config/includes.chroot/usr/local/libexec/kythos-recovery-topology.awk" \
    || fail 'recovery-storage topology policy is missing or empty'
"$repo_root/tests/test-recovery-topology.sh" \
    || fail 'recovery-storage topology policy tests failed'
check_contains "$repo_root/docs/ENCRYPTION-SSH-CY.md" \
    'classic signed shim and GRUB path does not'

aide_initialize_service="$repo_root/config/includes.chroot/usr/lib/systemd/system/kythos-aide-initialize.service"
daily_aide_dropin="$repo_root/config/includes.chroot/etc/systemd/system/dailyaidecheck.service.d/60-kythos-live.conf"
check_contains "$aide_initialize_service" 'ConditionPathExists=!/run/live/medium'
check_contains "$daily_aide_dropin" 'ConditionPathExists=!/run/live/medium'

fips_config="$repo_root/config/includes.chroot/etc/ssl/kythos/openssl-fips.cnf"
fips_refresh="$repo_root/config/includes.chroot/usr/local/libexec/kythos-refresh-fips-config"
fips_status="$repo_root/config/includes.chroot/usr/local/sbin/kythos-fips-status"
check_contains "$fips_config" '.include /etc/ssl/kythos/fipsmodule.cnf'
check_contains "$fips_config" 'default_properties = fips=yes'
check_contains "$fips_refresh" 'openssl fipsinstall'
check_contains "$fips_refresh" '-pedantic'
check_contains "$fips_refresh" "-propquery 'fips=yes'"
check_contains "$fips_refresh" 'provider_is_active fips'
check_contains "$fips_refresh" 'status:[[:space:]]+active'
check_contains "$fips_status" "-propquery 'fips=yes'"
check_contains "$fips_status" 'provider_is_active fips'
check_contains "$fips_status" 'status:[[:space:]]+active'
check_contains "$repo_root/config/includes.chroot/etc/apt/apt.conf.d/53kythos-fips-refresh" \
    'DPkg::Post-Invoke {'
check_contains "$repo_root/config/hooks/live/015-prepare-compliance.hook.chroot" \
    'systemctl enable kythos-fips-refresh.service'

security_hook="$repo_root/config/hooks/live/010-enable-security.hook.chroot"
audit_rules="$repo_root/config/includes.chroot/etc/audit/rules.d/50-kythos-stig-alignment.rules"
check_contains "$security_hook" \
    'chmod 0640 /etc/audit/auditd.conf /etc/audit/rules.d/*.rules'
check_contains "$audit_rules" '-C egid!=gid'
check_contains "$audit_rules" '-F path=/usr/bin/mount -F perm=x'
check_contains "$audit_rules" '-F path=/usr/bin/umount -F perm=x'
check_contains "$repo_root/docs/COMPLIANCE.md" \
    'opt-in OpenSSL FIPS-provider configuration'
check_contains "$repo_root/docs/COMPLIANCE.md" \
    'initial STIG-derived hardening with a partial mapping'
check_contains "$repo_root/docs/COMPLIANCE.md" \
    'not been assessed or approved as a'
check_contains "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status" \
    'auditd.service nftables.service apt-daily-upgrade.timer'
check_contains "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status" \
    "pass ssh.service 'inactive in the live session'"
check_contains "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status" \
    'audit_enabled=$(kernel_argument audit)'
check_contains "$repo_root/config/includes.chroot/usr/local/sbin/kythos-security-status" \
    '-C user=root,host=localhost,addr=127.0.0.1'

stig_map="$repo_root/compliance/stig-map.tsv"
awk -F '\t' '
    NR == 1 {
        if ($1 != "reference_id" || $2 != "srg_id" || $3 != "cci_ids" ||
            $4 != "severity" || $5 != "status" ||
            $6 != "kythos_evidence_or_deviation") exit 1
        next
    }
    NF != 6 || $1 !~ /^UBTU-24-/ || $2 !~ /^SRG-OS-/ { exit 1 }
    END { if (NR != 196) exit 1 }
' "$stig_map" || fail 'STIG inventory must contain 195 well-formed control rows'
check_contains "$stig_map" 'user-approved-deviation'
check_contains "$stig_map" 'not-assessed'

if grep -Ev '^[[:space:]]*(#|$)' \
    "$repo_root/config/includes.chroot/etc/nftables.d/kythos-input.nft" \
    | grep -Eq '(^|[^[:digit:]])22([^[:digit:]]|$)|ssh'; then
    fail 'the common firewall must not expose SSH'
fi

tmp_packages=$(mktemp)
trap 'rm -f "$tmp_packages"' EXIT HUP INT TERM

{
    for list in "$repo_root"/config/package-lists/*.list.*
    do
        awk '!/^[[:space:]]*(#|!|$)/ { print $1 }' "$list"
    done
    "$repo_root/config/includes.chroot/usr/local/libexec/kythos-architecture" \
        --arch "${KYTHOS_ARCH:-$(dpkg --print-architecture)}" --packages
} | LC_ALL=C sort > "$tmp_packages"

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
        # This header is a normal local conffile modification, so dpkg keeps
        # it on ordinary upgrades rather than replacing it as package data.
        dpkg-query -W -f='${Conffiles}\n' base-files \
            | grep -Eq '^ /etc/update-motd.d/10-uname[[:space:]]' \
            || fail 'base-files login header no longer has conffile protection'
        while IFS= read -r package
        do
            apt-cache show "$package" >/dev/null 2>&1 \
                || fail "package unavailable in Debian 13: $package"
        done < "$tmp_packages"
    fi
fi

python3 "$repo_root/tests/test-architecture.py" || fail 'architecture profile validation failed'
python3 "$repo_root/tests/test-multiarch-pair.py" || fail 'multiarch artifact-pair validation failed'

test "$errors" -eq 0 || exit 1
printf '%s\n' 'KythOS Kernal source validation passed.'
