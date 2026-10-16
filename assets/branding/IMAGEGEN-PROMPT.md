# KythOS boot artwork source

The source PNG in this directory was generated with OpenAI's built-in image
generation tool. Exact product text is applied deterministically when deriving
the bootloader and Plymouth images, so the displayed name is always
`KythOS Kernal`.

## Prompt

> Create a refined, security-focused abstract boot background for a minimal
> operating system named KythOS Kernal. Use a deep near-black navy background
> with a restrained central geometric shield made from interlocking luminous
> lines, suggesting kernel rings and trusted computing. Use crisp,
> vector-friendly geometry with a calm, understated cyan and muted-violet
> glow. Make it a 16:9 wide canvas with generous clear space. Include no text,
> existing brand logos, watermark, people, scenery, busy circuitry, or padlock
> imagery.

Generated source SHA-256:
`3dc68b22cce543b494bd97ef334e70a712f6d46a5be1cbc7cb63699063add25f`.

## Installer banner source

`kythos-installer-banner-source.png` was generated from the boot artwork with
the following image-edit prompt, then reduced to the Debian Installer's exact
800 by 75 pixel RGB banner format. The final banner keeps its emblem and title
in the central area because the low-resolution GTK installer can crop its
edges.

> Create an ultra-wide operating-system installer header banner derived from
> this KythOS shield artwork. Dark navy-to-black background, subtle cyan and
> violet glow, crisp clean professional security-focused design. Use the same
> shield symbol as a small emblem and include the exact title text "KythOS
> Kernal" in a highly legible modern sans-serif. Compose all vital emblem and
> title content inside the central 60 percent so it remains visible if either
> side is cropped. No Debian logo, no extra words, no version number, no
> mockup, no frame. Target aspect ratio 800:75 (very wide and short).

Generated installer source SHA-256:
`0b0342e5bbf4d590c9c775f8f87a922e63a2ae75a9c68537e5ac62b8a27e4947`.
