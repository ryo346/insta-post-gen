from __future__ import annotations
import json
import re
import anthropic
from .models import Carousel

_SYSTEM = """\
あなたはInstagramのカルーセル投稿を作成するコンテンツディレクターです。
教育・学習系アカウント向けに、高校生・受験生に刺さるコンテンツを生成します。
必ずJSON形式のみで応答し、説明文・コードブロックは不要です。"""

_JSON_SCHEMA = '''\
{{
  "theme": "{theme}",
  "slides": [
    {{
      "slide_number": 1,
      "slide_type": "cover",
      "cover_subtitle": "＼キャッチーな煽り文句／（20文字以内・任意）",
      "cover_lines": [
        {{"text": "1行目（10文字以内）", "color": "blue"}},
        {{"text": "2行目（8文字以内）",  "color": "orange"}},
        {{"text": "3行目（10文字以内）", "color": "black"}}
      ],
      "illustration_hint": null,
      "show_save_cta": false
    }},
    {{
      "slide_number": 2,
      "slide_type": "content",
      "title": "タイトル（20文字以内。2行にする場合は\\nで区切る）",
      "paragraphs": [
        {{"text": "段落テキスト（30文字以内）", "highlight": "強調ワード", "highlight_color": "orange"}},
        {{"text": "別の段落テキスト（30文字以内）", "highlight": null}}
      ],
      "illustration_hint": "illustration description in English within 8 words",
      "show_save_cta": false
    }},
    {{
      "slide_number": 99,
      "slide_type": "summary",
      "title": "まとめタイトル（\\nで2行可・各行20文字以内）",
      "paragraphs": [
        {{"text": "段落テキスト（30文字以内）", "highlight": "強調ワード", "highlight_color": "orange"}}
      ],
      "illustration_hint": null,
      "show_save_cta": false
    }}
  ]
}}

制約:
- スライド数は10〜20枚の範囲
- 最初の1枚は必ずcover、最後の1枚は必ずsummary
- contentスライドのparagraphsは3〜4個
- summaryスライドのparagraphsは3〜5個
- highlightはtextの部分文字列であること（nullも可）
- highlight_colorは"orange"（ポジティブ・解決系）または"blue"（問題・課題系）
- illustration_hintはcontentのみ必須（summaryはnullでよい）
- cover_linesは2〜3行'''

_USER_TMPL = """\
テーマ「{theme}」で{num_slides}枚のInstagramカルーセルを作成してください。

推奨構成:
- 1枚目: cover（キャッチーな表紙）
- 2〜3枚目: content（導入・共感・問題提起）
- 4〜{mid}枚目: content（解決策・具体的内容）
- {last_m1}枚目: content（まとめの手前）
- {last}枚目: summary（締め・CTA）
{extra_instructions}
以下のJSON形式で出力してください:
{schema}"""

_USER_AUTO_TMPL = """\
テーマ「{theme}」のInstagramカルーセルを作成してください。
テーマの深さ・指示の量・伝えるべき内容量をもとに、10〜20枚の間で最適な枚数を自分で判断してください。

推奨構成（枚数に応じて比率調整）:
- 1枚目: cover（キャッチーな表紙）
- 冒頭数枚: content（導入・共感・問題提起）
- 中盤複数枚: content（解決策・具体的内容）
- 最後: summary（締め・CTA）
{extra_instructions}
以下のJSON形式で出力してください:
{schema}"""

_REVISE_TMPL = """\
以下の既存スライドのJSONを、修正指示に従って修正してください。

## 修正指示
{instructions}

## 修正対象スライド（現在のJSON）
{current_json}

## 制約
- slide_number・slide_typeは変更しないこと
- highlightはtextの部分文字列であること
- highlight_colorは"orange"または"blue"のみ
- cover_linesは各行10文字以内
- titleは20文字以内、paragraphsのtextは30文字以内

## 出力形式（JSONのみ・説明文不要）
{{"slides": [修正後のスライドの配列]}}
"""


def _strip_codeblock(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _clamp_slides(carousel: Carousel) -> Carousel:
    return Carousel(theme=carousel.theme, slides=carousel.slides[:20])


def generate_carousel(
    theme: str,
    num_slides: int | None = 10,
    instructions: str = "",
) -> Carousel:
    client = anthropic.Anthropic()
    extra = (
        f"\n追加指示（最優先で反映すること）:\n{instructions.strip()}\n"
        if instructions.strip()
        else ""
    )
    schema = _JSON_SCHEMA.format(theme=theme)

    if num_slides is None:
        content = _USER_AUTO_TMPL.format(
            theme=theme, extra_instructions=extra, schema=schema,
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
    return _clamp_slides(Carousel.model_validate(json.loads(raw)))


def revise_carousel(
    carousel: Carousel,
    instructions: str,
    slide_numbers: list[int] | None = None,
) -> Carousel:
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
