# Console, history, and terminal appearance

The default is white foreground text on a dark background. The prompt keeps
the real user, hostname, and working directory without a purple/blue hostname.
KythOS branding uses the trademark symbol; Linux-console banners use `[TM]`
when a readable glyph cannot be established. `/etc/issue` uses agetty's `\l`
escape, so the login banner reports the actual terminal dynamically.

After a local console login, the private tmux viewport reserves a top row:

```text
KythOS Kernal[TM] 2027 | https://kythos.ai /dev/tty1
```

The final field is tmux's actual outer client device, not a fixed `tty1` label.
The wrapper reads the current Linux console Unicode font map without changing
the font. It uses `™` if that map contains U+2122 and `[TM]` otherwise. Command
output scrolls below the bar; clear, resizing, and full-screen programs retain
it. Kernel messages remain available separately as described below.

## Appearance during and after installation

The setup guide's installation choices offer six original palettes: dark,
light, monochrome, blue, teal, and high contrast. Calamares transfers only that
allowlisted, nonsecret preference into `/etc/kythos/terminal-theme`. Direct
Calamares launches and the advanced Debian installer use the shipped dark
default when no choice was made. Account credentials, disks, encryption, and
installation confirmation remain in the installer.

After installation:

```sh
kythos-theme --list
kythos-theme light
kythos-theme --show
```

The command saves the invoking user's preference in
`${XDG_CONFIG_HOME:-$HOME/.config}/kythos/terminal-theme`. New terminals use that
preference; the current terminal receives supported color sequences, and the
managed console bar updates where supported. Some terminal emulators filter
palette requests or have their own profile overrides. In a managed local
console, reopen the login session to apply a changed physical VT palette fully.
Redirected/nonterminal output contains no palette escapes. No global Linux VT
palette, font, or unrelated tmux session is changed.

## Command history and search

Interactive Bash shells share persistent history for local TTY, GUI terminal,
and SSH sessions. Ordinary Up/Down recalls commands. Both CSI and application
cursor sequences are supplied when missing; existing user key bindings,
Readline macros, editing modes, and prompt hooks remain intact. Ctrl+R searches
backward in the normal Emacs editing mode. Vi mode also keeps its normal
history-search keys. User configuration can override defaults afterward.

At each prompt, Bash appends its new typed input and reloads the shared file
into its bounded in-memory history. This avoids the skipped/duplicated entries
that Bash's append-and-`history -n` pattern produces across concurrent sessions.
It never rewrites the shared file. The default memory limit is 20,000 entries;
on-disk history is not automatically truncated by competing shell exits. Set
`KYTHOS_HISTSIZE` and `KYTHOS_HISTFILESIZE` before the profile is sourced to
change those defaults. Large history files take longer to reload. Empty
`HISTFILE` disables persistence; normal Bash history controls remain available.

Only Bash's normal typed-command history is stored. There is no expanded
argument, environment, or command-output logger. A command starting with a
space is excluded by the default `ignorespace` policy; avoid typing literal
credentials into a command line that you intend to keep in history.

## Output scrollback

Output scrollback and command history are separate. In the managed console,
**Shift+PageUp** opens the private tmux scrollback (20,000 lines). PageUp/PageDown
move through it; Ctrl+R searches backward in the default copy mode. **q** or
**Esc** returns to the shell. `kythos-console scrollback` opens the same view
when a terminal cannot send Shift+PageUp. Plain Up/Down continues to reach Bash.
GUI terminals and SSH clients keep their native scrollback controls.

Each local login gets a private socket and one pane running as the authenticated
user. No user tmux configuration/plugins are loaded and no prefix key or network
listener is added. Mouse reporting stays off. The owned server/socket disappear
when that login ends; ordinary user tmux sessions remain independent.

Run `kythos-console raw` for a plain shell on the original physical console,
for example before `startx` or `setfont`. Leave a nested sudo shell first.
`kythos-console header` restores the bar from a raw local Linux console.
Automatic wrapping excludes live installer startup, GUI terminals, SSH,
noninteractive shells, and nested terminal sessions. A failed viewport start
falls back to Bash. `KYTHOS_CONSOLE_HEADER=0` opts out before an outer login.

The implementation lives in `/etc/profile.d/54-kythos-history.sh`,
`/etc/profile.d/55-kythos-console.sh`, `kythos-theme`,
`/usr/local/libexec/kythos-console-session`, and
`/usr/share/kythos/console-tmux.conf`. Debian and upstream copyright/license
notices remain in `/usr/share/doc/*/copyright`; `/etc/motd` retains attribution.

## Kernel diagnostics

On installed boots, `kythos-kernel-console.service` routes VT kernel diagnostics
to unused `tty12` before the first console login, keeping the shell viewport
intact without lowering kernel log levels or dropping diagnostics. **Alt+F12**
opens that console and **Alt+F1** returns. `sudo journalctl -k` and `sudo dmesg`
remain available. Serial output and live installer console routing are unchanged.

The oneshot respects an existing redirect, configured tty12 getty/boot console,
or an occupied tty12. Administrators assigning that VT to another custom service
should disable this service first. To restore foreground kernel messages:

```sh
sudo systemctl disable --now kythos-kernel-console.service
sudo /usr/local/libexec/kythos-kernel-console --restore
```

Restore acts only while the service still owns its redirect. Kernel routing has
no atomic compare-and-swap; order competing routing services after this one.
Stopping/restarting alone does not discard ownership. Diagnostic console text
remains available until reboot.

## Validation and remaining image checks

`tests/test-terminal-experience.py` runs actual Bash PTYs using Linux VT and
xterm cursor protocols, Ctrl+R, concurrent sessions, restart persistence,
custom key bindings/prompt hooks, command exit status, and nonexpanded history.
It also exercises the palette CLI on PTYs and redirected output, rejects unsafe
preference data, and verifies target preference propagation with fixtures.
`tests/test-console-header.py` uses native tmux PTYs for clear, scrolling,
full-screen `top`, resize, font fallback, raw transitions, cleanup, and separate
output scrollback. `tests/test-setup-wizard.py` exercises the native Qt selector
offscreen and the fixed installer handoff. Font mapping, physical VT rendering,
an installed desktop terminal, and fresh-image installation still need boot/VM
acceptance; source PTYs and offscreen GUI tests do not establish those results.
