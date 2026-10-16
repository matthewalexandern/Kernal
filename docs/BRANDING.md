# KythOS Kernal identity

The display branding is **KythOS Kernal™ 2027** and **https://kythos.ai**,
including the spelling Kernal. The release version is independent of the
requested display year. Use `[TM]` when a console font cannot display ™; the
symbol expresses a trademark claim, not a registered trademark. Debian's
derivative guidance encourages a derivative to replace the parent project's
name, logo, and service identity. Its trademark policy does not require dropping
the word Kernal from this independent name.

The operating-system release name and version, login banners, message of the
day, boot menus, ISO labels, installer presentation, and Plymouth theme metadata
use KythOS Kernal branding. The normal loading screen displays a white shield
on black and small product text in its lower-right corner. Encryption prompts
and boot questions remain readable. Esc exposes Plymouth boot diagnostics; the
GRUB diagnostics entry disables Plymouth, while existing recovery and
troubleshooting entries are retained.
The SSH server omits the distribution suffix from its protocol banner while
retaining the upstream OpenSSH version.

The local console banner uses
`KythOS Kernal[TM] 2027 | https://kythos.ai | terminal: tty1`, with the terminal
name expanded by agetty from `\l` in `/etc/issue`. The year `2027`
is the requested banner text, independent of the release version and build
date. `/etc/issue.net` uses the Unicode ™ identity without a terminal suffix.
The displayed domain does not change the machine's hostname or DNS settings.

The installer keeps its upstream native template loader. A startup hook routes
template loads through a small presentation filter, including templates loaded
later by installer components. Only description fields in an explicit list of
installer and installed-system identity questions are changed. Question keys,
defaults, machine-readable choices, substitutions, URLs, package indexes, and
archive descriptions retain their upstream meaning. The overlay source and
filter accompany the source ISO.
The optional debug-log web page also receives KythOS Kernal headings while
retaining its upstream paths and serving behavior.

Both installers offer `KythOS` as an editable default hostname and preserve its
case in the installed hostname. A hostname cannot contain the spaces in the
full display name. Network-provided hostnames and a user-entered hostname
retain their normal meaning.

The login header prints the running kernel type, release, and architecture
without the compiler/vendor string from `uname -v`. The kernel binary and
the complete output of `uname` remain untouched. `/etc/update-motd.d/10-uname`
is a `base-files` conffile; the image supplies a local modification using the
normal dpkg configuration mechanism. Ordinary package upgrades retain it;
an administrator can deliberately select the package maintainer version or
use `--force-confnew` to replace local configuration. Source validation checks
that the Debian builder still provides this conffile guarantee.

The display filter also covers product references that appear only in upstream
translations, including reviewed inflections such as `Debianu` and `Debianiin`.
Archive selection and update-service explanations continue to identify the
actual upstream provider. The filter does not rename the upstream archive as
if it were a KythOS service.

Calamares uses the white vector shield, neutral dark styling, exact product
branding and project URL in its own branding directory. Each normal ISO
installs its named edition; the installer does not offer four edition choices.
Upstream Calamares and package license notices remain available.

The OS release files are locally diverted through dpkg so a base-files upgrade
delivers its upstream identity to the `.distrib` paths and preserves the KythOS
identity. Both `/etc/os-release` and `/usr/lib/os-release` identify the system
as `ID=kythos` and `ID_LIKE=debian`. The dpkg vendor is KythOS, with Debian as
its parent. These machine identifiers describe compatibility and inheritance.

## Artwork and boot behavior

`assets/branding/kythos-mark-white.svg` is the canonical, self-contained vector
source. The original hand geometry commemorates **9:06 AM**, the birth time of
the user's son Cyrus. This meaning is preserved; Cyrus is not a visible product
name. The enclosed monogram is a contour conversion of the opaque core of the
original approved cyan mark, uniformly scaled and translated inside a clean
white shield. It does not substitute clock hands or independently rotate,
stretch or redesign any hand. The loop and negative spaces remain intact.
The original cyan PNG and SHA-256 are retained as provenance; its glow is not
part of the new artwork. The conversion recipe is in
[assets/branding/IMAGEGEN-PROMPT.md](../assets/branding/IMAGEGEN-PROMPT.md).

Calamares consumes the SVG directly. Plymouth, GRUB, Syslinux and the Debian
Installer consume deterministic PNG derivatives sized for their supported
framebuffers. Installer filenames `logo_debian.png` and
`logo_debian_dark.png` are upstream interfaces, not Debian logo artwork.
The small wordmark is separate from the shield and never crosses its boundary.

The loading bar shows Plymouth's supplied boot progress when it changes.
If no new progress arrives for five seconds, a moving segment indicates
activity instead of estimating an artificial percentage. It remains separate
from password entry and boot questions. The `plymouth-label` plugin is an
explicit dependency so text and encrypted-root prompts remain functional even
when installation disables recommended packages.

Source checks verify the preserved monogram geometry, white pixels,
containment, wordmark placement, identical installer variants and regenerated
artifacts. An optional test runs the actual Debian Plymouth script interpreter
and image/text/sprite libraries without a DRM screen. These checks do not
establish boot timing, Esc behavior or successful encrypted installation on
hardware; both architecture ISO boot/install checks remain acceptance work.

## References retained for functionality and attribution

Replacing every byte occurrence of Debian would corrupt interfaces and erase
provenance. The following remain accurate and retain their upstream spelling:

- Repository URLs, suite names, archive Origin/Label fields, signing keys, and
  authenticated package metadata used by APT and unattended upgrades.
- Package and source names, versions, maintainers, copyrights, licenses,
  changelogs, documentation references, and the stock kernel's build identity.
- Compatibility and inheritance identifiers such as `ID_LIKE=debian`,
  `/etc/debian_version`, dpkg `Parent: Debian`, and internal installer question
  names beginning with `debian-installer/`.
- Required interface paths such as the installer's `logo_debian.png`, and any
  signed bootloader paths or package-owned interfaces used for Secure Boot.
- Build tools and formats such as debootstrap, debian-installer, and the
  `debian/` source-package directory, plus factual build and source records.
- Upstream source attribution, the trademark notice, and documentation that
  explains the base system or links to authoritative upstream instructions.

These exceptions do not change the product's visible operating-system name.
They keep updates, hardware drivers, package tooling, and source attribution
working. Package update output can still show the upstream package provenance.

The NOTICE file accompanies the binary ISO, source ISO, and installed system.
Package license and copyright files remain available under `/usr/share/doc`.

Sources: [Debian derivative guidance](https://www.debian.org/derivatives/),
[Debian trademark policy](https://www.debian.org/trademark).
