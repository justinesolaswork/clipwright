from array import array
import copy
import math
from pathlib import Path
import tempfile
import unittest
import wave

from PIL import Image, ImageChops

from app import validate
from media import _is_safe_public_url, _score_candidate, asset_path, avatar_path, build_query, save_uploaded_avatar, save_uploaded_image
import music
from render import audio_levels, compose_frame, draw_mascot, full_caption, prepare_scene
from scriptgen import DEMO_SCRIPT, _fit_headline, _merge_revised_scenes, _stream_completion, _target_plan, clean, detect_vibe, direct_style, estimate_duration, format_research


class AnimationTests(unittest.TestCase):
    def test_mouth_follows_audio_and_closes_in_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "voice.wav"
            samples = array("h", [0] * 2400 +
                            [int(12000 * math.sin(i * 2 * math.pi * 220 / 24000)) for i in range(2400)] +
                            [0] * 2400)
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(samples.tobytes())
            levels = audio_levels(path, 30)
            self.assertEqual(levels[:3], [0, 0, 0])
            self.assertGreater(min(levels[3:6]), .9)
            self.assertEqual(levels[6:], [0, 0, 0])

    def test_motion_and_avatar_controls_change_artwork(self):
        scene = DEMO_SCRIPT["scenes"][0]
        prepared = prepare_scene(scene, 0, "#FF6B3D", {"motion": "lively"})
        a, b = compose_frame(prepared, 1, 4), compose_frame(prepared, 2, 4, mouth=.9)
        self.assertIsNotNone(ImageChops.difference(a, b).getbbox())
        still = prepare_scene(scene, 0, "#FF6B3D", {"motion": "none"})
        self.assertIsNone(ImageChops.difference(compose_frame(still, 1, 4), compose_frame(still, 2, 4)).getbbox())
        a = draw_mascot("smile", (255, 107, 61), 240).convert("RGB")
        b = draw_mascot("smile", (255, 107, 61), 240, mouth=8, color="#44AAFF", style="cat", accessory="glasses").convert("RGB")
        self.assertIsNotNone(ImageChops.difference(a, b).getbbox())

    def test_reject_bad_assets_and_look_settings(self):
        with self.assertRaises(ValueError):
            asset_path("../../main.py")
        for bad in ({"avatar_size": 900}, {"avatar_color": "red"}, {"talking": "yes"}, {"motion": "wild"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})

    def test_image_search_helpers_and_upload(self):
        self.assertTrue(_is_safe_public_url("https://example.com/photo.jpg"))
        for bad in ("http://example.com/a.jpg", "https://localhost/a.jpg", "https://127.0.0.1/a.jpg", "https://192.168.1.5/a.jpg"):
            self.assertFalse(_is_safe_public_url(bad))
        good = _score_candidate("Claude Mythos AI", "Anthropic Claude Mythos AI benchmark", 1280, 720, "tech.co")
        bad = _score_candidate("Claude Mythos AI", "Claude Debussy 1908 portrait", 800, 1000, "wikimedia.org")
        self.assertGreater(good, bad)
        query = build_query("how good is claude mythos", {"line1": "TRY IT NOW", "line2": "UPGRADE TODAY", "voiceover": "Upgrade your coding workflow."})
        self.assertIn("claude", query.lower())
        self.assertIn("mythos", query.lower())
        import io
        buf = io.BytesIO()
        Image.new("RGB", (320, 320), (40, 120, 200)).save(buf, format="PNG")
        asset_id = save_uploaded_image(buf.getvalue(), "custom.png")
        self.assertTrue(asset_path(asset_id).is_file())
        asset_path(asset_id).unlink(missing_ok=True)
        asset_path(asset_id).with_suffix(".json").unlink(missing_ok=True)

    def test_revise_validation_and_scene_merge(self):
        project = copy.deepcopy(DEMO_SCRIPT)
        valid = validate({**project, "instruction": "make it 30 seconds", "revise_scope": "all",
                          "selected_index": 0, "chat_history": [{"role": "user", "text": "more trendy"}]})
        self.assertEqual(valid["instruction"], "make it 30 seconds")
        for bad in ({"instruction": ""}, {"revise_scope": "invalid"}, {"selected_index": 9},
                    {"chat_history": [{"role": "system", "text": "hi"}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})
        old = [
            {"line1": "A", "line2": "B", "voiceover": "One two three.", "pose": "happy",
             "image_query": "laptop computer", "image": "a" * 24},
            {"line1": "C", "line2": "D", "voiceover": "Four five six.", "pose": "smile",
             "image_query": "code editor", "image": "b" * 24},
        ]
        # Preserves image when query stays the same, drops when query changes
        new_all = [
            {"line1": "A2", "line2": "B2", "voiceover": "Updated.", "pose": "happy", "image_query": "laptop computer"},
            {"line1": "C2", "line2": "D2", "voiceover": "Changed topic.", "pose": "flat", "image_query": "rocket launch"},
        ]
        merged = _merge_revised_scenes(old, new_all)
        self.assertEqual(merged[0].get("image"), "a" * 24)
        self.assertNotIn("image", merged[1])
        # Single-scene revision only replaces the target scene
        single = _merge_revised_scenes(old, [{"line1": "NEW", "line2": "HOOK", "voiceover": "Better.", "pose": "surprised", "image_query": "laptop computer"}], target_index=0)
        self.assertEqual(single[0]["line1"], "NEW")
        self.assertEqual(single[0].get("image"), "a" * 24)
        self.assertEqual(single[1]["line1"], "C")
        self.assertGreater(estimate_duration(DEMO_SCRIPT["scenes"], 185), 5)
        self.assertEqual(_target_plan("make it longer as 30 seconds video", 4, 185), (30, 6, 14))
        self.assertEqual(_target_plan("make it more trendy", 4, 185), (None, None, None))
        validate({**copy.deepcopy(DEMO_SCRIPT), "web_search": True})
        with self.assertRaises(ValueError):
            validate({**copy.deepcopy(DEMO_SCRIPT), "web_search": "yes"})
        notes = format_research([{"title": "Claude Mythos", "snippet": "Fast coding model.", "url": "https://example.com"}])
        self.assertIn("Claude Mythos", notes)
        self.assertIn("Fast coding model.", notes)
        self.assertEqual(_fit_headline("INFORMED ALLOCATION"), "INFORMED ALLOCATION")
        self.assertEqual(_fit_headline("TRANSFORM LEARNING"), "TRANSFORM LEARNING")
        self.assertEqual(_fit_headline("THIS HEADLINE IS WAY TOO LONG TO FIT"), "THIS HEADLINE IS WAY TOO")
        self.assertEqual(_fit_headline("AUGMENTATION NOT"), "AUGMENTATION")
        dedup = clean({
            "scenes": [
                {"line1": "AI TAKES OVER", "line2": "JOBS AT RISK", "voiceover": "AI is changing work.", "pose": "flat",
                 "image_query": "robot in office, AI assistant, automation"},
                {"line1": "AI TAKES OVER", "line2": "JOBS AT RISK", "voiceover": "AI is changing work.", "pose": "flat",
                 "image_query": "robot in office"},
                {"line1": "HUMAN PLUS AI", "line2": "BETTER TOGETHER", "voiceover": "Humans and AI work together.", "pose": "happy",
                 "image_query": "robot in office"},
            ]
        }, "ai replace human")
        self.assertEqual(len(dedup["scenes"]), 2)
        self.assertEqual(dedup["scenes"][0]["image_query"], "robot in office")
        self.assertNotEqual(dedup["scenes"][0]["image_query"], dedup["scenes"][1]["image_query"])
        validate({**copy.deepcopy(DEMO_SCRIPT), "tts": "edge", "voice": "en-US-BrianNeural"})
        validate({**copy.deepcopy(DEMO_SCRIPT), "download_model_key": "llama3.1-8b"})
        with self.assertRaises(ValueError):
            validate({**copy.deepcopy(DEMO_SCRIPT), "download_model_key": "nonexistent-model"})
        many = {"scenes": [{"line1": f"S{i}", "line2": "TEST", "voiceover": f"Line {i}.", "pose": "smile"} for i in range(15)]}
        self.assertEqual(len(clean(many, "test")["scenes"]), 12)

    def test_avatar_builder_options_and_custom_avatar(self):
        base = draw_mascot("smile", (255, 107, 61), 240).convert("RGB")
        variants = [
            {"style": "bunny", "accessory": "crown", "eyes": "star", "antenna": "bolt", "cheeks": True},
            {"style": "bear", "accessory": "party", "eyes": "happy", "antenna": "none", "body_color": "#2244AA"},
            {"style": "cat", "accessory": "sunglasses", "eyes": "wink", "antenna": "double"},
            {"style": "square", "accessory": "cap", "eyes": "sleepy"},
            {"style": "round", "accessory": "bowtie", "eyes": "wide", "mouth": 6},
        ]
        for kwargs in variants:
            with self.subTest(kwargs=kwargs):
                img = draw_mascot("smile", (255, 107, 61), 240, **kwargs).convert("RGB")
                self.assertIsNotNone(ImageChops.difference(base, img).getbbox())
        validate({**copy.deepcopy(DEMO_SCRIPT), "avatar_style": "bunny", "avatar_accessory": "crown", "avatar_eyes": "star",
                  "avatar_antenna": "bolt", "avatar_position": "left", "avatar_cheeks": True, "avatar_body_follow": False,
                  "avatar_body_color": "#112233"})
        for bad in ({"avatar_eyes": "laser"}, {"avatar_antenna": "horn"}, {"avatar_position": "top"},
                    {"avatar_body_color": "blue"}, {"avatar_cheeks": "yes"}, {"avatar_image": "../x"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})
        import io
        buf = io.BytesIO()
        art = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        art.paste(Image.new("RGBA", (100, 120), (240, 60, 60, 255)), (50, 40))
        art.save(buf, format="PNG")
        avatar_id = save_uploaded_avatar(buf.getvalue())
        try:
            self.assertTrue(avatar_path(avatar_id).is_file())
            with Image.open(avatar_path(avatar_id)) as saved:
                self.assertEqual(saved.size, (100, 120))
            look = {"avatar_image": avatar_id, "motion": "lively"}
            validate({**copy.deepcopy(DEMO_SCRIPT), **look})
            prepared = prepare_scene(DEMO_SCRIPT["scenes"][0], 0, "#FF6B3D", look)
            plain = prepare_scene(DEMO_SCRIPT["scenes"][0], 0, "#FF6B3D", {"motion": "lively"})
            self.assertIsNotNone(ImageChops.difference(compose_frame(prepared, 1, 3), compose_frame(plain, 1, 3)).getbbox())
        finally:
            avatar_path(avatar_id).unlink(missing_ok=True)

    def test_themes_text_animations_captions_and_transitions(self):
        scene = DEMO_SCRIPT["scenes"][0]
        base = prepare_scene(scene, 0, "#FF6B3D", {"theme": "dark", "bg_effect": "orbs", "text_anim": "slide", "caption_style": "box", "motion": "lively"})
        base_img = compose_frame(base, 0.25, 3.0, mouth=0.6, progress=0.2)
        for look in (
            {"theme": "neon", "bg_effect": "grid", "text_anim": "pop", "caption_style": "karaoke", "motion": "hyper"},
            {"theme": "minimal", "bg_effect": "confetti", "text_anim": "split", "caption_style": "bold", "motion": "lively"},
            {"theme": "sunset", "bg_effect": "waves", "text_anim": "typewriter", "caption_style": "minimal", "motion": "lively"},
            {"theme": "retro", "bg_effect": "orbs", "text_anim": "glitch", "caption_style": "karaoke", "motion": "lively"},
            {"theme": "midnight", "bg_effect": "waves", "text_anim": "zoom", "caption_style": "bold", "motion": "lively"},
        ):
            with self.subTest(look=look):
                validate({**copy.deepcopy(DEMO_SCRIPT), **look, "transition": "slide_left"})
                p = prepare_scene(scene, 0, "#FF6B3D", look)
                img = compose_frame(p, 0.25, 3.0, mouth=0.6, progress=0.2)
                self.assertIsNotNone(ImageChops.difference(base_img, img).getbbox())
        for bad in ({"theme": "unknown"}, {"font_style": "wingdings"}, {"bg_effect": "fire"},
                    {"text_anim": "spin"}, {"caption_style": "comic"}, {"caption_anim": "explode"}, {"transition": "wipe"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})
        for font_style, caption_anim in (("modern", "pop"), ("tech", "bounce"), ("editorial", "glow"), ("playful", "reveal"), ("clean", "slide_up")):
            with self.subTest(font_style=font_style, caption_anim=caption_anim):
                look = {"font_style": font_style, "caption_anim": caption_anim, "caption_style": "bold", "motion": "lively"}
                validate({**copy.deepcopy(DEMO_SCRIPT), **look})
                p = prepare_scene(scene, 0, "#FF6B3D", look)
                img = compose_frame(p, 0.4, 3.0, mouth=0.5, progress=0.2)
                self.assertIsNotNone(ImageChops.difference(base_img, img).getbbox())

    def test_music_library_and_mixing(self):
        tracks = music.catalog_list()
        self.assertGreaterEqual(len(tracks), 30)
        validate({**copy.deepcopy(DEMO_SCRIPT), "bgm": "synth_lofi", "bgm_volume": 20})
        for bad in ({"bgm": "unknown_song"}, {"bgm_volume": 99}, {"bgm_volume": -5}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})
        wav_path = music.ensure_track("synth_lofi")
        self.assertTrue(wav_path and wav_path.is_file())
        with tempfile.TemporaryDirectory() as folder:
            voice = Path(folder) / "voice.wav"
            samples = array("h", [0] * 44100)
            with wave.open(str(voice), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(samples.tobytes())
            mixed = music.mix_bgm(voice, "synth_lofi", 25, Path(folder) / "mix.wav")
            self.assertTrue(mixed.is_file() and mixed.stat().st_size > 40000)
        self.assertIn("Kevin MacLeod", music.bgm_credit("km_carefree"))

    def test_content_aware_director_and_live_token_stream(self):
        self.assertEqual(detect_vibe("Why AI coding agents break python tests", DEMO_SCRIPT["scenes"]), "tech")
        self.assertEqual(detect_vibe("Haunted ghost mystery in the dark", [{"line1": "DARK", "line2": "GHOST", "voiceover": "A scary horror story."}]), "spooky")
        self.assertEqual(detect_vibe("Calm morning study lofi session", [{"line1": "CALM", "line2": "MIND", "voiceover": "Relax and breathe."}]), "chill")
        self.assertEqual(detect_vibe("Funny cat meme compilation", [{"line1": "CUTE", "line2": "CAT", "voiceover": "Funny joke and party."}]), "playful")
        style = direct_style("Why AI coding agents break tests", DEMO_SCRIPT["scenes"], "kokoro")
        self.assertEqual(style["vibe"], "tech")
        val_props = {k: v for k, v in style.items() if k not in ("vibe", "vibe_label")}
        validate({**copy.deepcopy(DEMO_SCRIPT), **val_props})

        class FakeLLM:
            def tokenize(self, data: bytes):
                return list(range(25))

            def create_chat_completion(self, **kwargs):
                for part in ('{"scenes":[{"line1":"COOK",', '"line2":"NOW","voiceover":"Let him cook.",', '"pose":"happy","image_query":"chef cooking"}]}'):
                    yield {"choices": [{"delta": {"content": part}}]}

        text, stats = _stream_completion(FakeLLM(), [{"role": "user", "content": "hi"}], {}, 200, "🔥 Cooking")
        self.assertIn("Let him cook.", text)
        self.assertEqual(stats["output_tokens"], 3)
        self.assertEqual(stats["prompt_tokens"], 29)
        self.assertEqual(stats["total_tokens"], 32)
        long_vo = "Experience the magical world of Girly Ghost Town, a unique location in GTA 6 with its own storyline and gameplay mechanics."
        for style in ("bold", "box", "minimal", "karaoke"):
            cap_start = full_caption(long_vo, 2, (236, 72, 153), style=style, anim="pop", beat=0.5)
            cap_mid = full_caption(long_vo, 8, (236, 72, 153), style=style, anim="pop", beat=0.5)
            self.assertLessEqual(cap_start.height, 210)
            self.assertLessEqual(cap_mid.height, 210)
            self.assertNotEqual(cap_start.tobytes(), cap_mid.tobytes())
        validate({**copy.deepcopy(DEMO_SCRIPT), "render_quality": "fast"})
        with self.assertRaises(ValueError):
            validate({**copy.deepcopy(DEMO_SCRIPT), "render_quality": "4k"})
        base_m = draw_mascot("smile", (255, 107, 61), 240).convert("RGB")
        for pose in ("excited", "shocked", "angry", "sad", "crying", "thinking", "smirk", "laugh", "wink", "love", "confused", "mindblown"):
            with self.subTest(pose=pose):
                m_img = draw_mascot(pose, (255, 107, 61), 240).convert("RGB")
                self.assertIsNotNone(ImageChops.difference(base_m, m_img).getbbox())
        validate({
            **copy.deepcopy(DEMO_SCRIPT),
            "avatar_position": "alternate",
            "avatar_move": "walk_in",
            "camera_style": "cinema_push",
        })
        for bad in ({"avatar_move": "teleport"}, {"camera_style": "drone"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate({**copy.deepcopy(DEMO_SCRIPT), **bad})
