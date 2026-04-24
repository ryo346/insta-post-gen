from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class TitleLine(BaseModel):
    text: str
    color: Literal["black", "orange", "blue"] = "black"


class Paragraph(BaseModel):
    text: str
    highlight: Optional[str] = None
    highlight_color: Literal["orange", "blue"] = "orange"


class Slide(BaseModel):
    slide_number: int
    slide_type: Literal["cover", "content", "summary"]
    # ── cover ──────────────────────────────────────
    cover_subtitle: Optional[str] = None   # e.g. "＼成績良い人はみるな⚠️／"
    cover_lines: List[TitleLine] = Field(default_factory=list)
    # ── content / summary ──────────────────────────
    title: str = ""                        # \n で2行可
    paragraphs: List[Paragraph] = Field(default_factory=list)
    illustration_hint: Optional[str] = None
    show_save_cta: bool = False


class Carousel(BaseModel):
    theme: str
    slides: List[Slide]
