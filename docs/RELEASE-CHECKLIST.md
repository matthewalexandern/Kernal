# Release checklist

- [ ] Source tree is clean and the release tag is signed.
- [ ] Build ran in a recorded Debian 13 environment from a reviewed commit.
- [ ] APT authentication remained enabled and build logs contain no fetch or
      signature warnings.
- [ ] The tracked Debian snapshot timestamp and its InRelease hashes are
      present in provenance.
- [ ] Binary ISO and source ISO were produced.
- [ ] Live-image and installed-system package manifests, configuration dump,
      build log, and SHA256SUMS exist.
- [ ] No required source package is missing from the source release.
- [ ] Source coverage audit matches the live root and every ISO pool
      `.deb`/`.udeb`, plus extracted bootloader binary inputs, to an exact
      source version.
- [ ] Extracted b43 and b43legacy firmware is absent from the binary image.
- [ ] `firmware-ipw2x00` and `firmware-ivtv` are absent from the live root;
      their interactive recipient-license path remains available.
- [ ] BIOS boot passed.
- [ ] UEFI boot passed.
- [ ] UEFI Secure Boot passed with Debian-signed shim, GRUB, and kernel.
- [ ] Unencrypted and encrypted-LVM installation passed.
- [ ] Installed system boots, updates, and reports healthy security services.
- [ ] Network, storage, audio, display, suspend/resume, and firmware checks
      passed on named physical test hardware.
- [ ] Variant-specific ports and services have explicit firewall tests.
- [ ] SHA256SUMS has a detached maintainer signature.
- [ ] Binary ISO, source ISO, signatures, licenses, and release notes are
      published together.
- [ ] Both ISO roots and the installed image contain the exact KythOS MIT
      license, and disk/OS identity checks report KythOS.
