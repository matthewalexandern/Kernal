# Explicit, local command suggestions for interactive Bash with Emacs Readline.
# Tab previews; a second Tab or Right accepts. Only ordinary Enter executes.
[ -n "${BASH_VERSION:-}" ] || return 0
case $- in *i*) ;; *) return 0 ;; esac

# This explicit interface also works with custom bindings, vi mode, or disabled
# suggestions. Only names and completion declarations travel over an anonymous
# pipe. No history, function bodies, alias expansions, environment dump, error
# output, or files from the working directory are collected.
function __kythos_assist {
    local mode=explain status= json= name item key count line
    while (( $# )); do
        case $1 in
            --explain|--complete|--intent|--diagnose) mode=${1#--}; shift ;;
            --status)
                if (( $# < 2 )) || [[ ! $2 =~ ^[0-9]{1,3}$ ]]; then
                    builtin printf '%s\n' 'Usage: kythos-assist [--explain|--complete|--intent|--diagnose] [--status N] command-line' >&2
                    return 2
                fi
                status=$2; shift 2 ;;
            --json) json=-json; shift ;;
            --help|-h) command /usr/local/libexec/kythos-command-suggest --assist --help; return ;;
            --) shift; break ;;
            *) break ;;
        esac
    done
    if (( $# <= 1 )); then
        line=${1-}
    else
        # Keep distinct argv values distinct when the user supplies a command
        # and arguments rather than one quoted shell expression.
        builtin printf -v line '%q ' "$@"
        line=${line% }
    fi
    {
        builtin printf '%s\0%s\0%s\0' "$mode" "$status" "$line"
        for key in builtins aliases functions keywords; do
            case $key in
                builtins) item=builtin ;; aliases) item=alias ;;
                functions) item=function ;; keywords) item=keyword ;;
            esac
            count=0
            while IFS= read -r name; do
                [[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9_.+-]{0,254}$ ]] || continue
                builtin printf '%s:%s\0' "$key" "$name"
                (( ++count < 2048 )) || break
            done < <(builtin compgen -A "$item")
        done
        count=0
        while IFS= read -r item; do
            (( ${#item} <= 4096 )) || continue
            builtin printf 'completion:%s\0' "$item"
            (( ++count < 2048 )) || break
        done < <(builtin complete -p 2>/dev/null)
    } | /usr/local/libexec/kythos-command-suggest "--assist-shell${json}"
}
case $(builtin type -t kythos-assist 2>/dev/null) in
    alias|function) ;; # A deliberately supplied user interface takes precedence.
    *) function kythos-assist { __kythos_assist "$@"; } ;;
esac
[ "${KYTHOS_SUGGESTIONS:-1}" != 0 ] || return 0
[ "${__kythos_suggestions_loaded:-0}" != 1 ] || return 0
[[ -t 0 && -t 1 && ${TERM:-dumb} != dumb ]] || return 0
[[ -o emacs ]] || return 0
case $(builtin bind -v 2>/dev/null) in
    *$'set keymap emacs\n'*|*$'set keymap emacs-standard\n'*) ;;
    *) return 0 ;;
esac
[[ -x /usr/local/libexec/kythos-command-suggest ]] || return 0

# Readline metadata is constant during the two initialization phases. Reading
# all three binding classes once per phase avoids spawning a new subshell for
# every absent/private key, which is especially expensive under emulation.
# Outside initialization, binding inspection always reads the current state so
# a user's later changes still win when the integration is disabled.
__kythos_binding_snapshot() {
    local type definition key
    __kythos_binding_cached_type=() __kythos_binding_cached_definition=()
    for type in p s X; do
        while IFS= read -r definition; do
            [[ $definition == \"*\":\ * ]] || continue
            key=${definition%%\": *}
            key=${key#\"}
            __kythos_binding_cached_type["$key"]=$type
            __kythos_binding_cached_definition["$key"]=$definition
        done < <(builtin bind -m emacs-standard -"$type" 2>/dev/null)
    done
    __kythos_binding_cached=1
}

__kythos_binding_snapshot_clear() {
    unset __kythos_binding_cached_type __kythos_binding_cached_definition __kythos_binding_cached
    unset -f __kythos_binding_snapshot __kythos_binding_snapshot_clear
}

declare -A __kythos_binding_cached_type=() __kythos_binding_cached_definition=()
__kythos_binding_snapshot

# Return a complete Readline definition without evaluating its contents.
__kythos_binding() {
    local key=$1 type definition
    __kythos_binding_type= __kythos_binding_definition=
    if [[ ${__kythos_binding_cached:-0} == 1 ]]; then
        __kythos_binding_type=${__kythos_binding_cached_type[$key]-}
        __kythos_binding_definition=${__kythos_binding_cached_definition[$key]-}
        [[ -n $__kythos_binding_type ]]
        return
    fi
    for type in p s X; do
        while IFS= read -r definition; do
            if [[ $definition == \""$key"\":\ * ]]; then
                __kythos_binding_type=$type
                __kythos_binding_definition=$definition
                return 0
            fi
        done < <(builtin bind -m emacs-standard -"$type" 2>/dev/null)
    done
    return 1
}

# Do not replace custom Tab macros, shell callbacks, or reserved private keys.
__kythos_binding '\C-i'
if [[ $__kythos_binding_type != p || $__kythos_binding_definition != *': complete' ]]; then
    __kythos_binding_snapshot_clear
    unset -f __kythos_binding
    unset __kythos_binding_type __kythos_binding_definition
    return 0
fi
declare -A __kythos_suggestions_original_type=() __kythos_suggestions_original=()
declare -A __kythos_suggestions_owned_type=() __kythos_suggestions_owned=()
__kythos_suggestions_keys=('\C-i' '\e[99;1~' '\e[99;2~' '\e[99;3~' '\e[99;4~')
__kythos_suggestions_collision=0
for __kythos_suggestions_key in '\e[99;1~' '\e[99;2~' '\e[99;3~' '\e[99;4~'; do
    if __kythos_binding "$__kythos_suggestions_key"; then
        __kythos_suggestions_collision=1
    fi
done
if (( __kythos_suggestions_collision )); then
    __kythos_binding_snapshot_clear
    unset -f __kythos_binding
    unset __kythos_binding_type __kythos_binding_definition __kythos_suggestions_key
    unset __kythos_suggestions_collision __kythos_suggestions_keys
    unset __kythos_suggestions_original_type __kythos_suggestions_original
    unset __kythos_suggestions_owned_type __kythos_suggestions_owned
    return 0
fi
# Right is optional: a user's custom binding remains intact.
for __kythos_suggestions_key in '\e[C' '\eOC'; do
    if __kythos_binding "$__kythos_suggestions_key" &&
       [[ $__kythos_binding_type == p && $__kythos_binding_definition == *': forward-char' ]]; then
        __kythos_suggestions_keys+=("$__kythos_suggestions_key")
    fi
done
# F1 is local contextual help in Linux VTs and common terminal emulators.
# Existing user bindings win; no command line is accepted or executed by F1.
__kythos_suggestions_help_keys=()
for __kythos_suggestions_key in '\e[[A' '\eOP' '\e[11~'; do
    if ! __kythos_binding "$__kythos_suggestions_key"; then
        __kythos_suggestions_keys+=("$__kythos_suggestions_key")
        __kythos_suggestions_help_keys+=("$__kythos_suggestions_key")
    fi
done
for __kythos_suggestions_key in "${__kythos_suggestions_keys[@]}"; do
    __kythos_binding "$__kythos_suggestions_key" || :
    __kythos_suggestions_original_type["$__kythos_suggestions_key"]=$__kythos_binding_type
    __kythos_suggestions_original["$__kythos_suggestions_key"]=$__kythos_binding_definition
done

__kythos_suggestions_clear() {
    __kythos_suggestions_phrase= __kythos_suggestions_command=
    __kythos_suggestions_history= __kythos_suggestions_point=
}

__kythos_suggestions_native() {
    local key=$1
    __kythos_suggestions_native_tab=0
    if [[ $key == '\C-i' ]]; then
        # bind-x callbacks interrupt Readline's repeated-complete bookkeeping.
        # Reproduce its unchanged-buffer second Tab with the native listing
        # function; programmable completion still receives COMP_KEY=9/type=63.
        if [[ ${__kythos_suggestions_completed:-0} == 1 &&
              $READLINE_LINE == "$__kythos_suggestions_completed_line" &&
              $READLINE_POINT == "$__kythos_suggestions_completed_point" &&
              ${HISTCMD:-0} == "$__kythos_suggestions_completed_history" ]]; then
            builtin bind -m emacs-standard '"\C-i": possible-completions'
        else
            __kythos_suggestions_restore_key "$key"
        fi
        __kythos_suggestions_native_tab=1
        __kythos_suggestions_completion_before=$READLINE_LINE
        __kythos_suggestions_completion_point=$READLINE_POINT
    else
        __kythos_suggestions_completed=0
        __kythos_suggestions_restore_key "$key"
    fi
}

__kythos_suggestions_restore_key() {
    local key=$1 type=${__kythos_suggestions_original_type[$1]}
    case $type in
        p|s) builtin bind -m emacs-standard "${__kythos_suggestions_original[$key]}" ;;
        X) builtin bind -m emacs-standard -x "${__kythos_suggestions_original[$key]}" ;;
        *) builtin bind -m emacs-standard -r "$key" ;;
    esac
}

__kythos_suggestions_macro() {
    case $1 in
        '\C-i') builtin bind -m emacs-standard '"\C-i": "\e[99;1~\C-i\e[99;4~"' ;;
        '\e[C') builtin bind -m emacs-standard '"\e[C": "\e[99;2~\e[C\e[99;4~"' ;;
        '\eOC') builtin bind -m emacs-standard '"\eOC": "\e[99;3~\eOC\e[99;4~"' ;;
    esac
}

__kythos_suggestions_pending() {
    [[ -n $__kythos_suggestions_command &&
       $READLINE_LINE == "$__kythos_suggestions_phrase" &&
       $READLINE_POINT == "$__kythos_suggestions_point" &&
       ${HISTCMD:-0} == "$__kythos_suggestions_history" &&
       $READLINE_POINT == ${#READLINE_LINE} ]]
}

__kythos_suggestions_help() {
    local first output kind
    [[ ${KYTHOS_SUGGESTIONS:-1} != 0 ]] || return 0
    __kythos_suggestions_clear
    __kythos_suggestions_completed=0
    if [[ $READLINE_LINE =~ ^[[:space:]]*([^[:space:]]+)([[:space:]]|$) ]]; then
        first=${BASH_REMATCH[1]}
        # Do not echo control/bidi bytes from unusual alias or function names.
        # Other input goes through the engine's bounded literal parser below.
        if [[ $first =~ ^[a-zA-Z0-9_+./:!%-]+$ || $first == '[' || $first == '[[' ||
              $first == '{' || $first == '}' ]]; then
            kind=$(builtin type -t -- "$first" 2>/dev/null) || kind=
            case $kind in
                builtin|keyword)
                    if output=$(builtin help -s -- "$first" 2>/dev/null); then
                        builtin printf '\n%s\n' "$output"
                    fi
                    return 0 ;;
                alias|function)
                    builtin printf '\n%s is a shell %s. Inspect it with: type %s\n' "$first" "$kind" "$first"
                    return 0 ;;
            esac
        fi
    fi
    if output=$(__kythos_assist --explain -- "$READLINE_LINE" 2>/dev/null); then
        builtin printf '\n%s\n' "$output"
    fi
}

__kythos_suggestions_dispatch() {
    local key=$1 output status first kind message command field
    local -a fields=()
    __kythos_suggestions_resume=$key
    __kythos_suggestions_native_tab=0
    if [[ ${KYTHOS_SUGGESTIONS:-1} != 0 ]] && __kythos_suggestions_pending; then
        READLINE_LINE=$__kythos_suggestions_command
        READLINE_POINT=${#READLINE_LINE}
        __kythos_suggestions_clear
        __kythos_suggestions_completed=0
        builtin bind -m emacs-standard "\"$key\": \"\""
        return 0
    fi
    __kythos_suggestions_clear
    # A Right key is ordinary cursor movement unless a preview is pending.
    if [[ $key != '\C-i' || ${KYTHOS_SUGGESTIONS:-1} == 0 ||
          $READLINE_POINT != ${#READLINE_LINE} || -z $READLINE_LINE ]]; then
        __kythos_suggestions_native "$key"
        return 0
    fi
    # User aliases/functions and builtins always keep their native semantics.
    # Only inspect an unquoted literal first word; never parse shell input by eval.
    if [[ $READLINE_LINE =~ ^[[:space:]]*([a-zA-Z0-9_+./:-]+)([[:space:]]|$) ]]; then
        first=${BASH_REMATCH[1]}
        case $(builtin type -t -- "$first" 2>/dev/null) in
            alias|function|builtin|keyword)
                __kythos_suggestions_native "$key"
                return 0 ;;
        esac
    else
        __kythos_suggestions_native "$key"
        return 0
    fi
    if output=$(builtin printf '%s\n' "$READLINE_LINE" |
        /usr/local/libexec/kythos-command-suggest --shell 2>/dev/null); then
        status=0
    else
        status=$?
    fi
    builtin mapfile -t fields <<< "$output"
    if (( status != 0 || ${#fields[@]} != 3 )); then
        __kythos_suggestions_native "$key"
        return 0
    fi
    for field in "${fields[@]}"; do
        if [[ $field == *[[:cntrl:]]* ]]; then
            __kythos_suggestions_native "$key"
            return 0
        fi
    done
    command=${fields[0]} message=${fields[1]} kind=${fields[2]}
    case $kind in
        suggestion)
            if [[ -z $command ]]; then
                __kythos_suggestions_native "$key"
                return 0
            fi
            __kythos_suggestions_phrase=$READLINE_LINE
            __kythos_suggestions_point=$READLINE_POINT
            __kythos_suggestions_history=${HISTCMD:-0}
            __kythos_suggestions_command=$command
            builtin printf '\nSuggested: %s [Tab/Right to use]\n' "$command" ;;
        incomplete|ambiguous)
            [[ -n $message ]] && builtin printf '\n%s\n' "$message" ;;
        *) __kythos_suggestions_native "$key"; return 0 ;;
    esac
    __kythos_suggestions_completed=0
    # Suppress the queued Tab after a recognized phrase, then restore our macro.
    builtin bind -m emacs-standard '"\C-i": ""'
}

__kythos_suggestions_resume_key() {
    if [[ ${__kythos_suggestions_native_tab:-0} == 1 ]]; then
        __kythos_suggestions_completed=0
        if [[ $READLINE_LINE == "$__kythos_suggestions_completion_before" &&
              $READLINE_POINT == "$__kythos_suggestions_completion_point" ]]; then
            __kythos_suggestions_completed=1
        fi
        __kythos_suggestions_completed_line=$READLINE_LINE
        __kythos_suggestions_completed_point=$READLINE_POINT
        __kythos_suggestions_completed_history=${HISTCMD:-0}
    fi
    __kythos_suggestions_macro "$__kythos_suggestions_resume"
    __kythos_suggestions_resume=
}

kythos_suggestions_off() {
    local key
    for key in "${__kythos_suggestions_keys[@]}"; do
        __kythos_binding "$key" || :
        # A subsequent user .bashrc binding takes precedence, including at off.
        if [[ $__kythos_binding_type == "${__kythos_suggestions_owned_type[$key]}" &&
              $__kythos_binding_definition == "${__kythos_suggestions_owned[$key]}" ]]; then
            __kythos_suggestions_restore_key "$key"
        fi
    done
    __kythos_suggestions_clear
    __kythos_suggestions_completed=0
    KYTHOS_SUGGESTIONS=0
    unset __kythos_suggestions_loaded
}

builtin bind -m emacs-standard -x '"\e[99;1~": __kythos_suggestions_dispatch "\C-i"'
builtin bind -m emacs-standard -x '"\e[99;2~": __kythos_suggestions_dispatch "\e[C"'
builtin bind -m emacs-standard -x '"\e[99;3~": __kythos_suggestions_dispatch "\eOC"'
builtin bind -m emacs-standard -x '"\e[99;4~": __kythos_suggestions_resume_key'
for __kythos_suggestions_key in "${__kythos_suggestions_help_keys[@]}"; do
    builtin bind -m emacs-standard -x "\"$__kythos_suggestions_key\": __kythos_suggestions_help"
done
for __kythos_suggestions_key in "${__kythos_suggestions_keys[@]}"; do
    __kythos_suggestions_macro "$__kythos_suggestions_key"
done
__kythos_binding_snapshot
for __kythos_suggestions_key in "${__kythos_suggestions_keys[@]}"; do
    __kythos_binding "$__kythos_suggestions_key" || :
    __kythos_suggestions_owned_type["$__kythos_suggestions_key"]=$__kythos_binding_type
    __kythos_suggestions_owned["$__kythos_suggestions_key"]=$__kythos_binding_definition
done
__kythos_binding_snapshot_clear
__kythos_suggestions_clear
__kythos_suggestions_loaded=1
export -n __kythos_suggestions_loaded
unset __kythos_binding_type __kythos_binding_definition __kythos_suggestions_key
unset __kythos_suggestions_collision
