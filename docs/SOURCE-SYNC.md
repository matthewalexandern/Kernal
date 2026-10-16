# Shared source on Ubuntu and Mac

Ubuntu and the Mac use separate Git checkouts of the same private repository:
`https://github.com/matthewalexandern/Kernal.git`. Share reviewed commits through
that origin. Each machine needs its own working Git authentication and access
to the repository; copying a checkout or a Git bundle does not transfer login
credentials.

## Before working on main

From the repository directory on either machine, run:

```sh
git status --short --branch
./scripts/sync-source.sh
```

The helper checks that `origin` identifies `matthewalexandern/Kernal` over
HTTPS or SSH, requires `main` and a clean checkout including untracked files,
then fetches `origin/main`. An already current or safely fast-forwarded checkout
returns exit code 0. Local-only commits return exit code 2 with instructions to
review and push normally; those commits remain local. Diverged history, a dirty
checkout, an unfinished Git operation, another branch, a wrong origin or an
authentication failure stops with exit code 1. The helper never commits or
pushes. Reconcile reported differences
deliberately and resolve authentication failures before assuming either
computer has the latest source.

The equivalent manual update is:

```sh
git status --short --branch
git pull --ff-only origin main
```

Check that the working tree is clean before the manual update. At the end of a
task, inspect the diff, stage only the intended files, then commit and push:

```sh
git status --short --branch
git diff
git add -- path/to/reviewed-file
git commit -m "Describe the reviewed change"
git push origin main
```

Replace the example file and message with the actual reviewed changes. A push
that is rejected because remote history advanced needs a fetch and review of
both histories. Keep the history; do not force-push, reset away local work, or
automatically stash it. Run the sync helper on the other machine before its
next task. Uncommitted edits are local to their checkout.

## Simultaneous work

Give each simultaneous task a separate named branch, for example
`mac/arm64-install-checks` and `ubuntu/network-tests`. Start from updated `main`:

```sh
./scripts/sync-source.sh
git switch -c mac/arm64-install-checks
```

Commit and push that branch by its actual name. On the task branch, fetch and
merge reviewed `origin/main` deliberately when shared changes are needed:

```sh
git fetch origin
git merge origin/main
```

Review conflicts and test the result before sharing it. Merge completed work
into `main` after review, then update the other checkout. The main-only sync
helper does not manage task branches or resolve conflicts. Do not run a
background file mirror between the two working trees.

## Restore the transferred repository on the Mac

The complete Desktop handoff contains a bundle with source history and the
build-record commit `94cf361`. After verifying the handoff folder's
`SHA256SUMS`, restore it into a new destination:

```sh
git clone ~/Desktop/KythOS-Kernal-cc472f5/source/Kernal-records-94cf361.bundle ~/Kernal
git -C ~/Kernal remote set-url origin https://github.com/matthewalexandern/Kernal.git
git -C ~/Kernal log -1 --oneline
git -C ~/Kernal status --short --branch
```

That bundle ends at `94cf361`; later workflow changes, including the sync
helper, arrive through a subsequent published commit or a newer verified
bundle. Once those commits have been pushed and Mac Git authentication works,
update the restored checkout:

```sh
git -C ~/Kernal pull --ff-only origin main
cd ~/Kernal
./scripts/sync-source.sh
```

Until the publishing machine successfully pushes, its newer commits are not
available from GitHub. A conversation appearing on both computers does not
synchronize files or give either session shell access to the other machine.

## Source changes and architecture builds

Choose one reviewed, clean source commit for both AMD64 and ARM64 builds.
Transfer or check out that exact revision inside each isolated Debian builder
before starting. Keep active build inputs fixed; do not pull changes into a
builder while it is staging or building an image. Follow
[BUILDING.md](BUILDING.md) and [ARM64.md](ARM64.md), and run the multiarch pair
gate after both builds finish.

The [completed cc472f5 build records](builds/2026-10-16-cc472f5/README.md)
describe images built from `cc472f571c2784a105ee12e5df408275ef14fa37`.
The later evidence commit `94cf361` does not change that image source identity.
Both architecture builds, source coverage and transfer checks passed. AMD64
has fresh installed-system VM acceptance; ARM64 boot, installation, Secure
Boot, Parallels and physical hardware remain untested.

Pulling source does not update an existing ISO or installed OS. Changes to
common image sources require rebuilding both architectures from the new shared
commit and retaining new manifests and checksums. The ignored `.build/`
directory, ISOs, VM disks, caches and private runtime files stay outside source
sync. Deliver immutable build artifacts separately and verify the destination
against their manifests.
