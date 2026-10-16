# KythOS boot artwork source

The approved source is `kythos-mark-cyan-source.png`: a cyan KythOS mark on a
transparent canvas. It contains no wordmark or other text. The user supplied
the mark as a cyan-on-black reference, and OpenAI's built-in image generation
tool was used to isolate it from the black background while preserving its
shape, cyan color, and soft outer glow.

## Image edit direction

> Extract the cyan KythOS symbol from the supplied reference as a clean,
> transparent PNG. Preserve the complete hand-drawn mark, its proportions,
> rounded strokes, bright cyan fill, and restrained cyan edge glow. Remove the
> black background and all surrounding content. Add no letters, words,
> watermark, frame, or new symbol.

Approved transparent source SHA-256:
`0bf8e10c25b3880d43adcb997474ae2e1cf6d5fd6fb638ce3c4316efb95a6157`.

## Deterministic derivatives

Run the renderer from the repository root after intentionally replacing the
approved transparent source:

```sh
python3 scripts/render-branding.py
```

The renderer produces the checked-in Plymouth logo and static background,
BIOS and UEFI menu artwork, and both Debian Installer header variants. It does
not add text. The exact `logo_debian.png` filenames are required by the Debian
Installer overlay interface; the images themselves contain only KythOS art.

The Plymouth script animates the transparent mark with a staged reveal, a
diagonal light pass, a restrained breathing glow, and a short handoff fade.
Password, question, and boot-status text remain separate functional overlays
so encrypted systems stay usable.
