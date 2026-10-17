# KythOS Kernal™ 2027 — 0.2.0 implementation and acceptance

https://kythos.ai

This source line implements the requested 2027 changes on the existing Debian
13 recipe. Version **0.2.0** distinguishes the new candidate from retained
**0.1.0** images. The year in the display name is product branding, not a claim
about the build date. Existing images, frozen source exports, manifests, and
their historical acceptance records retain their original identities and
bytes. Updating source does not update an uploaded ISO.

**The change set is not release-complete until the affected ISOs are built and
their required installation/runtime checks pass.** Source tests, package
resolution, image construction, boot acceptance, physical hardware tests, and
Apple-host acceptance are distinct evidence.

## Edition and architecture scope

The selected default is a common-base **amd64 + ARM64** pair. A separate
**desktop** profile is available when an installed GUI is wanted. Source
profiles currently describe these combinations:

| Edition | amd64 recipe | ARM64 recipe | Installed workflow |
| --- | --- | --- | --- |
| base | Available | Available | Console, networking, SSH, command assistance, security baseline |
| desktop | Available | Available | XFCE, graphical networking, optional smart cards, desktop VM components |
| server / hypervisor / AI server | Future workloads | Future workloads | No completed dedicated workload profile or image claimed |

Two available profiles across two architectures describe four possible binary
variants; that is not an artifact inventory or acceptance count. The default
base pair would produce two binary ISOs and their corresponding source ISOs
once those builds complete. Desktop builds are separate, explicitly selected
targets. There is no all-in-one image or combined edition selector in this
candidate. Recovery and troubleshooting menu entries remain available.

Each architecture/edition build must use the same reviewed clean source
commit and pinned Debian snapshot. Keep architecture, edition, version, source
commit, image checksum, and acceptance result together. The multiarchitecture
pair check compares matching editions and does not establish boot compatibility.
See [building](BUILDING.md) and [ARM64](ARM64.md).

## Implementation and acceptance matrix

“Source checks” below describe test coverage, not final aggregate results for
the release candidate. The final execution receipt must record the actual
commands, results, build provenance, and produced artifact paths/checksums.

| Requested change | Implemented behavior | Source/native checks | Required image or platform acceptance |
| --- | --- | --- | --- |
| White branding and logo | Scalable white shield retains the original hand geometry meaning 9:06 AM; small lower-right product name and URL; visible product naming omits Cyrus; ™ with readable console fallback; actual terminal identifier | Artwork/layout and Plymouth runtime fixtures, real agetty issue parser, native tmux PTYs and font-map fixtures | Inspect live/installed boot and installer at representative resolutions; verify the approved geometry and real console font/terminal rendering |
| SSH access | OpenSSH installed/enabled, installed firewall permits TCP 22 on IPv4/IPv6, existing running systems use enable-and-start, build/live contexts avoid starting host services, per-installation host keys, installer-created ordinary account | Service/context/policy fixtures; isolated real RSA SHA-2 SSH login where the required binaries are available | Fresh install on both architectures, external connection with installed account, observed running service and network/firewall state, host-key uniqueness across independent installations |
| RSA workflow | `kythos-ssh generate` defaults RSA 4096, preserves existing identities, supports explicit alternatives; separate previewed `ssh-copy-id -i` public-key installation; no SHA-1 policy relaxation | Key generation/selection/preservation and confirmation tests; real RSA SHA-2 negotiation checks | Generate/install a key from another test machine, verify fingerprint/selected key and successful login; confirm existing keys remain intact |
| Command assistant | Discovers PATH and current-shell names/completion metadata; local/version-aware documentation inspection, flags/subcommands, intent leads, corrections, explicit diagnosis; offline operation without silent execution or an AI backend | Disposable manuals/trap executables, stale/new-command cases, syntax/quoting/pipelines/redirections, uncertainty, protected arguments, native Bash PTY integration | Exercise varied installed and newly installed commands in fresh images; preview typo correction, preserve ordinary shell behavior, verify missing-documentation behavior and responsiveness |
| History and terminal navigation | Up/Down recall, Ctrl+R search, append-only shared history with bounded memory; custom bindings/hooks retained; separate managed-console output scrollback | Actual Bash PTYs using Linux/xterm protocols, simultaneous sessions and restart, expansion/privacy checks; native tmux scrollback/clear/top/resize | Test fresh installed TTY and desktop terminal, multiple sessions/reboots, actual Shift+PageUp behavior and history persistence |
| Smart cards | Desktop includes OpenSC, PC/SC socket/daemon, CCID drivers, p11-kit and Firefox OpenSC PKCS#11 registration; ordinary login remains card-free | Reader/certificate/status fixtures and desktop package/integration checks | Attach named supported card/reader; detect reader, enumerate expected public certificates, complete verified signature or supported application authentication, then verify card-free login |
| Apple virtualization/graphics | Architecture-specific stock virtual-device drivers, desktop Mesa/agents, bounded guest graphics/status diagnostics; no guessed GPU passthrough settings | Guest/device/channel/renderer fixtures distinguish observed components from host/acceleration claims | Record actual Mac chip/macOS/hypervisor/version; boot/install, usable display modes, resize and representative rendering workload; document software rendering or unsupported features accurately |
| `WiFi` | Exact PATH symlink to maintained launcher; desktop graphical manager and TTY interface; adapter/radio/permission/dependency diagnostics | Exact symlink invocation, graphical/TTY selection and blocked/missing-state fixtures | Launch actual GUI and TTY interfaces, join a test AP and confirm connectivity with a supported adapter; VM host Wi-Fi does not imply guest Wi-Fi hardware |
| Installer/loading/ISO choices | Consistent white branding and clean Plymouth loading presentation; real progress when exposed, indeterminate animation otherwise; diagnostics/recovery retained; separate edition images | Boot artwork/menu/Plymouth runtime and edition staging tests | Observe live and installed boot, Esc diagnostics, recovery entry, encryption prompt and installer behavior; inspect each selected ISO's edition identity |
| Terminal appearance/attribution | White-on-dark default; dark, light, monochrome, blue, teal and high-contrast choices in the guide and `kythos-theme` afterward; original upstream license/attribution files retained | Qt offscreen selector/launcher tests, actual palette CLI PTYs, redirection/safe-preference fixtures, target transfer and attribution checks | Install chosen palette, verify target persistence and rendering in physical VT and GUI terminal, change after installation, verify Debian/upstream notices remain available |

## User workflows

The installed system listens for SSH on its ordinary configured address. VM
NAT, host forwarding, routing, and the remote machine's reachability still
matter:

```sh
ssh USER@TARGET_ADDRESS
```

On an already running installed system, `sudo kythos-enable-ssh` enables and
starts `ssh.service`. In an image/chroot use `--offline` to enable only. The
live installer guard is deliberate: its temporary account remains local-only
even if someone invokes the helper or systemctl there. Never remove that guard
to test installed-system access. Neither shared host keys nor shared login
credentials are shipped. See [SSH details](ENCRYPTION-SSH-CY.md).

```sh
kythos-ssh generate
kythos-ssh install --public-key ~/.ssh/id_rsa.pub USER@TARGET_ADDRESS
kythos-ssh generate --type ed25519
```

Generation and installation are separate. Installation previews the intended
public-key fingerprint and correctly spelled `ssh-copy-id -i` command. RSA
keys use modern SHA-2 authentication; RSA preference does not authorize the
obsolete SHA-1 `ssh-rsa` signature algorithm.

```sh
WiFi
WiFi --tty
kythos-theme --list
kythos-theme high-contrast
kythos-assist --explain 'ls --all ./documents | grep invoice > matches.txt'
kythos-assist --complete 'git comm'
kythos-assist --intent 'show network interfaces'
kythos-assist --diagnose --status 127 'missing-tool argument'
```

F1 inspects the current shell line. Correction previews require acceptance
into the edit buffer and a separate ordinary Enter to execute. Assistance
does not inspect history, execute unknown `--help`/`--version` programs, or send
terminal data to a remote model. Local missing/incomplete documentation and
unsupported shell constructs are reported explicitly. See
[assistant capabilities and limits](COMMAND-SUGGESTIONS.md).

Up/Down navigates commands; Ctrl+R searches history in the default Bash mode.
Output scrollback uses the terminal's own controls, or Shift+PageUp /
`kythos-console scrollback` in the managed console; q/Esc returns to the shell.
See [console and appearance](CONSOLE.md), [Wi-Fi](WIFI.md),
[smart-card acceptance](SMART-CARDS.md), and [Apple virtualization](APPLE-VIRTUALIZATION.md).

## Execution receipt and artifact inventory

| Evidence | Current status |
| --- | --- |
| Source/native tests | Both actual final-pin normal builds passed their complete source gates: 272/272 tests across 21 suites per architecture, zero failures/skips, plus shell/parser/branding/package and native-root nftables checks. amd64 checkout stayed clean with no unexpected generated source files. Earlier ARM64 pre-pin gate also passed 272 tests but failed its strict postcheck solely for one bytecode file, with all 299 declared inputs unchanged; corrected console rerun passed 11/11 with strict verification. Native Docker console passed 11/11, host Bash/Readline passed 26/26, and final-pin ARM64 Plymouth passed 3/3. These overlapping counts are not summed. |
| Native Calamares modules | amd64 and ARM64 modules linked and passed their C++ policy test and all 13 schemas each against Calamares `3.3.14-1`. Module hashes/provenance are recorded in the build progress record; no installed-system boot test is implied. |
| Immutable image source | Commit `b99b4b7ec90a11ef09ad3958e01ccc67363b55cd`, tree `25ffcb6c9ae1314e335e83fd084374134d97a049`; source-bundle SHA-256 `a989c07b180ff995e875bf2a575f530a45b8e0e4fd77e24cb809dafa30fde928` |
| Authenticated dependency resolution/source closure | amd64 normal build passed: 147 binary-pool/961 live-root packages, 554 required/556 provided source tuples, 1,233 verified source payloads, zero missing tuples. Normal license/architecture/identity/recipe and producer checksum read-back checks passed. ARM64 image/source-closure gates remain pending. |
| New 0.2.0 amd64/ARM64 binary/source ISO builds | Original amd64 normal build and recorded exit marker both reported 0 on the clean pin; binary and source ISOs were produced. Independent SSH export is active; verified export receipt, private-material audit and cleanup remain pending. ARM64 image construction remains held until amd64 export completes. |
| amd64 binary early checks | `kythos-kernal-base-0.2.0-amd64.hybrid.iso`: 1,906,999,296 bytes; SHA-256 `2f3051662ee0d60d7acc38bc425c75f956aea636471e82d3e916c4b0bfbeb6cf`. Stable before/after read-only checks; finished-image SSH configuration checker passed 19/19 assertions and BIOS/UEFI boot metadata plus KythOS volume headers passed. These inspections do not establish actual boot, installation or remote SSH authentication. |
| amd64 source ISO and artwork | `kythos-kernal-base-0.2.0-source.iso`: 4,168,837,120 bytes; SHA-256 `57c008b9e7ef8a343e44d0b584ea37e3658210c28b7ad31673568f2321575ccd`. Binary checksum remained unchanged at full-build completion. All five packaged artwork byte comparisons matched the frozen source; this does not establish observed boot presentation. |
| Fresh-install SSH and other VM acceptance | Pending on the affected images |
| Physical Wi-Fi/card reader/card operation | Pending on applicable hardware |
| Apple-host boot/display/resize/acceleration | Pending on the actual supported host/hypervisor combination |
| Exact new artifacts and checksums | Both amd64 ISOs are recorded in the normal-build receipt. Original 29-entry producer `SHA256SUMS` SHA-256: `165471f66b6831ed84088a3a766a9e2818182e126648fb6d6a9cb9f30e66cbbc`. Independent export/read-back, private-material audit, ARM64 images and pair verification remain pending. |

The [sanitized source-validation progress record](builds/2026-10-16-b99b4b7/README.md)
and its [machine-readable receipt](builds/2026-10-16-b99b4b7/source-validation.json)
preserve the distinction between the 272-test command success, its failed
strict postcheck, and the successful targeted rerun. The separately observed
complete final-pin source gates are recorded in the
[amd64 receipt](builds/2026-10-16-b99b4b7/amd64-source-gate.json) and
[ARM64 receipt](builds/2026-10-16-b99b4b7/arm64-source-gate.json). The hashed
source bundle is a transfer artifact, not a binary or source ISO.
The [amd64 early binary receipt](builds/2026-10-16-b99b4b7/amd64-binary-early-checks.json)
records the produced binary and read-only inspections separately from pending
runtime acceptance. The [amd64 normal-build receipt](builds/2026-10-16-b99b4b7/amd64-normal-build.json)
now establishes producer build completion and source closure; it does not
establish independent export or fresh-install/runtime acceptance.

The final receipt must replace these pending entries with observed results or
specific blockers and list only artifacts that actually exist. Record a
failed/blocked build as such, never as a tested ISO. Historical 0.1.0 build or
transfer evidence cannot qualify the new 0.2.0 behavior. No public release,
ISO upload, Apple GPU passthrough, universal smart-card compatibility, formal
FIPS validation, or STIG approval is implied by this source integration.
