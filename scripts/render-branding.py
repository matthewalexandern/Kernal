#!/usr/bin/env python3
"""Render or verify white KythOS artwork from its scalable canonical SVG.

librsvg handles SVG rasterization; Pillow places the same artwork and small
wordmark on the framebuffer sizes required by GRUB, Syslinux and d-i.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/branding/kythos-mark-white.svg"
ORIGINAL_SOURCE = ROOT / "assets/branding/kythos-mark-cyan-source.png"
ORIGINAL_SOURCE_SHA256 = (
    "0bf8e10c25b3880d43adcb997474ae2e1cf6d5fd6fb638ce3c4316efb95a6157"
)
PRODUCT = "KythOS Kernal™ 2027"
URL = "https://kythos.ai"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
CALAMARES = ROOT / "config/includes.chroot/etc/calamares/branding/kythos"
THEME_DIR = (
    ROOT
    / "config/includes.chroot/usr/share/plymouth/themes/kythos"
)


def load_mark() -> Image.Image:
    source_hash = hashlib.sha256(ORIGINAL_SOURCE.read_bytes()).hexdigest()
    if source_hash != ORIGINAL_SOURCE_SHA256:
        raise SystemExit(
            f"original monogram provenance mismatch: {source_hash}"
        )
    # Keep the master genuinely scalable and self-contained. Do not silently
    # accept a bitmap embedded in an SVG wrapper or external resource loads.
    document = ET.fromstring(SOURCE.read_bytes())
    forbidden = {"image", "script", "foreignObject", "text"}
    for element in document.iter():
        if element.tag.rsplit("}", 1)[-1] in forbidden:
            raise SystemExit("canonical mark must contain only vector artwork")
        if any("href" in key for key in element.attrib):
            raise SystemExit("canonical mark must not load external resources")
    renderer = os.environ.get("KYTHOS_RSVG_CONVERT") or shutil.which("rsvg-convert")
    if not renderer:
        raise SystemExit("Install librsvg2-bin to render or check branding.")
    output = subprocess.run(
        [renderer, "--width", "1280", "--height", "1440", str(SOURCE)],
        capture_output=True, check=True, timeout=20,
    ).stdout
    with Image.open(io.BytesIO(output)) as source_image:
        mark = source_image.convert("RGBA")
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
    wordmark: bool = True,
) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    placed = resized(mark, *mark_box)
    x = (size[0] - placed.width) // 2
    y = center_y - placed.height // 2
    canvas.alpha_composite(placed, (x, y))
    if wordmark:
        add_wordmark(canvas)
    return canvas.convert("RGB")


def add_wordmark(canvas: Image.Image) -> None:
    """Small lower-right text, separate from the symbol and menu region."""
    draw = ImageDraw.Draw(canvas)
    size = max(10, round(canvas.width / 80))
    font = ImageFont.truetype(FONT, size)
    margin = max(12, round(canvas.width * .025))
    bottom = canvas.height - margin
    for line in (URL, PRODUCT):
        draw.text((canvas.width - margin, bottom), line, fill="white",
                  font=font, anchor="rs")
        bottom -= round(size * 1.5)


def save_rgb(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="PNG", optimize=True)
    path.chmod(0o644)


def save_rgba(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, format="PNG", optimize=True)
    path.chmod(0o644)


def render_assets() -> dict[Path, Image.Image]:
    mark = load_mark()
    assets: dict[Path, Image.Image] = {}

    animation_logo = resized(mark, 640, 720)
    assets[THEME_DIR / "kythos-logo.png"] = animation_logo
    assets[THEME_DIR / "progress-track.png"] = Image.new("RGB", (1, 1), "#2e2e2e")
    assets[THEME_DIR / "progress-fill.png"] = Image.new("RGB", (1, 1), "white")
    assets[CALAMARES / "kythos-logo.png"] = resized(mark, 320, 360)

    # Full-screen static frame used by installed GRUB and as the animation's
    # visual fallback. Product text is deliberately small and lower-right.
    installed = black_canvas(mark, (1280, 720), (360, 405), 330)
    assets[THEME_DIR / "kythos-background.png"] = installed
    assets[ROOT / "assets/branding/kythos-boot-source.png"] = (
        installed.resize((1672, 941), Image.Resampling.LANCZOS)
    )

    # Menus use the lower fifth; the small wordmark sits below their entries.
    assets[ROOT / "config/bootloaders/grub-pc/splash.png"] = black_canvas(
        mark, (800, 600), (250, 285), 230
    )

    # Syslinux uses a lower-resolution 4:3 framebuffer.
    assets[ROOT / "config/bootloaders/syslinux_common/splash.png"] = (
        black_canvas(mark, (640, 480), (145, 160), 105)
    )

    # Debian Installer requires these exact filenames. Both variants remain
    # byte-identical because the banner itself uses a black background.
    installer = Image.new("RGB", (800, 75), "black")
    symbol = resized(mark, 56, 63)
    installer.paste(symbol, (20, 6), symbol)
    draw = ImageDraw.Draw(installer)
    draw.text((92, 20), PRODUCT, fill="white", font=ImageFont.truetype(FONT, 16))
    draw.text((92, 44), URL, fill="white", font=ImageFont.truetype(FONT, 12))
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
    (CALAMARES / "kythos-logo.svg").write_bytes(SOURCE.read_bytes())
    (CALAMARES / "kythos-logo.svg").chmod(0o644)
    for path, image in assets.items():
        if image.mode == "RGBA":
            save_rgba(image, path)
        else:
            save_rgb(image, path)


def check_assets(assets: dict[Path, Image.Image]) -> None:
    errors: list[str] = []
    if not (CALAMARES / "kythos-logo.svg").is_file() or (
        CALAMARES / "kythos-logo.svg"
    ).read_bytes() != SOURCE.read_bytes():
        errors.append("Calamares vector logo differs from canonical source")
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
