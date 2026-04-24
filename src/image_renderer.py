from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from .models import Slide, Paragraph, TitleLine
from . import illustration_generator as _ilgen

# ── Font paths ────────────────────────────────────────────────────────────────
_FONT_DIR = Path(__file__).parent.parent / "genjyuugothic-20150607"
FONT_HEAVY  = str(_FONT_DIR / "GenJyuuGothic-Heavy.ttf")
FONT_BOLD   = str(_FONT_DIR / "GenJyuuGothic-Bold.ttf")
FONT_MEDIUM = str(_FONT_DIR / "GenJyuuGothic-Medium.ttf")

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Colors ────────────────────────────────────────────────────────────────────
BG_BLUE      = (122, 170, 200)
SHADOW_COLOR = (88,  128, 158)
SHEET_WHITE  = (255, 255, 255)
FOLD_COLOR   = (205, 222, 234)
TITLE_PEACH  = (253, 224, 202)
TEXT_BLACK   = (26,  26,  26)
COLOR_ORANGE = (255, 129,   0)
COLOR_BLUE   = (82,  113, 255)
ILLUST_BG    = (242, 247, 251)
ILLUST_FG    = (180, 205, 220)
CTA_COLOR    = (140, 140, 140)

# ── Sheet ─────────────────────────────────────────────────────────────────────
SX, SY  = 60, 80
SW, SH  = 960, 1220
DOG     = 85
SHADOW  = 10
SHEET_BOTTOM = SY + SH   # 1300

# ── Title bar ─────────────────────────────────────────────────────────────────
TB_Y         = SY + DOG   # 165
TB_H_SINGLE  = 120
TB_H_DOUBLE  = 185
TITLE_SIZE_1 = 68
TITLE_SIZE_2 = 52

# ── Symmetric side padding (text & illustration) ──────────────────────────────
SIDE_PAD = 55           # left = right margin inside sheet
TEXT_MAX_W = SW - SIDE_PAD * 2   # 850 px

# ── Illustration ──────────────────────────────────────────────────────────────
IL_W = _ilgen.IL_W      # 620
IL_H = _ilgen.IL_H      # 370
IL_X = SX + (SW - IL_W) // 2   # centred horizontally

# ── Paragraph typography ──────────────────────────────────────────────────────
PARA_FONT    = 40
PARA_HEAVY   = 42
PARA_LINE_H  = 68
PARA_SPACING = 26       # extra gap between separate paragraphs

# ── Cover ────────────────────────────────────────────────────────────────────
COVER_SUB_SIZE   = 36
COVER_LINE_SIZE  = 100
COVER_LINE_MIN   = 60
COVER_LINE_GAP   = 20   # extra gap between cover lines

# ── Save CTA ──────────────────────────────────────────────────────────────────
CTA_TEXT      = "保存はここから →"
CTA_FONT_SIZE = 28
CTA_PAD       = 30      # from sheet right/bottom edge

# ── Minimum breathing room above/below content ───────────────────────────────
MIN_VPAD = 25


@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _color_for(name: str) -> tuple:
    return {"orange": COLOR_ORANGE, "blue": COLOR_BLUE, "black": TEXT_BLACK}[name]


# ── Pre-measurement helpers (no draw object needed) ───────────────────────────
def _char_w(font: ImageFont.FreeTypeFont, char: str) -> float:
    return font.getlength(char)


def _count_lines(segments: list[tuple[str, ImageFont.FreeTypeFont]], max_w: float) -> int:
    """Count how many display lines the inline segments occupy when wrapped."""
    cur_x = 0.0
    lines = 1
    for text, font in segments:
        for ch in text:
            cw = _char_w(font, ch)
            if cur_x + cw > max_w and cur_x > 0:
                lines += 1
                cur_x = cw
            else:
                cur_x += cw
    return lines


def _para_height(para: Paragraph, max_w: float) -> int:
    fn = _font(FONT_BOLD,  PARA_FONT)
    fh = _font(FONT_HEAVY, PARA_HEAVY)
    text, hl = para.text, para.highlight
    if hl and hl in text:
        idx = text.index(hl)
        segs = []
        if text[:idx]:  segs.append((text[:idx], fn))
        segs.append((hl, fh))
        if text[idx+len(hl):]: segs.append((text[idx+len(hl):], fn))
    else:
        segs = [(text, fn)]
    return _count_lines(segs, max_w) * PARA_LINE_H


def _paragraphs_total_h(paragraphs: list[Paragraph], max_w: float) -> int:
    if not paragraphs:
        return 0
    total = sum(_para_height(p, max_w) for p in paragraphs)
    total += PARA_SPACING * (len(paragraphs) - 1)
    return total


# ── Sheet base ────────────────────────────────────────────────────────────────
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
    draw.polygon([(SX, SY+DOG), (SX+DOG, SY), (SX+DOG, SY+DOG)], fill=FOLD_COLOR)


# ── Title bar ─────────────────────────────────────────────────────────────────
def _draw_title_bar(draw: ImageDraw.Draw, title: str) -> int:
    lines = title.split("\n")
    tb_h  = TB_H_DOUBLE if len(lines) > 1 else TB_H_SINGLE
    draw.rectangle([SX, TB_Y, SX + SW, TB_Y + tb_h], fill=TITLE_PEACH)

    fs = TITLE_SIZE_2 if len(lines) > 1 else TITLE_SIZE_1
    total_text_h = sum(
        draw.textbbox((0, 0), ln, font=_font(FONT_HEAVY, fs))[3]
        for ln in lines
    )
    gap = (tb_h - total_text_h) // (len(lines) + 1)
    cy  = TB_Y + gap
    for ln in lines:
        f  = _font(FONT_HEAVY, fs)
        bx = draw.textbbox((0, 0), ln, font=f)
        tx = SX + (SW - (bx[2] - bx[0])) // 2
        draw.text((tx, cy), ln, font=f, fill=TEXT_BLACK)
        cy += (bx[3] - bx[1]) + gap
    return TB_Y + tb_h


# ── Illustration ──────────────────────────────────────────────────────────────
def _draw_illustration(
    img: Image.Image,
    draw: ImageDraw.Draw,
    il_y: int,
    il_image: Optional[Image.Image],
    hint: str,
) -> None:
    if il_image is not None:
        img.paste(il_image, (IL_X, il_y))
    else:
        draw.rectangle([IL_X, il_y, IL_X + IL_W, il_y + IL_H],
                       fill=ILLUST_BG)
        lw = 2
        p  = 18
        draw.line([IL_X+p, il_y+p, IL_X+IL_W-p, il_y+IL_H-p], fill=ILLUST_FG, width=lw)
        draw.line([IL_X+IL_W-p, il_y+p, IL_X+p, il_y+IL_H-p], fill=ILLUST_FG, width=lw)
        f  = _font(FONT_MEDIUM, 22)
        tw = _font(FONT_MEDIUM, 22).getlength(hint)
        draw.text((IL_X + (IL_W - tw) // 2, il_y + IL_H // 2 - 11),
                  hint, font=f, fill=ILLUST_FG)


# ── Inline paragraph renderer ─────────────────────────────────────────────────
def _render_inline(
    draw: ImageDraw.Draw,
    x0: int, y0: int, max_w: int,
    segments: list[tuple[str, str, tuple]],
    line_h: int,
) -> int:
    fn = _font(FONT_BOLD,  PARA_FONT)
    fh = _font(FONT_HEAVY, PARA_HEAVY)
    fmap = {FONT_BOLD: fn, FONT_HEAVY: fh}
    cur_x, cur_y = float(x0), y0
    for text, fpath, color in segments:
        font = fmap[fpath]
        for ch in text:
            cw = _char_w(font, ch)
            if cur_x + cw > x0 + max_w and cur_x > x0:
                cur_x = x0
                cur_y += line_h
            draw.text((cur_x, cur_y), ch, font=font, fill=color)
            cur_x += cw
    return cur_y + line_h


def _draw_paragraphs(
    draw: ImageDraw.Draw,
    paragraphs: list[Paragraph],
    y_start: int,
    max_w: int,
) -> int:
    x   = SX + SIDE_PAD
    cur_y = y_start
    for para in paragraphs:
        text, hl = para.text, para.highlight
        if hl and hl in text:
            hl_color = COLOR_ORANGE if para.highlight_color == "orange" else COLOR_BLUE
            idx  = text.index(hl)
            segs = []
            if text[:idx]:           segs.append((text[:idx],      FONT_BOLD,  TEXT_BLACK))
            segs.append(                          (hl,              FONT_HEAVY, hl_color))
            if text[idx+len(hl):]:   segs.append((text[idx+len(hl):], FONT_BOLD, TEXT_BLACK))
        else:
            segs = [(text, FONT_BOLD, TEXT_BLACK)]
        cur_y  = _render_inline(draw, x, cur_y, max_w, segs, PARA_LINE_H)
        cur_y += PARA_SPACING
    return cur_y


# ── Save CTA ──────────────────────────────────────────────────────────────────
def _draw_save_cta(draw: ImageDraw.Draw) -> None:
    f  = _font(FONT_MEDIUM, CTA_FONT_SIZE)
    tw = f.getlength(CTA_TEXT)
    draw.text((SX + SW - tw - CTA_PAD, SHEET_BOTTOM - CTA_FONT_SIZE - CTA_PAD),
              CTA_TEXT, font=f, fill=CTA_COLOR)


# ── Slide type renderers ──────────────────────────────────────────────────────
def _draw_cover(draw: ImageDraw.Draw, slide: Slide) -> None:
    fn_sub  = _font(FONT_HEAVY, COVER_SUB_SIZE)
    fn_line = _font(FONT_HEAVY, COVER_LINE_SIZE)

    # ── Measure total content height for vertical centring ──
    sub_h = fn_sub.getbbox("あ")[3] + 20 if slide.cover_subtitle else 0

    line_heights: list[int] = []
    for tl in slide.cover_lines:
        fs = COVER_LINE_SIZE
        while fs >= COVER_LINE_MIN:
            f = _font(FONT_HEAVY, fs)
            if f.getlength(tl.text) <= SW - 80:
                break
            fs -= 4
        bb = _font(FONT_HEAVY, fs).getbbox(tl.text)
        line_heights.append((bb[3] - bb[1], fs))

    gaps         = COVER_LINE_GAP * (len(slide.cover_lines) - 1)
    content_h    = sub_h + sum(h for h, _ in line_heights) + gaps
    start_y      = SY + (SH - content_h) // 2

    # ── Draw subtitle ──
    cur_y = start_y
    if slide.cover_subtitle:
        tw = fn_sub.getlength(slide.cover_subtitle)
        draw.text((SX + (SW - tw) // 2, cur_y),
                  slide.cover_subtitle, font=fn_sub, fill=TEXT_BLACK)
        cur_y += sub_h

    # ── Draw cover lines ──
    for (lh, fs), tl in zip(line_heights, slide.cover_lines):
        f  = _font(FONT_HEAVY, fs)
        tw = f.getlength(tl.text)
        draw.text((SX + (SW - tw) // 2, cur_y),
                  tl.text, font=f, fill=_color_for(tl.color))
        cur_y += lh + COVER_LINE_GAP


def _draw_content(
    draw: ImageDraw.Draw,
    img: Image.Image,
    slide: Slide,
    il_image: Optional[Image.Image],
) -> None:
    tb_bottom  = _draw_title_bar(draw, slide.title)
    available  = SHEET_BOTTOM - tb_bottom

    IL_PARA_GAP   = 22
    para_h        = _paragraphs_total_h(slide.paragraphs, TEXT_MAX_W)
    content_h     = IL_H + IL_PARA_GAP + para_h
    vpad          = max((available - content_h) // 2, MIN_VPAD)

    il_y   = tb_bottom + vpad
    para_y = il_y + IL_H + IL_PARA_GAP

    _draw_illustration(img, draw, il_y, il_image,
                       slide.illustration_hint or "illustration")
    _draw_paragraphs(draw, slide.paragraphs, para_y, TEXT_MAX_W)
    if slide.show_save_cta:
        _draw_save_cta(draw)


def _draw_summary(
    draw: ImageDraw.Draw,
    slide: Slide,
) -> None:
    tb_bottom = _draw_title_bar(draw, slide.title)
    available = SHEET_BOTTOM - tb_bottom
    para_h    = _paragraphs_total_h(slide.paragraphs, TEXT_MAX_W)
    vpad      = max((available - para_h) // 2, MIN_VPAD)

    _draw_paragraphs(draw, slide.paragraphs, tb_bottom + vpad, TEXT_MAX_W)
    if slide.show_save_cta:
        _draw_save_cta(draw)


# ── Public API ────────────────────────────────────────────────────────────────
def render_slide(
    slide: Slide,
    illustration: Optional[Image.Image] = None,
    output_path: Optional[str] = None,
) -> Image.Image:
    img  = Image.new("RGB", (W, H), BG_BLUE)
    draw = ImageDraw.Draw(img)
    _draw_base(draw)

    if slide.slide_type == "cover":
        _draw_cover(draw, slide)
    elif slide.slide_type == "content":
        _draw_content(draw, img, slide, illustration)
    elif slide.slide_type == "summary":
        _draw_summary(draw, slide)

    if output_path:
        img.save(output_path, "PNG")
    return img


def render_carousel(
    slides: list[Slide],
    output_dir: str,
    illustrations: Optional[dict[int, Image.Image]] = None,
) -> list[str]:
    from pathlib import Path as _P
    out = _P(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for slide in slides:
        il = (illustrations or {}).get(slide.slide_number)
        p  = str(out / f"slide_{slide.slide_number:02d}.png")
        render_slide(slide, il, p)
        paths.append(p)
    return paths
