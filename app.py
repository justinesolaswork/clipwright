"""Local Clipwright studio. Run with: python app.py"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import re
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from scriptgen import DEMO_SCRIPT, POSES

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "work" / "studio"
TONES = {"Calm": 155, "Hyped": 185, "Deadpan": 165}
jobs: dict[str, dict] = {}
lock = threading.Lock()


def validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Expected a project object.")
    topic = data.get("topic", "")
    scenes = data.get("scenes")
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 2000:
        raise ValueError("Enter a topic or notes (up to 2,000 characters).")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 12:
        raise ValueError("A project needs 1–12 scenes.")
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Invalid scene.")
        for key, limit in (("line1", 24), ("line2", 24), ("voiceover", 350)):
            value = scene.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Each scene needs {key} (1–{limit} characters).")
        if scene.get("pose") not in POSES:
            raise ValueError("Choose a valid mascot expression.")
        if not isinstance(scene.get("image_query", ""), str) or len(scene.get("image_query", "")) > 160:
            raise ValueError("Image keywords must be at most 160 characters.")
        if scene.get("image"):
            from media import asset_path
            asset_path(scene["image"])
    accent = data.get("accent", "#FF6B3D")
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        raise ValueError("Invalid accent colour.")
    if data.get("tts", "pyttsx3") not in ("pyttsx3", "kokoro", "edge", "silent"):
        raise ValueError("Unknown voice engine.")
    if data.get("tone", "Hyped") not in TONES:
        raise ValueError("Unknown tone.")
    for key, default, low, high in (("rate", 185, 100, 260), ("fps", 30, 12, 60),
                                   ("gpu_layers", 0, 0, 100), ("n_ctx", 4096, 1024, 16384),
                                   ("bgm_volume", 18, 0, 80), ("target_scenes", 6, 3, 12)):
        value = data.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
    for key in ("voice", "model"):
        if not isinstance(data.get(key, ""), str) or len(data.get(key, "")) > 500:
            raise ValueError(f"Invalid {key}.")
    for key, values, default in (
        ("motion", ("none", "gentle", "lively", "hyper"), "lively"),
        ("theme", ("dark", "neon", "sunset", "midnight", "minimal", "retro"), "dark"),
        ("font_style", ("impact", "modern", "tech", "editorial", "playful", "clean"), "impact"),
        ("bg_effect", ("orbs", "grid", "confetti", "waves", "none"), "orbs"),
        ("text_anim", ("slide", "pop", "split", "zoom", "glitch", "typewriter"), "slide"),
        ("caption_style", ("box", "karaoke", "bold", "minimal"), "box"),
        ("caption_anim", ("highlight", "pop", "bounce", "glow", "reveal", "slide_up"), "highlight"),
        ("transition", ("fade", "slide_left", "slide_up", "zoom_in", "flash", "none"), "fade"),
        ("avatar_style", ("round", "square", "cat", "bunny", "bear", "none"), "round"),
        ("avatar_accessory", ("none", "glasses", "sunglasses", "headphones", "crown", "party", "cap", "bowtie"), "none"),
        ("avatar_eyes", ("round", "wide", "happy", "sleepy", "star", "wink"), "round"),
        ("avatar_antenna", ("ball", "double", "bolt", "none"), "ball"),
        ("avatar_position", ("auto", "alternate", "roam", "left", "center", "right", "mid_left", "mid_right", "top_left", "top_right"), "auto"),
        ("avatar_move", ("bounce", "walk_in", "pace", "float", "jump", "peek"), "bounce"),
        ("camera_style", ("ken_burns", "cinema_push", "handheld", "dynamic_tilt", "spotlight", "static"), "ken_burns"),
        ("render_quality", ("fast", "hd", "draft"), "hd"),
    ):
        if data.get(key, default) not in values:
            raise ValueError(f"Invalid {key}.")
    color = data.get("avatar_color", "#F4F1EA")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Invalid avatar colour.")
    size = data.get("avatar_size", 100)
    if type(size) is not int or not 70 <= size <= 130:
        raise ValueError("Avatar size must be between 70 and 130.")
    for key in ("talking", "auto_images", "web_search", "avatar_cheeks", "avatar_body_follow"):
        if type(data.get(key, True)) is not bool:
            raise ValueError(f"Invalid {key}.")
    body_color = data.get("avatar_body_color", "#FF6B3D")
    if not isinstance(body_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", body_color):
        raise ValueError("Invalid avatar body colour.")
    if data.get("avatar_image"):
        from media import avatar_path
        avatar_path(data["avatar_image"])
    for key in ("image_target", "scene_offset", "selected_index"):
        if key in data and (type(data[key]) is not int or not 0 <= data[key] < 12):
            raise ValueError("Invalid scene index.")
    if "image_target" in data and data["image_target"] >= len(scenes):
        raise ValueError("Image search scene does not exist.")
    if "selected_index" in data and data["selected_index"] >= len(scenes):
        raise ValueError("Selected scene does not exist.")
    if "revise_scope" in data and data["revise_scope"] not in ("all", "selected"):
        raise ValueError("Invalid revision scope.")
    if "instruction" in data:
        inst = data["instruction"]
        if not isinstance(inst, str) or not 1 <= len(inst.strip()) <= 1000:
            raise ValueError("Enter an edit instruction (1–1,000 characters).")
    if "chat_history" in data:
        hist = data["chat_history"]
        if not isinstance(hist, list) or len(hist) > 12:
            raise ValueError("Invalid chat history.")
        for item in hist:
            if (not isinstance(item, dict) or item.get("role") not in ("user", "assistant")
                    or not isinstance(item.get("text"), str) or len(item["text"]) > 600):
                raise ValueError("Invalid chat history entry.")
    if "bgm" in data:
        from music import valid_track_id
        if not isinstance(data["bgm"], str) or not valid_track_id(data["bgm"]):
            raise ValueError("Choose a valid background music track.")
    if "download_model_key" in data:
        from download_model import CATALOG
        if data["download_model_key"] not in CATALOG:
            raise ValueError("Unknown downloadable model.")
    return data


def worker(folder: Path) -> None:
    data = validate(json.loads((folder / "request.json").read_text(encoding="utf-8")))
    action = data["action"]
    if action == "generate":
        from scriptgen import generate_script
        model = Path(data.get("model", ""))
        if model.suffix.lower() != ".gguf" or not model.is_file():
            raise ValueError("Choose an existing .gguf model in Settings to generate scripts.")
        print("STATUS:Loading your local AI model...", flush=True)
        n_scenes = data.get("target_scenes", 6)
        script = generate_script(
            f'{data["topic"]}\nVoiceover tone: {data.get("tone", "Hyped")}.',
            str(model), n_scenes, data.get("gpu_layers", 0), data.get("n_ctx", 4096),
            web_search=data.get("web_search", True), tts_engine=data.get("tts", "kokoro"))
        script["topic"] = data["topic"]
        validate({**data, **script})
        if data.get("auto_images", True):
            from media import collect_images
            script["media_notes"] = collect_images(script)
        (folder / "result.json").write_text(json.dumps(script), encoding="utf-8")
        return
    if action == "revise":
        from scriptgen import revise_script
        model = Path(data.get("model", ""))
        if model.suffix.lower() != ".gguf" or not model.is_file():
            raise ValueError("Choose an existing .gguf model in Settings to edit scripts with AI.")
        instruction = str(data.get("instruction", "")).strip()
        if not instruction:
            raise ValueError("Enter an edit instruction.")
        print("STATUS:Loading your local AI model...", flush=True)
        target_index = data.get("selected_index", 0) if data.get("revise_scope") == "selected" else None
        script = revise_script(
            data["topic"],
            data["scenes"],
            instruction,
            str(model),
            rate=data.get("rate", 185),
            tone=data.get("tone", "Hyped"),
            history=data.get("chat_history"),
            target_index=target_index,
            n_gpu_layers=data.get("gpu_layers", 0),
            n_ctx=data.get("n_ctx", 4096),
            web_search=data.get("web_search", True),
        )
        validate({**data, **script})
        if data.get("auto_images", True):
            from media import collect_images
            script["media_notes"] = collect_images(script)
        (folder / "result.json").write_text(json.dumps(script), encoding="utf-8")
        return
    if action == "download_model":
        from download_model import catalog_status, download
        path = download(data["download_model_key"])
        (folder / "result.json").write_text(
            json.dumps({"model": str(path), "models": [str(p) for p in (ROOT / "models").glob("*.gguf") if not re.search(r"-0000[2-9]-of-", p.name)], "model_catalog": catalog_status()}),
            encoding="utf-8",
        )
        return
    if action == "images":
        from media import collect_images
        script = {"topic": data["topic"], "scenes": data["scenes"]}
        script["media_notes"] = collect_images(script, data.get("image_target"))
        (folder / "result.json").write_text(json.dumps(script), encoding="utf-8")
        return
    import tts
    from render import render_video
    print("STATUS:Making voiceover...", flush=True)
    paths = tts.synth_all([s["voiceover"] for s in data["scenes"]], folder / "audio",
                          data.get("tts", "pyttsx3"), data.get("voice") or None,
                          data.get("rate", 185))
    audio, durations = tts.assemble(paths, folder / "audio")
    bgm_id = data.get("bgm", "none")
    bgm_vol = data.get("bgm_volume", 18)
    if bgm_id != "none" and bgm_vol > 0:
        import music
        mixed = music.mix_bgm(audio, bgm_id, bgm_vol, folder / "audio" / "mix.wav")
        if action == "audio":
            audio = mixed
    if action in ("render", "motion"):
        print("STATUS:Rendering video...", flush=True)
        render_video(data["scenes"], durations, audio, folder / "video.mp4",
                     data.get("accent", "#FF6B3D"), 24 if action == "motion" else data.get("fps", 30),
                     data, action == "motion", data.get("scene_offset", 0))
        from media import credits
        import music
        credit_text = credits(data["scenes"])
        extra = music.bgm_credit(bgm_id) if bgm_vol > 0 else ""
        if extra:
            credit_text = credit_text.rstrip() + "\n\n" + extra
        (folder / "credits.txt").write_text(credit_text, encoding="utf-8")


def run_job(job_id: str, data: dict) -> None:
    folder = JOBS / job_id
    try:
        folder.mkdir(parents=True)
        (folder / "request.json").write_text(json.dumps(data), encoding="utf-8")
        with subprocess.Popen([sys.executable, "-X", "utf8", "-u", str(ROOT / "app.py"), "--worker", str(folder)],
                              cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace") as proc:
            output = []
            for line in proc.stdout:
                line = line.strip()
                if line:
                    output.append(line)
                    if line.startswith("STATUS:") or re.fullmatch(r"frame \d+/\d+", line):
                        with lock:
                            jobs[job_id]["message"] = line.removeprefix("STATUS:")
            code = proc.wait()
        if code:
            raise RuntimeError(output[-1] if output else "The job failed.")
        result = {"status": "done", "message": "Ready"}
        if data["action"] in ("generate", "images", "revise"):
            result["script"] = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        elif data["action"] == "download_model":
            result.update(json.loads((folder / "result.json").read_text(encoding="utf-8")))
        else:
            filename = "video.mp4" if data["action"] in ("render", "motion") else (
                "audio/mix.wav" if (folder / "audio" / "mix.wav").is_file() else "audio/voiceover.wav"
            )
            result["url"] = f"/output/{job_id}/{filename}"
            if data["action"] in ("render", "motion"):
                result["credits"] = f"/output/{job_id}/credits.txt"
        with lock:
            jobs[job_id].update(result)
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="error", message=str(exc))


class Handler(BaseHTTPRequestHandler):
    def reply(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json(self, value, status: int = 200) -> None:
        self.reply(status, json.dumps(value).encode(), "application/json")

    def local_request(self) -> bool:
        host = self.headers.get("Host", "")
        expected = f"127.0.0.1:{self.server.server_port}"
        return host == expected and self.headers.get("Origin", f"http://{expected}") == f"http://{expected}"

    def do_GET(self) -> None:
        if not self.local_request():
            self.json({"error": "Use the local studio URL."}, 403)
            return
        path = urlparse(self.path).path
        if path == "/api/init":
            import importlib.util
            import download_model
            import music
            import tts
            self.json({"script": DEMO_SCRIPT,
                       "models": [str(p) for p in (ROOT / "models").glob("*.gguf")
                                  if not re.search(r"-0000[2-9]-of-", p.name)],
                       "model_catalog": download_model.catalog_status(),
                       "music_tracks": music.catalog_list(),
                       "voices": self.server.voices,
                       "kokoro_voices": [{"id": key, "name": name} for key, name in tts.KOKORO_VOICES.items()],
                       "kokoro_ready": importlib.util.find_spec("kokoro_onnx") is not None
                       and all((tts.KOKORO_DIR / name).is_file()
                               for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin")),
                       "edge_voices": [{"id": key, "name": name} for key, name in tts.EDGE_VOICES.items()],
                       "edge_ready": importlib.util.find_spec("edge_tts") is not None})
        elif path.startswith("/api/jobs/"):
            with lock:
                result = dict(jobs.get(path.rsplit("/", 1)[-1], {}))
            self.json(result or {"error": "Job not found."}, 200 if result else 404)
        elif path in ("/", "/studio.css", "/studio.js"):
            file = ROOT / "web" / ("index.html" if path == "/" else path[1:])
            self.reply(200, file.read_bytes(), mimetypes.guess_type(file)[0] or "text/plain")
        elif re.fullmatch(r"/avatar/[0-9a-f]{24}\.png", path):
            from media import AVATARS
            file = AVATARS / path.rsplit("/", 1)[-1]
            if file.is_file():
                self.reply(200, file.read_bytes(), "image/png")
            else:
                self.json({"error": "Avatar not found."}, 404)
        elif re.fullmatch(r"/media/[0-9a-f]{24}\.(jpg|json)", path):
            from media import CACHE
            file = CACHE / path.rsplit("/", 1)[-1]
            if file.is_file():
                self.reply(200, file.read_bytes(), "image/jpeg" if file.suffix == ".jpg" else "application/json")
            else:
                self.json({"error": "Image not found."}, 404)
        elif re.fullmatch(r"/music/[a-z0-9_]{2,32}\.wav", path):
            import music
            track_id = path.rsplit("/", 1)[-1].removesuffix(".wav")
            try:
                file = music.ensure_track(track_id)
            except ValueError:
                file = None
            if file and file.is_file():
                self.reply(200, file.read_bytes(), "audio/wav")
            else:
                self.json({"error": "Music track not found."}, 404)
        elif re.fullmatch(r"/output/[0-9a-f]{32}/(video\.mp4|credits\.txt|audio/(?:voiceover|mix)\.wav)", path):
            file = JOBS / path.removeprefix("/output/")
            if file.is_file():
                self.reply(200, file.read_bytes(), mimetypes.guess_type(file)[0] or "application/octet-stream")
            else:
                self.json({"error": "Output not found."}, 404)
        else:
            self.json({"error": "Not found."}, 404)

    def do_POST(self) -> None:
        if not self.local_request():
            self.json({"error": "Use the local studio URL."}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.path == "/api/upload-music":
                if not 0 < length <= 20 * 1024 * 1024:
                    raise ValueError("Music file must be between 1 byte and 20 MB.")
                from urllib.parse import unquote
                import music
                filename = unquote(self.headers.get("X-Filename", "music.mp3"))
                self.json(music.save_uploaded_music(self.rfile.read(length), filename), 200)
                return
            if self.path == "/api/search-music":
                if not 0 < length <= 4000:
                    raise ValueError("Invalid search request.")
                import music
                body = json.loads(self.rfile.read(length))
                self.json(music.search_open_music(str(body.get("query", ""))), 200)
                return
            if self.path == "/api/upload-avatar":
                if not 0 < length <= 12 * 1024 * 1024:
                    raise ValueError("Avatar image must be between 1 byte and 12 MB.")
                from media import save_uploaded_avatar
                self.json({"id": save_uploaded_avatar(self.rfile.read(length))}, 200)
                return
            if self.path == "/api/upload-image":
                if not 0 < length <= 12 * 1024 * 1024:
                    raise ValueError("Image must be between 1 byte and 12 MB.")
                from media import save_uploaded_image
                raw = self.rfile.read(length)
                from urllib.parse import unquote
                filename = unquote(self.headers.get("X-Filename", "upload.jpg"))
                asset_id = save_uploaded_image(raw, filename)
                self.json({"id": asset_id}, 200)
                return
            if not 0 < length <= 64000:
                raise ValueError("Project is too large or empty.")
            data = validate(json.loads(self.rfile.read(length)))
            if self.path == "/api/preview":
                from render import scene_frame
                index = data.get("index", 0)
                if type(index) is not int or not 0 <= index < len(data["scenes"]):
                    raise ValueError("Select an existing scene.")
                frame = scene_frame(data["scenes"][index], index, data.get("accent", "#FF6B3D"),
                                    (index + 0.15) / len(data["scenes"]), data)
                frame.thumbnail((540, 960))
                buffer = io.BytesIO()
                frame.save(buffer, format="PNG")
                self.reply(200, buffer.getvalue(), "image/png")
            elif self.path == "/api/jobs":
                if data.get("action") not in ("generate", "render", "audio", "motion", "images", "revise", "download_model"):
                    raise ValueError("Unknown action.")
                with lock:
                    if any(job["status"] == "running" for job in jobs.values()):
                        self.json({"error": "Wait for the current job to finish."}, 409)
                        return
                    job_id = uuid.uuid4().hex
                    jobs[job_id] = {"status": "running", "message": "Starting…"}
                threading.Thread(target=run_job, args=(job_id, data), daemon=True).start()
                self.json({"id": job_id}, 202)
            else:
                self.json({"error": "Not found."}, 404)
        except (ValueError, TypeError) as exc:
            self.json({"error": str(exc)}, 400)
        except Exception as exc:
            self.json({"error": str(exc)}, 500)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        import tts
        server.voices = [name for _, name in tts.list_voices()]
    except Exception:
        server.voices = []
    url = f"http://127.0.0.1:{args.port}"
    print(f"Clipwright Studio: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
