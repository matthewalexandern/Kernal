# Apple-hosted virtual machines and graphics

Select the guest architecture before building or importing an image. Apple
Silicon normally uses an **arm64** guest with native virtualization; an Intel
Mac normally uses **amd64**. An amd64 guest on Apple Silicon requires explicit
emulation where available and must not be described as native ARM performance.
Confirm the actual Mac model, chip, macOS version, hypervisor name/version and
selected VM settings on the host. A cloud Linux worker cannot establish these
facts for the user's Mac.

On the Mac, `uname -m`, `sw_vers`, and
`system_profiler SPHardwareDataType SPDisplaysDataType` provide useful host
observations. The system-profiler report may contain serial numbers; remove
them before sharing. Record the VM's guest architecture, firmware, virtual
display model, 3D setting and guest-tools version separately. Do not install
proprietary guest tools from an unrelated hypervisor.

## Guest components

The stock kernel provides supported virtio GPU, virtio network/storage and
other virtual device drivers. The desktop profile includes Xorg's available
video drivers, Mesa, `mesa-utils` (`glxinfo`), `spice-vdagent`, and
`qemu-guest-agent`. Package-provided udev, systemd and desktop autostart rules
activate agents when their corresponding channels/session exist. Installing
agents alone cannot create a missing host channel, enable host 3D support,
or establish that a particular virtual GPU is accelerated.

| Platform | Guest display integration to investigate | Boundaries |
| --- | --- | --- |
| UTM/QEMU with SPICE | Virtio GPU or QXL where the selected architecture/backend supports it; SPICE agent channel plus desktop agent for resize and clipboard integration | A software framebuffer may work without rendering acceleration. Backend/UTM version and the chosen display determine 3D support. |
| QEMU through a manager | Its actual virtual GPU, SPICE configuration and guest-agent channels | `qemu-guest-agent` supplies management integration; it is not a graphics driver or SPICE resize agent. |
| Parallels Desktop | Its supported Linux display driver and version-matched Parallels Tools | Proprietary tools are not bundled. Install only from the current Parallels-provided tools medium when that guest/kernel is supported. QEMU evidence does not validate Parallels. |
| VMware Fusion | Its supported virtual GPU and version-compatible guest tools | This profile does not automatically install Fusion-specific tools. Verify guest/architecture support before adding the vendor-supported Debian tools. |
| Apple Virtualization.framework based apps | The application's presented virtio display and its supported resize integration | The framework/app versions define capabilities. A SPICE agent does not provide resizing for an app without SPICE. |

No custom Xorg mode, forced resolution, kernel driver blacklist, or guessed
GPU-passthrough configuration is installed. Automatic driver discovery and
advertised display modes remain authoritative. Use the desktop Display
settings to choose a mode. In an X11 session, `xrandr --current` lists outputs
and modes; a deliberate `xrandr --output OUTPUT --mode MODE` can select an
already advertised mode. Under Wayland, configure native outputs through the
compositor rather than treating Xwayland's `xrandr` as physical output control.

## Observe and validate

Run inside the installed guest's graphical session:

```sh
kythos-vm-status
kythos-vm-status --json
kythos-hardware-status
glxinfo -B
```

The status command records guest architecture, `systemd-detect-virt` results,
available DMI identification, functional DRM drivers, connector modes, guest
agent channels/service state, and X11 display/renderer probes when available.
It leaves host identity and acceptance as unestablished. DMI is a hint supplied
by the hypervisor, not independent proof of the host chip or macOS release.
`llvmpipe`/`softpipe` indicates software rendering. A non-software renderer
still needs a real application exercise before claiming usable acceleration.
With Wayland, the GLX result describes the Xwayland path.

For each architecture/platform combination being claimed:

1. Boot the affected ISO, install to a blank test disk, eject the ISO and boot
   the installed system. Record the source commit and artifact SHA-256.
2. Verify a readable initial graphical display and record the actual driver,
   renderer, current resolution and offered modes.
3. Resize the VM window through at least two sizes. Confirm the guest's desktop
   resolution changes correctly, including after logout/login and reboot, if
   the platform claims automatic resizing. Record manual mode selection
   separately from automatic resizing.
4. Exercise a representative graphical workload and check the journal for
   display errors. Record software rendering as such; an agent process or a
   `direct rendering: Yes` line alone is insufficient proof of hardware 3D.
5. Validate SSH from another machine, including the VM network mode and its
   routing/port-forwarding rules. NAT may require an explicit host forwarding
   rule; the guest cannot infer or configure that rule.

## Virtual GPU versus physical GPU passthrough

A virtio/QXL/Parallels virtual display is a **virtual GPU**. Its acceleration
may translate or forward rendering through the host graphics stack. **Physical
GPU passthrough** assigns a real PCI GPU to the guest and requires explicit
host firmware, IOMMU/isolation, device ownership and hypervisor support. The
Apple integrated GPU is not established as an assignable PCI device by this
project. No physical GPU passthrough or native bare-metal Apple GPU support is
claimed. Pursue a passthrough setup only after the exact host/hypervisor vendor
documents support for that device and guest architecture.

`python3 tests/test-device-support.py` verifies guest detection/reporting using
fixtures and confirms it does not infer Apple-host acceptance or acceleration
from a virtio binding or agent channel. Actual Mac-host boot, resizing,
acceleration and proprietary-tools acceptance remain hardware/platform tests.

Useful primary references: [UTM documentation](https://docs.getutm.app/),
[SPICE guest integration](https://www.spice-space.org/download.html),
[QEMU guest agent](https://www.qemu.org/docs/master/interop/qemu-ga.html),
[Parallels support](https://kb.parallels.com/), and
[Apple Virtualization](https://developer.apple.com/documentation/virtualization).
