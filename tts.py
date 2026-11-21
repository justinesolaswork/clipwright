"""Local text-to-speech: Kokoro neural voices, Windows voices, and silent testing."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

RATE = 44100
KOKORO_DIR = Path(__file__).parent / "models" / "kokoro"
KOKORO_VOICES = {
    "af_heart": "Heart · American · female",
    "af_bella": "Bella · American · female",
    "af_sarah": "Sarah · American · female",
    "am_adam": "Adam · American · male",
    "am_michael": "Michael · American · male",
    "bf_emma": "Emma · British · female",
    "bf_isabella": "Isabella · British · female",
    "bm_george": "George · British · male",
    "bm_lewis": "Lewis · British · male",
}
EDGE_VOICES = {
    "en-US-BrianNeural": "Brian · American · male (narrator)",
    "en-US-AvaNeural": "Ava · American · female (expressive)",
    "en-US-EmmaNeural": "Emma · American · female (clear)",
    "en-US-GuyNeural": "Guy · American · male (punchy)",
    "en-US-AriaNeural": "Aria · American · female (lively)",
    "en-GB-RyanNeural": "Ryan · British · male",
    "en-GB-SoniaNeural": "Sonia · British · female",
    "en-PH-JamesNeural": "James · Filipino · male",
    "en-PH-RosaNeural": "Rosa · Filipino · female",
}


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def list_voices() -> list[tuple[str, str]]:
    import pyttsx3
    engine = pyttsx3.init()
    return [(v.id, v.name) for v in engine.getProperty("voices")]


def _write_silent(text: str, path: Path, words_per_sec: float = 2.6) -> None:
    dur = max(1.2, len(text.split()) / words_per_sec)
    n = int(dur * 22050)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * n)


def _speak_pyttsx3(texts: list[str], paths: list[Path], voice: str | None, rate: int) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    if voice:
        match = [v for v in engine.getProperty("voices") if voice.lower() in v.name.lower()]
        if not match:
            raise SystemExit(f"No voice matching '{voice}'. Run: python main.py voices")
        engine.setProperty("voice", match[0].id)
    engine.setProperty("rate", rate)
    for text, path in zip(texts, paths):
        engine.save_to_file(text, str(path))
    engine.runAndWait()
    for p in paths:
        if not p.exists() or p.stat().st_size == 0:
            raise SystemExit(f"The voice engine did not create {p}. Try --tts silent to test the rest.")


def _speak_kokoro(texts: list[str], paths: list[Path], voice: str | None, rate: int) -> None:
    try:
        from kokoro_onnx import Kokoro
        import soundfile
    except ImportError as exc:
        raise RuntimeError("Install Kokoro with: .venv\\Scripts\\python.exe -m pip install -r requirements-tts.txt") from exc
    model, voices = KOKORO_DIR / "kokoro-v1.0.onnx", KOKORO_DIR / "voices-v1.0.bin"
    if not model.is_file() or not voices.is_file():
        raise ValueError("Kokoro voice files are missing from models/kokoro. See README.md for download links.")
    voice = voice or "af_heart"
    if voice not in KOKORO_VOICES:
        raise ValueError("Choose a Kokoro voice, such as Heart or Emma, in Voice settings.")
    print("STATUS:Loading Kokoro voice model...", flush=True)
    engine = Kokoro(str(model), str(voices))
    for index, (text, path) in enumerate(zip(texts, paths)):
        print(f"STATUS:Creating natural voiceover {index + 1}/{len(texts)}...", flush=True)
        samples, sample_rate = engine.create(
            text, voice=voice, speed=rate / 185, lang="en-gb" if voice.startswith("b") else "en-us")
        soundfile.write(str(path), samples, sample_rate, subtype="PCM_16")


def _speak_edge(texts: list[str], paths: list[Path], voice: str | None, rate: int) -> None:
    import asyncio
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Install Edge Neural TTS with: .venv\\Scripts\\python.exe -m pip install edge-tts") from exc
    voice = voice or "en-US-BrianNeural"
    if voice not in EDGE_VOICES:
        raise ValueError("Choose an Edge Neural voice in Voice settings.")
    pct = max(-40, min(60, round((rate - 185) / 185 * 100)))
    rate_str = f"{pct:+d}%"

    async def _one(index: int, text: str, path: Path) -> None:
        mp3_path = path.with_suffix(".mp3")
        kwargs = {"rate": rate_str} if pct else {}
        await edge_tts.Communicate(text, voice, **kwargs).save(str(mp3_path))
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(mp3_path), str(path)],
            check=True,
        )
        mp3_path.unlink(missing_ok=True)

    async def _run() -> None:
        print(f"STATUS:Creating Edge neural voiceover ({len(texts)} scenes in parallel)...", flush=True)
        await asyncio.gather(*(_one(i, t, p) for i, (t, p) in enumerate(zip(texts, paths))))

    asyncio.run(_run())


def synth_all(texts: list[str], outdir: Path, backend: str = "pyttsx3",
              voice: str | None = None, rate: int = 185) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    raw = [outdir / f"scene{i + 1}_raw.wav" for i in range(len(texts))]
    if backend == "silent":
        for t, p in zip(texts, raw):
            _write_silent(t, p)
    elif backend == "pyttsx3":
        _speak_pyttsx3(texts, raw, voice, rate)
    elif backend == "kokoro":
        _speak_kokoro(texts, raw, voice, rate)
    elif backend == "edge":
        _speak_edge(texts, raw, voice, rate)
    else:
        raise SystemExit(f"Unknown TTS backend: {backend}")

    # Normalise everything to 44.1 kHz mono 16-bit so the files can be joined safely.
    norm = []
    for p in raw:
        out = p.with_name(p.name.replace("_raw", ""))
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(p),
             "-ar", str(RATE), "-ac", "1", "-sample_fmt", "s16", str(out)],
            check=True,
        )
        norm.append(out)
    return norm


def assemble(paths: list[Path], outdir: Path, gap: float = 0.45) -> tuple[Path, list[float]]:
    """Join scene audio with a short pause after each. Returns (file, scene durations)."""
    final = outdir / "voiceover.wav"
    durations = []
    with wave.open(str(final), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        for p in paths:
            with wave.open(str(p), "rb") as w:
                frames = w.readframes(w.getnframes())
                dur = w.getnframes() / w.getframerate()
            out.writeframes(frames)
            out.writeframes(b"\x00\x00" * int(gap * RATE))
            durations.append(dur + gap)
    return final, durations
