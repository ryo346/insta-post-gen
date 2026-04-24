from __future__ import annotations
import hashlib
import io
import os
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image

try:
    from openai import OpenAI as _OpenAI
    _ENABLED = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    _ENABLED = False

_STYLE = (
    "Flat minimalist vector illustration, pure white background, no text, no letters, "
    "clean simple outlines, soft pastel colors, modern friendly style. "
    "Subject: {hint}"
)

# Target size for the illustration area in slides
IL_W = 620
IL_H = 370


def is_available() -> bool:
    return _ENABLED


def generate(hint: str, cache_dir: Path) -> Optional[Image.Image]:
    """Return a PIL Image for the hint, or None if generation is unavailable."""
    if not _ENABLED:
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    key  = hashlib.md5(hint.encode()).hexdigest()[:16]
    path = cache_dir / f"{key}.png"

    if path.exists():
        return _load_and_fit(Image.open(path).convert("RGB"))

    client = _OpenAI()
    resp = client.images.generate(
        model="dall-e-3",
        prompt=_STYLE.format(hint=hint),
        size="1024x1024",
        quality="standard",
        n=1,
    )
    with urllib.request.urlopen(resp.data[0].url) as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")

    img.save(path, "PNG")
    return _load_and_fit(img)


def _load_and_fit(img: Image.Image) -> Image.Image:
    """Center-crop to target aspect ratio, then resize."""
    src_w, src_h = img.size
    target_ratio  = IL_W / IL_H
    src_ratio      = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left  = (src_w - new_w) // 2
        img   = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top   = (src_h - new_h) // 2
        img   = img.crop((0, top, src_w, top + new_h))

    return img.resize((IL_W, IL_H), Image.LANCZOS)
