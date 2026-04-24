from __future__ import annotations
import csv
import io
from pathlib import Path
from .models import Carousel, Slide

_MAX_BODY  = 5   # max paragraphs per content/summary slide
_MAX_LINES = 3   # max cover title lines


def _headers() -> list[str]:
    cols = ["slide_number", "slide_type", "subtitle"]
    for i in range(1, _MAX_LINES + 1):
        cols += [f"title_line{i}", f"title_line{i}_color"]
    cols.append("title")
    for i in range(1, _MAX_BODY + 1):
        cols += [f"body{i}", f"highlight{i}", f"highlight{i}_color"]
    return cols


def _row(slide: Slide) -> dict[str, str]:
    d: dict[str, str] = {h: "" for h in _headers()}
    d["slide_number"] = str(slide.slide_number)
    d["slide_type"]   = slide.slide_type

    if slide.slide_type == "cover":
        d["subtitle"] = slide.cover_subtitle or ""
        for i, tl in enumerate(slide.cover_lines[:_MAX_LINES], 1):
            d[f"title_line{i}"]       = tl.text
            d[f"title_line{i}_color"] = tl.color
    else:
        d["title"] = slide.title.replace("\n", " ")
        for i, para in enumerate(slide.paragraphs[:_MAX_BODY], 1):
            d[f"body{i}"]              = para.text
            d[f"highlight{i}"]         = para.highlight or ""
            d[f"highlight{i}_color"]   = para.highlight_color if para.highlight else ""

    return d


def export_csv(carousel: Carousel) -> str:
    """Return UTF-8-with-BOM CSV string suitable for Canva bulk create."""
    headers = _headers()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for slide in carousel.slides:
        writer.writerow(_row(slide))
    return "﻿" + buf.getvalue()   # BOM for Excel / Canva compatibility


def save_csv(carousel: Carousel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_csv(carousel), encoding="utf-8")
