# One-shot prompt: build Clipwright (paste this into your coding agent)

You are extending an existing Python project in this folder called Clipwright. Read every file in it first (`main.py`, `scriptgen.py`, `tts.py`, `render.py`, `requirements*.txt`). The command-line pipeline already works: topic -> script.json -> voiceover -> 1080x1920 MP4 with headline, mascot, captions and progress bar. Your job is to turn it into a finished local desktop-style web app. Do not rewrite what already works; refactor only where needed.

## Hard constraints
- Pure local Python 3.10-3.12. No cloud APIs, no accounts, no telemetry. Everything runs offline after models are downloaded.
- Target machine: Windows laptop, Intel i5-12th gen H, NVIDIA RTX 4050 with 6 GB VRAM, 24 GB RAM. Code must also run CPU-only.
- Script writing uses llama-cpp-python with a local GGUF model. The GPU layer count must be configurable because 6 GB fits a 3B-4B model fully or a 7B-8B Q4 model only partly.
- The mascot is an original character drawn in code (`draw_mascot`). Do not copy any real creator's characters, branding, or videos.
- Users review and edit the script before rendering. AI can get facts wrong, so never skip this step.

## What to build
1. **Local web UI** (NiceGUI preferred, Gradio acceptable), started with `python app.py`, opening in the browser. Dark theme. Three panels that stack on narrow screens:
   - **Idea:** topic or pasted notes input, voiceover tone (Calm / Hyped / Deadpan, which changes the script prompt and the speaking rate), number of scenes, accent colour picker, a note that scripts must be reviewed.
   - **Script and scenes:** editable cards, one per scene, each with headline line 1, headline line 2, voiceover text, mascot pose (surprised / flat / smile / happy) and an estimated duration. Add, delete, reorder, regenerate-one-scene, regenerate-all. Selecting a card updates the preview.
   - **Preview:** a 9:16 live preview of the selected scene (render a single still with the existing Pillow code), a "Play preview" button that plays the scene's voiceover audio, and a "Render MP4" button with a progress bar and a link to open the output folder.
2. **Settings page:** model path (file picker or text), GPU layers, context size, TTS engine, voice, speaking rate, output folder, FPS.
3. **Better voices:** keep pyttsx3 and the `silent` test backend. Add Piper TTS as an optional backend (voice model files in `models/`) with a clear error and install hint if missing. List installed voices in the UI.
4. **Accurate captions:** add optional `faster-whisper` word-level timestamps (model `base` or `small`, runs on the GPU if available, else CPU) and fall back to the existing length-based timing if it is not installed.
5. **Projects:** save and load each video as a folder with `script.json`, audio and output. Recent projects list on the home screen.
6. **Background work:** script generation and rendering must not freeze the UI. Show progress and allow cancel. Free the language model from memory before rendering.
7. **Quality of life:** helpful error messages (missing model, missing voice, ffmpeg problem), a first-run check that tells the user what is not installed, and a `python app.py --check` command.

## Visual style
Dark ground `#111113`, text `#F4F1EA`, muted text `#A8A8A0`, panel borders `#2A2A2F`, cards `#16161A`, selected card border = accent (default `#FF6B3D`). Inter for the interface. Headline font Anton if `assets/fonts/Anton-Regular.ttf` exists, otherwise Impact. Buttons are at least 44 px tall. Keep text contrast readable.

## Engineering rules
- Keep modules small and typed. Put settings in a `config.json` with sensible defaults.
- Add `pytest` tests for script cleaning, word timing, audio assembly, and a short end-to-end render using the `silent` backend.
- Update `README.md` with Windows setup steps (venv, `pip install -r requirements.txt`, installing llama-cpp-python with CUDA, downloading a GGUF model), how to run, and troubleshooting.
- Work in milestones and run the tests after each: (1) refactor into functions the UI can call, (2) UI with script editing and still preview, (3) background rendering with progress, (4) Piper and faster-whisper, (5) projects and settings, (6) polish and README.

## Done when
- `python app.py` opens the UI and I can type a topic, get a script from my local model, edit it, preview a scene, and render an MP4 with voiceover and captions.
- `python main.py demo --tts silent` still works.
- Tests pass and the README steps work on a clean Windows machine.
