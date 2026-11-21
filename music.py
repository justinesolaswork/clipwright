"""Open-source background music library (30 built-in tracks + Wikimedia Commons search + local upload)."""
from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request
import wave

import tts

MUSIC_DIR = Path(__file__).parent / "assets" / "music"
USER_AGENT = "Clipwright/1.0 (https://github.com/clipwright; contact@clipwright.local) Python-urllib/3.12"

# 5 instant procedural studio loops + 25 verified Kevin MacLeod (CC BY 3.0 / 4.0) tracks on Wikimedia Commons.
LIBRARY: dict[str, dict] = {
    "synth_lofi": {
        "name": "Lo-Fi Study Chill · Studio Beat",
        "author": "Clipwright Studio Synth",
        "license": "CC0 1.0 Public Domain",
        "source": "local-synth",
        "synth": {"bpm": 82, "root": 220.0, "chords": [(0, 3, 7, 10), (5, 8, 12, 15), (7, 10, 14, 17), (3, 7, 10, 14)], "style": "lofi"},
    },
    "synth_pulse": {
        "name": "Synthwave Neon Pulse · Studio Beat",
        "author": "Clipwright Studio Synth",
        "license": "CC0 1.0 Public Domain",
        "source": "local-synth",
        "synth": {"bpm": 118, "root": 146.83, "chords": [(0, 3, 7), (8, 12, 15), (3, 7, 10), (10, 14, 17)], "style": "pulse"},
    },
    "synth_cyber": {
        "name": "Cyber Bass Drive · Studio Beat",
        "author": "Clipwright Studio Synth",
        "license": "CC0 1.0 Public Domain",
        "source": "local-synth",
        "synth": {"bpm": 128, "root": 110.0, "chords": [(0, 7, 12), (3, 10, 15), (5, 12, 17), (2, 9, 14)], "style": "cyber"},
    },
    "synth_ambient": {
        "name": "Warm Horizon Pad · Studio Ambient",
        "author": "Clipwright Studio Synth",
        "license": "CC0 1.0 Public Domain",
        "source": "local-synth",
        "synth": {"bpm": 70, "root": 196.0, "chords": [(0, 4, 7, 11), (5, 9, 12, 16), (9, 12, 16, 19), (7, 11, 14, 19)], "style": "ambient"},
    },
    "synth_chip": {
        "name": "Arcade Pixel Bounce · Studio Chiptune",
        "author": "Clipwright Studio Synth",
        "license": "CC0 1.0 Public Domain",
        "source": "local-synth",
        "synth": {"bpm": 136, "root": 261.63, "chords": [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)], "style": "chip"},
    },
    "km_carefree": {
        "name": "Carefree · Upbeat Ukulele (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Carefree.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/5/58/Kevin_MacLeod_-_Carefree.ogg",
    },
    "km_cleansoul": {
        "name": "Clean Soul · Chill Jazz Piano (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Clean_Soul.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/43/Kevin_MacLeod_-_Clean_Soul.ogg",
    },
    "km_dreamculture": {
        "name": "Dream Culture · Chill Electronic (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Dream_Culture.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/e/e0/Kevin_MacLeod_-_Dream_Culture.ogg",
    },
    "km_smoothermove": {
        "name": "Smoother Move · Funky Groove (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Smoother_Move.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/e/e5/Kevin_MacLeod_-_Smoother_Move.ogg",
    },
    "km_earlyriser": {
        "name": "Early Riser · Bright Explainer (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Early_Riser.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d7/Kevin_MacLeod_-_Early_Riser.ogg",
    },
    "km_unity": {
        "name": "Unity · Upbeat EDM / Tech (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Unity.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/0d/Kevin_MacLeod_-_Unity.ogg",
    },
    "km_windswept": {
        "name": "Windswept · Inspiring Aerial (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Windswept.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/2/23/Kevin_MacLeod_-_Windswept.ogg",
    },
    "km_calmant": {
        "name": "Calmant · Calm Study Piano (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Calmant.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Kevin_MacLeod_-_Calmant.ogg",
    },
    "km_stratosphere": {
        "name": "Stratosphere · Sci-Fi Space Synth (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Stratosphere,_(MacLeod,_Kevin).oga",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/76/Stratosphere%2C_%28MacLeod%2C_Kevin%29.oga",
    },
    "km_liftmotif": {
        "name": "Lift Motif · Punchy Hook Riff (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Lift_Motif.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/9/9e/Kevin_MacLeod_-_Lift_Motif.ogg",
    },
    "km_reachingout": {
        "name": "Reaching Out · Warm Cinematic (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Reaching_Out.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/7f/Kevin_MacLeod_-_Reaching_Out.ogg",
    },
    "km_autumnday": {
        "name": "Autumn Day · Gentle Acoustic (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Autumn_Day.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/5/59/Kevin_MacLeod_-_Autumn_Day.ogg",
    },
    "km_parisian": {
        "name": "Parisian · Playful Comedy Bistro (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Parisian.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d4/Kevin_MacLeod_-_Parisian.ogg",
    },
    "km_schmetterling": {
        "name": "Schmetterling · Quirky & Curious (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Schmetterling.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/e/e3/Kevin_MacLeod_-_Schmetterling.ogg",
    },
    "km_theendless": {
        "name": "The Endless · Deep Thoughtful (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_The_Endless.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/45/Kevin_MacLeod_-_The_Endless.ogg",
    },
    "km_relent": {
        "name": "Relent · Driving Suspense (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Relent.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/1d/Kevin_MacLeod_-_Relent.ogg",
    },
    "km_therule": {
        "name": "The Rule · Dramatic Tension (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_The_Rule.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/7f/Kevin_MacLeod_-_The_Rule.ogg",
    },
    "km_sovereign": {
        "name": "Sovereign Quarter · Documentary Epic (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Sovereign_Quarter.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/43/Kevin_MacLeod_-_Sovereign_Quarter.ogg",
    },
    "km_enchanted": {
        "name": "Enchanted Journey · Fantasy Story (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Enchanted_Journey.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/9/96/Kevin_MacLeod_-_Enchanted_Journey.ogg",
    },
    "km_ghostdance": {
        "name": "Ghost Dance · Mystery & Intrigue (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Ghost_Dance_(MacLeod,_Kevin)_(ISRC_USUAN1100573).oga",
        "url": "https://upload.wikimedia.org/wikipedia/commons/8/84/Ghost_Dance_%28MacLeod%2C_Kevin%29_%28ISRC_USUAN1100573%29.oga",
    },
    "km_sugarplum": {
        "name": "Sugar Plum Dark Mix · Dark Trap Twist (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Sugar_Plum_Dark_Mix_(Kevin_MacLeod)_(ISRC_USUAN1100623).oga",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/4b/Sugar_Plum_Dark_Mix_%28Kevin_MacLeod%29_%28ISRC_USUAN1100623%29.oga",
    },
    "km_horroriffic": {
        "name": "Horroriffic · Spooky Thriller (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Horroriffic.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/7b/Kevin_MacLeod_-_Horroriffic.ogg",
    },
    "km_winter": {
        "name": "Winter Reflections · Peaceful Ambient (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Winter_Reflections.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Kevin_MacLeod_-_Winter_Reflections.ogg",
    },
    "km_tinyfugue": {
        "name": "Tiny Fugue · Smart Classical Motif (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Tiny_Fugue.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/ba/Kevin_MacLeod_-_Tiny_Fugue.ogg",
    },
    "km_sonatina": {
        "name": "Sonatina · Light Classical Story (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Sonatina.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Kevin_MacLeod_-_Sonatina.ogg",
    },
    "km_resignation": {
        "name": "Resignation · Gentle Reflective (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Resignation.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/0b/Kevin_MacLeod_-_Resignation.ogg",
    },
    "km_snowdrop": {
        "name": "Snow Drop · Delicate Storyteller (Kevin MacLeod)",
        "author": "Kevin MacLeod (incompetech.com)",
        "license": "CC BY 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Kevin_MacLeod_-_Snow_Drop.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3a/Kevin_MacLeod_-_Snow_Drop.ogg",
    },
}


def valid_track_id(track_id: str) -> bool:
    if track_id == "none":
        return True
    if track_id in LIBRARY:
        return True
    return bool(re.fullmatch(r"(?:web|custom)_[0-9a-f]{16}", track_id) and (MUSIC_DIR / f"{track_id}.wav").is_file())


def catalog_list() -> list[dict]:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for key, spec in LIBRARY.items():
        items.append({
            "id": key,
            "name": spec["name"],
            "author": spec["author"],
            "license": spec["license"],
            "cached": (MUSIC_DIR / f"{key}.wav").is_file() or "synth" in spec,
        })
    for meta_file in sorted(MUSIC_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        key = meta_file.stem
        if key in LIBRARY or not (MUSIC_DIR / f"{key}.wav").is_file():
            continue
        try:
            info = json.loads(meta_file.read_text(encoding="utf-8"))
            items.append({
                "id": key,
                "name": info.get("name", key),
                "author": info.get("author", "Custom"),
                "license": info.get("license", ""),
                "cached": True,
            })
        except Exception:
            continue
    return items


def _synth_loop(spec: dict, target: Path, duration: float = 12.0) -> Path:
    rate = 22050
    total = int(duration * rate)
    bpm = spec["bpm"]
    beat_sec = 60.0 / bpm
    root = spec["root"]
    chords = spec["chords"]
    style = spec["style"]
    samples = array("h", [0] * total)
    two_pi = 2.0 * math.pi
    for i in range(total):
        t = i / rate
        beat = t / beat_sec
        bar = int(beat // 4) % len(chords)
        chord = chords[bar]
        sub_beat = beat % 1.0
        half_beat = (beat * 2) % 1.0
        # Warm chord pad
        pad = 0.0
        for semi in chord:
            freq = root * (2.0 ** (semi / 12.0))
            if style == "chip":
                pad += (0.22 if math.sin(two_pi * freq * t) >= 0 else -0.22)
            else:
                pad += 0.26 * math.sin(two_pi * freq * t) + 0.08 * math.sin(two_pi * freq * 2.0 * t)
        pad /= max(1, len(chord))
        # Arpeggio / melody note
        arp_semi = chord[int(beat * 2) % len(chord)] + 12
        arp_freq = root * (2.0 ** (arp_semi / 12.0))
        arp_env = math.exp(-half_beat * (5.5 if style != "ambient" else 2.2))
        arp = 0.22 * arp_env * math.sin(two_pi * arp_freq * t)
        # Bassline
        bass_freq = (root * 0.5) * (2.0 ** (chord[0] / 12.0))
        bass_env = math.exp(-sub_beat * 3.5) if style != "ambient" else 0.7
        bass = 0.34 * bass_env * math.sin(two_pi * bass_freq * t)
        # Soft kick & hat pulse (except pure ambient)
        perc = 0.0
        if style != "ambient":
            if sub_beat < 0.18:
                k_freq = 52.0 + 90.0 * math.exp(-sub_beat * 28.0)
                perc += 0.35 * math.exp(-sub_beat * 18.0) * math.sin(two_pi * k_freq * t)
            if 0.5 <= sub_beat < 0.62:
                perc += 0.09 * math.exp(-(sub_beat - 0.5) * 40.0) * math.sin(two_pi * 3100.0 * t)
        val = (pad * 0.48 + arp * 0.32 + bass * 0.42 + perc * 0.38)
        samples[i] = max(-32000, min(32000, int(val * 18000)))
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = target.with_suffix(".raw.wav")
    with wave.open(str(raw_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    subprocess.run(
        [tts.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(raw_path),
         "-ar", str(tts.RATE), "-ac", "1", "-sample_fmt", "s16", str(target)],
        check=True,
    )
    raw_path.unlink(missing_ok=True)
    return target


def _convert_to_wav(raw_bytes: bytes, suffix: str, target: Path) -> Path:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(suffix)
    tmp.write_bytes(raw_bytes)
    try:
        subprocess.run(
            [tts.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(tmp),
             "-t", "120", "-ar", str(tts.RATE), "-ac", "1", "-sample_fmt", "s16", str(target)],
            check=True,
        )
    finally:
        tmp.unlink(missing_ok=True)
    return target


def ensure_track(track_id: str) -> Path | None:
    if not track_id or track_id == "none":
        return None
    if not valid_track_id(track_id):
        raise ValueError("Unknown background music track.")
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    target = MUSIC_DIR / f"{track_id}.wav"
    if target.is_file():
        return target
    spec = LIBRARY.get(track_id)
    if not spec:
        raise ValueError("Music file is missing.")
    if "synth" in spec:
        return _synth_loop(spec["synth"], target)
    print(f"STATUS:Downloading open-source music ({spec['name']})...", flush=True)
    try:
        req = urllib.request.Request(spec["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("Music track is too large.")
        _convert_to_wav(raw, ".ogg", target)
        (MUSIC_DIR / f"{track_id}.json").write_text(json.dumps(spec), encoding="utf-8")
        return target
    except Exception:
        # Deterministic per-track offline synth fallback so every track sounds unique even offline
        h = int(hashlib.sha256(track_id.encode()).hexdigest()[:8], 16)
        roots = (130.81, 146.83, 164.81, 174.61, 196.0, 220.0, 246.94, 261.63)
        styles = ("lofi", "pulse", "cyber", "ambient", "chip")
        progs = [
            [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],
            [(0, 3, 7, 10), (5, 8, 12, 15), (7, 10, 14, 17), (3, 7, 10, 14)],
            [(0, 7, 12), (3, 10, 15), (5, 12, 17), (2, 9, 14)],
            [(0, 4, 7, 11), (5, 9, 12, 16), (9, 12, 16, 19), (7, 11, 14, 19)],
        ]
        fallback = {
            "bpm": 76 + (h % 62),
            "root": roots[h % len(roots)],
            "chords": progs[(h // 8) % len(progs)],
            "style": styles[(h // 32) % len(styles)],
        }
        return _synth_loop(fallback, target)


def search_open_music(query: str) -> dict:
    from media import plain
    q = (query or "").strip()[:120]
    if not q:
        raise ValueError("Enter music keywords, e.g. 'lofi chill' or 'cinematic ambient'.")
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{q} filetype:audio", "gsrnamespace": 6, "gsrlimit": 10,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata",
    })
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + params, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    for page in pages:
        info = page.get("imageinfo", [{}])[0]
        url = info.get("url", "")
        size = int(info.get("size") or 0)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "upload.wikimedia.org":
            continue
        if not 50_000 <= size <= 18_000_000:
            continue
        track_id = "web_" + hashlib.sha256(url.encode()).hexdigest()[:16]
        target = MUSIC_DIR / f"{track_id}.wav"
        meta = info.get("extmetadata", {})
        title = page.get("title", "").removeprefix("File:").rsplit(".", 1)[0][:70]
        record = {
            "id": track_id,
            "name": f"{title} · Open-Source Commons",
            "author": plain(meta.get("Artist", {}).get("value", "Wikimedia Commons")),
            "license": plain(meta.get("LicenseShortName", {}).get("value", "CC / Open Source")),
            "source": info.get("descriptionurl", url),
        }
        if not target.is_file():
            dl = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(dl, timeout=25) as r:
                raw = r.read(18_000_000 + 1)
            suffix = Path(parsed.path).suffix or ".ogg"
            _convert_to_wav(raw, suffix, target)
        (MUSIC_DIR / f"{track_id}.json").write_text(json.dumps(record), encoding="utf-8")
        return {**record, "cached": True}
    raise ValueError("No matching open-source audio track found. Try simpler keywords like 'ambient' or 'piano'.")


def save_uploaded_music(content: bytes, filename: str = "music.mp3") -> dict:
    if not 100 < len(content) <= 20 * 1024 * 1024:
        raise ValueError("Audio file must be under 20 MB.")
    track_id = "custom_" + hashlib.sha256(content).hexdigest()[:16]
    suffix = Path(filename or "music.mp3").suffix or ".mp3"
    if suffix.lower() not in (".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".opus"):
        suffix = ".mp3"
    target = MUSIC_DIR / f"{track_id}.wav"
    _convert_to_wav(content, suffix, target)
    clean_name = Path(filename or "Custom music").stem[:60]
    record = {
        "id": track_id,
        "name": f"{clean_name} · Uploaded",
        "author": "Local upload",
        "license": "User provided",
        "source": "local-upload",
    }
    (MUSIC_DIR / f"{track_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return {**record, "cached": True}


def mix_bgm(voice_wav: Path, bgm_id: str, volume: int, out_wav: Path) -> Path:
    if not bgm_id or bgm_id == "none" or volume <= 0:
        return voice_wav
    bgm_wav = ensure_track(bgm_id)
    if not bgm_wav or not bgm_wav.is_file():
        return voice_wav
    with wave.open(str(voice_wav), "rb") as w:
        duration = w.getnframes() / max(1, w.getframerate())
    vol = max(0.02, min(0.8, volume / 100.0))
    fade_start = max(0.2, duration - 1.2)
    filter_complex = (
        f"[1:a]volume={vol:.3f},afade=t=out:st={fade_start:.2f}:d=1.1[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
    )
    subprocess.run(
        [tts.ffmpeg_exe(), "-y", "-loglevel", "error",
         "-i", str(voice_wav), "-stream_loop", "-1", "-i", str(bgm_wav),
         "-filter_complex", filter_complex, "-map", "[out]",
         "-ar", str(tts.RATE), "-ac", "1", "-sample_fmt", "s16", str(out_wav)],
        check=True,
    )
    return out_wav


def bgm_credit(bgm_id: str) -> str:
    if not bgm_id or bgm_id == "none":
        return ""
    spec = LIBRARY.get(bgm_id)
    if not spec:
        meta_file = MUSIC_DIR / f"{bgm_id}.json"
        if meta_file.is_file():
            spec = json.loads(meta_file.read_text(encoding="utf-8"))
    if not spec:
        return ""
    return (
        f"Background music: {spec.get('name', bgm_id)}\n"
        f"Author: {spec.get('author', 'See source')}\n"
        f"License: {spec.get('license', 'See source')}\n"
        f"{spec.get('source', '')}\n"
    )
