# Local console viewport and neutral default prompt. User rc files may override
# PS1 afterward; no PROMPT_COMMAND or terminal escape is used to redraw a header.
[ -n "${BASH_VERSION:-}" ] || return 0
case $- in *i*) ;; *) return 0 ;; esac
[ "${TERM:-dumb}" != dumb ] || return 0

PS1='\u@\h:\w\$ '
if [ -x /usr/local/bin/kythos-theme ]; then
    /usr/local/bin/kythos-theme --apply
fi

# --check performs the strict local VT/live-image/SSH/nesting guards without
# starting tmux or modifying the console. Live installer login stays untouched.
if [ -x /usr/local/libexec/kythos-console-session ] &&
   /usr/local/libexec/kythos-console-session --check; then
    exec /usr/local/libexec/kythos-console-session
fi
