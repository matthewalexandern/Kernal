# KythOS Kernal security design

## Trust base

KythOS uses Debian 13 packages fetched through HTTPS and authenticated by
Debian archive signatures. The image keeps Debian's signed stock kernel and
module packages. Secure Boot is explicitly required during image assembly;
the build must fail if signed UEFI boot packages are unavailable.

Secure Boot authenticates the installed boot chain. Release checksums must
also be signed because Secure Boot does not authenticate a downloaded ISO.

## Common controls

- AppArmor remains enabled using Debian's supported kernel and package
  profiles. Experimental blanket profiles are excluded.
- Audit rules record changes to identity, sudo, APT, firewall, policy, and
  kernel module state without blocking those operations.
- nftables drops unsolicited inbound traffic. Loopback, established traffic,
  ICMP/ICMPv6, DHCP replies, outbound traffic, and forwarding remain usable.
  Editions own the forwarding and inbound exceptions required by their roles.
  Starting, reloading, or stopping the service only changes the KythOS-owned
  table; it does not flush tables installed by libvirt or container engines.
- Debian's unattended updater installs authenticated stable and security
  updates without forcing an automatic reboot or removing fallback kernels.
- Persistent compressed journals have bounded disk and time retention.
- Conservative sysctl settings reduce kernel pointer and log exposure and
  reject redirects/source routing. Reverse-path filtering is untouched so
  bridges, containers, asymmetric routing, and multihoming keep working.

## Compatibility boundaries

The common base does not disable kernel modules, USB, user namespaces,
virtualization extensions, packet-forwarding capability, core dumps, kexec,
or debugging tools. Those controls can break a desktop, container host,
hypervisor, or AI profiling workload and require edition-level testing.

The base installs no SSH server and opens no inbound service port. Server and
hypervisor editions must add explicit service rules. The AI and desktop
editions must handle proprietary NVIDIA modules and MOK enrollment separately.

The raw pre-release image installs KythOS policy files directly into the filesystem.
Before the first supported public release, those files must move into a
versioned `kythos-base-config` Debian package delivered from a signed APT
repository so installed systems can receive policy fixes and verify ownership.

## Release evidence

Every release needs the binary ISO, corresponding source ISO, build log,
live-build configuration dump, live-image package manifest, a separately
captured installed-system package manifest, checksums, signed tag, and a
detached signature over the checksum file. Release validation must also check
that every distributed binary has corresponding source where its license
requires it.
