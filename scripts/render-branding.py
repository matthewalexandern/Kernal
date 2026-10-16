#!/usr/bin/env python3
"""Render or verify KythOS boot artwork from the approved cyan mark."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/branding/kythos-mark-cyan-source.png"
APPROVED_SOURCE_SHA256 = (
    "0bf8e10c25b3880d43adcb997474ae2e1cf6d5fd6fb638ce3c4316efb95a6157"
)
THEME_DIR = (
    ROOT
    / "config/includes.chroot/usr/share/plymouth/themes/kythos"
)


def load_mark() -> Image.Image:
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_hash != APPROVED_SOURCE_SHA256:
        raise SystemExit(
            f"unapproved source hash for {SOURCE}: {source_hash}"
        )

    with Image.open(SOURCE) as source_image:
        if source_image.mode != "RGBA" or source_image.size != (1672, 941):
            raise SystemExit(
                f"expected a 1672x941 RGBA source, got "
                f"{source_image.size[0]}x{source_image.size[1]} "
                f"{source_image.mode}"
            )
        mark = source_image.copy()

    visible_pixels = 0
    pixels = mark.load()
    for y in range(mark.height):
        for x in range(mark.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 8:
                continue
            visible_pixels += 1
            if green < red + 10 or blue < red + 10:
                raise SystemExit(
                    "approved source contains a visible non-cyan pixel"
                )
    if visible_pixels < 100_000:
        raise SystemExit("approved source is empty or unexpectedly sparse")

    bbox = mark.getbbox()
    if bbox is None:
        raise SystemExit(f"transparent or empty source image: {SOURCE}")
    return mark.crop(bbox)


def resized(mark: Image.Image, max_width: int, max_height: int) -> Image.Image:
    scale = min(max_width / mark.width, max_height / mark.height)
    size = (max(1, round(mark.width * scale)), max(1, round(mark.height * scale)))
    return mark.resize(size, Image.Resampling.LANCZOS)


def black_canvas(
    mark: Image.Image,
    size: tuple[int, int],
    mark_box: tuple[int, int],
    center_y: int,
) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    placed = resized(mark, *mark_box)
    x = (size[0] - placed.width) // 2
    y = center_y - placed.height // 2
    canvas.alpha_composite(placed, (x, y))
    return canvas.convert("RGB")


def save_rgb(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="PNG", optimize=True)


def save_rgba(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, format="PNG", optimize=True)


def render_assets() -> dict[Path, Image.Image]:
    mark = load_mark()
    assets: dict[Path, Image.Image] = {}

    # Transparent asset used by the Plymouth script. The fixed canvas gives the
    # script stable dimensions while retaining the generated semitransparent glow.
    animation_logo = Image.new("RGBA", (960, 540), (0, 0, 0, 0))
    placed = resized(mark, 900, 500)
    animation_logo.alpha_composite(
        placed,
        ((animation_logo.width - placed.width) // 2,
         (animation_logo.height - placed.height) // 2),
    )
    assets[THEME_DIR / "kythos-logo.png"] = animation_logo

    # Full-screen static frame used by installed GRUB and as the animation's
    # visual fallback. No product name is baked into any image.
    installed = black_canvas(mark, (1280, 720), (850, 470), 315)
    assets[THEME_DIR / "kythos-background.png"] = installed
    assets[ROOT / "assets/branding/kythos-boot-source.png"] = (
        installed.resize((1672, 941), Image.Resampling.LANCZOS)
    )

    # GRUB menu occupies the lower fifth of the screen.
    assets[ROOT / "config/bootloaders/grub-pc/splash.png"] = black_canvas(
        mark, (800, 600), (570, 335), 220
    )

    # Syslinux uses a lower-resolution 4:3 framebuffer.
    assets[ROOT / "config/bootloaders/syslinux_common/splash.png"] = (
        black_canvas(mark, (640, 480), (455, 270), 170)
    )

    # Debian Installer requires these exact filenames. Both variants remain
    # byte-identical because the banner itself uses a black background.
    installer = black_canvas(mark, (800, 75), (112, 65), 37)
    light = (
        ROOT
        / "config/includes.installer/usr/share/graphics/logo_debian.png"
    )
    dark = (
        ROOT
        / "config/includes.installer/usr/share/graphics/logo_debian_dark.png"
    )
    assets[light] = installer
    assets[dark] = installer.copy()
    assets[ROOT / "assets/branding/kythos-installer-banner-source.png"] = (
        installer.resize((1600, 150), Image.Resampling.NEAREST)
    )
    return assets


def write_assets(assets: dict[Path, Image.Image]) -> None:
    for path, image in assets.items():
        if image.mode == "RGBA":
            save_rgba(image, path)
        else:
            save_rgb(image, path)


def check_assets(assets: dict[Path, Image.Image]) -> None:
    errors: list[str] = []
    for path, expected in assets.items():
        if not path.is_file():
            errors.append(f"missing rendered asset: {path}")
            continue
        try:
            with Image.open(path) as actual_file:
                actual = actual_file.copy()
        except OSError as error:
            errors.append(f"cannot decode {path}: {error}")
            continue
        if actual.mode != expected.mode or actual.size != expected.size:
            errors.append(
                f"wrong mode or size for {path}: "
                f"{actual.mode} {actual.size}, expected "
                f"{expected.mode} {expected.size}"
            )
        elif actual.tobytes() != expected.tobytes():
            errors.append(f"rendered pixels differ: {path}")

    if errors:
        raise SystemExit("\n".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify checked-in assets without modifying them",
    )
    arguments = parser.parse_args()
    assets = render_assets()
    if arguments.check:
        check_assets(assets)
    else:
        write_assets(assets)


if __name__ == "__main__":
    main()
