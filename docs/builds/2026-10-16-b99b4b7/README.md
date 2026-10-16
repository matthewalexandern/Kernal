# KythOS Kernal 0.2.0 validation progress

The amd64 base-image build is in progress; the ARM64 build is queued until the
amd64 export completes. No new binary or source ISO is recorded as produced,
and no fresh-install acceptance is claimed here.
This record captures source-test evidence available before the builds finish;
it does not promote the retained 0.1.0 images or their acceptance results.

Both builds are pinned to image source commit
`b99b4b7ec90a11ef09ad3958e01ccc67363b55cd`, tree
`25ffcb6c9ae1314e335e83fd084374134d97a049`, and Debian snapshot
`20261016T000000Z`. The independently hashed `source-b99b4b7.bundle` has SHA-256
`a989c07b180ff995e875bf2a575f530a45b8e0e4fd77e24cb809dafa30fde928`.
The bundle is a source-transfer artifact, not an ISO. Documentation commits
recording progress do not change the immutable source used by these builders.

## Observed source checks

| Evidence label | Observed result | Scope and limits |
| --- | --- | --- |
| `worktree-gate-20261016T210321Z-b055c6` | ARM64 root source gate: 272 tests passed across 21 suites; zero failures, errors or skips; source-validation command exited 0 | Frozen working-tree snapshot preceding the final pin. Strict postcheck failed because one Python bytecode file appeared; all 299 declared input hashes, modes and symlink targets remained unchanged, with no missing inputs. The wrapper therefore failed its strict source-integrity condition. |
| `console-bytecode-gate-20261016T211050Z-9317e7` | ARM64 corrected console fixture: 11/11 passed, zero skips; command exited 0; strict source-unchanged check passed | Only `tests/test-console-header.py` changed from the preceding snapshot. The corrected isolated interpreter uses `-B` to prevent bytecode output. This rerun is a targeted check, not a repeated full source gate. |
| Native amd64 Docker console check | 11/11 console tests passed | Targeted native console evidence observed during development; does not establish image boot acceptance. |
| Host Bash/Readline check | 26/26 tests passed | Targeted shell integration evidence; does not establish installed-system acceptance. |
| `source-b99b4b7-input-verification` | Clean ARM64 candidate clone matches all 299 declared input bytes and symlink targets | The clone uses canonical Git modes. There are 276 mode differences from the private working snapshot's account-specific modes, zero noncanonical Git modes, zero unexpected/missing paths and no Git changes. |
| Native ARM64 Plymouth check at `b99b4b7` | 3/3 tests passed, zero skips, in 1.031 seconds with Plymouth `24.004.60-5` | Targeted native branding-runtime tests; not a boot-screen observation in a finished ISO. |
| amd64 full source gate at `b99b4b7` | 272/272 tests passed across 21 suites, zero skips; checkout remained Git-clean with no unexpected generated source files | Actual final-pin source gate in the amd64 Debian guest. Shell/branding/recovery checks and native-kernel nftables validation passed. The subsequent native Calamares stage validated 13 schemas; CMake work is underway. No completed installer or ISO is claimed. |

These counts overlap and must not be added into a final aggregate. The 272-test
run used a pre-pin working-tree snapshot; its command success and failed strict
postcheck are separate outcomes. The subsequent targeted console check closes
the observed bytecode issue, but is not evidence of a complete aggregate run
against the final commit. The actual amd64 build has now separately passed
its complete normal source gate at the pin, as recorded in the sanitized
[amd64 receipt](amd64-source-gate.json). The queued ARM64 build must still run
its full gate, and both builds must record their remaining construction and
artifact results. Passing source and module-schema checks does not establish
a completed native module build or a bootable ISO.

The machine-readable [source-validation receipt](source-validation.json)
contains sanitized evidence labels, snapshot digests and counts. Private raw
runtime logs and credentials remain outside Git.

## Pending production and acceptance

- Complete the affected amd64 and ARM64 base binary/source ISO builds and
  record build exits, exact artifacts, sizes, checksums and source closure.
- Run the matching-edition architecture-pair integrity gate after both builds
  complete. A pair gate does not substitute for boot and installation tests.
- Test fresh installation and external SSH access, unique host keys, boot
  presentation, terminal history/scrollback, Wi-Fi launching and varied
  command assistance on the new images.
- Test the separate desktop profile when selected; physical Wi-Fi, supported
  smart-card operations and actual Apple-host display/resize/acceleration
  require their applicable hardware/platform evidence.

No new ISO artifact checksums, completed build status, release readiness,
public publication or hardware compatibility are claimed by this progress
receipt. Update it with observed results as the builds and acceptance finish.
