"""Draw the video frames with Pillow and pipe them to ffmpeg."""
from __future__ import annotations

import math
import subprocess
import wave
from array import array
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1920
CREAM = (244, 241, 234)
INK = (11, 11, 13)
BGS = ["#1A1A1F", "#201A1A", "#1A201C", "#1A1A1F"]

THEMES = {
    "dark": {
        "top": ["#1A1A1F", "#201A1A", "#1A201C", "#1A1A1F"],
        "bottom": ["#1A1A1F", "#201A1A", "#1A201C", "#1A1A1F"],
        "text": CREAM,
        "box": INK,
        "box_text": CREAM,
        "stroke": INK,
        "scanlines": False,
        "glow": False,
    },
    "neon": {
        "top": ["#0B0724", "#12082E", "#07152B", "#180828"],
        "bottom": ["#1C0D42", "#260B44", "#0C294A", "#240B3B"],
        "text": (245, 248, 255),
        "box": (12, 10, 28),
        "box_text": (245, 248, 255),
        "stroke": (8, 5, 20),
        "scanlines": False,
        "glow": True,
    },
    "sunset": {
        "top": ["#241023", "#2E1220", "#22122A", "#2B141C"],
        "bottom": ["#4A1F2D", "#592622", "#3E1E38", "#4D2426"],
        "text": (255, 246, 238),
        "box": (22, 10, 18),
        "box_text": (255, 246, 238),
        "stroke": (24, 10, 18),
        "scanlines": False,
        "glow": True,
    },
    "midnight": {
        "top": ["#071321", "#091A2B", "#071C24", "#0A1526"],
        "bottom": ["#0F2E44", "#10354A", "#0D3A40", "#122B46"],
        "text": (238, 247, 252),
        "box": (7, 17, 28),
        "box_text": (238, 247, 252),
        "stroke": (5, 14, 22),
        "scanlines": False,
        "glow": True,
    },
    "minimal": {
        "top": ["#F7F5F0", "#F3F1EC", "#F5F6F8", "#F7F5F0"],
        "bottom": ["#E9E5DC", "#E4E0D8", "#E6E9EE", "#E9E5DC"],
        "text": (20, 20, 24),
        "box": (24, 24, 28),
        "box_text": (248, 246, 242),
        "stroke": (255, 255, 255),
        "scanlines": False,
        "glow": False,
    },
    "retro": {
        "top": ["#151418", "#18141A", "#131716", "#181515"],
        "bottom": ["#262028", "#2B1E24", "#1C2624", "#28211C"],
        "text": (246, 239, 220),
        "box": (16, 14, 18),
        "box_text": (246, 239, 220),
        "stroke": (10, 8, 12),
        "scanlines": True,
        "glow": False,
    },
}

ASSETS = Path(__file__).parent / "assets" / "fonts"
HEAD_FONTS = [
    ASSETS / "Anton-Regular.ttf",
    Path("C:/Windows/Fonts/impact.ttf"),
    Path("/System/Library/Fonts/Supplemental/Impact.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
BODY_FONTS = [
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
FONT_PRESETS = {
    "impact": {"head": HEAD_FONTS, "body": BODY_FONTS},
    "modern": {
        "head": [Path("C:/Windows/Fonts/bahnschrift.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf"), *HEAD_FONTS],
        "body": [Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/bahnschrift.ttf"), *BODY_FONTS],
    },
    "tech": {
        "head": [Path("C:/Windows/Fonts/consolab.ttf"), Path("C:/Windows/Fonts/consola.ttf"), *HEAD_FONTS],
        "body": [Path("C:/Windows/Fonts/consolab.ttf"), Path("C:/Windows/Fonts/consola.ttf"), *BODY_FONTS],
    },
    "editorial": {
        "head": [Path("C:/Windows/Fonts/georgiab.ttf"), Path("C:/Windows/Fonts/palab.ttf"), *HEAD_FONTS],
        "body": [Path("C:/Windows/Fonts/georgiab.ttf"), Path("C:/Windows/Fonts/timesbd.ttf"), *BODY_FONTS],
    },
    "playful": {
        "head": [Path("C:/Windows/Fonts/comicbd.ttf"), Path("C:/Windows/Fonts/segoeprb.ttf"), *HEAD_FONTS],
        "body": [Path("C:/Windows/Fonts/comicbd.ttf"), Path("C:/Windows/Fonts/segoescb.ttf"), *BODY_FONTS],
    },
    "clean": {
        "head": [Path("C:/Windows/Fonts/trebucbd.ttf"), Path("C:/Windows/Fonts/verdanab.ttf"), *HEAD_FONTS],
        "body": [Path("C:/Windows/Fonts/verdanab.ttf"), Path("C:/Windows/Fonts/trebucbd.ttf"), *BODY_FONTS],
    },
}


def load_font(candidates, size: int):
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_out_back(x: float) -> float:
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * ((x - 1) ** 3) + c1 * ((x - 1) ** 2)


def _blend_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _make_theme_bg(theme_name: str, index: int, accent: tuple[int, int, int]) -> Image.Image:
    spec = THEMES.get(theme_name, THEMES["dark"])
    top = hex_to_rgb(spec["top"][index % len(spec["top"])])
    bottom = hex_to_rgb(spec["bottom"][index % len(spec["bottom"])])
    if top == bottom and not spec["scanlines"] and not spec["glow"]:
        return Image.new("RGB", (W, H), top)
    strip = Image.new("RGB", (1, H))
    px = strip.load()
    for y in range(H):
        px[0, y] = _blend_rgb(top, bottom, y / (H - 1))
    bg = strip.resize((W, H), Image.Resampling.BILINEAR)
    if spec["glow"]:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for radius, alpha in ((520, 22), (340, 28), (190, 24)):
            od.ellipse((W // 2 - radius, 340 - radius, W // 2 + radius, 340 + radius),
                       fill=(accent[0], accent[1], accent[2], alpha))
        bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    if spec["scanlines"]:
        draw = ImageDraw.Draw(bg)
        for y in range(0, H, 6):
            draw.line((0, y, W, y), fill=(8, 8, 10), width=1)
    return bg


# ---------- mascot (original character, drawn in code) ----------

def _quad(p0, c, p1, n=24):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1]
        pts.append((x, y))
    return pts


def _star_points(cx: float, cy: float, r: float, inner: float = .45):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    return pts


def _heart_points(cx: float, cy: float, r: float):
    pts = []
    for i in range(28):
        t = i / 28 * 2 * math.pi
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 17, cy + y * r / 17))
    return pts


@lru_cache(maxsize=512)
def draw_mascot(pose: str, accent, width: int = 560, mouth: int = 0,
                blink: bool = False, color: str = "#F4F1EA",
                style: str = "round", accessory: str = "none", eyes: str = "round",
                body_color: str | None = None, cheeks: bool = False,
                antenna: str = "ball") -> Image.Image:
    ss = 2  # draw large, then shrink for smooth edges
    sc = width * ss / 120
    img = Image.new("RGBA", (int(120 * sc), int(140 * sc)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = hex_to_rgb(body_color) if body_color else accent
    GOLD = (255, 205, 60)
    PINK = (255, 105, 155)
    TEAR = (90, 195, 255)
    RED = (235, 55, 70)

    def P(x, y):
        return (x * sc, y * sc)

    lw = int(4 * sc)
    # body and arms (pose-driven gestures)
    d.rounded_rectangle([*P(40, 87), *P(80, 132)], radius=12 * sc, fill=body, outline=INK, width=lw)
    if pose in ("excited", "mindblown"):
        d.line([P(42, 98), P(22, 82), P(16, 68)], fill=color, width=lw * 2, joint="curve")
        d.line([P(78, 98), P(98, 82), P(104, 68)], fill=color, width=lw * 2, joint="curve")
    elif pose == "shocked":
        d.line([P(42, 98), P(24, 86), P(26, 68)], fill=color, width=lw * 2, joint="curve")
        d.line([P(78, 98), P(96, 86), P(94, 68)], fill=color, width=lw * 2, joint="curve")
    elif pose == "thinking":
        d.line([P(42, 100), P(27, 115), P(20, 108)], fill=color, width=lw * 2, joint="curve")
        d.line([P(78, 100), P(88, 96), P(68, 82)], fill=color, width=lw * 2, joint="curve")
    elif pose == "angry":
        d.line([P(42, 100), P(24, 98), P(28, 88)], fill=color, width=lw * 2, joint="curve")
        d.line([P(78, 100), P(96, 98), P(92, 88)], fill=color, width=lw * 2, joint="curve")
    else:
        d.line([P(42, 100), P(27, 115), P(20, 108)], fill=color, width=lw * 2, joint="curve")
        hand_y = 95 if pose in ("happy", "surprised", "wink", "laugh", "love") else 118
        d.line([P(78, 100), P(95, hand_y), P(102, hand_y - 8)], fill=color, width=lw * 2, joint="curve")
    d.ellipse([*P(54, 102), *P(66, 114)], fill=CREAM)
    if accessory == "bowtie":
        for sign in (-1, 1):
            d.polygon([P(60, 92), P(60 + sign * 15, 84), P(60 + sign * 15, 100)], fill=RED, outline=INK, width=max(2, lw // 2))
        d.ellipse([*P(56, 88), *P(64, 96)], fill=(190, 40, 60), outline=INK, width=max(2, lw // 2))

    # antenna
    if antenna == "ball":
        d.line([P(60, 22), P(60, 10)], fill=CREAM, width=lw)
        cx, cy = P(60, 8)
        r = 5 * sc
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    elif antenna == "double":
        for ax, tilt in ((48, -8), (72, 8)):
            d.line([P(ax, 24), P(ax + tilt, 9)], fill=CREAM, width=lw)
            cx, cy = P(ax + tilt, 7)
            r = 4 * sc
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    elif antenna == "bolt":
        d.polygon([P(62, 2), P(54, 14), P(60, 14), P(56, 24), P(68, 10), P(61, 10)], fill=GOLD, outline=INK, width=max(2, lw // 2))

    # ears behind the head
    if style == "cat":
        d.polygon([P(20, 38), P(22, 8), P(45, 27)], fill=color, outline=INK, width=lw)
        d.polygon([P(100, 38), P(98, 8), P(75, 27)], fill=color, outline=INK, width=lw)
        d.polygon([P(25, 32), P(26, 16), P(38, 27)], fill=(255, 170, 185))
        d.polygon([P(95, 32), P(94, 16), P(82, 27)], fill=(255, 170, 185))
    elif style == "bunny":
        for ex in (38, 82):
            d.ellipse([*P(ex - 9, 0), *P(ex + 9, 42)], fill=color, outline=INK, width=lw)
            d.ellipse([*P(ex - 4, 6), *P(ex + 4, 34)], fill=(255, 170, 185))
    elif style == "bear":
        for ex in (24, 96):
            d.ellipse([*P(ex - 12, 14), *P(ex + 12, 38)], fill=color, outline=INK, width=lw)
            d.ellipse([*P(ex - 6, 20), *P(ex + 6, 32)], fill=(255, 170, 185))

    # head
    if style == "square":
        d.rounded_rectangle([*P(16, 22), *P(104, 94)], radius=14 * sc, fill=color, outline=INK, width=lw)
    else:
        d.ellipse([*P(16, 22), *P(104, 94)], fill=color, outline=INK, width=lw)
    if style == "bear":
        d.ellipse([*P(48, 60), *P(72, 82)], fill=(235, 225, 205))

    # pose-driven eye overrides
    eff_eyes = eyes
    if pose == "love":
        eff_eyes = "heart"
    elif pose == "laugh":
        eff_eyes = "happy"
    elif pose in ("shocked", "mindblown"):
        eff_eyes = "wide"
    elif pose == "wink":
        eff_eyes = "wink"
    elif pose == "excited" and eyes == "round":
        eff_eyes = "star"

    for index, ex in enumerate((46, 74)):
        x, y = P(ex, 54)
        closed = blink and eff_eyes in ("round", "wide", "star", "wink")
        if eff_eyes == "wink" and index == 1:
            closed = True
        if closed:
            d.line([P(ex - 6, 54), P(ex + 6, 54)], fill=INK, width=lw)
        elif eff_eyes == "heart":
            d.polygon(_heart_points(x, y, 9.5 * sc), fill=PINK, outline=INK, width=max(2, lw // 2))
        elif eff_eyes == "happy":
            d.arc([x - 8 * sc, y - 7 * sc, x + 8 * sc, y + 9 * sc], 180, 360, fill=INK, width=lw)
        elif eff_eyes == "sleepy":
            d.ellipse([x - 7 * sc, y - 7 * sc, x + 7 * sc, y + 7 * sc], fill=INK)
            d.rectangle([x - 9 * sc, y - 9 * sc, x + 9 * sc, y - 1 * sc], fill=color)
            d.line([P(ex - 8, 53), P(ex + 8, 53)], fill=INK, width=lw)
        elif eff_eyes == "star":
            d.polygon(_star_points(x, y, 9 * sc), fill=GOLD, outline=INK, width=max(2, lw // 2))
        elif eff_eyes == "wide":
            d.ellipse([x - 10 * sc, y - 10 * sc, x + 10 * sc, y + 10 * sc], fill=CREAM, outline=INK, width=max(2, lw // 2))
            d.ellipse([x - 6 * sc, y - 6 * sc, x + 6 * sc, y + 6 * sc], fill=INK)
            hx, hy = P(ex + 2, 51)
            d.ellipse([hx - 2 * sc, hy - 2 * sc, hx + 2 * sc, hy + 2 * sc], fill=CREAM)
        else:
            d.ellipse([x - 7 * sc, y - 7 * sc, x + 7 * sc, y + 7 * sc], fill=INK)
            hx, hy = P(ex + 2, 52)
            d.ellipse([hx - 2 * sc, hy - 2 * sc, hx + 2 * sc, hy + 2 * sc], fill=CREAM)

    # pose-driven eyebrows and emotion effects
    if pose == "angry":
        d.line([P(36, 40), P(53, 47)], fill=INK, width=lw)
        d.line([P(84, 40), P(67, 47)], fill=INK, width=lw)
        # red anger vein mark on upper right forehead
        d.line([P(83, 28), P(89, 34), P(95, 28)], fill=RED, width=max(2, lw // 2))
        d.line([P(83, 38), P(89, 32), P(95, 38)], fill=RED, width=max(2, lw // 2))
    elif pose in ("sad", "crying"):
        d.line([P(36, 46), P(52, 41)], fill=INK, width=lw)
        d.line([P(84, 46), P(68, 41)], fill=INK, width=lw)
        if pose == "crying":
            for ex in (46, 74):
                d.rounded_rectangle([*P(ex - 4, 60), *P(ex + 4, 84)], radius=3 * sc, fill=TEAR)
        else:
            d.ellipse([*P(34, 60), *P(41, 70)], fill=TEAR)
    elif pose in ("thinking", "confused", "smirk"):
        d.line([P(37, 44), P(53, 44)], fill=INK, width=lw)
        d.arc([*P(66, 35), *P(84, 47)], 180, 360, fill=INK, width=lw)
        if pose in ("thinking", "confused"):
            for bx, by, br in ((96, 26, 2.5), (104, 17, 3.8), (112, 7, 5.2)):
                d.ellipse([*P(bx - br, by - br), *P(bx + br, by + br)], fill=CREAM, outline=INK, width=max(2, lw // 2))
    elif pose in ("surprised", "shocked", "mindblown"):
        for ex in (46, 74):
            d.arc([*P(ex - 9, 34), *P(ex + 9, 44)], 180, 360, fill=INK, width=lw)
        if pose == "shocked":
            d.polygon([P(92, 34), P(88, 45), P(96, 45)], fill=TEAR)
            d.ellipse([*P(88, 42), *P(96, 50)], fill=TEAR)
        elif pose == "mindblown":
            for sx, sy, sr in ((26, 10, 6), (60, 3, 7), (94, 10, 6)):
                d.polygon(_star_points(*P(sx, sy), sr * sc), fill=GOLD, outline=INK, width=max(2, lw // 2))

    if cheeks or pose in ("love", "laugh", "excited"):
        for cx_ in (34, 86):
            d.ellipse([*P(cx_ - 7, 62), *P(cx_ + 7, 70)], fill=(255, 150, 170))

    # accessories on the face / head
    if accessory == "glasses":
        for ex in (46, 74):
            d.rounded_rectangle([*P(ex - 12, 43), *P(ex + 12, 65)], radius=5 * sc, outline=INK, width=lw)
        d.line([P(58, 50), P(62, 50)], fill=INK, width=lw)
    elif accessory == "sunglasses":
        for ex in (46, 74):
            d.rounded_rectangle([*P(ex - 13, 43), *P(ex + 13, 65)], radius=6 * sc, fill=INK)
            d.line([P(ex - 8, 47), P(ex - 3, 47)], fill=(120, 130, 150), width=max(2, lw // 2))
        d.line([P(58, 49), P(62, 49)], fill=INK, width=lw)
    elif accessory == "headphones":
        d.arc([*P(12, 16), *P(108, 100)], 180, 360, fill=accent, width=lw * 2)
        for x in (12, 100):
            d.rounded_rectangle([*P(x, 46), *P(x + 8, 70)], radius=3 * sc, fill=accent, outline=INK, width=lw)
    elif accessory == "crown":
        d.polygon([P(40, 28), P(40, 8), P(50, 19), P(60, 4), P(70, 19), P(80, 8), P(80, 28)], fill=GOLD, outline=INK, width=lw)
        d.ellipse([*P(57, 12), *P(63, 18)], fill=RED)
    elif accessory == "party":
        d.polygon([P(42, 28), P(78, 28), P(60, 1)], fill=accent, outline=INK, width=lw)
        for dx, dy in ((54, 20), (62, 14), (66, 23)):
            d.ellipse([*P(dx - 2, dy - 2), *P(dx + 2, dy + 2)], fill=CREAM)
        d.ellipse([*P(56, -3), *P(64, 5)], fill=GOLD, outline=INK, width=max(2, lw // 2))
    elif accessory == "cap":
        d.pieslice([*P(24, 8), *P(96, 52)], 180, 360, fill=accent, outline=INK, width=lw)
        d.rounded_rectangle([*P(56, 28), *P(106, 37)], radius=4 * sc, fill=accent, outline=INK, width=lw)
        d.ellipse([*P(57, 6), *P(63, 12)], fill=INK)

    # mouth
    if mouth:
        openness = min(8, max(0, mouth)) / 8
        d.ellipse([*P(48, 69 - openness * 2), *P(72, 73 + openness * 13)], fill=INK)
        d.ellipse([*P(54, 74 + openness * 6), *P(66, 77 + openness * 7)], fill=(255, 120, 140) if cheeks else accent)
    elif pose in ("surprised", "mindblown"):
        d.ellipse([*P(53, 68), *P(67, 82)], fill=INK)
    elif pose == "shocked":
        d.ellipse([*P(51, 66), *P(69, 86)], fill=INK)
        d.ellipse([*P(56, 76), *P(64, 84)], fill=PINK)
    elif pose in ("excited", "laugh"):
        d.pieslice([*P(46, 60), *P(74, 86)], 0, 180, fill=INK)
        d.ellipse([*P(54, 76), *P(66, 84)], fill=PINK)
    elif pose in ("sad", "crying", "angry"):
        d.line([P(*p) for p in _quad((48, 79), (60, 67), (72, 79))], fill=INK, width=lw, joint="curve")
    elif pose == "smirk":
        d.line([P(*p) for p in _quad((48, 74), (62, 77), (74, 67))], fill=INK, width=lw, joint="curve")
    elif pose == "confused":
        d.line([P(48, 74), P(54, 70), P(60, 76), P(66, 70), P(72, 74)], fill=INK, width=lw, joint="curve")
    elif pose == "thinking":
        d.line([P(52, 74), P(66, 71)], fill=INK, width=lw)
    elif pose == "flat":
        d.line([P(50, 72), P(70, 72)], fill=INK, width=lw)
    elif pose in ("happy", "love", "wink"):
        d.line([P(*p) for p in _quad((46, 68), (60, 84), (74, 68))], fill=INK, width=lw, joint="curve")
    else:  # smile
        d.line([P(*p) for p in _quad((50, 70), (60, 78), (70, 70))], fill=INK, width=lw, joint="curve")

    return img.resize((width, int(140 * width / 120)), Image.LANCZOS)


@lru_cache(maxsize=512)
def _draw_rotated_mascot(pose: str, accent, width: int, mouth: int, blink: bool,
                         color: str, style: str, accessory: str, eyes: str,
                         body_color: str | None, cheeks: bool, antenna: str,
                         angle_half_deg: int) -> Image.Image:
    base = draw_mascot(pose, accent, width, mouth, blink, color, style, accessory, eyes, body_color, cheeks, antenna)
    if angle_half_deg == 0:
        return base
    return base.rotate(angle_half_deg * 0.5, resample=Image.Resampling.BILINEAR)


# ---------- text layers ----------

def _headline_font_size(line1: str, line2: str, head_fonts=HEAD_FONTS) -> int:
    size = 190
    while size > 60:
        font = load_font(head_fonts, size)
        if max(font.getlength(line1), font.getlength(line2)) <= W - 120:
            break
        size -= 6
    return size


def _single_headline_line(text: str, font, color, stroke_color, shadow: bool = False) -> Image.Image:
    lh = int(font.size * 1.25)
    layer = Image.new("RGBA", (W, lh + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.text((66, 6), text, font=font, fill=(0, 0, 0, 140))
    d.text((60, 0), text, font=font, fill=color, stroke_width=4 if shadow else 0, stroke_fill=stroke_color)
    return layer


def headline_layer(line1: str, line2: str, accent, text_color=CREAM, stroke_color=INK, shadow: bool = False, head_fonts=HEAD_FONTS) -> Image.Image:
    size = _headline_font_size(line1, line2, head_fonts)
    font = load_font(head_fonts, size)
    lh = int(size * 1.12)
    layer = Image.new("RGBA", (W, lh * 2 + 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.text((66, 6), line1, font=font, fill=(0, 0, 0, 140))
        d.text((66, lh + 6), line2, font=font, fill=(0, 0, 0, 140))
    d.text((60, 0), line1, font=font, fill=text_color, stroke_width=4 if shadow else 0, stroke_fill=stroke_color)
    d.text((60, lh), line2, font=font, fill=accent, stroke_width=4 if shadow else 0, stroke_fill=stroke_color)
    return layer


def caption_layer(words: list[str], active: int, accent) -> Image.Image:
    size = 82
    while True:
        font = load_font(BODY_FONTS, size)
        space = font.getlength(" ")
        widths = [font.getlength(w) for w in words]
        total = sum(widths) + space * (len(words) - 1)
        if total <= W - 100 or size <= 40:
            break
        size -= 4
    layer = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = (W - total) / 2
    for i, w in enumerate(words):
        d.text((x, 30), w, font=font, fill=accent if i == active else CREAM,
               stroke_width=10, stroke_fill=INK)
        x += widths[i] + space
    return layer


def word_times(text: str, duration: float, lead: float = 0.05):
    """Spread words over the scene audio by length. Simple, but good enough for captions."""
    words = text.upper().split()
    weights = [len(w) + 2 for w in words]
    total = sum(weights)
    usable = max(duration - lead - 0.45, 0.3)  # the last 0.45 s is the pause
    t = lead
    out = []
    for w, wt in zip(words, weights):
        d = usable * wt / total
        out.append((w, t, t + d))
        t += d
    return out


def audio_levels(audio_path: Path, fps: int) -> list[float]:
    """Mouth opening follows actual PCM energy; silence closes the mouth."""
    with wave.open(str(audio_path), "rb") as audio:
        if audio.getsampwidth() != 2 or audio.getnchannels() != 1:
            raise ValueError("Mouth animation needs mono 16-bit PCM audio.")
        rate, count = audio.getframerate(), audio.getnframes()
        samples = array("h", audio.readframes(count))
    levels = []
    for frame in range(math.ceil(count / rate * fps)):
        start, end = int(frame * rate / fps), min(count, int((frame + 1) * rate / fps))
        chunk = samples[start:end]
        rms = math.sqrt(sum(sample * sample for sample in chunk) / max(1, len(chunk))) / 32768
        levels.append(rms)
    voiced = sorted(level for level in levels if level > .004)
    reference = voiced[int((len(voiced) - 1) * .85)] if voiced else 1
    return [0 if level < .004 else min(1, (level / max(.02, reference)) ** .7) for level in levels]


def prepare_scene(scene: dict, index: int, accent: str, look: dict) -> dict:
    photo = None
    credit = ""
    if scene.get("image"):
        from media import asset_path, metadata
        path = asset_path(scene["image"])
        if not path.is_file():
            raise ValueError("A scene image is missing. Find images again or remove it from the scene.")
        with Image.open(path) as source:
            photo = ImageOps.fit(source.convert("RGB"), (1100, 820), method=Image.Resampling.LANCZOS)
        info = metadata(scene["image"])
        credit = f"{info.get('author', '')} · {info.get('license', '')}"
    acc = hex_to_rgb(accent)
    theme_name = look.get("theme", "dark")
    theme = THEMES.get(theme_name, THEMES["dark"])
    font_preset = FONT_PRESETS.get(look.get("font_style", "impact"), FONT_PRESETS["impact"])
    head_fonts, body_fonts = font_preset["head"], font_preset["body"]
    shadow = theme_name != "dark"
    size = _headline_font_size(scene["line1"], scene["line2"], head_fonts)
    head_font = load_font(head_fonts, size)
    mask = Image.new("L", (940, 700))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 940, 700), radius=40, fill=255)
    avatar_img = None
    if look.get("avatar_image"):
        from media import avatar_path
        avatar_file = avatar_path(look["avatar_image"])
        if not avatar_file.is_file():
            raise ValueError("Your custom avatar image is missing. Upload it again or remove it.")
        avatar_img = Image.open(avatar_file).convert("RGBA")
    return {
        "scene": scene, "index": index, "look": look, "accent": acc, "theme": theme,
        "avatar_img": avatar_img,
        "head_fonts": head_fonts, "body_fonts": body_fonts,
        "bg": _make_theme_bg(theme_name, index, acc),
        "head": headline_layer(scene["line1"], scene["line2"], acc, theme["text"], theme["stroke"], shadow, head_fonts),
        "head_l1": _single_headline_line(scene["line1"], head_font, theme["text"], theme["stroke"], shadow),
        "head_l2": _single_headline_line(scene["line2"], head_font, acc, theme["stroke"], shadow),
        "head_lh": int(size * 1.12),
        "head_font": head_font,
        "photo": photo, "mask": mask, "credit": credit, "captions": {},
    }


def _draw_word(draw: ImageDraw.ImageDraw, x: float, y: float, word: str, font, fill,
               stroke_width: int = 0, stroke_fill=INK, glow_color=None) -> None:
    if glow_color is not None:
        for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3)):
            draw.text((x + ox, y + oy), word, font=font, fill=(*glow_color, 95))
    draw.text((x, y), word, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def _paginate_lines(lines: list[list[tuple[int, str]]], active: int, max_lines: int = 2) -> list[list[tuple[int, str]]]:
    if len(lines) <= max_lines:
        return lines
    active_row = 0
    if active >= 0:
        for r_idx, row in enumerate(lines):
            if any(idx == active for idx, _ in row):
                active_row = r_idx
                break
        else:
            if active > lines[-1][-1][0]:
                active_row = len(lines) - 1
    page_start = (active_row // max_lines) * max_lines
    return lines[page_start:page_start + max_lines]


def full_caption(text: str, active: int, accent, style: str = "box", theme: dict | None = None,
                 body_fonts=BODY_FONTS, anim: str = "highlight", beat: float = 1.0) -> Image.Image:
    theme = theme or THEMES["dark"]
    pop_boost = (1.0 + 0.20 * math.sin(min(1.0, beat) * math.pi)) if anim == "pop" else 1.0
    bounce_dy = int(-16 * math.sin(min(1.0, beat) * math.pi)) if anim == "bounce" else 0
    glow = accent if anim == "glow" else None

    if style == "karaoke":
        raw_words = text.upper().split()
        chunk_size = 3
        chunk_idx = max(0, active) // chunk_size if raw_words else 0
        start = chunk_idx * chunk_size
        chunk = raw_words[start:start + chunk_size] or raw_words[:chunk_size]
        local_active = (active - start) if 0 <= active - start < len(chunk) else -1
        if anim == "reveal" and local_active >= 0:
            chunk = chunk[:local_active + 1]
        size = 76
        while size > 40:
            font = load_font(body_fonts, size)
            total = sum(font.getlength(w) + 28 for w in chunk) + 18 * max(0, len(chunk) - 1)
            if total <= W - 140:
                break
            size -= 4
        font = load_font(body_fonts, size)
        active_font = load_font(body_fonts, int(size * pop_boost)) if pop_boost > 1.01 else font
        total = sum((active_font.getlength(w) if i == local_active else font.getlength(w)) + 28 for i, w in enumerate(chunk)) + 18 * max(0, len(chunk) - 1)
        layer = Image.new("RGBA", (W, 195), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        x = max(40.0, (W - total) / 2)
        for i, word in enumerate(chunk):
            is_act = i == local_active
            wf = active_font if is_act else font
            w_len = wf.getlength(word)
            if is_act:
                dy = bounce_dy - (wf.size - size) // 2
                if glow:
                    draw.rounded_rectangle((x - 16, 28 + dy, x + w_len + 32, 34 + dy + wf.size + 36), radius=26, fill=(*accent, 90))
                draw.rounded_rectangle((x - 10, 34 + dy, x + w_len + 26, 34 + dy + wf.size + 30), radius=22, fill=accent)
                draw.text((x + 8, 44 + dy), word, font=wf, fill=INK)
            else:
                draw.text((x + 8, 46), word, font=wf, fill=theme["text"], stroke_width=8, stroke_fill=theme["stroke"])
            x += w_len + 46
        return layer

    if style == "bold":
        size = 54
        font = load_font(body_fonts, size)
        active_font = load_font(body_fonts, int(size * pop_boost)) if pop_boost > 1.01 else font
        all_lines, line = [], []
        for index, word in enumerate(text.upper().split()):
            if line and font.getlength(" ".join(w for _, w in line) + " " + word) > W - 210:
                all_lines.append(line)
                line = []
            line.append((index, word))
        if line:
            all_lines.append(line)
        lines = _paginate_lines(all_lines, active, max_lines=2)
        if anim == "reveal" and active >= 0:
            lines = [[(i, w) for i, w in row if i <= active] for row in lines]
            lines = [row for row in lines if row] or [all_lines[0][:1]]
        height = max(1, len(lines)) * 74 + 48
        layer = Image.new("RGBA", (W, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        space_w = font.getlength(" ")
        for row, words in enumerate(lines):
            row_w = sum((active_font if idx == active else font).getlength(w) for idx, w in words) + space_w * max(0, len(words) - 1)
            x = max(55.0, (W - row_w) / 2)
            for index, word in words:
                is_act = index == active
                wf = active_font if is_act else font
                dy = (bounce_dy - (wf.size - size) // 2) if is_act else 0
                _draw_word(draw, x, 22 + row * 74 + dy, word, wf,
                           accent if is_act else theme["text"],
                           stroke_width=10, stroke_fill=theme["stroke"],
                           glow_color=glow if is_act else None)
                x += wf.getlength(word) + space_w
        return layer

    size = 48
    font = load_font(body_fonts, size)
    active_font = load_font(body_fonts, int(size * pop_boost)) if pop_boost > 1.01 else font
    all_lines, line = [], []
    for index, word in enumerate(text.split()):
        if line and font.getlength(" ".join(w for _, w in line) + " " + word) > W - 220:
            all_lines.append(line)
            line = []
        line.append((index, word))
    if line:
        all_lines.append(line)
    lines = _paginate_lines(all_lines, active, max_lines=2)
    if anim == "reveal" and active >= 0:
        lines = [[(i, w) for i, w in row if i <= active] for row in lines]
        lines = [row for row in lines if row] or [all_lines[0][:1]]
    height = max(1, len(lines)) * 62 + 66
    layer = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if style == "minimal":
        box_fill = (*theme["box"], 195)
        draw.rounded_rectangle((85, 6, W - 85, height - 6), radius=22, fill=box_fill, outline=(*accent, 140), width=2)
    else:
        draw.rounded_rectangle((65, 0, W - 65, height), radius=40, fill=theme["box"])
    space_w = font.getlength(" ")
    for row, words in enumerate(lines):
        row_w = sum((active_font if idx == active else font).getlength(w) for idx, w in words) + space_w * max(0, len(words) - 1)
        x = max(85.0, (W - row_w) / 2)
        for index, word in words:
            is_act = index == active
            wf = active_font if is_act else font
            dy = (bounce_dy - (wf.size - size) // 2) if is_act else 0
            _draw_word(draw, x, 28 + row * 62 + dy, word, wf,
                       accent if is_act else theme["box_text"],
                       glow_color=glow if is_act else None)
            x += wf.getlength(word) + space_w
    return layer


def _draw_bg_effect(frame: Image.Image, draw: ImageDraw.ImageDraw, effect: str,
                    time: float, strength: float, acc: tuple[int, int, int], mouth: float) -> None:
    if not strength or effect == "none":
        return
    soft = tuple(int(c * .38) for c in acc)
    bright = tuple(int(c * .65) for c in acc)
    if effect == "orbs":
        for i in range(12):
            x = int((i * 131 + math.sin(time * .5 * strength + i) * 35) % W)
            y = int((i * 179 - time * 32 * strength) % H)
            r = 4 + i % 4 * 3
            draw.ellipse((x - r, y - r, x + r, y + r), outline=soft, width=2)
    elif effect == "grid":
        step = 90
        offset = int((time * 42 * strength) % step)
        for x in range(0, W + step, step):
            draw.line((x, 0, x, H), fill=soft, width=1)
        for y in range(-step, H + step, step):
            draw.line((0, y + offset, W, y + offset), fill=soft, width=1)
    elif effect == "confetti":
        for i in range(18):
            x = int((i * 97 + math.sin(time * 1.1 * strength + i * 1.3) * 50) % W)
            y = int((i * 143 + time * (45 + i % 3 * 20) * strength) % H)
            r = 6 + (i % 4) * 3
            color = bright if i % 3 == 0 else soft
            if i % 3 == 0:
                draw.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], outline=color, width=2)
            elif i % 3 == 1:
                draw.line((x - r, y, x + r, y), fill=color, width=3)
                draw.line((x, y - r, x, y + r), fill=color, width=3)
            else:
                draw.ellipse((x - r // 2, y - r // 2, x + r // 2, y + r // 2), fill=color)
    elif effect == "waves":
        amp_boost = 1 + mouth * 1.4
        for band in range(3):
            base_y = 1480 + band * 70
            pts = []
            for x in range(0, W + 40, 36):
                y = base_y + math.sin(x * .009 + time * (2.2 + band * .7) * strength + band) * (18 + band * 8) * amp_boost
                pts.append((x, y))
            draw.line(pts, fill=bright if band == 1 else soft, width=4 - band)


def _paste_scaled(frame: Image.Image, layer: Image.Image, x: int, y: int, scale: float) -> None:
    scale = max(0.05, min(2.0, scale))
    if abs(scale - 1.0) < 0.01:
        frame.paste(layer, (x, y), layer)
        return
    nw, nh = max(1, int(layer.width * scale)), max(1, int(layer.height * scale))
    resized = layer.resize((nw, nh), Image.Resampling.BILINEAR)
    ox = x + (layer.width - nw) // 2
    oy = y + (layer.height - nh) // 2
    frame.paste(resized, (ox, oy), resized)


def _draw_headline(frame: Image.Image, prepared: dict, time: float, strength: float, text_anim: str) -> None:
    if not strength or text_anim == "slide":
        entrance = ease_out(min(time / .45, 1)) if strength else 1
        head = prepared["head"]
        frame.paste(head, (0, int(110 + (1 - entrance) * 140)), head)
        return

    l1, l2, lh = prepared["head_l1"], prepared["head_l2"], prepared["head_lh"]
    speed = 0.42 / max(0.5, min(1.5, strength))
    if text_anim in ("pop", "split", "zoom") and time >= speed + 0.14:
        frame.paste(prepared["head"], (0, 110), prepared["head"])
        return

    if text_anim == "pop":
        s1 = ease_out_back(min(time / speed, 1))
        s2 = ease_out_back(min(max(0.0, time - 0.12) / speed, 1))
        _paste_scaled(frame, l1, 0, 110, max(0.1, s1))
        if time > 0.10:
            _paste_scaled(frame, l2, 0, 110 + lh, max(0.1, s2))
    elif text_anim == "split":
        e1 = ease_out(min(time / speed, 1))
        e2 = ease_out(min(max(0.0, time - 0.08) / speed, 1))
        frame.paste(l1, (int((1 - e1) * -420), 110), l1)
        frame.paste(l2, (int((1 - e2) * 420), 110 + lh), l2)
    elif text_anim == "zoom":
        e1 = ease_out(min(time / speed, 1))
        e2 = ease_out(min(max(0.0, time - 0.1) / speed, 1))
        _paste_scaled(frame, l1, 0, 110, 1.55 - 0.55 * e1)
        _paste_scaled(frame, l2, 0, 110 + lh, 1.55 - 0.55 * e2)
    elif text_anim == "glitch":
        e = ease_out(min(time / 0.35, 1))
        jitter = int(math.sin(time * 75) * 18 * (1 - e)) if time < 0.4 else (int(math.sin(time * 90) * 6) if int(time * 2) % 3 == 2 and (time % 0.5) < 0.08 else 0)
        if jitter:
            frame.paste(l1, (jitter, 110 - 3), l1)
            frame.paste(l2, (-jitter, 110 + lh + 3), l2)
        frame.paste(l1, (0, 110), l1)
        frame.paste(l2, (0, 110 + lh), l2)
    elif text_anim == "typewriter":
        scene, theme, acc = prepared["scene"], prepared["theme"], prepared["accent"]
        full = scene["line1"] + "\n" + scene["line2"]
        shown = max(1, int(min(1.0, time / max(0.55, speed * 1.6)) * len(full)))
        part = full[:shown]
        p1, _, p2 = part.partition("\n")
        font = prepared["head_font"]
        draw = ImageDraw.Draw(frame)
        cursor = "|" if shown < len(full) and int(time * 8) % 2 == 0 else ""
        if not p2 and "\n" not in part:
            draw.text((60, 110), p1 + cursor, font=font, fill=theme["text"])
        else:
            draw.text((60, 110), p1, font=font, fill=theme["text"])
            draw.text((60, 110 + lh), p2 + cursor, font=font, fill=acc)
    else:
        frame.paste(prepared["head"], (0, 110), prepared["head"])


def _apply_transition(prev: Image.Image, curr: Image.Image, progress: float, mode: str, acc: tuple[int, int, int]) -> Image.Image:
    p = ease_out(progress)
    if mode == "none":
        return curr
    if mode == "slide_left":
        dx = int(W * p)
        out = Image.new("RGB", (W, H))
        out.paste(prev, (-dx, 0))
        out.paste(curr, (W - dx, 0))
        return out
    if mode == "slide_up":
        dy = int(H * p)
        out = Image.new("RGB", (W, H))
        out.paste(prev, (0, -dy))
        out.paste(curr, (0, H - dy))
        return out
    if mode == "zoom_in":
        scale = 1.0 + 0.14 * (1 - p)
        nw, nh = int(W / scale), int(H / scale)
        left, top = (W - nw) // 2, (H - nh) // 2
        zoomed = curr.crop((left, top, left + nw, top + nh)).resize((W, H), Image.Resampling.BILINEAR)
        return Image.blend(prev, zoomed, p)
    if mode == "flash":
        flash = Image.new("RGB", (W, H), acc)
        if progress < 0.5:
            return Image.blend(prev, flash, progress * 2)
        return Image.blend(flash, curr, (progress - 0.5) * 2)
    return Image.blend(prev, curr, p)


def compose_frame(prepared: dict, time: float, duration: float,
                  mouth: float = 0, progress: float = 0) -> Image.Image:
    look, scene, acc, theme = prepared["look"], prepared["scene"], prepared["accent"], prepared["theme"]
    motion = look.get("motion", "lively")
    strength = {"none": 0, "gentle": .4, "lively": 1, "hyper": 1.45}[motion]
    frame = prepared["bg"].copy()
    draw = ImageDraw.Draw(frame)
    _draw_bg_effect(frame, draw, look.get("bg_effect", "orbs"), time, strength, acc, mouth)
    _draw_headline(frame, prepared, time, strength, look.get("text_anim", "slide"))
    camera = look.get("camera_style", "ken_burns")
    sway_x = int(math.sin(time * 1.9) * 14 * strength) if camera == "handheld" and strength else 0
    sway_y = int(math.cos(time * 2.5) * 10 * strength) if camera == "handheld" and strength else 0
    if prepared["photo"] is not None:
        prog = min(1.0, time / max(duration, .1))
        idx_mode = prepared["index"] % 4
        if camera == "static" or not strength:
            zoom, pan_x, pan_y = 1.0, 0.5, 0.5
        elif camera == "cinema_push":
            zoom = 1.0 + 0.14 * ease_out(prog) * strength
            pan_x, pan_y = 0.5, 0.45
        elif camera == "handheld":
            zoom = 1.04 + 0.04 * math.sin(time * 1.6) * strength
            pan_x = 0.5 + 0.35 * math.sin(time * 0.9) * min(1.0, strength)
            pan_y = 0.5 + 0.35 * math.cos(time * 1.1) * min(1.0, strength)
        elif camera == "dynamic_tilt":
            zoom = 1.03 + (0.09 * prog + 0.05 * mouth) * strength
            pan_x = 0.5 + 0.3 * math.sin(time * 0.7 + prepared["index"]) * min(1.0, strength)
            pan_y = 0.5
        elif camera == "spotlight":
            zoom = 1.02 + 0.10 * math.sin(prog * math.pi) * strength
            pan_x = 0.5 + 0.25 * math.cos(prog * math.pi)
            pan_y = 0.5
        else:  # ken_burns alternating pan & zoom per scene
            if idx_mode == 0:
                zoom, pan_x, pan_y = 1.0 + 0.11 * prog * strength, 0.3 + 0.4 * prog, 0.45
            elif idx_mode == 1:
                zoom, pan_x, pan_y = 1.11 - 0.10 * prog * min(1.0, strength), 0.7 - 0.4 * prog, 0.55
            elif idx_mode == 2:
                zoom, pan_x, pan_y = 1.05 + 0.06 * prog * strength, 0.2 + 0.6 * prog, 0.5
            else:
                zoom, pan_x, pan_y = 1.02 + 0.10 * prog * strength, 0.5, 0.25 + 0.5 * prog
        zoom = max(1.0, min(1.35, zoom))
        width, height = int(1000 / zoom), int(745 / zoom)
        left = max(0, min(1100 - width, int((1100 - width) * max(0.0, min(1.0, pan_x)))))
        top = max(0, min(820 - height, int((820 - height) * max(0.0, min(1.0, pan_y)))))
        photo = prepared["photo"].crop((left, top, left + width, top + height)).resize((940, 700), Image.Resampling.BILINEAR)
        px_card = max(20, min(120, 70 + sway_x))
        py_card = 530 + sway_y
        frame.paste(photo, (px_card, py_card), prepared["mask"])
        draw.rounded_rectangle((px_card, py_card, px_card + 940, py_card + 700), radius=40, outline=acc, width=4)
        credit_font = load_font(BODY_FONTS, 23)
        credit = prepared["credit"]
        while credit and credit_font.getlength(credit) > 940:
            credit = credit[:-4] + "…" if len(credit) > 4 else ""
        draw.text((px_card, py_card + 710), credit, font=credit_font, fill=theme["text"])
    if camera == "cinema_push":
        draw.rectangle((0, 0, W, 42), fill=INK)
        draw.rectangle((0, H - 56, W, H - 14), fill=INK)
    elif camera == "spotlight":
        for pad, col_w in ((10, 2), (24, 1)):
            draw.rounded_rectangle((pad, pad, W - pad, H - 20 - pad), radius=48, outline=tuple(int(c * 0.45) for c in acc), width=col_w)
    active = -1
    word_progress = 1.0
    if strength:
        for i, (_, start, end) in enumerate(word_times(scene["voiceover"], duration)):
            if start <= time < end:
                active = i
                word_progress = (time - start) / max(0.05, end - start)
                break
    caption_style = look.get("caption_style", "box")
    caption_anim = look.get("caption_anim", "highlight") if strength else "highlight"
    beat_step = int(min(0.99, word_progress) * 5) if caption_anim in ("pop", "bounce") else 0
    cap_key = (caption_style, caption_anim, active, beat_step)
    if cap_key not in prepared["captions"]:
        beat_val = (beat_step + 0.5) / 5.0 if caption_anim in ("pop", "bounce") else 1.0
        prepared["captions"][cap_key] = full_caption(
            scene["voiceover"], active, acc, caption_style, theme,
            body_fonts=prepared["body_fonts"], anim=caption_anim, beat=beat_val,
        )
    caption = prepared["captions"][cap_key]
    base_cap_y = H - 110 - caption.height
    cap_y = base_cap_y
    if caption_anim == "slide_up" and strength:
        slide_p = ease_out(min(1.0, time / 0.35))
        cap_y += int((1.0 - slide_p) * 90)

    style = look.get("avatar_style", "round")
    custom_avatar = prepared.get("avatar_img")
    if style != "none" or custom_avatar is not None:
        width = int((320 if prepared["photo"] is not None else 500) * look.get("avatar_size", 100) / 100)
        if custom_avatar is not None:
            pulse = 1 + .05 * mouth if look.get("talking", True) and strength else 1
            ratio = custom_avatar.height / max(1, custom_avatar.width)
            cw = max(8, int(width * pulse))
            mascot = custom_avatar.resize((cw, max(8, int(cw * ratio))), Image.Resampling.BILINEAR)
            if strength:
                mascot = mascot.rotate(math.sin(time * 2.7 * min(1.3, strength)) * 3 * strength, resample=Image.Resampling.BILINEAR)
        else:
            blink = strength > 0 and (time + prepared["index"] * .4) % 3.4 > 3.23
            body_color = None if look.get("avatar_body_follow", True) else look.get("avatar_body_color")
            angle_half = round(math.sin(time * 2.7 * min(1.3, strength)) * 3 * strength * 2) if strength else 0
            mascot = _draw_rotated_mascot(
                scene.get("pose", "smile"), acc, width,
                round(mouth * 8) if look.get("talking", True) else 0,
                blink, look.get("avatar_color", "#F4F1EA"), style,
                look.get("avatar_accessory", "none"), look.get("avatar_eyes", "round"),
                body_color, bool(look.get("avatar_cheeks", False)),
                look.get("avatar_antenna", "ball"), angle_half,
            )
        position = look.get("avatar_position", "auto")
        if position == "alternate":
            position = "right" if prepared["index"] % 2 == 0 else "left"
        elif position == "roam":
            position = ("right", "left", "mid_right", "mid_left", "top_right")[prepared["index"] % 5]

        max_base_y = base_cap_y - mascot.height - 22
        default_bottom_y = min(1170 if prepared["photo"] is not None else 720, max_base_y)
        if position == "left":
            x, base_y = 45, default_bottom_y
        elif position == "right":
            x, base_y = W - width - 45, default_bottom_y
        elif position == "center":
            x, base_y = (W - width) // 2, default_bottom_y
        elif position == "mid_left":
            x, base_y = 32, min(860, max_base_y)
        elif position == "mid_right":
            x, base_y = W - width - 32, min(860, max_base_y)
        elif position == "top_left":
            x, base_y = 35, 420
        elif position == "top_right":
            x, base_y = W - width - 35, 420
        else:
            x = W - width - 45 if prepared["photo"] is not None else (W - width) // 2
            base_y = default_bottom_y

        move_mode = look.get("avatar_move", "bounce")
        dx, dy = 0, int(math.sin(time * 4 * min(1.3, strength)) * 14 * strength)
        if strength:
            if move_mode == "walk_in":
                walk_p = ease_out(min(1.0, time / 0.65))
                from_left = x < W // 2
                dx = int((1.0 - walk_p) * (-320 if from_left else 320))
                if time < 0.65:
                    dy = int(-abs(math.sin(time * 18)) * 22 * strength)
            elif move_mode == "pace":
                dx = int(math.sin(time * 1.7 * min(1.3, strength)) * 85 * min(1.2, strength))
                dy = int(-abs(math.sin(time * 5.2)) * 14 * strength)
            elif move_mode == "float":
                dx = int(math.sin(time * 1.8) * 55 * min(1.2, strength))
                dy = int(math.cos(time * 3.6) * 24 * min(1.2, strength))
            elif move_mode == "jump":
                jump_amp = 26 + 22 * mouth
                dy = int(-abs(math.sin(time * 5.8 * min(1.3, strength))) * jump_amp * min(1.25, strength))
            elif move_mode == "peek":
                peek_p = ease_out(min(1.0, time / 0.5))
                from_left = x < W // 2
                edge_offset = -int(width * 0.22) if from_left else int(width * 0.22)
                dx = edge_offset + int((1.0 - peek_p) * (-180 if from_left else 180))

        x = max(-int(width * 0.35), min(W - int(width * 0.65), x + (width - mascot.width) // 2 + dx + sway_x))
        y = min(max_base_y, base_y + dy + sway_y)
        frame.paste(mascot, (x, y), mascot)
        if strength and position not in ("top_left", "top_right"):
            shadow_y = y + int(mascot.height * .97)
            draw.ellipse((x + mascot.width * .25, shadow_y, x + mascot.width * .75, shadow_y + max(4, int(mascot.width * .05))), fill=INK)

    frame.paste(caption, (0, cap_y), caption)
    draw.rectangle((0, H - 14, max(0, min(W, int(W * progress))), H), fill=acc)
    return frame


def scene_frame(scene: dict, index: int = 0, accent: str = "#FF6B3D",
                progress: float = 0.0, look: dict | None = None) -> Image.Image:
    """Shared studio still and animated export artwork."""
    prepared = prepare_scene(scene, index, accent, look or {})
    return compose_frame(prepared, 1.2, max(2, len(scene["voiceover"].split()) / 2.6), progress=progress)


# ---------- video ----------

def render_video(scenes: list[dict], durations: list[float], audio_path: Path,
                 out_path: Path, accent: str = "#FF6B3D", fps: int = 30,
                 look: dict | None = None, preview: bool = False,
                 scene_offset: int = 0) -> None:
    import imageio_ffmpeg

    acc = hex_to_rgb(accent)
    look = look or {}
    prepared = [prepare_scene(scene, i + scene_offset, accent, look) for i, scene in enumerate(scenes)]
    levels = audio_levels(audio_path, fps)
    quality = "draft" if preview else look.get("render_quality", "hd")
    output_size = {"draft": (540, 960), "fast": (720, 1280), "hd": (W, H)}.get(quality, (W, H))
    preset = "ultrafast" if quality in ("draft", "fast") else "superfast"

    starts = [0.0]
    for d in durations:
        starts.append(starts[-1] + d)
    total = starts[-1]
    n_frames = int(round(total * fps))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mux_audio = audio_path.parent / "mix.wav"
    if not mux_audio.is_file():
        mux_audio = audio_path
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{output_size[0]}x{output_size[1]}", "-r", str(fps), "-i", "-",
        "-i", str(mux_audio),
        "-c:v", "libx264", "-preset", preset, "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    idx = 0
    previous = None
    transition = look.get("transition", "fade")
    try:
        for f in range(n_frames):
            t = f / fps
            while idx < len(scenes) - 1 and t >= starts[idx + 1]:
                previous = compose_frame(prepared[idx], durations[idx], durations[idx])
                idx += 1
            local_time = t - starts[idx]
            frame = compose_frame(prepared[idx], local_time, durations[idx],
                                  levels[f] if f < len(levels) else 0, t / total)
            if previous is not None and local_time < .28 and look.get("motion", "lively") != "none":
                frame = _apply_transition(previous, frame, local_time / .28, transition, acc)

            ImageDraw.Draw(frame).rectangle([0, H - 14, int(W * t / total), H], fill=acc)

            if output_size != (W, H):
                frame = frame.resize(output_size, Image.Resampling.BILINEAR)
            proc.stdin.write(frame.tobytes())
            if f % fps == 0:
                print(f"  frame {f}/{n_frames}", flush=True)
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed with exit code {code}")
