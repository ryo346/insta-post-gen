from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from .models import Slide, SlideItem

# ── Paths ────────────────────────────────────────────────────────────────────
_FONT_DIR = Path(__file__).parent.parent / "genjyuugothic-20150607"
FONT_HEAVY  = str(_FONT_DIR / "GenJyuuGothic-Heavy.ttf")
FONT_BOLD   = str(_FONT_DIR / "GenJyuuGothic-Bold.ttf")
FONT_MEDIUM = str(_FONT_DIR / "GenJyuuGothic-Medium.ttf")

# ── Canvas ───────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Colors ───────────────────────────────────────────────────────────────────
BG_BLUE        = (122, 170, 200)   # #7AAAC8
SHADOW_COLOR   = (88, 128, 158)    # #58809E
SHEET_WHITE    = (255, 255, 255)
FOLD_COLOR     = (205, 222, 234)   # dog-ear inner triangle
TITLE_PEACH    = (253, 224, 202)   # #FDE0CA
TEXT_BLACK     = (26,  26,  26)
HIGHLIGHT_NEG  = (82,  113, 255)   # #5271FF  negative
HIGHLIGHT_POS  = (255, 129,   0)   # #FF8100  positive
PLACEHOLDER_BG = (240, 245, 250)
PLACEHOLDER_FG = (180, 200, 215)

# ── Sheet layout ─────────────────────────────────────────────────────────────
SX, SY   = 60, 80          # sheet top-left origin
SW, SH   = 960, 1220       # sheet size
DOG      = 85              # dog-ear triangle size
SHADOW   = 10              # shadow offset (px)

# title bar (inside sheet)
TB_OFFSET_Y = 85           # from sheet top
TB_H        = 158          # title bar height
TITLE_SIZE  = 72

# checklist
ITEM_START_Y = TB_OFFSET_Y + TB_H + 68   # relative to sheet top
LINE_H       = 128
INDENT_X        = 55   # left indent inside sheet
CB_SIZE         = 40   # checkbox square size
CB_GAP          = 14   # gap between checkbox and text
ITEM_SIZE       = 46   # base item font size
ITEM_HEAVY_SIZE = 48   # highlighted word (Heavy) slightly larger
ITEM_MIN_SIZE   = 28   # floor for auto-shrink
TEXT_RIGHT_PAD  = 30   # clearance from sheet right edge

# illustration placeholder (bottom-right of sheet)
IL_W, IL_H  = 280, 280
IL_PAD      = 20           # margin from sheet edges


@lru_cache(maxsize=32)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_w(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _draw_checkbox(draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple) -> None:
    lw = max(2, size // 12)
    draw.rectangle([x, y, x + size, y + size], outline=color, width=lw)
    # checkmark: ↘ then ↗
    p1 = (x + size // 6,       y + size // 2)
    p2 = (x + size * 5 // 14,  y + size * 5 // 6)
    p3 = (x + size * 5 // 6,   y + size // 5)
    draw.line([p1, p2, p3], fill=color, width=lw + 1)


def _fit_item_size(draw: ImageDraw.Draw, item: SlideItem, max_w: int) -> int:
    """Return the largest font size where the full item text fits within max_w."""
    for size in range(ITEM_SIZE, ITEM_MIN_SIZE - 1, -2):
        fn = _font(FONT_BOLD,  size)
        fh = _font(FONT_HEAVY, size + 2)
        text = item.text
        hl   = item.highlight_text
        if not hl or hl not in text:
            total = _text_w(draw, text, fn)
        else:
            idx    = text.index(hl)
            total  = (_text_w(draw, text[:idx], fn)
                      + _text_w(draw, hl, fh)
                      + _text_w(draw, text[idx + len(hl):], fn))
        if total <= max_w:
            return size
    return ITEM_MIN_SIZE


def _draw_item_text(
    draw: ImageDraw.Draw,
    x: int,
    y: int,
    item: SlideItem,
    max_w: int,
) -> None:
    size = _fit_item_size(draw, item, max_w)
    fn   = _font(FONT_BOLD,  size)
    fh   = _font(FONT_HEAVY, size + 2)
    text = item.text
    hl   = item.highlight_text

    if not hl or hl not in text:
        draw.text((x, y), text, font=fn, fill=TEXT_BLACK)
        return

    hl_color = HIGHLIGHT_NEG if item.highlight_sentiment == "negative" else HIGHLIGHT_POS
    idx    = text.index(hl)
    before = text[:idx]
    after  = text[idx + len(hl):]

    bold_bbox  = draw.textbbox((0, 0), "あ", font=fn)
    heavy_bbox = draw.textbbox((0, 0), "あ", font=fh)
    hl_dy = (bold_bbox[3] - heavy_bbox[3]) // 2

    cur_x = x
    for seg, font, color, dy in [
        (before, fn, TEXT_BLACK,  0),
        (hl,     fh, hl_color,   hl_dy),
        (after,  fn, TEXT_BLACK,  0),
    ]:
        if seg:
            draw.text((cur_x, y + dy), seg, font=font, fill=color)
            cur_x += _text_w(draw, seg, font)


def _sheet_polygon(ox: int = 0, oy: int = 0):
    """5-point polygon for the sheet (dog-ear top-left)."""
    return [
        (SX + DOG + ox, SY + oy),
        (SX + SW  + ox, SY + oy),
        (SX + SW  + ox, SY + SH + oy),
        (SX       + ox, SY + SH + oy),
        (SX       + ox, SY + DOG + oy),
    ]


def render_slide(slide: Slide, output_path: Optional[str] = None) -> Image.Image:
    img  = Image.new("RGB", (W, H), BG_BLUE)
    draw = ImageDraw.Draw(img)

    # ── shadow ──────────────────────────────────────────────────────────────
    draw.polygon(_sheet_polygon(SHADOW, SHADOW), fill=SHADOW_COLOR)

    # ── white sheet ─────────────────────────────────────────────────────────
    draw.polygon(_sheet_polygon(), fill=SHEET_WHITE)

    # ── dog-ear fold triangle ────────────────────────────────────────────────
    fold = [
        (SX,        SY + DOG),
        (SX + DOG,  SY),
        (SX + DOG,  SY + DOG),
    ]
    draw.polygon(fold, fill=FOLD_COLOR)

    # ── title bar (peach) ────────────────────────────────────────────────────
    tb_y = SY + TB_OFFSET_Y
    draw.rectangle([SX, tb_y, SX + SW, tb_y + TB_H], fill=TITLE_PEACH)

    # ── title text (Heavy, centred) ──────────────────────────────────────────
    ft = _font(FONT_HEAVY, TITLE_SIZE)
    tb = draw.textbbox((0, 0), slide.title, font=ft)
    tx = SX + (SW - (tb[2] - tb[0])) // 2
    ty = tb_y + (TB_H - (tb[3] - tb[1])) // 2 - tb[1]
    draw.text((tx, ty), slide.title, font=ft, fill=TEXT_BLACK)

    # ── checklist items ──────────────────────────────────────────────────────
    item_x = SX + INDENT_X
    item_y = SY + ITEM_START_Y

    fn = _font(FONT_BOLD, ITEM_SIZE)

    for item in slide.items:
        cb_color = HIGHLIGHT_NEG if item.highlight_sentiment == "negative" else HIGHLIGHT_POS
        cb_y     = item_y + (ITEM_SIZE - CB_SIZE) // 2 + 4
        _draw_checkbox(draw, item_x, cb_y, CB_SIZE, cb_color)

        text_x  = item_x + CB_SIZE + CB_GAP
        max_w   = (SX + SW - TEXT_RIGHT_PAD) - text_x
        _draw_item_text(draw, text_x, item_y, item, max_w)

        item_y += LINE_H

    # ── illustration placeholder (bottom-right of sheet) ────────────────────
    il_x = SX + SW - IL_W - IL_PAD
    il_y = SY + SH - IL_H - IL_PAD
    draw.rectangle([il_x, il_y, il_x + IL_W, il_y + IL_H], fill=PLACEHOLDER_BG)

    hint_text = slide.illustration_hint or "illustration"
    fh_sm = _font(FONT_MEDIUM, 22)
    ht_bbox = draw.textbbox((0, 0), hint_text, font=fh_sm)
    ht_x = il_x + (IL_W - (ht_bbox[2] - ht_bbox[0])) // 2
    ht_y = il_y + (IL_H - (ht_bbox[3] - ht_bbox[1])) // 2
    draw.text((ht_x, ht_y), hint_text, font=fh_sm, fill=PLACEHOLDER_FG)

    if output_path:
        img.save(output_path, "PNG")

    return img


def render_carousel(slides: list[Slide], output_dir: str) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for slide in slides:
        p = str(out / f"slide_{slide.slide_number:02d}.png")
        render_slide(slide, p)
        paths.append(p)
    return paths
