"""Download verified local GGUF models with resumable chunks and checksum verification."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request

REPO = "Qwen/Qwen2.5-7B-Instruct-GGUF"
ROOT = Path(__file__).resolve().parent / "models"
CHUNK = 16 * 1024 * 1024

CATALOG = {
    "qwen2.5-7b": {
        "name": "Qwen 2.5 7B Instruct · balanced (4.4 GB)",
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "match": "q4_k_m-",
        "expected": 2,
        "primary": "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    },
    "llama3.1-8b": {
        "name": "Llama 3.1 8B Instruct · punchy & fast (4.9 GB)",
        "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "match": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "expected": 1,
        "primary": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
    },
    "gemma2-9b": {
        "name": "Gemma 2 9B Instruct · creative writing (5.8 GB)",
        "repo": "bartowski/gemma-2-9b-it-GGUF",
        "match": "gemma-2-9b-it-Q4_K_M.gguf",
        "expected": 1,
        "primary": "gemma-2-9b-it-Q4_K_M.gguf",
    },
}


def catalog_status() -> list[dict]:
    items = []
    for key, spec in CATALOG.items():
        path = ROOT / spec["primary"]
        items.append({
            "key": key,
            "name": spec["name"],
            "path": str(path),
            "installed": path.is_file(),
        })
    return items


def download(model_key: str = "qwen2.5-7b") -> Path:
    if model_key not in CATALOG:
        raise ValueError(f"Unknown model key: {model_key}")
    spec = CATALOG[model_key]
    repo = REPO if model_key == "qwen2.5-7b" else spec["repo"]
    print(f"STATUS:Checking {spec['name']} on Hugging Face...", flush=True)
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}?blobs=true", timeout=60) as response:
        metadata = json.load(response)
    match = spec["match"]
    files = [
        f for f in metadata["siblings"]
        if (match in f["rfilename"] if spec["expected"] > 1 else f["rfilename"] == match)
    ]
    if len(files) != spec["expected"]:
        raise RuntimeError(f"Expected {spec['expected']} official GGUF file(s) for {model_key}.")
    ROOT.mkdir(exist_ok=True)
    for file in files:
        name, size = file["rfilename"], file["size"]
        destination = ROOT / name
        if destination.exists():
            with destination.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == file["lfs"]["sha256"]:
                    print(f"Already verified: {name}", flush=True)
                    continue
            raise RuntimeError(f"Existing file failed verification: {destination}")
        chunks = ROOT / (name + ".chunks")
        chunks.mkdir(exist_ok=True)
        url = f"https://huggingface.co/{repo}/resolve/{metadata['sha']}/{name}"

        def fetch(index: int) -> int:
            start, end = index * CHUNK, min(size, (index + 1) * CHUNK) - 1
            part = chunks / str(index)
            if part.exists() and part.stat().st_size == end - start + 1:
                return part.stat().st_size
            for attempt in range(4):
                try:
                    request = urllib.request.Request(
                        f"{url}?download=true&chunk={index}",
                        headers={"Range": f"bytes={start}-{end}"})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                            raise RuntimeError("Server did not return the requested byte range.")
                        with part.open("wb") as target:
                            shutil.copyfileobj(response, target, 1024 * 1024)
                    if part.stat().st_size != end - start + 1:
                        raise RuntimeError("Incomplete chunk.")
                    return part.stat().st_size
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
            return 0

        count = (size + CHUNK - 1) // CHUNK
        print(f"Downloading {name} ({size / 1e9:.2f} GB)", flush=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            completed = 0
            for length in pool.map(fetch, range(count)):
                completed += length
                pct = int(completed / max(1, size) * 100)
                print(f"  {completed / size:.0%} · {completed / 1e9:.2f}/{size / 1e9:.2f} GB", flush=True)
                print(f"STATUS:Downloading {name} · {pct}% ({completed / 1e9:.2f}/{size / 1e9:.2f} GB)", flush=True)
        partial = destination.with_suffix(".gguf.part")
        digest = hashlib.sha256()
        with partial.open("wb") as target:
            for index in range(count):
                with (chunks / str(index)).open("rb") as source:
                    while block := source.read(8 * 1024 * 1024):
                        digest.update(block)
                        target.write(block)
        if digest.hexdigest() != file["lfs"]["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {name}")
        partial.replace(destination)
        shutil.rmtree(chunks)
        print(f"Verified: {name}", flush=True)
    print("Model ready.", flush=True)
    return ROOT / spec["primary"]


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-7b"
    download(key)
