from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Paragraph(BaseModel):
    text: str


class Slide(BaseModel):
    slide_number: int
    slide_type: Literal["cover", "content", "summary"]
    # ── cover ──────────────────────────────────────
    cover_subtitle: Optional[str] = None
    cover_lines: List[str] = Field(default_factory=list)
    # ── content / summary ──────────────────────────
    title: str = ""
    paragraphs: List[Paragraph] = Field(default_factory=list)
    illustration_hint: Optional[str] = None


class Carousel(BaseModel):
    theme: str
    slides: List[Slide]
