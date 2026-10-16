# Optional desktop smart cards

The desktop edition includes OpenSC, its PKCS#11 module, PC/SC Lite (`pcscd`),
CCID reader drivers (`libccid`), `pcsc-tools`, and p11-kit. `pcscd.socket` is
enabled in the image; reader applications activate the daemon on demand. The
build hook configures this offline and does not start the builder's services.
The base edition does not install GUI/card integrations by default.

The hook reuses the package's OpenSC p11-kit registration, or installs a
multiarch-correct fallback. Firefox ESR receives an NSS `SecurityDevices.Add`
policy for the installed OpenSC module. This registers the card interface;
it does not trust arbitrary certificate authorities or choose a client
certificate for the user. Check `about:policies` and Firefox Settings →
Privacy & Security → Certificates → Security Devices. On a site that requests
a supported client certificate, the browser can offer the card certificate
and prompt for its PIN. The site must trust the certificate's issuer.

No PAM, disk-unlock, or mandatory smart-card login configuration is added.
Ordinary account login continues to work without a card. OpenSC and libccid
support specific cards/readers, not every product marketed as a smart card.
Use the relevant vendor/OpenSC compatibility information for the exact model;
some devices require additional vendor drivers. Do not insert generic PKCS#11
libraries from an unverified download.

## Reader and certificate checks

Run these in the installed desktop system, after attaching the reader and
inserting a supported card:

```sh
systemctl is-enabled pcscd.socket
kythos-smartcard-status
kythos-smartcard-status --certificates
pcsc_scan
```

Exit `pcsc_scan` with Ctrl-C after observing reader detection and card insertion.
The status helper is bounded and does not request a PIN, log into a token,
initialize a card, or change a card. `--certificates` explicitly asks for public
certificate enumeration; labels and reader/token information can identify
their owner, so review logs before sharing. Some cards hide certificates until
login: absence from unauthenticated enumeration does not establish an empty card.

Read-only observations are deliberately distinguished from a working
authentication/signature. A PIN prompt belongs in the consuming application
or `pkcs11-tool`'s interactive terminal, never a command-line `--pin` argument,
environment variable, source file, log, or shell history.

## Actual signing acceptance

Use a test card with an existing RSA signing key and corresponding public
certificate, whose policy permits `SHA256-RSA-PKCS`. Do not initialize or
generate a key on an existing personal card to test this feature. First obtain
the module path and inspect the card's supported mechanisms:

```sh
kythos-smartcard-status --json
# Set MODULE to the observed OpenSC module path for this architecture.
pkcs11-tool --module "$MODULE" --list-slots
pkcs11-tool --module "$MODULE" --list-mechanisms
pkcs11-tool --module "$MODULE" --list-objects --type cert
```

Choose the intended slot and a certificate/key pair with the same object ID.
If several readers or tokens are present, add the observed `--slot SLOT_ID`
to **each** command below. Replace `OBJECT_ID` deliberately; it is a public
identifier, not a PIN. Work in a private temporary directory:

```sh
umask 077
test_directory=$(mktemp -d)
cd "$test_directory"
printf '%s\n' 'KythOS smart-card acceptance challenge' > challenge.txt
pkcs11-tool --module "$MODULE" --read-object --type cert --id OBJECT_ID --output-file card.der
openssl x509 -inform DER -in card.der -pubkey -noout > card-public.pem
pkcs11-tool --module "$MODULE" --sign --mechanism SHA256-RSA-PKCS --id OBJECT_ID --login --input-file challenge.txt --output-file challenge.sig
openssl dgst -sha256 -verify card-public.pem -signature challenge.sig challenge.txt
```

The signing command prompts for the card PIN interactively. Stop after a PIN
failure and check the remaining retry count; repeated attempts can lock a card.
`Verified OK` proves a signature operation for this selected key/mechanism,
not certificate-chain validity or every application. Validate certificate
trust/revocation separately for production use. Cards using ECDSA, RSA-PSS,
or a different policy need their own supported mechanism and matching
verification procedure; do not substitute mechanism flags by guesswork.

For browser authentication acceptance, use a controlled HTTPS service requesting
client authentication, a trusted server certificate and an issuer trusted by
the server. Select the intended card certificate in Firefox, supply the PIN
through the browser, and verify the authenticated identity in the server's
audit result. Test ordinary login again with the card removed.

## Evidence boundaries

`python3 tests/test-device-support.py` exercises reader/slot reporting, explicit
public certificate queries, missing dependencies, and the absence of PIN/login
operations using fixtures. Image building validates the installed p11-kit
module and writes the Firefox policy. Neither check substitutes for a reader,
card, PIN interaction, successful signature verification, or browser client
authentication. Record card/reader model, OpenSC version, supported mechanism,
application version, operation result and ordinary card-free login result in
the ISO acceptance receipt. Hardware-dependent results remain untested until
those operations are actually performed.

Reference configuration: [OpenSC supported hardware](https://github.com/OpenSC/OpenSC/wiki/Supported-hardware),
[Debian 13 OpenSC module files](https://packages.debian.org/trixie/amd64/opensc-pkcs11/filelist),
and [Firefox SecurityDevices policy](https://mozilla.github.io/policy-templates/#securitydevices).
