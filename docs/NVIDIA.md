# NVIDIA driver path

KythOS keeps the stock kernel modules, matching kernel headers, DKMS, MOK
tooling, baseline NVIDIA graphics firmware, and `nvidia-detect` in the common
base. It does not force one proprietary driver onto machines with different
GPU generations. The selected Debian driver pulls its exact matching GSP
firmware branch, avoiding a stale or incompatible universal GSP package.

Run the detector on the installed system:

```sh
sudo kythos-nvidia-readiness
```

For a GPU supported by Debian's proprietary kernel module:

```sh
sudo cy update
sudo cy install nvidia-driver
```

For a Turing-or-newer GPU supported by NVIDIA's open kernel module, request
that provider with the driver stack:

```sh
sudo cy update
sudo cy install nvidia-open-kernel-dkms nvidia-driver
```

Use Debian packages rather than NVIDIA's `.run` installer. With Secure Boot
enabled, DKMS generates or uses a Machine Owner Key. Enroll the public key with
`mokutil`, complete enrollment in the physical MOK screen at reboot, then
confirm the running module has a signer:

```sh
sudo mokutil --import /var/lib/dkms/mok.pub
sudo reboot
modinfo -F signer nvidia
nvidia-smi
```

The exact key path is reported by DKMS and may differ if the administrator has
configured a site-owned signing key. Never delete the previous kernel until
the new kernel, module signature, `nvidia-smi`, and the edition's CUDA workload
have all passed. OpenSSL's opt-in FIPS provider configuration is not applied
globally, so it does not change DKMS or NVIDIA package behavior.
