# Kernal collaboration

The Ubuntu and Mac workspaces use separate clones of the private
`matthewalexandern/Kernal` repository. GitHub is the shared source history.
See [the source synchronization workflow](docs/SOURCE-SYNC.md).
For the actual private draft ISO delivery and continuation on another device,
start with [the cloud handoff](docs/CLOUD-CONTINUATION.md). Verify delivery
completion and checksums before using its assets.

## Noreply history migration

- The user authorized rewriting the 22 unpublished commits to use GitHub
  noreply email addresses. The shared origin uses the rewritten history;
  [the identity map](docs/git-identity-map-2026-10-16.json) preserves the mapping
  and equivalent source trees.
- Original `94cf361` bundle checkouts cannot fast-forward to the rewritten
  `main`. Preserve old checkouts, local edits, private backup refs and frozen
  exports. On the Mac, clone GitHub into a new `~/Kernal-synced` directory and
  bring only reviewed file changes into new commits. Never merge, cherry-pick
  or push the original private-email history or backup refs into shared
  branches. New bundles must include only the rewritten shared branch.
- Before committing on either machine, set and verify the repository-local
  `user.email` as `321331429+matthewalexandern@users.noreply.github.com`, using
  the verified GitHub account ID and login. Preserve author names and ensure
  author/committer environment overrides do not restore a previous email.

## Before changing source

- Inspect the current branch and working tree. On a clean `main` checkout,
  run `./scripts/sync-source.sh` before editing. It fetches and fast-forwards
  safely, and reports unpublished commits or divergence.
- Preserve existing local changes and commits. Never force-push, reset away
  work, automatically stash, or rewrite another machine's history.
- For concurrent tasks, use separate named branches. Fetch current `origin/main`
  before branching and deliberately merge reviewed shared changes. The sync
  helper operates on `main` only.
- If authentication or connectivity prevents synchronization, report the
  actual state and preserve local work. Do not describe the two machines as
  synchronized without observing matching source revisions.

## After changing source

- Review and verify the task's changes. Stage exact intended paths, inspect
  the staged diff and check whitespace and credentials before committing.
- The user has requested shared source updates between these two machines:
  commit and normally push completed, reviewed project work to the appropriate
  shared branch. Fetch again before pushing; reconcile concurrent changes
  without discarding either side. Report failed authentication or rejected
  pushes accurately. Public releases and ISO uploads need separate instructions.
- The other machine must fetch and fast-forward or merge before starting its
  next source task. A shared conversation or transferred folder is not evidence
  that a checkout has updated.

## Build and artifact boundaries

- Both architecture builds must pin the same reviewed, clean source commit.
  Use independent build checkouts or immutable source bundles; never pull into
  active build inputs.
- Existing `cc472f5` images retain that exact source identity. Their verified
  records are in `docs/builds/2026-10-16-cc472f5/`; later workflow or records
  commits do not change the bytes or identity of those images.
- The equivalent noreply source commit is recorded in the identity map. Its
  matching tree does not replace the original commit ID embedded in existing
  images, manifests or frozen exports.
- Keep ISOs, VM disks, caches, private keys, passwords and private runtime logs
  out of Git. Transfer artifacts separately with checksum read-back. Preserve
  frozen transfer folders and the retained user VM/account.
- ARM64 image build/integrity checks passed for that pair. ARM64 boot/install,
  Parallels, physical hardware and formal compliance require their own evidence.
