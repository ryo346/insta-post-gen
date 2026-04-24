from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SlideItem(BaseModel):
    text: str
    highlight_text: Optional[str] = None
    # negative → #5271FF blue  /  positive → #FF8100 orange
    highlight_sentiment: Literal["negative", "positive"] = "negative"


class Slide(BaseModel):
    slide_number: int
    title: str
    items: List[SlideItem] = Field(default_factory=list)
    illustration_hint: Optional[str] = None


class Carousel(BaseModel):
    theme: str
    slides: List[Slide]
