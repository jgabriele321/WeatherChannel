"""
Replicate FLUX-Schnell text-to-image helper for AI-stylized weather screens.

Cheap (~$0.003/image), fast (~5-10s), text rendering imperfect but acceptable
per the design. Returns PIL.Image or None on failure (so callers can fall back
to PIL rendering — screen never goes blank).
"""
import hashlib
import os
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent / ".env")

CACHE_DIR = Path(__file__).parent / "cache" / "styled"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "black-forest-labs/flux-schnell"


def _prompt_hash(prompt, aspect):
    h = hashlib.sha256()
    h.update(aspect.encode())
    h.update(prompt.encode())
    return h.hexdigest()[:16]


def fetch_styled(prompt, aspect_ratio="4:3", use_cache=True):
    """Generate one image from FLUX-Schnell. Returns PIL.Image (RGB) or None.

    aspect_ratio: one of "1:1", "4:3", "3:4", "16:9", "9:16", "21:9"
    use_cache: skip API call if we already have an image for this prompt+aspect
    """
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        print("  (no REPLICATE_API_TOKEN — skipping AI render)")
        return None

    cache_key = _prompt_hash(prompt, aspect_ratio)
    cache_path = CACHE_DIR / f"{cache_key}.png"
    if use_cache and cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGB")
        except Exception:
            cache_path.unlink(missing_ok=True)

    try:
        import replicate
        os.environ["REPLICATE_API_TOKEN"] = token
        print(f"  flux-schnell: {prompt[:80]}...")
        out = replicate.run(
            MODEL,
            input={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "num_outputs": 1,
                "output_format": "png",
                "go_fast": True,
                "megapixels": "1",
            },
        )
        # The replicate client returns either a list of URL strings, or
        # a list of FileOutput objects (newer versions). Handle both.
        if not out:
            return None
        first = out[0]
        if hasattr(first, "read"):
            img_bytes = first.read()
        elif isinstance(first, str):
            img_bytes = requests.get(first, timeout=30).content
        else:
            img_bytes = bytes(first)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img.save(cache_path)
        return img
    except Exception as e:
        print(f"  ! flux-schnell failed: {e}")
        return None


if __name__ == "__main__":
    # Quick smoke test
    img = fetch_styled(
        "Vintage 1990s television news weather broadcast, big bright "
        "headline showing 78 degrees Fahrenheit, sunny, vibrant blue gradient.",
        aspect_ratio="4:3",
        use_cache=False,
    )
    if img:
        out = Path("/tmp/flux-smoke.png")
        img.save(out)
        print(f"OK -> {out} ({img.size})")
    else:
        print("FAILED (no image returned)")
