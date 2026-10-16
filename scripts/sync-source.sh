#!/bin/sh
# Synchronize the shared main checkout without overwriting local work.
set -eu

main()
{
    if [ "$#" -ne 0 ]; then
        printf 'Usage: ./scripts/sync-source.sh\n' >&2
        return 1
    fi
    repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
    cd "$repo_root"
    if [ "$(git rev-parse --show-toplevel)" != "$repo_root" ]; then
        printf 'Run this helper from its Kernal checkout.\n' >&2
        return 1
    fi
    case "$(git remote get-url origin)" in
        https://github.com/matthewalexandern/Kernal.git|\
        https://github.com/matthewalexandern/Kernal|\
        git@github.com:matthewalexandern/Kernal.git|\
        git@github.com:matthewalexandern/Kernal|\
        ssh://git@github.com/matthewalexandern/Kernal.git) ;;
        *) printf 'origin must identify matthewalexandern/Kernal on GitHub.\n' >&2; return 1 ;;
    esac
    branch=$(git symbolic-ref --quiet --short HEAD) || {
        printf 'Detached checkout: keep pinned build inputs unchanged.\n' >&2
        return 1
    }
    if [ "$branch" != main ]; then
        printf 'This helper updates main only; fetch and merge feature branches deliberately.\n' >&2
        return 1
    fi
    for operation in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply sequencer; do
        if [ -e "$(git rev-parse --git-path "$operation")" ]; then
            printf 'Finish the current Git operation before synchronizing.\n' >&2
            return 1
        fi
    done
    if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
        printf 'Checkout has local changes. Review them before synchronizing.\n' >&2
        return 1
    fi
    if ! git fetch --no-tags origin main; then
        printf 'Fetch failed; local source was not updated. Check Git authentication and connectivity.\n' >&2
        return 1
    fi
    fetched_head=$(git rev-parse --verify 'FETCH_HEAD^{commit}')
    local_head=$(git rev-parse HEAD)
    if [ "$local_head" = "$fetched_head" ]; then
        printf 'Kernal main is current: %s\n' "$local_head"
        return 0
    fi
    if git merge-base --is-ancestor "$fetched_head" "$local_head"; then
        ahead=$(git rev-list --count "$fetched_head..$local_head")
        printf 'Local main is %s commit(s) ahead. Review them, then run git push origin main.\n' "$ahead" >&2
        return 2
    fi
    if ! git merge-base --is-ancestor "$local_head" "$fetched_head"; then
        printf 'Local and remote main diverged. Review and reconcile both histories before continuing.\n' >&2
        return 1
    fi
    if [ "$(git rev-parse HEAD)" != "$local_head" ] ||
       [ "$(git symbolic-ref --quiet --short HEAD)" != main ] ||
       [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
        printf 'Checkout changed during fetch; synchronize again after reviewing it.\n' >&2
        return 1
    fi
    git merge --ff-only --no-edit "$fetched_head"
    printf 'Kernal main updated to: %s\n' "$fetched_head"
}

main "$@"
