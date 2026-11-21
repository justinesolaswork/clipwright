from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import tts


class KokoroTests(unittest.TestCase):
    def test_voice_language_speed_and_pcm_output(self):
        engine = Mock()
        engine.create.return_value = ([0.0, 0.1], 24000)
        factory, write = Mock(return_value=engine), Mock()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
                (root / name).touch()
            with patch.object(tts, "KOKORO_DIR", root), patch.dict("sys.modules", {
                "kokoro_onnx": SimpleNamespace(Kokoro=factory),
                "soundfile": SimpleNamespace(write=write),
            }):
                tts._speak_kokoro(["Hello", "Again"], [root / "1.wav", root / "2.wav"], "bf_emma", 185)
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(engine.create.call_args.kwargs, {"voice": "bf_emma", "speed": 1.0, "lang": "en-gb"})
                self.assertEqual(write.call_count, 2)
                self.assertEqual(write.call_args.kwargs["subtype"], "PCM_16")
                tts._speak_kokoro(["Hello"], [root / "3.wav"], None, 148)
                self.assertEqual(engine.create.call_args.kwargs, {"voice": "af_heart", "speed": .8, "lang": "en-us"})
                with self.assertRaisesRegex(ValueError, "Choose a Kokoro voice"):
                    tts._speak_kokoro(["Hello"], [root / "4.wav"], "Windows voice", 185)
