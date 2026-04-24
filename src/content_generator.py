from __future__ import annotations
import json
import re
import anthropic
from .models import Carousel

_SYSTEM = """\
あなたはInstagramのカルーセル投稿を作成するコンテンツディレクターです。
教育・学習系アカウント向けに、高校生・受験生に刺さるコンテンツを生成します。
必ずJSON形式のみで応答し、説明文・コードブロックは不要です。"""

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
- 各スライドのitemsは3〜4個
- highlight_textは必ずtextの部分文字列にすること
- highlight_sentimentは問題・不安系 → "negative", 解決・成果系 → "positive"
- titleは20文字以内
"""


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


def generate_carousel(
    theme: str,
    num_slides: int = 10,
    instructions: str = "",
) -> Carousel:
    client = anthropic.Anthropic()
    mid = num_slides - 3
    last = num_slides
    last_m1 = num_slides - 1

    extra = (
        f"\n追加指示（最優先で反映すること）:\n{instructions.strip()}\n"
        if instructions.strip()
        else ""
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": _USER_TMPL.format(
                    theme=theme,
                    num_slides=num_slides,
                    mid=mid,
                    last=last,
                    last_m1=last_m1,
                    extra_instructions=extra,
                ),
            }
        ],
    )

    raw = _strip_codeblock(response.content[0].text)
    data = json.loads(raw)
    return Carousel.model_validate(data)


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
