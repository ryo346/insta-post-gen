from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from .models import Slide, Paragraph, TitleLine

# ── Font paths ────────────────────────────────────────────────────────────────
_FONT_DIR = Path(__file__).parent.parent / "genjyuugothic-20150607"
FONT_HEAVY  = str(_FONT_DIR / "GenJyuuGothic-Heavy.ttf")
FONT_BOLD   = str(_FONT_DIR / "GenJyuuGothic-Bold.ttf")
FONT_MEDIUM = str(_FONT_DIR / "GenJyuuGothic-Medium.ttf")

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Colors ────────────────────────────────────────────────────────────────────
BG_BLUE       = (122, 170, 200)
SHADOW_COLOR  = (88,  128, 158)
SHEET_WHITE   = (255, 255, 255)
FOLD_COLOR    = (205, 222, 234)
TITLE_PEACH   = (253, 224, 202)
TEXT_BLACK    = (26,  26,  26)
COLOR_ORANGE  = (255, 129,   0)   # #FF8100  positive / cover line
COLOR_BLUE    = (82,  113, 255)   # #5271FF  negative / cover line
ILLUST_BG     = (242, 247, 251)
ILLUST_FG     = (180, 205, 220)
CTA_COLOR     = (140, 140, 140)

# ── Sheet geometry ────────────────────────────────────────────────────────────
SX, SY   = 60, 80
SW, SH   = 960, 1220
DOG      = 85
SHADOW   = 10

# ── Title bar ─────────────────────────────────────────────────────────────────
TB_Y         = SY + DOG          # 165
TB_H_SINGLE  = 120
TB_H_DOUBLE  = 185
TITLE_SIZE_1 = 68
TITLE_SIZE_2 = 52

# ── Content layout ────────────────────────────────────────────────────────────
IL_MARGIN_X  = 140          # horizontal inset from sheet edge
IL_GAP_TOP   = 25           # gap from title bar bottom
IL_H         = 360          # illustration height
PARA_INDENT  = 58           # left indent inside sheet
PARA_GAP     = 22           # gap between illustration/titlebar and first para
PARA_FONT    = 40
PARA_HEAVY   = 42
PARA_LINE_H  = 68
PARA_SPACING = 28           # extra gap between separate paragraphs

# ── Cover layout ─────────────────────────────────────────────────────────────
COVER_SUB_Y      = SY + 100
COVER_SUB_SIZE   = 36
COVER_LINE_START = SY + 195
COVER_LINE_H     = 135
COVER_LINE_SIZE  = 100
COVER_LINE_MIN   = 60

# ── Save CTA ──────────────────────────────────────────────────────────────────
CTA_TEXT      = "保存はここから →"
CTA_FONT_SIZE = 28


@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _tw(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _color_for(name: str) -> tuple:
    return {"orange": COLOR_ORANGE, "blue": COLOR_BLUE, "black": TEXT_BLACK}[name]


# ── Sheet drawing ─────────────────────────────────────────────────────────────
def _sheet_poly(ox: int = 0, oy: int = 0):
    return [
        (SX + DOG + ox, SY + oy),
        (SX + SW  + ox, SY + oy),
        (SX + SW  + ox, SY + SH + oy),
        (SX       + ox, SY + SH + oy),
        (SX       + ox, SY + DOG + oy),
    ]


def _draw_base(draw: ImageDraw.Draw) -> None:
    draw.polygon(_sheet_poly(SHADOW, SHADOW), fill=SHADOW_COLOR)
    draw.polygon(_sheet_poly(), fill=SHEET_WHITE)
    fold = [(SX, SY + DOG), (SX + DOG, SY), (SX + DOG, SY + DOG)]
    draw.polygon(fold, fill=FOLD_COLOR)


# ── Title bar ─────────────────────────────────────────────────────────────────
def _draw_title_bar(draw: ImageDraw.Draw, title: str) -> int:
    """Draw title bar and return y-coordinate below it."""
    lines = title.split("\n")
    tb_h = TB_H_DOUBLE if len(lines) > 1 else TB_H_SINGLE
    draw.rectangle([SX, TB_Y, SX + SW, TB_Y + tb_h], fill=TITLE_PEACH)

    fs = TITLE_SIZE_2 if len(lines) > 1 else TITLE_SIZE_1
    total_text_h = sum(
        draw.textbbox((0, 0), ln, font=_font(FONT_HEAVY, fs))[3]
        for ln in lines
    )
    line_gap = (tb_h - total_text_h) // (len(lines) + 1)
    cy = TB_Y + line_gap
    for ln in lines:
        f = _font(FONT_HEAVY, fs)
        bx = draw.textbbox((0, 0), ln, font=f)
        tx = SX + (SW - (bx[2] - bx[0])) // 2
        draw.text((tx, cy), ln, font=f, fill=TEXT_BLACK)
        cy += (bx[3] - bx[1]) + line_gap
    return TB_Y + tb_h


# ── Illustration placeholder ──────────────────────────────────────────────────
def _draw_illustration(draw: ImageDraw.Draw, hint: str, y_top: int) -> int:
    """Draw centered illustration placeholder; returns y below it."""
    x = SX + IL_MARGIN_X
    w = SW - IL_MARGIN_X * 2
    draw.rectangle([x, y_top, x + w, y_top + IL_H], fill=ILLUST_BG)
    # subtle X cross to indicate placeholder
    pad = 20
    lw = 2
    draw.line([x + pad, y_top + pad, x + w - pad, y_top + IL_H - pad],
              fill=ILLUST_FG, width=lw)
    draw.line([x + w - pad, y_top + pad, x + pad, y_top + IL_H - pad],
              fill=ILLUST_FG, width=lw)
    # hint text
    fh = _font(FONT_MEDIUM, 22)
    hw = _tw(draw, hint, fh)
    hx = x + (w - hw) // 2
    hy = y_top + IL_H // 2 - 11
    draw.text((hx, hy), hint, font=fh, fill=ILLUST_FG)
    return y_top + IL_H


# ── Paragraph renderer ────────────────────────────────────────────────────────
def _render_inline(
    draw: ImageDraw.Draw,
    x0: int, y0: int, max_w: int,
    segments: list[tuple[str, str, tuple]],   # (text, font_path, color)
    font_size_normal: int,
    font_size_heavy: int,
    line_h: int,
) -> int:
    """Render mixed-font/color segments with character-level line wrapping.
    Returns y position of line after the last rendered line."""
    fn = _font(FONT_BOLD,  font_size_normal)
    fh = _font(FONT_HEAVY, font_size_heavy)
    font_map = {FONT_BOLD: fn, FONT_HEAVY: fh}

    cur_x, cur_y = x0, y0
    for text, fpath, color in segments:
        font = font_map[fpath]
        for char in text:
            cw = _tw(draw, char, font)
            if cur_x + cw > x0 + max_w and cur_x > x0:
                cur_x = x0
                cur_y += line_h
            draw.text((cur_x, cur_y), char, font=font, fill=color)
            cur_x += cw
    return cur_y + line_h


def _draw_paragraphs(
    draw: ImageDraw.Draw,
    paragraphs: list[Paragraph],
    y_start: int,
    max_w: int,
) -> int:
    x = SX + PARA_INDENT
    cur_y = y_start
    for para in paragraphs:
        text = para.text
        hl   = para.highlight
        if hl and hl in text:
            hl_color = COLOR_ORANGE if para.highlight_color == "orange" else COLOR_BLUE
            idx    = text.index(hl)
            before = text[:idx]
            after  = text[idx + len(hl):]
            segments = []
            if before: segments.append((before, FONT_BOLD,  TEXT_BLACK))
            segments.append((hl,     FONT_HEAVY, hl_color))
            if after:  segments.append((after,  FONT_BOLD,  TEXT_BLACK))
        else:
            segments = [(text, FONT_BOLD, TEXT_BLACK)]

        cur_y = _render_inline(
            draw, x, cur_y, max_w, segments,
            PARA_FONT, PARA_HEAVY, PARA_LINE_H,
        )
        cur_y += PARA_SPACING
    return cur_y


# ── Save CTA ──────────────────────────────────────────────────────────────────
def _draw_save_cta(draw: ImageDraw.Draw) -> None:
    f = _font(FONT_MEDIUM, CTA_FONT_SIZE)
    tw = _tw(draw, CTA_TEXT, f)
    x = SX + SW - tw - 30
    y = SY + SH - CTA_FONT_SIZE - 30
    draw.text((x, y), CTA_TEXT, font=f, fill=CTA_COLOR)


# ── Slide type renderers ──────────────────────────────────────────────────────
def _draw_cover(draw: ImageDraw.Draw, slide: Slide) -> None:
    # Optional subtitle
    if slide.cover_subtitle:
        f = _font(FONT_HEAVY, COVER_SUB_SIZE)
        tw = _tw(draw, slide.cover_subtitle, f)
        draw.text((SX + (SW - tw) // 2, COVER_SUB_Y),
                  slide.cover_subtitle, font=f, fill=TEXT_BLACK)

    # Large title lines (auto-shrink to fit width)
    cur_y = COVER_LINE_START
    max_line_w = SW - 80
    for line in slide.cover_lines:
        fs = COVER_LINE_SIZE
        while fs >= COVER_LINE_MIN:
            f = _font(FONT_HEAVY, fs)
            if _tw(draw, line.text, f) <= max_line_w:
                break
            fs -= 4
        f = _font(FONT_HEAVY, fs)
        tw = _tw(draw, line.text, f)
        draw.text((SX + (SW - tw) // 2, cur_y),
                  line.text, font=f, fill=_color_for(line.color))
        bb = draw.textbbox((0, 0), line.text, font=f)
        cur_y += (bb[3] - bb[1]) + COVER_LINE_H - COVER_LINE_SIZE


def _draw_content(draw: ImageDraw.Draw, slide: Slide) -> None:
    tb_bottom = _draw_title_bar(draw, slide.title)
    il_y = tb_bottom + IL_GAP_TOP
    il_hint = slide.illustration_hint or "illustration"
    para_y = _draw_illustration(draw, il_hint, il_y) + PARA_GAP
    max_w = SW - PARA_INDENT - 30
    _draw_paragraphs(draw, slide.paragraphs, para_y, max_w)
    if slide.show_save_cta:
        _draw_save_cta(draw)


def _draw_summary(draw: ImageDraw.Draw, slide: Slide) -> None:
    tb_bottom = _draw_title_bar(draw, slide.title)
    para_y = tb_bottom + 50
    max_w = SW - PARA_INDENT - 30
    _draw_paragraphs(draw, slide.paragraphs, para_y, max_w)
    if slide.show_save_cta:
        _draw_save_cta(draw)


# ── Public API ────────────────────────────────────────────────────────────────
def render_slide(slide: Slide, output_path: Optional[str] = None) -> Image.Image:
    img  = Image.new("RGB", (W, H), BG_BLUE)
    draw = ImageDraw.Draw(img)
    _draw_base(draw)

    if slide.slide_type == "cover":
        _draw_cover(draw, slide)
    elif slide.slide_type == "content":
        _draw_content(draw, slide)
    elif slide.slide_type == "summary":
        _draw_summary(draw, slide)

    if output_path:
        img.save(output_path, "PNG")
    return img


def render_carousel(slides: list[Slide], output_dir: str) -> list[str]:
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for slide in slides:
        p = str(out / f"slide_{slide.slide_number:02d}.png")
        render_slide(slide, p)
        paths.append(p)
    return paths
