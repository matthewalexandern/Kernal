# Wi-Fi launcher

`WiFi` is a case-sensitive PATH command: `/usr/local/bin/WiFi` is a symbolic
link to the maintained `/usr/local/bin/kythos-wifi` launcher. It works in each
edition with NetworkManager, including an installed system.

Run `WiFi` from a desktop session to open NetworkManager's graphical connection
editor. Select a Wi-Fi profile, or add a Wi-Fi connection. The desktop edition
includes `nm-connection-editor` and `network-manager-applet`. From a TTY, it opens `nmtui connect`, where
available wireless networks can be selected. `WiFi --tty` explicitly chooses
the terminal interface; `WiFi --gui` requires a graphical session. An SSH
session needs an allocated TTY, for example `ssh -t HOST WiFi --tty`.

Launching the helper never enables radios, activates a connection, changes
profiles, or asks for credentials itself. Those actions happen only through
the selected interactive NetworkManager interface. NetworkManager and the
desktop authentication agent enforce the caller's authorization. Do not use
`sudo WiFi` to work around a missing desktop authentication agent.

Before opening the interface, the launcher checks whether NetworkManager can
answer, a Wi-Fi device exists, and its hardware/software radio is enabled. It
reports distinct problems and suggested next steps:

- No adapter: inspect `kythos-hardware-status`, driver/firmware availability,
  and USB attachment. A virtual machine often exposes only Ethernet even when
  the host uses Wi-Fi. Configure the host Wi-Fi normally, or explicitly attach
  a supported USB Wi-Fi adapter to the guest.
- Hardware block: inspect the switch, airplane mode and `rfkill list`. Software
  cannot override a hardware block.
- Software block: inspect `rfkill list` and explicitly run
  `nmcli radio wifi on` if appropriate, then retry.
- Missing interfaces: the TTY UI comes from `network-manager`; the graphical
  editor comes from `nm-connection-editor` (the older `network-manager-gnome`
  package is transitional in Debian 13). A desktop session with no graphical
  editor falls back to `nmtui` when an interactive terminal is available.
- Daemon/permission failure: inspect `systemctl status NetworkManager` and the
  session authorization. The launcher will not start services or elevate itself.

`python3 tests/test-device-support.py` exercises selection, dependency errors,
radio states, noninteractive handling, and execution through the exact symlink
using isolated executable fixtures. It does not establish physical Wi-Fi
connectivity. ISO acceptance additionally requires opening the actual GUI and
TTY interfaces, associating to a test access point, and checking connectivity
on the installed system without disrupting the tester's management connection.
