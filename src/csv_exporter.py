from __future__ import annotations
import csv
import io
from pathlib import Path
from .models import Carousel, Slide

_MAX_BODY = 4   # max paragraphs per slide


def _headers() -> list[str]:
    cols = ["slide_number", "slide_type", "header", "illustration"]
    for i in range(1, _MAX_BODY + 1):
        cols.append(f"body{i}")
    return cols


def _row(slide: Slide) -> dict[str, str]:
    d: dict[str, str] = {h: "" for h in _headers()}
    d["slide_number"] = str(slide.slide_number)
    d["slide_type"]   = slide.slide_type

    if slide.slide_type == "cover":
        subtitle = slide.cover_subtitle or ""
        lines    = "\n".join(slide.cover_lines)
        d["header"] = f"{subtitle}\n{lines}".strip() if subtitle else lines
    else:
        d["header"]       = slide.title.replace("\n", " ")
        d["illustration"] = slide.illustration_hint or ""
        for i, para in enumerate(slide.paragraphs[:_MAX_BODY], 1):
            d[f"body{i}"] = para.text

    return d


def export_csv(carousel: Carousel) -> str:
    """Return UTF-8-with-BOM CSV string suitable for Canva bulk create."""
    headers = _headers()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for slide in carousel.slides:
        writer.writerow(_row(slide))
    return "﻿" + buf.getvalue()


def save_csv(carousel: Carousel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_csv(carousel), encoding="utf-8")
