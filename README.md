# Clipwright

Create punchy 9:16 vertical explainer videos from a topic — powered locally by GGUF language models (`llama-cpp-python`), neural text-to-speech (`Kokoro` & `Edge Neural`), web search grounding, a customizable animated mascot, and a 32-track open-source background music library.

---

## Features

- **🔥 Let Him Cook! (Content-Aware Auto-Director)**:
  - Generates a structured, high-retention script (**Hook → Stakes → Distinct Breakdowns → Payoff & CTA**) with live web search grounding (`ddgs`).
  - Automatically detects the content vibe (`Tech & Cyber`, `Dark Mystery`, `Chill & Calm`, `Fun & Playful`, `Story & Explainer`, `High-Energy Hype`) and directs the **visual theme, font style, background effect, headline animation, subtitle style & effect, scene transition, camera videography, voice, background music, and mascot design** to match.
  - **Live Token Burn Meter**: Streams generation token-by-token, showing prompt tokens, live generated tokens, total tokens burned, and `tok/s` speed in real time.
- **✦ AI Script Editor (Revision Chat)**:
  - Refine the whole script or a single selected scene with natural-language prompts (e.g., *"Make it a 30 second video"*, *"More trendy"*, *"Stronger hook"*), complete with quick suggestion chips and multi-step **↶ Undo**.
- **Avatar Studio (Build Your Own)**:
  - **16 Mascot Expressions**: `Smile`, `Happy`, `Excited`, `Surprised`, `Shocked`, `Mind blown`, `Laughing`, `Winking`, `Heart-eyes`, `Smirk`, `Thinking`, `Confused`, `Angry`, `Sad`, `Crying`, and `Deadpan`.
  - **8 Character Presets & 🎲 Randomizer**: Customize character shape (`Round`, `Square`, `Cat`, `Bunny`, `Bear`), eyes, antenna, accessories (`Glasses`, `Sunglasses`, `Headphones`, `Crown`, `Party hat`, `Cap`, `Bow tie`), head/body colors, rosy cheeks, size, **10 stage placements** (including `Alternate left & right` and `Roam corners`), **6 location movement modes** (`Idle bounce`, `Walk-in`, `Stage pacing`, `Zero-G float`, `Jump beats`, `Side peek`), or upload a custom transparent PNG avatar.
- **Themes, Fonts, Subtitles & Videography**:
  - **6 Visual Themes** (`Studio Dark`, `Cyber Neon`, `Sunset Glow`, `Midnight Ocean`, `Minimal Light`, `Retro VHS`) + **🎲 Theme & Effects Randomizer**.
  - **6 Font Styles** (`Bold Impact`, `Modern Sans`, `Tech Mono`, `Editorial Serif`, `Playful`, `Geometric Clean`).
  - **4 Subtitle Styles** (`Classic dark pill`, `TikTok karaoke pop`, `Bold outline`, `Minimal translucent bar`) with automatic 2-line pagination + **6 Subtitle Effects** (`Word highlight`, `Word pop`, `Kinetic bounce`, `Neon glow`, `Progressive reveal`, `Slide-up entrance`).
  - **6 Videography & Camera Modes** (`Ken Burns alternating pan & zoom`, `Cinematic push-in + letterbox`, `Handheld vlog sway`, `Dynamic zoom & voice punch`, `Stage spotlight frame`, `Locked tripod`).
- **32+ Open-Source Background Music Tracks**:
  - 5 instant procedural studio beats (`CC0`) + 27 Kevin MacLeod / Wikimedia Commons (`CC-BY`) tracks, plus live Wikimedia Commons open-source music search, custom MP3/WAV upload, preview player, volume control with end fade-out, and automatic attribution in `credits.txt`.
- **Natural Voices & Local AI Model Switcher**:
  - Switch between **Kokoro v1.0** (local ONNX neural voices), **Edge Neural** (free American, British, and Filipino neural voices), and **Windows SAPI5 voices**.
  - Switch between installed `.gguf` models or download **Qwen 2.5 7B Instruct**, **Llama 3.1 8B Instruct**, or **Gemma 2 9B Instruct** directly from the UI with SHA-256 verification.

---

## Project Structure

```text
clipwright/
├── app.py                 # Local HTTP studio server & background job worker
├── main.py                # Command-line interface (demo, script, render, voices)
├── scriptgen.py           # Local GGUF LLM script generator, AI revision chat & auto-director
├── render.py              # 9:16 frame compositor, themes, mascot renderer & ffmpeg video pipeline
├── tts.py                 # Kokoro local neural TTS, Edge Neural TTS & Windows SAPI5 voices
├── media.py               # Web & Wikimedia Commons scene image search, scoring & local cache
├── music.py               # 32-track open-source BGM library, synth engine & audio mixer
├── download_model.py      # Resumable, checksum-verified Hugging Face GGUF downloader
├── web/                   # Zero-build frontend (index.html, studio.css, studio.js)
├── assets/                # Fonts and runtime media/music/avatar caches
├── models/                # Local GGUF and Kokoro ONNX model files (git-ignored)
├── tests/                 # Python unit tests, UI progress test & Playwright smoke test
├── docs/                  # Design brief and reference screenshots
└── Start Studio.bat       # One-click Windows launcher
```

---

## Quick Start (Windows)

1. **Create a Python 3.12 virtual environment and install dependencies:**
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-tts.txt
   .venv\Scripts\python.exe -m pip install llama-cpp-python --only-binary=llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
   .venv\Scripts\python.exe -m pip install -r requirements-llm.txt
   ```
2. **Download the default local GGUF model (`Qwen 2.5 7B Instruct Q4_K_M`):**
   ```powershell
   .venv\Scripts\python.exe download_model.py
   ```
   *(Optional)* Place `kokoro-v1.0.onnx` and `voices-v1.0.bin` in `models/kokoro/` for local Kokoro TTS, or use the built-in **Edge Neural** voices right away.
3. **Launch Clipwright Studio:**
   Double-click **`Start Studio.bat`** or run:
   ```powershell
   .venv\Scripts\python.exe app.py
   ```
   Open http://127.0.0.1:8000 in your browser.

---

## Running Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
node tests/test_progress.cjs
```
