# Compliance position

## Claims this release makes

KythOS Kernal 0.1.0 supplies an opt-in OpenSSL FIPS-provider configuration. It
also provides **initial STIG-derived hardening with a partial mapping to
selected Ubuntu 24.04 controls**. It has not been assessed or approved as a
STIG baseline and is not a FIPS validated cryptographic module, a FIPS
certified operating system, or a DISA approved STIG product.

Those boundaries are part of the security design. FIPS validation applies to
named module binaries, versions, architectures, operational environments, and
their security policies. A downstream rebuild does not inherit another
vendor's certificate. A DISA STIG claim similarly requires a product-specific
benchmark, checks, fixes, evidence, and applicability decisions.

## Opt-in OpenSSL FIPS provider path

The image includes Debian's `openssl-provider-fips` and prepares a separate
OpenSSL configuration that activates only the FIPS and base providers. It is
not applied globally, which keeps APT, SSH, Wi-Fi, storage, NVIDIA DKMS, and
edition workloads from being silently broken by an incomplete crypto-policy
switch.

KythOS generates that provider configuration with OpenSSL's strict
`-pedantic` runtime checks. An APT post-invoke hook and a boot service
regenerate and verify the module integrity configuration after provider
updates; the update hook reports a failure without interrupting an otherwise
valid package transaction.

Verify the provider and its integrity/self tests:

```sh
sudo kythos-fips-status
```

Run a tested OpenSSL consumer in the isolated provider context with:

```sh
OPENSSL_CONF=/etc/ssl/kythos/openssl-fips.cnf command ...
```

This scope covers that OpenSSL provider invocation only. It does not move the
stock kernel crypto API, OpenSSH, GnuTLS, libgcrypt, LUKS, or an application
into a validated boundary. Formal KythOS FIPS claims require exact validated
modules and a certificate-backed configuration manifest, or KythOS-sponsored
CMVP validation.

Ubuntu's useful design pattern is to keep separate validated, security-updated,
and preview streams with locked bills of materials and dedicated kernel
flavours. Canonical supplies those binaries through Ubuntu Pro entitlements;
KythOS does not copy, bundle, or redistribute them.

## STIG-derived hardening inventory

DISA does not publish a Debian 13 product STIG. The authoritative baseline for
this work is the [General Purpose Operating System SRG
V3R4](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_GPOS_V3R4_SRG.zip).
The [Canonical Ubuntu 24.04 LTS STIG
V1R7](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_CAN_Ubuntu_24-04_LTS_V1R7_STIG.zip)
is used only as a nearby implementation reference; Ubuntu package names and
fixes are not copied blindly onto Debian.

The machine-readable first-pass inventory is in
[`compliance/stig-map.tsv`](../compliance/stig-map.tsv). It lists all 195
Ubuntu 24.04 V1R7 controls, cross-references their SRG and CCI identifiers, and
marks every control that has not yet been assessed. It is not a complete GPOS
V3R4 product assessment. Default controls include authenticated packages, a
default-drop inbound firewall, early and persistent audit, AppArmor on
installed systems, AIDE system-file checks, persistent bounded logs, Secure
Boot support, encrypted-install support, no direct SSH root login, and no
empty SSH passwords.

The following requested compatibility choices are explicit deviations:

- Password SSH is permitted and KythOS adds no complexity or expiry policy.
- The common firewall does not expose port 22 until an edition or administrator
  adds an inbound rule.
- Kernel modules, NVIDIA DKMS, IPv4/IPv6, user namespaces, virtualization,
  debugging, USB, Wi-Fi, Bluetooth, core dumps, and forwarding capability stay
  available.
- Audit failure logs and suspends at storage thresholds; it does not panic the
  kernel or make the rule set immutable.
- Remote audit forwarding, smart-card/PIV authentication, site consent text,
  session timeouts, and organization-specific time sources require deployment
  policy.
- Debian's live overlay intentionally does not start the stock AppArmor unit;
  AppArmor enforcement and persistent journals are installed-system controls.

Run `sudo kythos-security-status` on an installed system for a baseline health
check. It is not a compliance assessment or evidence bundle. A supported
release still needs an independent SRG control-by-control assessment and a
signed evidence bundle.

## Primary references

- [NIST CMVP validated modules](https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules)
- [OpenSSL FIPS guidance](https://github.com/openssl/openssl/blob/master/README-FIPS.md)
- [Canonical FIPS overview](https://documentation.ubuntu.com/security/compliance/fips/fips-overview/)
- [Ubuntu Pro service terms](https://canonical.com/legal/ubuntu-pro-service-terms/2025-06-16)
- [DISA vendor STIG process](https://public.cyber.mil/stigs/vendor-process/)
