# Console appearance

After a local console login, KythOS reserves a top row for:

```text
KythOS Kernal 2027 | https://kythos.ai tty1
```

The terminal suffix is the actual outer virtual console, such as `tty1` or
`tty2`. Command output scrolls below this row. Clearing the command area and
using full-screen terminal applications leave the header available.

The header and the hostname in the default Bash prompt use the same light
periwinkle blue without requesting bold text. The theme uses the normal-blue
palette entry and SGR34, so it works with 512-glyph console fonts that expose
eight simultaneous text colors. The hostname remains the real machine name.
The installer offers `KythOS` as its editable default; custom hostnames are
preserved.

The original text-console font is retained. The header and default prompt
use regular weight, without a bold attribute.

The original KythOS session wrapper uses a packaged tmux terminal viewport to
reserve the row and report the remaining screen size correctly to programs.
Each login gets a private socket and one pane running as the authenticated
user. The KythOS configuration does not load user plugins, capture ordinary
prefix keys, open a network listener, or join another session. Its owned
server and socket are removed when that login ends. Ordinary tmux sessions
are independent.

Run `kythos-console raw` to return to a plain shell on the physical console
for direct VT tools such as `startx` or `setfont`. This ends the viewport and
returns to the originally authenticated account. Leave a nested sudo shell
first. Run `kythos-console header` from that raw console to restore the bar.

Automatic wrapping applies only to local Linux virtual consoles. Live-media
installer startup, SSH, noninteractive shells and existing terminal sessions
keep their ordinary entry paths. The wrapper falls back to a plain login
shell if the viewport cannot start.

Set `KYTHOS_CONSOLE_HEADER=0` before opening an outer login shell to opt out. User
Bash configuration can override the default prompt. The main files are:

- `/etc/profile.d/55-kythos-console.sh`
- `/usr/local/libexec/kythos-console-session`
- `/usr/share/kythos/console-tmux.conf`

Linux virtual consoles have a limited palette. The wrapper applies the
per-console normal-blue theme entry `#9eafff`; it persists until that console's
palette is reset. Other consoles, global palette defaults and other palette
entries are not modified. `KYTHOS_CONSOLE_COLOR=0` disables that theme update.
