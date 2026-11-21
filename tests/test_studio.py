import copy
import unittest

from app import validate
from render import H, W, scene_frame
from scriptgen import DEMO_SCRIPT


class StudioTests(unittest.TestCase):
    def test_sample_project_and_artwork(self):
        project = validate(copy.deepcopy(DEMO_SCRIPT))
        for index, scene in enumerate(project["scenes"]):
            image = scene_frame(scene, index, "#FF6B3D", .5)
            self.assertEqual(image.size, (W, H))
            self.assertEqual(image.getpixel((10, H - 5)), (255, 107, 61))
            self.assertEqual(image.getpixel((W // 2, H - 125)), (11, 11, 13))

    def test_reject_invalid_render_inputs(self):
        for change in ({"scenes": []}, {"fps": 0}, {"rate": "185"},
                       {"accent": "red"}, {"tts": "unknown"}, {"topic": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **change})
        project = copy.deepcopy(DEMO_SCRIPT)
        project["scenes"][0]["voiceover"] = ""
        with self.assertRaises(ValueError):
            validate(project)


if __name__ == "__main__":
    unittest.main()
