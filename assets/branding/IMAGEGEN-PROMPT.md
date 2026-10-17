# KythOS white shield provenance

The current master is `kythos-mark-white.svg`: white vector paths with a
transparent background, a complete inner monogram, and a simple shield.
It contains no raster embedding or external resource references.

The inner monogram retains the geometry of the approved original
`kythos-mark-cyan-source.png`, SHA-256
`0bf8e10c25b3880d43adcb997474ae2e1cf6d5fd6fb638ce3c4316efb95a6157`.
That historical transparent cyan source was isolated from the user's original
reference using OpenAI image generation. It remains unchanged for provenance.

A later image-editing draft proposed a white shield but introduced unwanted
artifacts. It was rejected and is not used in shipped art. The canonical SVG
instead preserves the original opaque monogram contour, its asymmetric loop,
negative spaces and hand angles, by deterministic vector conversion. It
uniformly scales/translates the whole shape inside a separately authored
shield. It does not interpret the 9:06 meaning by generating new clock hands.
The time commemorates the birth of the user's son Cyrus; this explanation is
provenance, not a visible product name.

## Reproducible monogram conversion

The source's soft cyan glow is discarded. ImageMagick 6 identifies the opaque
bright core, then Potrace 1.16 converts its boundary to smooth vector curves:

```sh
convert assets/branding/kythos-mark-cyan-source.png -background white \
  -alpha on -fx '(u.a>0.95 && u.g>0.9 && u.b>0.95)?0:1' \
  -alpha off /tmp/kythos-monogram-core.pbm
potrace /tmp/kythos-monogram-core.pbm --svg --flat --opttolerance 0.2 \
  -o /tmp/kythos-monogram-traced.svg
```

The traced path and its original `translate(0 941) scale(.1 -.1)` coordinate
transform are preserved in the master. A single surrounding
`translate(86 214) scale(.28)` transformation provides inner spacing.
No independent hand rotation, nonuniform scaling or replacement is applied.
The geometry test compares the reverse-transformed vector with the original
opaque-core mask at native resolution and requires overlap above 99.5%.

## Deterministic derivatives

```sh
python3 scripts/render-branding.py
python3 scripts/render-branding.py --check
python3 tests/test-boot-artwork.py
```

The renderer requires `python3-pil`, `librsvg2-bin` and `fonts-dejavu-core`.
It produces the transparent Plymouth and installer logos, boot backgrounds,
BIOS/UEFI menu artwork, progress-pixel assets, and both identically branded
Debian Installer header variants. Calamares receives an identical SVG copy.
The exact `logo_debian.png` interface filenames are preserved.

Boot-screen product text is small and lower-right:

```
KythOS Kernal™ 2027
https://kythos.ai
```

The Plymouth script renders text separately and handles real progress,
indeterminate activity, encrypted-volume input and functional messages.
