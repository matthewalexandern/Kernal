# Bash history and Readline defaults for local, graphical and SSH sessions.
[ -n "${BASH_VERSION:-}" ] || return 0
case $- in *i*) ;; *) return 0 ;; esac

# Append new input, then rebuild the in-memory list from the shared file. Bash's
# history -n offset counts this shell's appends and can skip a concurrent append;
# reloading avoids skipped entries and duplicated imports. Never rewrite the
# shared file. The memory list remains bounded by HISTSIZE.
# Bash records the typed line, not expanded arguments or command output.
shopt -s histappend cmdhist
HISTSIZE=${KYTHOS_HISTSIZE:-20000}
HISTFILESIZE=${KYTHOS_HISTFILESIZE:--1}
HISTFILE=${HISTFILE-"$HOME/.bash_history"}
case ":${HISTCONTROL:-}:" in
    *:ignorespace:*|*:ignoreboth:*) ;;
    *) HISTCONTROL="${HISTCONTROL:+${HISTCONTROL}:}ignorespace" ;;
esac

_kythos_history_sync()
{
    local previous=$?
    # An empty HISTFILE is an intentional per-user opt out.
    if [ -n "${HISTFILE:-}" ]; then
        if builtin history -a && [ -r "$HISTFILE" ]; then
            builtin history -c
            builtin history -r
        fi
    fi
    return "$previous"
}

# Preserve existing string or array hooks and their order. Run first so an
# existing prompt command still sees the command's original exit status.
if ! declare -p PROMPT_COMMAND 2>/dev/null | /usr/bin/grep -q '^declare -[^ ]*r'; then
    _kythos_history_registered=0
    for _kythos_prompt_hook in "${PROMPT_COMMAND[@]}"; do
        [ "$_kythos_prompt_hook" != _kythos_history_sync ] || _kythos_history_registered=1
    done
    if [ "$_kythos_history_registered" = 0 ]; then
        PROMPT_COMMAND=(_kythos_history_sync "${PROMPT_COMMAND[@]}")
    fi
    unset _kythos_history_registered _kythos_prompt_hook
fi

# Keep user bindings, macros, bind -x commands, and editing mode intact. Supply
# missing VT/application-cursor sequences as well as emulator CSI sequences.
_kythos_history_bind_default()
{
    local map=$1 key=$2 action=$3 bindings
    bindings=$(bind -m "$map" -p; bind -m "$map" -s; bind -m "$map" -X) 2>/dev/null
    case "$bindings" in *"\"$key\":"*) return 0 ;; esac
    bind -m "$map" "\"$key\": $action" 2>/dev/null || :
}
for _kythos_history_map in emacs-standard vi-insertion vi-command; do
    _kythos_history_bind_default "$_kythos_history_map" '\e[A' previous-history
    _kythos_history_bind_default "$_kythos_history_map" '\e[B' next-history
    _kythos_history_bind_default "$_kythos_history_map" '\eOA' previous-history
    _kythos_history_bind_default "$_kythos_history_map" '\eOB' next-history
    _kythos_history_bind_default "$_kythos_history_map" '\C-r' reverse-search-history
done
unset _kythos_history_map
unset -f _kythos_history_bind_default
