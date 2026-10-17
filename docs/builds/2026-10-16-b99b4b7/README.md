# KythOS Kernal 0.2.0 validation progress

The normal amd64 base build exited **0** and produced its binary and source
ISOs. Source-coverage and the normal producer validation gates passed.
Independent SSH export is active; its verified receipt, private-material
audit, cleanup and fresh-install/runtime acceptance remain pending. Both
native Calamares modules have linked and passed their policy/schema checks.
ARM64's image-construction stages remain held by the external build
coordinator until amd64 export completes; its image job has not started.
This record captures progress before both builds and acceptance finish;
it does not promote the retained 0.1.0 images or their acceptance results.

Both builds are pinned to image source commit
`b99b4b7ec90a11ef09ad3958e01ccc67363b55cd`, tree
`25ffcb6c9ae1314e335e83fd084374134d97a049`, and Debian snapshot
`20261016T000000Z`. The independently hashed `source-b99b4b7.bundle` has SHA-256
`a989c07b180ff995e875bf2a575f530a45b8e0e4fd77e24cb809dafa30fde928`.
The bundle is a source-transfer artifact, not an ISO. Documentation commits
recording progress do not change the immutable source used by these builders.

## Completed amd64 normal build; independent export pending

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `kythos-kernal-base-0.2.0-amd64.hybrid.iso` | 1,906,999,296 | `2f3051662ee0d60d7acc38bc425c75f956aea636471e82d3e916c4b0bfbeb6cf` |
| `kythos-kernal-base-0.2.0-source.iso` | 4,168,837,120 | `57c008b9e7ef8a343e44d0b584ea37e3658210c28b7ad31673568f2321575ccd` |

The original normal build process and recorded exit marker both reported 0
from a clean pinned checkout. The producer's final checksum read-back passed;
its original 29-entry `SHA256SUMS` has SHA-256
`165471f66b6831ed84088a3a766a9e2818182e126648fb6d6a9cb9f30e66cbbc`.
The [normal-build receipt](amd64-normal-build.json) records 147 binary-pool
packages, 961 live-root packages, 554 required/556 provided source tuples,
1,233 verified source payloads and zero missing tuples. License, architecture,
image-identity and recipe checks passed. The minimum sampled physical free
space during the build was 5,409,939,456 bytes.

All five [packaged artwork byte comparisons](amd64-packaged-artwork.json)
matched the frozen source. The [source-alias proof](amd64-source-alias.json)
confirms the existing normal `005` source hook covered `grub2`
`2.12-9+deb13u2`; no manual repair was used.

The final binary checksum matches its earlier read-only inspections. Its
finished-image SSH configuration checker passed all
19 assertions; BIOS/UEFI boot metadata and KythOS volume-header checks also
passed. See the [sanitized early image receipt](amd64-binary-early-checks.json).

The earlier image checks and artwork comparisons are inspections, not
observed BIOS/UEFI boot, installation, or external SSH authentication. Normal
build completion and source coverage are now separately established by the
producer receipt. Independent export verification, private-material audit,
cleanup, architecture-pair verification and fresh-install/runtime acceptance
remain pending; the active SSH copy is not yet an accepted delivery.

## Observed source checks

| Evidence label | Observed result | Scope and limits |
| --- | --- | --- |
| `worktree-gate-20261016T210321Z-b055c6` | ARM64 root source gate: 272 tests passed across 21 suites; zero failures, errors or skips; source-validation command exited 0 | Frozen working-tree snapshot preceding the final pin. Strict postcheck failed because one Python bytecode file appeared; all 299 declared input hashes, modes and symlink targets remained unchanged, with no missing inputs. The wrapper therefore failed its strict source-integrity condition. |
| `console-bytecode-gate-20261016T211050Z-9317e7` | ARM64 corrected console fixture: 11/11 passed, zero skips; command exited 0; strict source-unchanged check passed | Only `tests/test-console-header.py` changed from the preceding snapshot. The corrected isolated interpreter uses `-B` to prevent bytecode output. This rerun is a targeted check, not a repeated full source gate. |
| Native amd64 Docker console check | 11/11 console tests passed | Targeted native console evidence observed during development; does not establish image boot acceptance. |
| Host Bash/Readline check | 26/26 tests passed | Targeted shell integration evidence; does not establish installed-system acceptance. |
| `source-b99b4b7-input-verification` | Clean ARM64 candidate clone matches all 299 declared input bytes and symlink targets | The clone uses canonical Git modes. There are 276 mode differences from the private working snapshot's account-specific modes, zero noncanonical Git modes, zero unexpected/missing paths and no Git changes. |
| Native ARM64 Plymouth check at `b99b4b7` | 3/3 tests passed, zero skips, in 1.031 seconds with Plymouth `24.004.60-5` | Targeted native branding-runtime tests; not a boot-screen observation in a finished ISO. |
| amd64 full source gate at `b99b4b7` | 272/272 tests passed across 21 suites, zero skips; checkout remained Git-clean with no unexpected generated source files | Actual final-pin source gate in the amd64 Debian guest. Shell/branding/recovery checks and native-kernel nftables validation passed. |
| ARM64 full source gate at `b99b4b7` | 272/272 tests passed across 21 suites, zero failures or skips | Actual normal `build-arm64.sh` invocation as root. Shell/parser/branding/package and root nftables checks passed. |

These counts overlap and must not be added into a final aggregate. The earlier
ARM64 272-test run used a pre-pin working-tree snapshot; its command success
and failed strict postcheck are separate outcomes. The subsequent targeted console check closes
the observed bytecode issue, but is not evidence of a complete aggregate run
against the final commit. Both actual builds have now separately passed their
complete normal source gates at the pin, as recorded in the sanitized
[amd64 receipt](amd64-source-gate.json) and [ARM64 receipt](arm64-source-gate.json).
ARM64 must still record its image-construction and artifact results, and
both architectures require their remaining verification and runtime checks.
Native module construction alone does not establish image boot behavior.

## Native Calamares modules

Both architectures built `calamares_viewmodule_partition` from Calamares
`3.3.14-1` with the reviewed partition policy patch. Each module linked, passed
its C++ policy test, and passed all 13 native schemas. The required installed
Calamares runtime package remains version `3.3.14-1`.

| Architecture | Partition module SHA-256 | Receipt |
| --- | --- | --- |
| amd64 | `2d4819cc4cab073dc698de07f7ca063792d781ac25b912e5e3dad31fc310ce0b` | [Native module](amd64-native-module.json) |
| ARM64 | `cd904ac746cb1dd5f9918e8baeaae061967b955e1bbfe40eea84d9978c3df014` | [Native module and image-stage hold](arm64-native-module.json) |

The ARM64 hold receipt confirms the image permit is absent and none of the
live-build `chroot`, `binary` or `source` stage directories exists. No module
build performs an installed-system boot test. These native library hashes
are not ISO checksums or evidence of a finished image.

The machine-readable [source-validation receipt](source-validation.json)
contains sanitized evidence labels, snapshot digests and counts. Private raw
runtime logs and credentials remain outside Git.

## Pending production and acceptance

- Complete independent amd64 export verification, private-material audit and
  cleanup, then ARM64 image construction and its normal producer gates.
  Record each actual artifact's size/checksum and verified source closure.
- Run the matching-edition architecture-pair integrity gate after both builds
  complete. A pair gate does not substitute for boot and installation tests.
- Test fresh installation and external SSH access, unique host keys, boot
  presentation, terminal history/scrollback, Wi-Fi launching and varied
  command assistance on the new images.
- Test the separate desktop profile when selected; physical Wi-Fi, supported
  smart-card operations and actual Apple-host display/resize/acceleration
  require their applicable hardware/platform evidence.

The amd64 normal build and both listed ISO checksums are established by the
producer receipt. Independent export acceptance, ARM64 image completion,
fresh-install/runtime acceptance, release readiness, public publication and
hardware compatibility remain unestablished. Update this record with observed
results as the remaining gates and acceptance finish.
