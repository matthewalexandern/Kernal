# Shared source on Ubuntu and Mac

Ubuntu and the Mac use separate Git checkouts of the same private repository:
`https://github.com/matthewalexandern/Kernal.git`. Share reviewed commits through
that origin. Each machine needs its own working Git authentication and access
to the repository; copying a checkout or a Git bundle does not transfer login
credentials.

The unpublished commits were rewritten with the user's authorization to use
GitHub noreply email addresses. The shared origin uses that new history. See
the [identity map](git-identity-map-2026-10-16.json). If a checkout came from the
original `94cf361` handoff bundle, follow the migration below before syncing.

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

## Migrate the original handoff checkout

The original `Kernal-records-94cf361.bundle` contains the previous email
history. Its `main` cannot fast-forward to the rewritten shared `main`.
Preserve that bundle, its frozen handoff folder and any existing checkout for
image provenance and local edits. Do not merge or push the old history or its
backup refs into the shared repository.

After the rewritten history is published and Mac Git authentication works,
clone it into a new directory, leaving the old checkout intact:

```sh
git clone https://github.com/matthewalexandern/Kernal.git ~/Kernal-synced
cd ~/Kernal-synced
git config --local user.email 321331429+matthewalexandern@users.noreply.github.com
git config --get user.email
./scripts/sync-source.sh
```

The email above uses the verified GitHub account ID `321331429` and login
`matthewalexandern`. Set and verify that repository-local email on Ubuntu as
well before committing. Preserve the existing author name. Ensure author or
committer environment overrides do not substitute the previous email.

If the old checkout has local work, compare the relevant files and bring only
reviewed file changes into the fresh checkout. Inspect the new diff and commit
those changes with the noreply identity. Do not merge, cherry-pick or push the
old commits, or include the old bundles and backup refs in a new export. A new
handoff bundle must contain only the rewritten shared branch.

A successful clone or pull requires published commits and working local Git
authentication. A shared conversation does not synchronize files or provide
shell access to the other computer.

## Source changes and architecture builds

Choose one reviewed, clean source commit for both AMD64 and ARM64 builds.
Transfer or check out that exact revision inside each isolated Debian builder
before starting. Keep active build inputs fixed; do not pull changes into a
builder while it is staging or building an image. Follow
[BUILDING.md](BUILDING.md) and [ARM64.md](ARM64.md), and run the multiarch pair
gate after both builds finish.

The [completed cc472f5 build records](builds/2026-10-16-cc472f5/README.md)
describe images built from `cc472f571c2784a105ee12e5df408275ef14fa37`.
Those original IDs remain the truth for the existing images and records.
The [identity map](git-identity-map-2026-10-16.json) identifies the equivalent
noreply source commit `56a1b71c023beef9c6a2db4b57cb2c5d5ccd1516`, whose source
tree is identical. Rewriting Git metadata does not relabel or update an ISO.
Both architecture builds, source coverage and transfer checks passed. AMD64
has fresh installed-system VM acceptance; ARM64 boot, installation, Secure
Boot, Parallels and physical hardware remain untested.

Pulling source does not update an existing ISO or installed OS. Changes to
common image sources require rebuilding both architectures from the new shared
commit and retaining new manifests and checksums. The ignored `.build/`
directory, ISOs, VM disks, caches and private runtime files stay outside source
sync. Deliver immutable build artifacts separately and verify the destination
against their manifests.
