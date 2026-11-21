"""Find scene illustrations via web image search (with Wikimedia fallback) and cache them locally."""
from __future__ import annotations

import hashlib
import html
import io
import ipaddress
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

CACHE = Path(__file__).parent / "assets" / "media"
USER_AGENT = "Clipwright/1.0 (local video studio; image search)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
BLOCKED_DOMAINS = (
    "shutterstock.com",
    "gettyimages.com",
    "istockphoto.com",
    "alamy.com",
    "dreamstime.com",
    "123rf.com",
    "depositphotos.com",
    "stock.adobe.com",
    "vecteezy.com",
    "plus.unsplash.com",
)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "get",
    "good", "how", "in", "into", "is", "it", "its", "just", "more", "now", "of",
    "on", "or", "our", "out", "so", "than", "that", "the", "their", "them", "this",
    "to", "today", "try", "up", "very", "what", "why", "with", "you", "your",
}
JUNK_HINTS = ("geograph.org.uk", "wikimedia", "wiki.png", "oologist", "book images", "scan")


def asset_path(asset_id: str) -> Path:
    if not isinstance(asset_id, str) or not re.fullmatch(r"[0-9a-f]{24}", asset_id):
        raise ValueError("Invalid image ID.")
    return CACHE / f"{asset_id}.jpg"


AVATARS = Path(__file__).parent / "assets" / "avatars"


def avatar_path(avatar_id: str) -> Path:
    if not isinstance(avatar_id, str) or not re.fullmatch(r"[0-9a-f]{24}", avatar_id):
        raise ValueError("Invalid avatar ID.")
    return AVATARS / f"{avatar_id}.png"


def save_uploaded_avatar(content: bytes) -> str:
    if len(content) > 12 * 1024 * 1024:
        raise ValueError("Avatar image is larger than 12 MB.")
    avatar_id = hashlib.sha256(content).hexdigest()[:24]
    with Image.open(io.BytesIO(content)) as source:
        if source.width * source.height > 20_000_000 or min(source.size) < 48:
            raise ValueError("Avatar image dimensions are unsupported (minimum 48 px).")
        image = ImageOps.exif_transpose(source).convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box:
        image = image.crop(box)
    image.thumbnail((800, 800))
    AVATARS.mkdir(parents=True, exist_ok=True)
    image.save(avatar_path(avatar_id), format="PNG")
    return avatar_id


def metadata(asset_id: str) -> dict:
    path = asset_path(asset_id).with_suffix(".json")
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def plain(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()[:600]


def _is_safe_public_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().strip(".")
    if host in ("localhost", "ip6-localhost") or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return False
    except ValueError:
        if "." not in host:
            return False
    return True


def _domain_blocked(url: str, source: str = "") -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    src = (source or "").lower()
    return any(host == d or host.endswith("." + d) or d in src for d in BLOCKED_DOMAINS)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in STOPWORDS}


def _score_candidate(query: str, title: str, width: int, height: int, domain: str = "") -> float:
    q_tokens = _tokens(query)
    t_tokens = _tokens(f"{title} {domain}")
    overlap = len(q_tokens & t_tokens) / max(1, len(q_tokens))
    score = overlap * 10.0
    if width and height:
        min_dim, max_dim = min(width, height), max(width, height)
        if min_dim < 250:
            score -= 5.0
        elif min_dim >= 500:
            score += 2.0
        if max_dim >= 900:
            score += 1.0
        ratio = max_dim / max(1, min_dim)
        if ratio > 2.6:
            score -= 3.5
    lower = f"{title} {domain}".lower()
    if any(hint in lower for hint in JUNK_HINTS):
        score -= 6.0
    if re.search(r"\b1[89]\d{2}\b", lower):
        score -= 3.0
    return score


def _save_image_bytes(content: bytes, asset_id: str, credit: dict, min_dim: int = 200) -> str:
    if len(content) > 12 * 1024 * 1024:
        raise ValueError("Image is larger than 12 MB.")
    with Image.open(io.BytesIO(content)) as source:
        if source.width * source.height > 20_000_000 or min(source.size) < min_dim:
            raise ValueError("Image dimensions are unsupported.")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1600, 1600))
        CACHE.mkdir(parents=True, exist_ok=True)
        target = asset_path(asset_id)
        image.save(target, quality=90)
    target.with_suffix(".json").write_text(json.dumps(credit), encoding="utf-8")
    return asset_id


def save_uploaded_image(content: bytes, filename: str = "upload.jpg") -> str:
    asset_id = hashlib.sha256(content).hexdigest()[:24]
    title = Path(filename or "upload.jpg").name[:160]
    credit = {
        "id": asset_id,
        "title": title,
        "source": "local-upload",
        "author": "Local upload",
        "license": "User provided",
        "license_url": "",
    }
    return _save_image_bytes(content, asset_id, credit, min_dim=100)


def _download_bytes(url: str, referer: str = "", timeout: int = 12) -> bytes:
    if not _is_safe_public_url(url):
        raise ValueError("Unsafe URL.")
    headers = {"User-Agent": BROWSER_UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
    if referer and _is_safe_public_url(referer):
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024:
        raise ValueError("Image too large.")
    return content


def _find_ddgs(query: str, exclude: set[str]) -> str | None:
    try:
        from ddgs import DDGS
    except ImportError:
        return None
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.images(query, safesearch="moderate", max_results=16))
    except Exception:
        return None
    candidates = []
    for item in raw_results:
        img_url = str(item.get("image") or "")
        thumb_url = str(item.get("thumbnail") or "")
        page_url = str(item.get("url") or img_url)
        source_name = str(item.get("source") or urllib.parse.urlparse(page_url).hostname or "")
        title = plain(str(item.get("title") or query))
        if not img_url and not thumb_url:
            continue
        if _domain_blocked(img_url, source_name) or _domain_blocked(page_url, source_name):
            continue
        try:
            w, h = int(item.get("width") or 0), int(item.get("height") or 0)
        except (TypeError, ValueError):
            w, h = 0, 0
        if w and h and min(w, h) < 220:
            continue
        asset_id = hashlib.sha256((img_url or thumb_url).encode()).hexdigest()[:24]
        if asset_id in exclude:
            continue
        score = _score_candidate(query, title, w, h, source_name)
        candidates.append((score, asset_id, img_url, thumb_url, page_url, title, source_name))
    candidates.sort(key=lambda row: row[0], reverse=True)
    for _, asset_id, img_url, thumb_url, page_url, title, source_name in candidates:
        target = asset_path(asset_id)
        if target.is_file() and target.with_suffix(".json").is_file():
            return asset_id
        credit = {
            "id": asset_id,
            "title": title or query,
            "source": page_url if _is_safe_public_url(page_url) else "",
            "author": source_name or "Web source",
            "license": "Web image · check source rights",
            "license_url": "",
        }
        for url in (img_url, thumb_url):
            if not url or not _is_safe_public_url(url):
                continue
            try:
                content = _download_bytes(url, referer=page_url)
                return _save_image_bytes(content, asset_id, credit)
            except Exception:
                continue
    return None


def _find_wikimedia(query: str, exclude: set[str]) -> str | None:
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1280,
    })
    request = urllib.request.Request(
        "https://commons.wikimedia.org/w/api.php?" + params, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        results = json.load(response)
    pages = list(results.get("query", {}).get("pages", {}).values())
    scored = []
    for page in pages:
        info = page.get("imageinfo", [{}])[0]
        title = page.get("title", "").removeprefix("File:")
        score = _score_candidate(query, title, int(info.get("width") or 0), int(info.get("height") or 0))
        scored.append((score, -page.get("index", 0), page))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    for _, _, page in scored:
        info = page.get("imageinfo", [{}])[0]
        url = info.get("thumburl", "")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ("upload.wikimedia.org", "thumb.wikimedia.org"):
            continue
        asset_id = hashlib.sha256(info.get("descriptionurl", url).encode()).hexdigest()[:24]
        if asset_id in exclude:
            continue
        target = asset_path(asset_id)
        if target.is_file() and target.with_suffix(".json").is_file():
            return asset_id
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as response:
                content = response.read(12 * 1024 * 1024 + 1)
            meta = info.get("extmetadata", {})
            credit = {
                "id": asset_id, "title": page["title"].removeprefix("File:"),
                "source": info.get("descriptionurl", ""),
                "author": plain(meta.get("Artist", {}).get("value", "See source")),
                "license": plain(meta.get("LicenseShortName", {}).get("value", "See source")),
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
            }
            return _save_image_bytes(content, asset_id, credit)
        except (OSError, ValueError):
            continue
    return None


def find_image(query: str, exclude: set[str]) -> str | None:
    asset_id = _find_ddgs(query, exclude)
    if asset_id:
        return asset_id
    return _find_wikimedia(query, exclude)


def build_query(topic: str, scene: dict) -> str:
    explicit = str(scene.get("image_query") or "").strip()
    if explicit:
        return explicit
    topic_words = [w for w in re.findall(r"[A-Za-z0-9.+-]+", topic or "") if w.lower() not in STOPWORDS]
    scene_text = f'{scene.get("line1", "")} {scene.get("line2", "")} {scene.get("voiceover", "")}'
    scene_words = [w for w in re.findall(r"[A-Za-z0-9.+-]+", scene_text) if len(w) > 2 and w.lower() not in STOPWORDS]
    combined: list[str] = []
    for word in topic_words[:4] + scene_words[:3]:
        if word.lower() not in {w.lower() for w in combined}:
            combined.append(word)
    return " ".join(combined[:6]) or (topic or "technology")[:60]


def collect_images(script: dict, target: int | None = None) -> list[str]:
    notes = []
    topic = str(script.get("topic") or "")
    used = {scene["image"] for scene in script["scenes"] if scene.get("image")}
    for index, scene in enumerate(script["scenes"]):
        if target is not None and index != target:
            continue
        if target is None and scene.get("image"):
            continue
        query = build_query(topic, scene)
        print(f"STATUS:Finding image for scene {index + 1}/{len(script['scenes'])}...", flush=True)
        try:
            asset_id = find_image(query, used)
            if not asset_id and len(query.split()) > 3:
                asset_id = find_image(" ".join(query.split()[:3]), used)
            if asset_id:
                scene["image"] = asset_id
                if not str(scene.get("image_query") or "").strip():
                    scene["image_query"] = query
                used.add(asset_id)
            else:
                notes.append(f"Scene {index + 1}: no matching image. Try simpler image keywords.")
        except Exception as exc:
            notes.append(f"Scene {index + 1}: image search unavailable ({exc}).")
    return notes


def credits(scenes: list[dict]) -> str:
    lines = ["Clipwright image credits", "Images may be cropped, animated, and overlaid with text.", ""]
    for index, scene in enumerate(scenes):
        if scene.get("image"):
            info = metadata(scene["image"])
            lines.extend([f"Scene {index + 1}: {info.get('title', 'Image')}",
                          f"Author: {info.get('author', 'See source')}",
                          f"License: {info.get('license', 'See source')} {info.get('license_url', '')}",
                          info.get("source", ""), ""])
    return "\n".join(lines)
