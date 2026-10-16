# Network defaults

Managed Ethernet adapters automatically request IPv4 addresses, DNS and routes
using DHCP, with IPv6 automatic configuration enabled. This includes PCI,
virtio and USB Ethernet. The default profile supports several adapters at once
and applies to newly connected adapters without interface-name or MAC bindings.
It waits for a usable link and continues retrying activation.

The fallback profile has the lowest autoconnect priority, `-999`. Configured
profiles normally use priority `0` and take precedence. Active connections are
not replaced by autoconnect. Administrator static profiles and network ownership
are not rewritten. A deliberately configured profile with autoconnect disabled
does not participate in automatic selection; disable device autoconnect too if
that adapter must stay disconnected, using `nmcli device set DEVICE autoconnect no`.

The profile is Ethernet-only and excludes the `veth` and `tun` drivers. It does
not configure bridge, VPN or tunnel connections. Controller and port profiles
for hypervisors or containers should be configured explicitly. No global
managed-device or udev override is installed.

Wi-Fi uses NetworkManager's normal enabled radio and DHCP defaults. Join a
chosen network with `nmtui` or `nmcli --ask device wifi connect SSID`; configured
networks may reconnect automatically. Unknown networks are not joined, and
hardware radio switches or administrator preferences are respected.

The root-only keyfile is validated by the exact packaged `nmcli --offline`
parser during image construction. Its UUID is derived from the filename by
NetworkManager. No fixed IP addresses, public DNS servers, shared connection
mode or credentials are shipped.

## Acceptance checks in a disposable installed VM

1. Boot with two ordinary Ethernet adapters on DHCP-capable virtual networks.
   Verify both use the fallback profile simultaneously, obtain leases and
   expected routes/DNS, and retain this behavior after reboot.
2. Hotplug a USB CDC Ethernet adapter. Verify it automatically obtains a DHCP
   lease instead of a profile whose IPv4 method is `link-local`.
3. Give one adapter a persistent static profile with ordinary priority `0`.
   Reboot and verify its static address and profile are retained, while the
   other adapters still use DHCP.
4. Create test bridge, veth and tunnel devices. Verify this fallback profile is
   unavailable for those devices and does not change their configuration.
5. Check Wi-Fi on real supported hardware: join a chosen secured SSID, verify
   DHCP and reconnect after reboot, then verify no unknown SSID is joined.

Useful read-only commands:

```sh
nmcli -f NAME,TYPE,DEVICE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show
nmcli -f GENERAL,IP4,IP6,DHCP4 device show
ip route
cat /etc/resolv.conf
```

Settings follow the packaged NetworkManager 1.52.1 documentation:
[connection properties](https://manpages.debian.org/trixie/network-manager/nm-settings-nmcli.5.en.html)
and [keyfile format](https://manpages.debian.org/trixie/network-manager/nm-settings-keyfile.5.en.html).

## Remote access acceptance

The installed base permits TCP port 22 in its default-drop firewall and enables
`ssh.service`; the temporary live installer does not serve SSH. See the
[SSH lifecycle and key workflow](ENCRYPTION-SSH-CY.md#ssh-access-after-installation).
For each architecture and affected edition, validate a fresh installation:

1. Select an ordinary account with a nonempty password. Boot the installed
   system without manually enabling services. Confirm `systemctl is-enabled
   ssh.service` returns `enabled` and `systemctl is-active ssh.service` returns
   `active`. Run `sudo kythos-security-status` and inspect any failures.
2. Record its real IPv4/IPv6 address and host-key fingerprint from the console.
   From a second machine on a reachable network, connect with
   `ssh USER@ADDRESS`, verify the fingerprint, and authenticate with the
   installer-created password. Confirm `id` identifies that ordinary account.
   Repeat using a public key installed with `kythos-ssh install -i KEY.pub`.
3. Confirm root password/key login and empty-password login fail. Verify RSA
   user keys negotiate RSA SHA-2; do not add `+ssh-rsa` compatibility options.
4. Reboot and repeat the remote connection. The host fingerprint must remain
   stable across reboots. Install a second disposable VM from the same ISO and
   confirm its host-key fingerprint differs from the first installation.
5. On a running installed VM, deliberately stop SSH, run
   `sudo kythos-enable-ssh`, and confirm it is immediately reachable and remains
   enabled for the next boot. Check host and VM NAT/bridging/firewall settings
   separately if the guest's listener is reachable only inside the VM.

The source test's isolated localhost connection validates OpenSSH RSA SHA-2
behavior, not external network reachability, kernel firewall application, or
the installed-account/PAM path. Do not mark these acceptance checks complete
without the separate-machine and fresh-install evidence.
