#!/usr/bin/env python3
"""Verify vector geometry/provenance and generated framebuffer artwork."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageStat

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("branding_renderer", ROOT / "scripts/render-branding.py")
branding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branding)
SVG = "{http://www.w3.org/2000/svg}"


class ArtworkTests(unittest.TestCase):
    def test_generated_assets_match_source_and_renderer(self):
        branding.check_assets(branding.render_assets())

    def test_white_mark_has_only_white_visible_pixels(self):
        mark = branding.load_mark()
        pixels = mark.tobytes()
        for offset in range(0, len(pixels), 4):
            red, green, blue, alpha = pixels[offset:offset + 4]
            if alpha:
                self.assertEqual((red, green, blue), (255, 255, 255))
        self.assertGreater(mark.getbbox()[2], 500)

    def test_original_hand_geometry_is_retained_in_vector_trace(self):
        # Render the inner monogram back in the ORIGINAL source coordinates,
        # ignoring only its uniform placement/size and the enclosing shield.
        import os
        import shutil
        document = ET.fromstring(branding.SOURCE.read_bytes())
        document.set("width", "1672")
        document.set("height", "941")
        document.set("viewBox", "0 0 1672 941")
        document.remove(document.find(SVG + "path"))
        group = document.find(SVG + "g")
        del group.attrib["transform"]
        renderer = os.environ.get("KYTHOS_RSVG_CONVERT") or shutil.which("rsvg-convert")
        output = subprocess.run([renderer], input=ET.tostring(document),
                                capture_output=True, timeout=10, check=True).stdout
        traced = Image.open(io.BytesIO(output)).convert("RGBA").getchannel("A").point(
            lambda value: 255 if value > 127 else 0)
        original = Image.open(branding.ORIGINAL_SOURCE).convert("RGBA")
        # This is the documented opaque-core threshold, excluding old glow.
        masks = [original.getchannel(channel).point(lambda v, t=threshold: 255 if v > t else 0)
                 for channel, threshold in (("A", 242.25), ("G", 229.5), ("B", 242.25))]
        expected = ImageChops.darker(ImageChops.darker(masks[0], masks[1]), masks[2])
        common = ImageStat.Stat(ImageChops.darker(expected, traced)).sum[0]
        combined = ImageStat.Stat(ImageChops.lighter(expected, traced)).sum[0]
        self.assertGreater(common / combined, .995,
                           "original hand angles, proportions or loop changed")

    def test_monogram_is_wholly_inside_shield(self):
        # The enclosed, filled shield must contain every monogram pixel.
        import os
        import shutil
        document = ET.fromstring(branding.SOURCE.read_bytes())
        shield = document.find(SVG + "path")
        shield.set("fill", "#ffffff")
        shield.set("stroke", "none")
        monogram = document.find(SVG + "g")
        document.remove(monogram)
        renderer = os.environ.get("KYTHOS_RSVG_CONVERT") or shutil.which("rsvg-convert")
        def mask(source):
            output = subprocess.run([renderer], input=ET.tostring(source),
                                    capture_output=True, timeout=10, check=True).stdout
            return Image.open(io.BytesIO(output)).convert("RGBA").getchannel("A")
        interior = mask(document)
        document.remove(shield)
        document.append(monogram)
        self.assertIsNone(ImageChops.subtract(mask(document), interior).getbbox())

    def test_wordmark_is_small_and_lower_right(self):
        canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
        branding.add_wordmark(canvas)
        x0, y0, x1, y1 = canvas.convert("RGB").getbbox()
        self.assertGreater(x0, 950)
        self.assertGreater(y0, 630)
        self.assertLess(x1, 1260)
        self.assertLess(y1, 700)
        self.assertEqual(branding.PRODUCT, "KythOS Kernal™ 2027")
        self.assertEqual(branding.URL, "https://kythos.ai")

    def test_installer_variants_are_identical_and_calamares_uses_vector(self):
        light = ROOT / "config/includes.installer/usr/share/graphics/logo_debian.png"
        self.assertEqual(light.read_bytes(), light.with_name("logo_debian_dark.png").read_bytes())
        self.assertIn("productLogo: kythos-logo.svg", (branding.CALAMARES / "branding.desc").read_text())


if __name__ == "__main__":
    unittest.main()
