from __future__ import annotations
import json
import re
import anthropic
from .models import Carousel

_SYSTEM = """\
あなたはInstagramのカルーセル投稿を作成するコンテンツディレクターです。
教育・学習系アカウント向けに、高校生・受験生に刺さるコンテンツを生成します。
必ずJSON形式のみで応答し、説明文・コードブロックは不要です。"""

# ── 枚数指定あり ─────────────────────────────────────────────────────────────
_USER_TMPL = """\
テーマ「{theme}」で{num_slides}枚のInstagramカルーセルを作成してください。

推奨構成:
- 1枚目: 問題提起（読者の悩みを突く）
- 2〜3枚目: 原因・現状（問題の深掘り）
- 4〜{mid}枚目: 解決策・具体的方法
- {last_m1}枚目: 成果・まとめ
- {last}枚目: CTA（フォロー・保存を促す）
{extra_instructions}
以下のJSON形式で出力してください:
{schema}"""

# ── 枚数自動（AIが判断）────────────────────────────────────────────────────
_USER_AUTO_TMPL = """\
テーマ「{theme}」のInstagramカルーセルを作成してください。
テーマの深さ・指示の量・伝えるべき内容量をもとに、10〜20枚の間で最適な枚数を自分で判断してください。

推奨構成（枚数に合わせて比率を調整）:
- 冒頭1〜2枚: 問題提起（読者の悩みを突く）
- 中盤数枚: 原因・現状の深掘り → 解決策・具体的方法
- 終盤1枚: 成果・まとめ
- 最後1枚: CTA（フォロー・保存を促す）
{extra_instructions}
以下のJSON形式で出力してください:
{schema}"""

_JSON_SCHEMA = """\
{{
  "theme": "{theme}",
  "slides": [
    {{
      "slide_number": 1,
      "title": "タイトル（20文字以内）",
      "items": [
        {{
          "text": "チェックリスト本文（30文字以内）",
          "highlight_text": "textに含まれる強調部分（なければnull）",
          "highlight_sentiment": "negative または positive"
        }}
      ],
      "illustration_hint": "イラスト説明（英語、15語以内）"
    }}
  ]
}}

制約:
- スライド数は10〜20枚の範囲に収めること
- 各スライドのitemsは3〜4個
- highlight_textは必ずtextの部分文字列にすること
- highlight_sentimentは問題・不安系 → "negative", 解決・成果系 → "positive"
- titleは20文字以内"""

_REVISE_TMPL = """\
以下の既存スライドのJSONを、修正指示に従って修正してください。

## 修正指示
{instructions}

## 修正対象スライド（現在のJSON）
{current_json}

## 制約
- slide_numberは絶対に変更しないこと
- highlight_textは必ずtextの部分文字列にすること
- highlight_sentimentは"negative"または"positive"のみ
- titleは20文字以内、itemsのtextは30文字以内
- itemsは3〜4個を維持すること

## 出力形式（JSONのみ・説明文不要）
{{"slides": [修正後のスライドの配列]}}
"""


def _strip_codeblock(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _clamp_slides(carousel: Carousel) -> Carousel:
    """10〜20枚の範囲を外れたスライドをクランプする（安全策）。"""
    slides = carousel.slides[:20]
    return Carousel(theme=carousel.theme, slides=slides)


def generate_carousel(
    theme: str,
    num_slides: int | None = 10,
    instructions: str = "",
) -> Carousel:
    """
    num_slides=None のとき AI が枚数を自動決定（10〜20枚）。
    整数を渡すとその枚数で固定生成。
    """
    client = anthropic.Anthropic()
    extra = (
        f"\n追加指示（最優先で反映すること）:\n{instructions.strip()}\n"
        if instructions.strip()
        else ""
    )
    schema = _JSON_SCHEMA.format(theme=theme)

    if num_slides is None:
        content = _USER_AUTO_TMPL.format(
            theme=theme,
            extra_instructions=extra,
            schema=schema,
        )
    else:
        content = _USER_TMPL.format(
            theme=theme,
            num_slides=num_slides,
            mid=num_slides - 3,
            last=num_slides,
            last_m1=num_slides - 1,
            extra_instructions=extra,
            schema=schema,
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
    )

    raw = _strip_codeblock(response.content[0].text)
    carousel = Carousel.model_validate(json.loads(raw))
    return _clamp_slides(carousel)


def revise_carousel(
    carousel: Carousel,
    instructions: str,
    slide_numbers: list[int] | None = None,
) -> Carousel:
    """指示に従って特定スライド（またはすべて）を修正し、更新後の Carousel を返す。"""
    from .models import Slide

    client = anthropic.Anthropic()
    targets = (
        [s for s in carousel.slides if s.slide_number in slide_numbers]
        if slide_numbers
        else carousel.slides
    )

    current_json = json.dumps(
        {"slides": [s.model_dump() for s in targets]},
        ensure_ascii=False,
        indent=2,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": _REVISE_TMPL.format(
                instructions=instructions.strip(),
                current_json=current_json,
            ),
        }],
    )

    raw = _strip_codeblock(response.content[0].text)
    updated_map = {s["slide_number"]: s for s in json.loads(raw)["slides"]}

    merged = [
        Slide.model_validate(updated_map[s.slide_number])
        if s.slide_number in updated_map
        else s
        for s in carousel.slides
    ]
    return Carousel(theme=carousel.theme, slides=merged)
