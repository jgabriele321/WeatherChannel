"""
OpenAI gpt-image-1 image-edit (img2img) helper.

Takes our PIL-rendered base image + a styling prompt, returns a stylized
PIL.Image. The base image's text/numbers stay accurate; gpt-image-1 just
restyles the look. Falls back to None on failure.

Quality "low" = ~$0.011/image, "medium" = ~$0.042, "high" = ~$0.167.
"""
import base64
import hashlib
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent / ".env")

CACHE_DIR = Path(__file__).parent / "cache" / "openai_styled"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(base_img, prompt, quality, size):
    h = hashlib.sha256()
    bio = BytesIO()
    base_img.save(bio, format="PNG")
    h.update(bio.getvalue())
    h.update(prompt.encode())
    h.update(quality.encode())
    h.update(size.encode())
    return h.hexdigest()[:16]


def fetch_edited(base_img, prompt, quality="low", size="1024x1024", use_cache=True):
    """Edit (style-transfer) `base_img` using gpt-image-1.

    base_img: PIL.Image (RGB) — the source we want stylized
    prompt:   how to restyle it
    quality:  "low" | "medium" | "high"
    size:     "1024x1024" | "1024x1536" | "1536x1024"
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("  (no OPENAI_API_KEY — skipping AI edit)")
        return None

    cache_key = _cache_key(base_img, prompt, quality, size)
    cache_path = CACHE_DIR / f"{cache_key}.png"
    if use_cache and cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGB")
        except Exception:
            cache_path.unlink(missing_ok=True)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        # Write base image as PNG to a BytesIO with .name (SDK needs a filename)
        bio = BytesIO()
        base_img.save(bio, format="PNG")
        bio.seek(0)
        bio.name = "base.png"
        print(f"  gpt-image-1 edit ({quality}): {prompt[:80]}...")
        resp = client.images.edit(
            model="gpt-image-1",
            image=bio,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        b64 = resp.data[0].b64_json
        img = Image.open(BytesIO(base64.b64decode(b64))).convert("RGB")
        img.save(cache_path)
        return img
    except Exception as e:
        print(f"  ! gpt-image-1 edit failed: {e}")
        return None


if __name__ == "__main__":
    # Smoke test: edit a tiny solid-color image
    test = Image.new("RGB", (1024, 1024), (50, 80, 200))
    out = fetch_edited(test, "Make this look like a 1995 weather TV broadcast with chunky 78 degrees text", use_cache=False)
    if out:
        out.save("/tmp/openai-edit-smoke.png")
        print(f"OK -> /tmp/openai-edit-smoke.png ({out.size})")
    else:
        print("FAILED")
