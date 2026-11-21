"""Write a short-video script with a local language model (llama-cpp-python)."""
from __future__ import annotations

import json
import os
import random
import re
import sysconfig
import time
from pathlib import Path

POSES = {
    "smile", "happy", "excited", "surprised", "shocked", "angry", "sad", "crying",
    "thinking", "smirk", "laugh", "wink", "love", "confused", "mindblown", "flat",
}
VIBES = ("tech", "hype", "chill", "story", "spooky", "playful")

VIBE_KEYWORDS = {
    "tech": {"ai", "code", "coding", "agent", "agents", "cyber", "robot", "software", "tech", "data", "gpu", "claude", "gpt", "llm", "python", "computer", "laptop", "app", "hack", "developer", "test", "tests", "bug", "algorithm", "digital"},
    "spooky": {"horror", "dark", "ghost", "scary", "creepy", "mystery", "crime", "shadow", "nightmare", "dead", "haunted", "curse", "danger", "fear", "thriller", "monster", "alien"},
    "chill": {"calm", "chill", "study", "relax", "peace", "nature", "sleep", "coffee", "morning", "mindful", "focus", "lofi", "ambient", "gentle", "breathe", "meditation", "cozy"},
    "playful": {"funny", "joke", "meme", "cat", "dog", "bunny", "pet", "kid", "game", "gaming", "play", "party", "food", "cook", "cute", "fun", "cartoon", "laugh"},
    "story": {"history", "story", "ancient", "war", "king", "queen", "empire", "book", "legend", "myth", "origin", "spider", "spiderman", "hero", "journey", "life", "lesson", "learn", "learning", "education", "school", "science"},
    "hype": {"fast", "best", "win", "money", "viral", "trend", "secret", "upgrade", "power", "insane", "crazy", "boost", "growth", "success", "ultimate"},
}

VIBE_PROFILES = {
    "tech": {
        "label": "Tech & Cyber",
        "themes": ["neon", "midnight", "dark"],
        "fonts": ["tech", "modern", "clean"],
        "bg_effects": ["grid", "waves", "orbs"],
        "text_anims": ["glitch", "typewriter", "split", "zoom"],
        "caption_styles": ["karaoke", "box", "minimal"],
        "caption_anims": ["glow", "pop", "highlight", "reveal"],
        "transitions": ["slide_left", "zoom_in", "flash", "fade"],
        "motions": ["lively", "hyper"],
        "tone": "Hyped", "rate": 185,
        "accents": ["#00E5FF", "#38BDF8", "#818CF8", "#34D399", "#A855F7"],
        "bgm": ["synth_cyber", "synth_pulse", "km_unity", "km_stratosphere", "km_liftmotif", "km_dreamculture"],
        "kokoro_voices": ["af_heart", "am_michael", "bf_emma", "am_adam"],
        "edge_voices": ["en-US-BrianNeural", "en-US-GuyNeural", "en-US-AriaNeural", "en-GB-RyanNeural"],
        "avatar_styles": ["cat", "square", "round"],
        "avatar_accessories": ["headphones", "glasses", "sunglasses"],
        "avatar_eyes": ["wide", "round", "wink"],
        "avatar_antennas": ["bolt", "double", "ball"],
        "avatar_colors": ["#70CFFF", "#E0F2FE", "#C4B5FD", "#A7F3D0"],
        "cheeks": False,
    },
    "spooky": {
        "label": "Dark Mystery",
        "themes": ["dark", "retro", "midnight"],
        "fonts": ["editorial", "impact", "tech"],
        "bg_effects": ["waves", "orbs"],
        "text_anims": ["glitch", "zoom", "typewriter"],
        "caption_styles": ["bold", "box", "karaoke"],
        "caption_anims": ["glow", "reveal", "slide_up"],
        "transitions": ["fade", "flash", "zoom_in"],
        "motions": ["gentle", "lively"],
        "tone": "Deadpan", "rate": 165,
        "accents": ["#EF4444", "#F97316", "#A855F7", "#E11D48"],
        "bgm": ["km_horroriffic", "km_ghostdance", "km_sugarplum", "km_therule", "km_relent"],
        "kokoro_voices": ["bm_george", "am_adam", "bf_isabella", "bm_lewis"],
        "edge_voices": ["en-GB-RyanNeural", "en-US-BrianNeural", "en-GB-SoniaNeural"],
        "avatar_styles": ["cat", "round", "square"],
        "avatar_accessories": ["sunglasses", "glasses", "crown"],
        "avatar_eyes": ["wide", "sleepy", "round"],
        "avatar_antennas": ["bolt", "double"],
        "avatar_colors": ["#E2E8F0", "#DDD6FE", "#FECDD3"],
        "cheeks": False,
    },
    "chill": {
        "label": "Chill & Calm",
        "themes": ["minimal", "midnight", "sunset"],
        "fonts": ["clean", "modern", "editorial"],
        "bg_effects": ["orbs", "waves"],
        "text_anims": ["slide", "typewriter"],
        "caption_styles": ["minimal", "box"],
        "caption_anims": ["highlight", "slide_up", "reveal"],
        "transitions": ["fade", "slide_up"],
        "motions": ["gentle", "lively"],
        "tone": "Calm", "rate": 155,
        "accents": ["#2DD4BF", "#60A5FA", "#F59E0B", "#34D399", "#818CF8"],
        "bgm": ["synth_lofi", "synth_ambient", "km_cleansoul", "km_calmant", "km_dreamculture", "km_autumnday", "km_winter", "km_resignation", "km_snowdrop"],
        "kokoro_voices": ["af_heart", "bf_emma", "af_sarah", "bm_george"],
        "edge_voices": ["en-US-EmmaNeural", "en-US-AvaNeural", "en-GB-SoniaNeural", "en-PH-RosaNeural"],
        "avatar_styles": ["bunny", "bear", "round", "cat"],
        "avatar_accessories": ["headphones", "glasses", "none"],
        "avatar_eyes": ["happy", "sleepy", "round"],
        "avatar_antennas": ["ball", "none"],
        "avatar_colors": ["#F4F1EA", "#FDE68A", "#BFDBFE", "#FBCFE8"],
        "cheeks": True,
    },
    "playful": {
        "label": "Fun & Playful",
        "themes": ["sunset", "minimal", "neon"],
        "fonts": ["playful", "modern", "impact"],
        "bg_effects": ["confetti", "orbs", "waves"],
        "text_anims": ["pop", "split", "zoom"],
        "caption_styles": ["karaoke", "bold"],
        "caption_anims": ["bounce", "pop", "glow"],
        "transitions": ["slide_up", "zoom_in", "slide_left"],
        "motions": ["lively", "hyper"],
        "tone": "Hyped", "rate": 185,
        "accents": ["#FF6B3D", "#EC4899", "#FACC15", "#22C55E", "#38BDF8"],
        "bgm": ["km_carefree", "km_parisian", "km_schmetterling", "synth_chip", "km_smoothermove", "km_earlyriser"],
        "kokoro_voices": ["af_bella", "af_heart", "am_michael", "bf_emma"],
        "edge_voices": ["en-US-AriaNeural", "en-US-AvaNeural", "en-US-GuyNeural", "en-PH-JamesNeural", "en-PH-RosaNeural"],
        "avatar_styles": ["bunny", "bear", "cat"],
        "avatar_accessories": ["party", "crown", "sunglasses", "cap", "bowtie"],
        "avatar_eyes": ["star", "happy", "wink", "wide"],
        "avatar_antennas": ["ball", "bolt", "none"],
        "avatar_colors": ["#FFD6E8", "#FEF08A", "#BBF7D0", "#BAE6FD"],
        "cheeks": True,
    },
    "story": {
        "label": "Story & Explainer",
        "themes": ["sunset", "retro", "midnight", "dark"],
        "fonts": ["editorial", "impact", "modern"],
        "bg_effects": ["orbs", "waves", "confetti"],
        "text_anims": ["slide", "split", "typewriter", "zoom"],
        "caption_styles": ["bold", "box", "karaoke"],
        "caption_anims": ["highlight", "pop", "reveal", "slide_up"],
        "transitions": ["fade", "slide_left", "zoom_in"],
        "motions": ["lively", "gentle"],
        "tone": "Hyped", "rate": 175,
        "accents": ["#F97316", "#EAB308", "#EF4444", "#3B82F6", "#10B981"],
        "bgm": ["km_sovereign", "km_enchanted", "km_reachingout", "km_theendless", "km_sonatina", "km_tinyfugue", "km_windswept"],
        "kokoro_voices": ["bm_george", "am_adam", "bf_emma", "af_heart", "bm_lewis"],
        "edge_voices": ["en-US-BrianNeural", "en-GB-RyanNeural", "en-US-AvaNeural", "en-PH-JamesNeural"],
        "avatar_styles": ["round", "bear", "cat", "square"],
        "avatar_accessories": ["crown", "cap", "glasses", "bowtie"],
        "avatar_eyes": ["wide", "round", "star"],
        "avatar_antennas": ["ball", "double", "none"],
        "avatar_colors": ["#F4F1EA", "#FDE68A", "#E2E8F0", "#FED7AA"],
        "cheeks": False,
    },
    "hype": {
        "label": "High-Energy Hype",
        "themes": ["neon", "sunset", "dark"],
        "fonts": ["impact", "modern"],
        "bg_effects": ["waves", "confetti", "grid"],
        "text_anims": ["zoom", "pop", "split", "glitch"],
        "caption_styles": ["karaoke", "bold"],
        "caption_anims": ["pop", "bounce", "glow"],
        "transitions": ["slide_left", "slide_up", "zoom_in", "flash"],
        "motions": ["hyper", "lively"],
        "tone": "Hyped", "rate": 185,
        "accents": ["#FF6B3D", "#00E5FF", "#F43F5E", "#A855F7", "#FACC15"],
        "bgm": ["km_unity", "synth_pulse", "km_liftmotif", "km_earlyriser", "km_windswept", "synth_cyber"],
        "kokoro_voices": ["af_heart", "am_michael", "af_bella"],
        "edge_voices": ["en-US-GuyNeural", "en-US-AriaNeural", "en-US-AvaNeural", "en-US-BrianNeural"],
        "avatar_styles": ["cat", "round", "bunny", "square"],
        "avatar_accessories": ["sunglasses", "headphones", "crown", "cap"],
        "avatar_eyes": ["star", "wide", "wink"],
        "avatar_antennas": ["bolt", "double", "ball"],
        "avatar_colors": ["#70CFFF", "#FFE9A8", "#F9A8D4", "#A7F3D0"],
        "cheeks": True,
    },
}


def detect_vibe(topic: str, scenes: list[dict], model_vibe: str | None = None) -> str:
    blob = " ".join([
        topic or "",
        *(f"{s.get('line1', '')} {s.get('line2', '')} {s.get('voiceover', '')} {s.get('image_query', '')}" for s in scenes),
    ]).lower()
    words = set(re.findall(r"[a-z0-9]+", blob))
    scores = {v: len(words & kw) * 2 for v, kw in VIBE_KEYWORDS.items()}
    if model_vibe in VIBE_PROFILES:
        scores[model_vibe] = scores.get(model_vibe, 0) + 1
    best_vibe, best_score = max(scores.items(), key=lambda item: item[1])
    return best_vibe if best_score > 0 else (model_vibe if model_vibe in VIBE_PROFILES else "hype")


def direct_style(topic: str, scenes: list[dict], tts_engine: str = "kokoro", model_vibe: str | None = None) -> dict:
    vibe = detect_vibe(topic, scenes, model_vibe)
    prof = VIBE_PROFILES[vibe]
    accent = random.choice(prof["accents"])
    voice = ""
    if tts_engine == "kokoro":
        voice = random.choice(prof["kokoro_voices"])
    elif tts_engine == "edge":
        voice = random.choice(prof["edge_voices"])
    return {
        "vibe": vibe,
        "vibe_label": prof["label"],
        "theme": random.choice(prof["themes"]),
        "font_style": random.choice(prof["fonts"]),
        "bg_effect": random.choice(prof["bg_effects"]),
        "text_anim": random.choice(prof["text_anims"]),
        "caption_style": random.choice(prof["caption_styles"]),
        "caption_anim": random.choice(prof["caption_anims"]),
        "transition": random.choice(prof["transitions"]),
        "motion": random.choice(prof["motions"]),
        "camera_style": random.choice(["ken_burns", "cinema_push", "handheld", "dynamic_tilt", "spotlight"]),
        "tone": prof["tone"],
        "rate": prof["rate"],
        "accent": accent,
        "bgm": random.choice(prof["bgm"]),
        "bgm_volume": random.choice([16, 18, 20, 22]),
        "voice": voice,
        "avatar_style": random.choice(prof["avatar_styles"]),
        "avatar_accessory": random.choice(prof["avatar_accessories"]),
        "avatar_eyes": random.choice(prof["avatar_eyes"]),
        "avatar_antenna": random.choice(prof["avatar_antennas"]),
        "avatar_color": random.choice(prof["avatar_colors"]),
        "avatar_position": random.choice(["auto", "alternate", "roam", "right", "left"]),
        "avatar_move": random.choice(["bounce", "walk_in", "pace", "float", "jump"]),
        "avatar_body_follow": True,
        "avatar_cheeks": prof["cheeks"],
    }

# Used by `python main.py demo` so the pipeline can be tested without any model.
DEMO_SCRIPT = {
    "topic": "Why AI coding agents keep breaking tests",
    "scenes": [
        {"line1": "YOUR AI AGENT", "line2": "BREAKS TESTS",
         "voiceover": "Your AI agent keeps breaking tests. Here is why.", "pose": "surprised"},
        {"line1": "IT SKIPS", "line2": "THE ERROR",
         "voiceover": "It guesses a fix without reading the error message.", "pose": "flat"},
        {"line1": "GIVE IT ONE", "line2": "FAILING TEST",
         "voiceover": "Hand it a single failing test and ask for the smallest change.", "pose": "smile"},
        {"line1": "SMALL STEPS", "line2": "SHIP FASTER",
         "voiceover": "Small steps, fewer surprises. Follow for more.", "pose": "happy"},
    ],
}

SYSTEM = (
    "You are an elite short-form video scriptwriter for viral TikTok, Reels, and YouTube Shorts explainers. "
    "Return JSON only. Write with a clear, high-retention narrative arc across the scenes:\n"
    "- Scene 1 (THE HOOK): Open with a scroll-stopping tension, surprising fact, or sharp problem statement. Never start with a dry textbook definition.\n"
    "- Scene 2 (THE STAKES): Show why the old way fails or why this topic matters right now.\n"
    "- Middle Scenes (THE BREAKDOWN): Each scene MUST reveal a new, specific angle, mechanism, real-world example, or turning point from the topic/notes. "
    "NEVER repeat the same idea across multiple scenes, and NEVER start two scenes with the same opening words.\n"
    "- Final Scene (THE PAYOFF & CTA): Land a memorable takeaway or thought-provoking question that sparks comments.\n\n"
    "Rules for every scene:\n"
    "- line1 and line2: A punchy 2-4 word visual headline split across two lines (UPPERCASE, max 18 characters per line, complete words only, no trailing prepositions like 'NOT' or 'FOR').\n"
    "- voiceover: 1 to 2 natural, conversational spoken sentences (13 to 22 words) that sound great read aloud with rhythm and contractions. Avoid stiff corporate repetition.\n"
    "- pose: One of smile, happy, excited, surprised, shocked, angry, sad, crying, thinking, smirk, laugh, wink, love, confused, mindblown, flat (pick a vivid, distinct expression that matches each scene's emotion!).\n"
    "- image_query: ONE concrete 3-6 word English web-search phrase for a specific photo or screenshot (e.g. 'data analytics dashboard on laptop', 'students using tablets in classroom'). Never write comma-separated lists or repeat the exact same image_query in two scenes.\n"
    "Ground all facts in the user's notes and web research notes. Do not invent fake statistics or quotes."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line1": {"type": "string"},
                    "line2": {"type": "string"},
                    "voiceover": {"type": "string"},
                    "pose": {"type": "string", "enum": sorted(POSES)},
                    "image_query": {"type": "string"},
                },
                "required": ["line1", "line2", "voiceover", "pose", "image_query"],
            },
        }
    },
    "required": ["scenes"],
}

REVISE_SYSTEM = (
    "You are an expert short-form vertical video script editor and storytelling director. "
    "You receive the current video topic, tone, speaking rate (words per minute), "
    "estimated duration, current scenes JSON, and the user's edit instruction. "
    "Return JSON only with 'summary' (1 short sentence explaining what you changed) and 'scenes'. "
    "Make every scene flow naturally as a cohesive story: Scene 1 is a scroll-stopping hook, middle scenes each advance a distinct point without repeating earlier sentences or opening words, and the final scene lands a strong payoff. "
    "Each scene has: line1 and line2 (punchy 2-4 word UPPERCASE headline, max 18 characters per line, complete words only); "
    "voiceover (1-2 natural, conversational spoken sentences, 13-24 words, spoken by a narrator); "
    "pose (one of: smile, happy, excited, surprised, shocked, angry, sad, crying, thinking, smirk, laugh, wink, love, confused, mindblown, flat — vary across scenes); "
    "image_query (ONE concrete 3-6 word English web-search query for an accurate photo or screenshot matching BOTH the topic and this scene's point; never use comma-separated lists). "
    "If the user asks for a target duration (e.g. '30 seconds'), adjust the number of scenes (1-12) and word count "
    "so total_words * 60 / rate + 0.45 * num_scenes matches the requested length. "
    "Do not invent fake statistics or quotes."
)

REVISE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "scenes": SCHEMA["properties"]["scenes"],
    },
    "required": ["summary", "scenes"],
}


def estimate_duration(scenes: list[dict], rate: int = 185) -> int:
    total = sum(len(str(s.get("voiceover", "")).split()) * 60 / max(100, rate) + 0.45 for s in scenes)
    return max(1, round(total))


def _target_plan(instruction: str, current_count: int, rate: int = 185) -> tuple[int | None, int | None, int | None]:
    """Return (target_seconds, target_scenes, words_per_scene) if the instruction asks for a length change."""
    lower = instruction.lower()
    secs: int | None = None
    m_sec = re.search(r"\b(\d{1,3})\s*(?:s|sec|secs|second|seconds)\b", lower)
    m_min = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\b", lower)
    if m_sec:
        secs = max(8, min(90, int(m_sec.group(1))))
    elif m_min:
        secs = max(15, min(90, round(float(m_min.group(1)) * 60)))
    elif "longer" in lower or "expand" in lower:
        scenes = min(12, max(current_count + 2, 6))
        return None, scenes, 15
    elif "shorter" in lower or "condense" in lower or "brief" in lower:
        scenes = max(2, current_count - 1)
        return None, scenes, 11
    if secs is None:
        return None, None, None
    target_scenes = max(2, min(12, round(secs / 5)))
    speaking = max(4.0, secs - 0.45 * target_scenes)
    words_per_scene = max(10, min(24, round((speaking * max(100, rate) / 60.0) / target_scenes)))
    return secs, target_scenes, words_per_scene


def _merge_revised_scenes(old_scenes: list[dict], new_scenes: list[dict], target_index: int | None = None) -> list[dict]:
    if target_index is not None and 0 <= target_index < len(old_scenes):
        replacement = dict(new_scenes[0])
        old = old_scenes[target_index]
        if old.get("image") and replacement.get("image_query", "").strip().lower() == str(old.get("image_query", "")).strip().lower():
            replacement["image"] = old["image"]
        merged = [dict(s) for s in old_scenes]
        merged[target_index] = replacement
        return merged[:12]

    by_query = {
        str(s.get("image_query", "")).strip().lower(): s["image"]
        for s in old_scenes
        if s.get("image") and str(s.get("image_query", "")).strip()
    }
    merged = []
    for idx, scene in enumerate(new_scenes[:12]):
        item = dict(scene)
        q = item.get("image_query", "").strip().lower()
        if q and q in by_query:
            item["image"] = by_query[q]
        elif idx < len(old_scenes) and old_scenes[idx].get("image") and q == str(old_scenes[idx].get("image_query", "")).strip().lower():
            item["image"] = old_scenes[idx]["image"]
        merged.append(item)
    return merged


DANGLING_WORDS = {"A", "AN", "THE", "AND", "OR", "BUT", "NOR", "FOR", "OF", "IN", "ON", "TO", "WITH", "BY", "AT", "FROM", "AS", "NOT"}


def _fit_headline(text: str, limit: int = 24) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip().upper()
    words = [w for w in cleaned.split(" ") if w]
    kept: list[str] = []
    for word in words:
        candidate = " ".join([*kept, word])
        if len(candidate) <= limit:
            kept.append(word)
        else:
            break
    while len(kept) > 1 and kept[-1].strip(".,!?:;-'\"") in DANGLING_WORDS:
        kept.pop()
    return " ".join(kept) if kept else cleaned[:limit]


def _clean_image_query(raw_query: str, topic: str, line1: str, line2: str, seen_queries: set[str]) -> str:
    # Take the first concrete clause if the model output comma/semicolon-separated phrases
    first_clause = re.split(r"[,;|/]+", str(raw_query or ""))[0]
    cleaned = re.sub(r"\s+", " ", first_clause).strip()
    if not cleaned:
        cleaned = re.sub(r"\s+", " ", f"{topic.splitlines()[0][:50]} {line1} {line2}").strip()
    words = cleaned.split()
    if len(words) > 8:
        cleaned = " ".join(words[:7])
    key = cleaned.lower()
    if key in seen_queries:
        extra = " ".join(w for w in f"{line1} {line2}".lower().split() if len(w) > 2 and w not in key)[:30].strip()
        if extra:
            cleaned = f"{cleaned} {extra}".strip()
    seen_queries.add(cleaned.lower())
    return cleaned[:160]


def clean(data: dict, topic: str) -> dict:
    scenes = []
    seen_queries: set[str] = set()
    seen_vo: set[str] = set()
    pose_cycle = ["shocked", "thinking", "excited", "smirk", "mindblown", "happy", "surprised", "laugh"]
    for idx, s in enumerate(data.get("scenes", [])):
        vo = re.sub(r"\s+", " ", str(s.get("voiceover", ""))).strip()
        if not vo:
            continue
        vo_key = re.sub(r"[^a-z0-9]+", "", vo.lower())
        if vo_key in seen_vo and len(data.get("scenes", [])) > 2:
            continue
        seen_vo.add(vo_key)
        line1 = _fit_headline(s.get("line1", ""), 24)
        line2 = _fit_headline(s.get("line2", ""), 24)
        if not line1 and not line2:
            words = re.sub(r"[^\w\s]", "", vo).upper().split()
            line1, line2 = _fit_headline(" ".join(words[:2]), 24), _fit_headline(" ".join(words[2:4]), 24)
        pose = s.get("pose") if s.get("pose") in POSES else pose_cycle[idx % len(pose_cycle)]
        img_q = _clean_image_query(s.get("image_query", ""), topic, line1, line2, seen_queries)
        scenes.append({"line1": line1, "line2": line2, "voiceover": vo, "pose": pose,
                       "image_query": img_q})
    if not scenes:
        raise ValueError("The model returned no usable scenes. Try again or edit script.json by hand.")
    return {"topic": topic, "scenes": scenes[:12]}


def _load_llm(model_path: str, n_gpu_layers: int = 0, n_ctx: int = 4096):
    # Windows wheels need the CUDA runtime DLLs installed by NVIDIA's pip packages.
    if os.name == "nt":
        for directory in (Path(sysconfig.get_paths()["purelib"]) / "nvidia").glob("*/bin"):
            os.add_dll_directory(str(directory))
            os.environ["PATH"] = str(directory) + os.pathsep + os.environ["PATH"]
    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise SystemExit(
            "llama-cpp-python is not installed. Run: pip install -r requirements-llm.txt"
        ) from e
    return Llama(model_path=str(model_path), n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False)


def web_research(query: str, max_results: int = 5) -> list[dict]:
    """Fetch recent web search snippets via ddgs so the local LLM has up-to-date facts."""
    q = re.sub(r"\s+", " ", (query or "").strip())[:200]
    if not q:
        return []
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    rows: list[dict] = []
    for backend in ("google,yahoo", "auto"):
        try:
            with DDGS(timeout=15) as ddgs:
                rows = list(ddgs.text(q, max_results=max_results, backend=backend))
            if rows:
                break
        except Exception:
            continue
    results = []
    for row in rows:
        title = str(row.get("title") or "").strip()[:140]
        body = str(row.get("body") or row.get("snippet") or "").strip()[:260]
        url = str(row.get("href") or row.get("url") or "").strip()
        if title or body:
            results.append({"title": title, "snippet": body, "url": url})
    return results


def format_research(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["Web research notes (use these facts; do not invent claims):"]
    for i, item in enumerate(results[:5], 1):
        lines.append(f"{i}. {item['title']}: {item['snippet']}")
    return "\n".join(lines)[:1800]


def _count_prompt_tokens(llm, messages: list[dict]) -> int:
    raw = "\n".join(str(m.get("content", "")) for m in messages).encode("utf-8", errors="ignore")
    try:
        return len(llm.tokenize(raw)) + len(messages) * 4
    except Exception:
        return max(1, len(raw) // 4)


def _stream_completion(llm, messages: list[dict], schema: dict, max_tokens: int, stage_label: str) -> tuple[str, dict]:
    prompt_tokens = _count_prompt_tokens(llm, messages)
    t0 = time.perf_counter()
    print(f"STATUS:{stage_label} · 0 gen + {prompt_tokens} prompt = {prompt_tokens} tokens", flush=True)
    try:
        stream = llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object", "schema": schema},
            temperature=0.72,
            top_p=0.9,
            repeat_penalty=1.15,
            max_tokens=max_tokens,
            stream=True,
        )
    except TypeError:
        stream = llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object", "schema": schema},
            temperature=0.72,
            max_tokens=max_tokens,
        )
    if isinstance(stream, dict):
        text = stream["choices"][0]["message"]["content"]
        usage = stream.get("usage", {})
        out_tok = int(usage.get("completion_tokens") or max(1, len(text) // 4))
        p_tok = int(usage.get("prompt_tokens") or prompt_tokens)
        elapsed = max(0.05, time.perf_counter() - t0)
        tps = round(out_tok / elapsed, 1)
        stats = {"prompt_tokens": p_tok, "output_tokens": out_tok, "total_tokens": p_tok + out_tok, "tok_per_sec": tps}
        print(f"STATUS:{stage_label} · {out_tok} gen + {p_tok} prompt = {p_tok + out_tok} tokens ({tps} tok/s)", flush=True)
        return text, stats

    pieces: list[str] = []
    output_tokens = 0
    last_print = t0
    for chunk in stream:
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        if delta:
            pieces.append(delta)
            output_tokens += 1
            now = time.perf_counter()
            if output_tokens % 4 == 0 or (now - last_print) >= 0.22:
                last_print = now
                elapsed = max(0.05, now - t0)
                tps = output_tokens / elapsed
                total = prompt_tokens + output_tokens
                print(
                    f"STATUS:{stage_label} · {output_tokens} gen + {prompt_tokens} prompt = {total} tokens ({tps:.1f} tok/s)",
                    flush=True,
                )
    elapsed = max(0.05, time.perf_counter() - t0)
    tps = round(output_tokens / elapsed, 1)
    total = prompt_tokens + output_tokens
    print(f"STATUS:{stage_label} · {output_tokens} gen + {prompt_tokens} prompt = {total} tokens ({tps} tok/s)", flush=True)
    return "".join(pieces), {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "tok_per_sec": tps,
    }


def generate_script(topic: str, model_path: str, n_scenes: int = 6,
                     n_gpu_layers: int = 0, n_ctx: int = 4096,
                     web_search: bool = False, tts_engine: str = "kokoro") -> dict:
    sources: list[dict] = []
    research_block = ""
    clean_topic = re.sub(r"\s+", " ", (topic or "").split("Voiceover tone:")[0]).strip()
    if web_search:
        print("STATUS:Searching the web for up-to-date facts...", flush=True)
        sources = web_research(clean_topic[:140])
        research_block = format_research(sources)
    n_scenes = max(1, min(12, n_scenes))
    llm = _load_llm(model_path, n_gpu_layers, n_ctx)
    user_prompt = (
        f"Topic & notes:\n{topic}\n\n"
        f"Write a cohesive, high-retention {n_scenes}-scene vertical video script:\n"
        f"- Scene 1: Scroll-stopping hook (tension, surprising truth, or bold question).\n"
        f"- Scenes 2 to {max(2, n_scenes - 1)}: Each scene must cover a distinct angle, mechanism, or proof point without repeating earlier sentences or starting with the same words.\n"
        f"- Scene {n_scenes}: Memorable takeaway or call to action.\n"
        f"- Voiceover length: 13 to 22 natural spoken words per scene."
    )
    if research_block:
        user_prompt = f"{user_prompt}\n\n{research_block}"
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    schema = json.loads(json.dumps(SCHEMA))
    schema["properties"]["scenes"]["minItems"] = n_scenes
    schema["properties"]["scenes"]["maxItems"] = n_scenes
    last_err = None
    for _ in range(2):
        text, token_stats = _stream_completion(llm, messages, schema, max(900, n_scenes * 160), "🔥 Cooking script")
        try:
            parsed = json.loads(text)
            result = clean(parsed, topic)
            result["token_stats"] = token_stats
            result["direction"] = direct_style(topic, result["scenes"], tts_engine, parsed.get("vibe"))
            if sources:
                result["sources"] = [{"title": s["title"], "url": s["url"]} for s in sources if s.get("url")]
            return result
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise SystemExit(f"Could not get a valid script from the model: {last_err}")


def revise_script(
    topic: str,
    scenes: list[dict],
    instruction: str,
    model_path: str,
    rate: int = 185,
    tone: str = "Hyped",
    history: list[dict] | None = None,
    target_index: int | None = None,
    n_gpu_layers: int = 0,
    n_ctx: int = 4096,
    web_search: bool = False,
) -> dict:
    sources: list[dict] = []
    research_block = ""
    if web_search:
        print("STATUS:Searching the web for up-to-date facts...", flush=True)
        sources = web_research(f"{topic} {instruction}"[:180])
        research_block = format_research(sources)
    llm = _load_llm(model_path, n_gpu_layers, n_ctx)
    print("STATUS:Revising your script...", flush=True)
    compact_scenes = [
        {
            "index": i + 1,
            "line1": s.get("line1", ""),
            "line2": s.get("line2", ""),
            "voiceover": s.get("voiceover", ""),
            "pose": s.get("pose", "smile"),
            "image_query": s.get("image_query", ""),
        }
        for i, s in enumerate(scenes)
    ]
    est = estimate_duration(scenes, rate)
    schema = json.loads(json.dumps(REVISE_SCHEMA))
    if target_index is not None and 0 <= target_index < len(scenes):
        scope_note = f"Edit ONLY scene {target_index + 1} and return a 'scenes' array with exactly 1 revised scene."
        schema["properties"]["scenes"]["minItems"] = 1
        schema["properties"]["scenes"]["maxItems"] = 1
    else:
        target_secs, target_scenes, words_per_scene = _target_plan(instruction, len(scenes), rate)
        if target_scenes is not None:
            dur_text = f" (~{target_secs} seconds total)" if target_secs else ""
            scope_note = (
                f"You MUST return EXACTLY {target_scenes} scenes{dur_text}, "
                f"with about {words_per_scene} spoken words per scene voiceover, "
                f"and a concrete 3-5 word image_query for every scene."
            )
            schema["properties"]["scenes"]["minItems"] = target_scenes
            schema["properties"]["scenes"]["maxItems"] = target_scenes
        else:
            scope_note = (
                "Return the full revised 'scenes' array (1 to 12 scenes), "
                "and make sure every scene has a concrete 3-5 word image_query."
            )
    messages = [{"role": "system", "content": REVISE_SYSTEM}]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        text = str(turn.get("text", "")).strip()
        if role in ("user", "assistant") and text:
            messages.append({"role": role, "content": text[:600]})
    research_section = f"\n\n{research_block}" if research_block else ""
    messages.append({
        "role": "user",
        "content": (
            f"Topic: {topic}\n"
            f"Tone: {tone} | Speaking rate: {rate} WPM | Current duration: ~{est}s ({len(scenes)} scenes)\n"
            f"Current scenes:\n{json.dumps(compact_scenes, ensure_ascii=False)}\n\n"
            f"Edit instruction: {instruction}\n"
            f"{scope_note}{research_section}"
        ),
    })
    last_err = None
    for _ in range(2):
        text, token_stats = _stream_completion(llm, messages, schema, 1600, "🔥 Cooking revision")
        try:
            parsed = json.loads(text)
            cleaned = clean(parsed, topic)
            merged = _merge_revised_scenes(scenes, cleaned["scenes"], target_index)
            summary = str(parsed.get("summary", "")).strip()[:300] or "Updated your script."
            result = {"topic": topic, "scenes": merged, "summary": summary, "token_stats": token_stats}
            if sources:
                result["sources"] = [{"title": s["title"], "url": s["url"]} for s in sources if s.get("url")]
            return result
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise SystemExit(f"Could not revise the script: {last_err}")
