# AMD64 build record

Image source: `cc472f571c2784a105ee12e5df408275ef14fa37`.

Fresh QEMU/KVM UEFI Secure Boot encrypted Calamares installation and all seven native acceptance groups passed for the exact binary ISO. See native-acceptance.json.

All 28 final artifacts were independently copied and read back; no required source tuples are missing. The paired comparison is recorded in `../multiarch-pair.json`.

`metadata/` preserves exact small build records and original artifact hashes. Its `SHA256SUMS` describes the full external artifact set, including ISOs and logs that are not stored in Git. Normalized provenance and transfer records retain the original metadata hashes while excluding private builder paths and authentication material. The top-level `RECORDS-SHA256SUMS` describes the files actually committed here.
