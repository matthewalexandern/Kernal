# KythOS Kernal 0.1.0 build records

Both architectures were built from clean image source commit `cc472f571c2784a105ee12e5df408275ef14fa37`, signed Debian snapshot `20261016T000000Z`, and source epoch `1792165132`. The canonical recipe digest is `5dfa0862922c5434a9b5ff8403d648db5cd542b3c21332255482ea735bd64d87`. These are evidence-only records; their Git commit is separate from the image source commit.

## Completed build and integrity checks

| Architecture | Verified artifacts | Required source tuples | Provided source tuples | Missing |
| --- | ---: | ---: | ---: | ---: |
| amd64 | 28 | 666 | 668 | 0 |
| arm64 | 28 | 656 | 658 | 0 |

Both normal builds exited 0. Each complete artifact set was transferred and independently read back. The final pair gate rehashed all 56 declared artifacts and confirmed matching clean source, snapshot, epoch and byte-identical canonical recipe. See `multiarch-pair.json` and the per-architecture provenance/transfer records.

| Image | Bytes | SHA-256 |
| --- | ---: | --- |
| amd64 binary | 2001469440 | `06c0e9619de021daabd59b7e7f28ef5961aa4563a98aad7ad62f48001ea5ccf8` |
| amd64 source | 4343633920 | `dbc1e92bcc8bda363c5198dc81968d4f2a898a2544c85f101cff0c70753982d4` |
| arm64 binary | 2078701568 | `b27a511580222ecd16ec1806b385945dd2b67ab78ab9fa6a60c0ff4d69005646` |
| arm64 source | 4328081408 | `876d8c0008d37293bfa82c946de495cac5600e06eaa767f3bcd0fc88170c08e3` |

The same-named source ISOs belong to separate architecture builds and must stay in separate architecture directories. ISOs, VM disks, caches and raw private VM logs are external to this Git record. Complete local artifact directories are `.build/calamares-candidate-cc472f5` and `.build/arm64-candidate-cc472f5`.

## Runtime evidence and remaining scope

AMD64 exact binary `06c0e961...a5ccf8` passed a fresh encrypted Calamares UEFI/Secure Boot installation, ordinary restart/unlock/login, installed baseline, command assistance, original regular console font and fixed header, kernel diagnostic routing, DHCP/hotplug/static retention, and normal owned test cleanup. Its acceptance report records all seven groups, 61 captures and zero retained fixture credential matches.

ARM64 boot, installation, Secure Boot, Parallels and physical hardware remain untested. The pair gate is an artifact/source consistency check. Physical NVIDIA, Wi-Fi, TPM and FIDO2 acceptance and formal FIPS certification or STIG compliance are not established by these builds.

## Build environment

Both disposable launchers explicitly used `LC_ALL=C.UTF-8` and `LANG=C.UTF-8`. Earlier failed/interrupted runs remain historical evidence; these final builds repeated normal gates from the same clean source. AMD64 used a verified package-archive-only cache seed; ARM64 used no external seed. The build environment records explain the earlier locale mismatch. No distribution locale, authentication policy or host settings were changed by this evidence commit.

Original upstream names, signed snapshot metadata and license notices are retained as provenance. Verify the committed evidence with `sha256sum -c RECORDS-SHA256SUMS`, or `shasum -a 256 -c RECORDS-SHA256SUMS` on macOS.
