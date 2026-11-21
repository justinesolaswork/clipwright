"""Clipwright: make short vertical videos from a topic, fully on your own machine."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).parent


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "video"


def save_script(script: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_script(args) -> Path:
    from scriptgen import generate_script
    print("Writing script with the local model...")
    script = generate_script(args.topic, args.model, args.scenes, args.gpu_layers)
    path = Path(args.out) if args.out else HERE / "work" / slugify(args.topic) / "script.json"
    save_script(script, path)
    print(f"Saved {path}")
    print("Read it, fix any wrong facts, then run:")
    print(f"  python main.py render {path}")
    return path


def cmd_render(args) -> None:
    import tts
    from render import render_video

    script_path = Path(args.script)
    script = json.loads(script_path.read_text(encoding="utf-8"))
    scenes = script["scenes"]
    workdir = script_path.parent / "audio"

    print(f"Making voiceover ({args.tts})...")
    paths = tts.synth_all([s["voiceover"] for s in scenes], workdir, args.tts, args.voice, args.rate)
    audio, durations = tts.assemble(paths, workdir)

    out = Path(args.out) if args.out else HERE / "out" / f"{slugify(script.get('topic', script_path.parent.name))}.mp4"
    print(f"Rendering {len(scenes)} scenes, {sum(durations):.0f} seconds...")
    render_video(scenes, durations, audio, out, args.accent, args.fps, look=script)
    print(f"Done: {out}")


def cmd_demo(args) -> None:
    from scriptgen import DEMO_SCRIPT
    path = HERE / "work" / "demo" / "script.json"
    save_script(DEMO_SCRIPT, path)
    args.script = str(path)
    cmd_render(args)


def cmd_voices(_args) -> None:
    import tts
    for vid, name in tts.list_voices():
        print(f"{name}   ({vid})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_render_opts(sp):
        sp.add_argument("--tts", default="pyttsx3", choices=["pyttsx3", "kokoro", "silent"],
                        help="voice engine; 'silent' is only for testing")
        sp.add_argument("--voice", help="part of a voice name, see: python main.py voices")
        sp.add_argument("--rate", type=int, default=185, help="speaking speed")
        sp.add_argument("--accent", default="#FF6B3D", help="accent colour as hex")
        sp.add_argument("--fps", type=int, default=30)
        sp.add_argument("--out", help="output .mp4 path")

    def add_script_opts(sp):
        sp.add_argument("--model", required=True, help="path to a .gguf model file")
        sp.add_argument("--scenes", type=int, default=4)
        sp.add_argument("--gpu-layers", type=int, default=0,
                        help="layers to offload to the GPU (0 = CPU only)")

    s = sub.add_parser("script", help="topic -> script.json (edit it before rendering)")
    s.add_argument("topic")
    add_script_opts(s)
    s.add_argument("--out", help="where to save script.json")
    s.set_defaults(fn=cmd_script)

    r = sub.add_parser("render", help="script.json -> mp4")
    r.add_argument("script")
    add_render_opts(r)
    r.set_defaults(fn=cmd_render)

    a = sub.add_parser("all", help="topic -> script -> mp4 in one go (no review step)")
    a.add_argument("topic")
    add_script_opts(a)
    add_render_opts(a)
    a.set_defaults(fn=lambda args: (setattr(args, "script", str(cmd_script(args))), cmd_render(args)))

    d = sub.add_parser("demo", help="render the built-in sample script (no model needed)")
    add_render_opts(d)
    d.set_defaults(fn=cmd_demo)

    v = sub.add_parser("voices", help="list voices installed on this computer")
    v.set_defaults(fn=cmd_voices)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
