#!/usr/bin/env python3
"""Exercise the real Plymouth script interpreter without display/TTY access.

Set KYTHOS_PLYMOUTH_PLUGIN to Debian's script.so to opt in. This harness uses
its exported interpreter ABI (Plymouth 24.004.60); it checks theme behavior,
not DRM, keyboard switching, real boot timing or a rendered VM framebuffer.
The plugin and libplymouth dependencies must be installed or discoverable
through the normal dynamic loader. Text assertions need plymouth-label.
"""
import ctypes as C
import ctypes.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = os.environ.get("KYTHOS_PLYMOUTH_PLUGIN")
PTR = C.c_void_p


class Result(C.Structure):
    _fields_ = [("type", C.c_int), ("object", PTR)]


@unittest.skipUnless(PLUGIN, "set KYTHOS_PLYMOUTH_PLUGIN for real interpreter tests")
class PlymouthTests(unittest.TestCase):
    def setUp(self):
        self.library = C.CDLL(PLUGIN)
        self.ply = C.CDLL(ctypes.util.find_library("ply") or "libply.so.5")
        self.data = []
        self.operations = []
        self.parse = self.function("script_parse_string", [C.c_char_p, C.c_char_p], PTR)
        self.execute = self.function("script_execute", [PTR, PTR], Result)
        self.number = self.function("script_obj_as_number", [PTR], C.c_double)
        self.state = self.function("script_state_new", [PTR], PTR)(None)
        for name in ("math", "string"):
            self.data.append((name, self.function("script_lib_" + name + "_setup", [PTR], PTR)(self.state)))
        image_dir = ROOT / "config/includes.chroot/usr/share/plymouth/themes/kythos"
        self.data.append(("image", self.function("script_lib_image_setup", [PTR, C.c_char_p], PTR)(
            self.state, os.fsencode(image_dir))))
        new_list = self.ply.ply_list_new
        new_list.argtypes, new_list.restype = [], PTR
        self.displays = new_list()
        self.data.append(("sprite", self.function("script_lib_sprite_setup", [PTR, PTR], PTR)(
            self.state, self.displays)))
        self.data.append(("plymouth", self.function("script_lib_plymouth_setup", [PTR, C.c_int, C.c_int, PTR], PTR)(
            self.state, 0, 30, None)))
        # No actual screens are attached. Only the window dimensions are faked;
        # image loading, text, sprites, math and callbacks use the real plugin.
        self.run_script("Window.GetWidth=fun(){return 1280;}; Window.GetHeight=fun(){return 720;};"
                        "Window.GetX=fun(){return 0;}; Window.GetY=fun(){return 0;};")
        self.run_script((image_dir / "kythos.script").read_text())
        self.run_script("refresh_callback();")

    def function(self, name, args, result):
        function = getattr(self.library, name)
        function.argtypes, function.restype = args, result
        return function

    def run_script(self, source):
        operation = self.parse(source.encode(), b"kythos-runtime-test")
        self.assertTrue(operation, "Plymouth could not parse theme/test input")
        self.operations.append(operation)
        result = self.execute(self.state, operation)
        self.assertNotEqual(result.type, 2, "Plymouth execution failed")
        if result.object:
            value = self.number(result.object)
            self.function("script_obj_unref", [PTR], None)(result.object)
            return value

    def value(self, expression):
        return self.run_script("return " + expression + ";")

    def tearDown(self):
        # Match Plymouth's own stop_script_animation destruction order: state
        # releases native sprite objects before their library classes disappear.
        self.function("script_state_destroy", [PTR], None)(self.state)
        by_name = dict(self.data)
        for name in ("sprite", "image", "plymouth", "math", "string"):
            data = by_name[name]
            self.function("script_lib_" + name + "_destroy", [PTR], None)(data)
        for operation in self.operations:
            self.function("script_parse_op_free", [PTR], None)(operation)
        self.ply.ply_list_free.argtypes = [PTR]
        self.ply.ply_list_free(self.displays)

    def test_real_progress_does_not_regress_and_stale_progress_becomes_activity(self):
        initial_width = self.value("bar.fill.GetImage().GetWidth()")
        self.assertEqual(initial_width, 61)  # Indeterminate segment at 1280px.
        self.run_script("progress_callback(1, 0.4); refresh_callback();")
        self.assertEqual(self.value("animation.progress"), .4)
        self.assertEqual(self.value("bar.fill.GetImage().GetWidth()"), 122)
        self.run_script("progress_callback(2, 0.2);")
        self.assertEqual(self.value("animation.progress"), .4)
        self.run_script("animation.frame += 151; refresh_callback();")
        self.assertEqual(self.value("bar.fill.GetImage().GetWidth()"), initial_width)
        self.assertEqual(self.value("animation.progress"), .4)

    def test_password_and_question_prompts_hide_activity_and_resume(self):
        self.run_script('display_password_callback("Unlock disk", 3); refresh_callback();')
        self.assertEqual(self.value("bar.fill.GetOpacity()"), 0)
        self.assertGreater(self.value("answer.image.GetWidth()"), 5)
        self.run_script('display_question_callback("Confirm", "yes"); refresh_callback();')
        self.assertEqual(self.value("prompt.sprite.GetOpacity()"), 1)
        self.run_script("display_normal_callback(); refresh_callback();")
        self.assertEqual(self.value("bar.fill.GetOpacity()"), 1)
        self.assertEqual(self.value("prompt.sprite.GetOpacity()"), 0)
        self.assertEqual(self.value("answer.sprite.GetOpacity()"), 0)

    def test_wordmark_is_readable_in_lower_right_and_message_lifecycle_works(self):
        self.assertGreater(self.value("wordmark.image.GetWidth()"), 100,
                           "plymouth-label is missing or did not load")
        self.assertGreater(self.value("wordmark.sprite.GetX()"), 1000)
        self.assertGreater(self.value("wordmark.sprite.GetY()"), 630)
        self.run_script('display_message_callback("Checking filesystem");')
        self.assertEqual(self.value("message.sprite.GetOpacity()"), 1)
        self.run_script('hide_message_callback(""); quit_callback();')
        self.assertEqual(self.value("message.sprite.GetOpacity()"), 0)
        self.assertEqual(self.value("bar.background.GetOpacity()"), 0)


if __name__ == "__main__":
    unittest.main()
