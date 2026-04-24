from __future__ import annotations
import json
import re
import anthropic
from .models import Carousel

_SYSTEM = """\
あなたはInstagramのカルーセル投稿を作るプロのコンテンツライターです。
教育・学習系アカウント向けに、高校生・受験生に刺さる投稿を作ります。

【文体・口調の規則】
- 友人や先輩が語りかけるような、カジュアルで親しみやすい口調
- 体験談・共感を交えた内容（「〜ばかりでした」「〜と思いませんか？」など）
- 「！」「…」「？」を適度に使い、テンポよく読める文章
- 難しい言葉は使わず、中高生でも理解できるシンプルな表現
- 「〜ましょう」「〜べし！」「〜ですね」など自然な語尾

【ヘッダーの規則】
- 1〜2行・1行あたり最大15文字
- 短くインパクトのある言葉（「模試の判定大嫌い！」「7:00 起床」のようなイメージ）
- 感情・驚き・共感を引き出す言葉選び

【本文の規則】
- 1段落あたり2〜3行（1行15〜20文字程度）
- 1スライドに3〜4段落
- 説明文ではなく、語りかけるような文体

必ずJSON形式のみで応答すること。説明文・コードブロック不要。"""

_JSON_SCHEMA = '''\
{{
  "theme": "{theme}",
  "slides": [
    {{
      "slide_number": 1,
      "slide_type": "cover",
      "cover_subtitle": "＼キャッチな煽り文句／（20文字以内・任意）",
      "cover_lines": [
        "1行目（10文字以内）",
        "2行目（8文字以内）",
        "3行目（10文字以内・任意）"
      ],
      "illustration_hint": null
    }},
    {{
      "slide_number": 2,
      "slide_type": "content",
      "title": "ヘッダー（1〜2行・各15文字以内。2行の場合は\\nで区切る）",
      "paragraphs": [
        {{"text": "本文段落1（2〜3行分・語りかける口調）"}},
        {{"text": "本文段落2"}},
        {{"text": "本文段落3"}}
      ],
      "illustration_hint": "subject described in 8 words or less in English"
    }},
    {{
      "slide_number": 99,
      "slide_type": "summary",
      "title": "まとめヘッダー（\\nで2行可・各15文字以内）",
      "paragraphs": [
        {{"text": "本文段落1"}},
        {{"text": "本文段落2"}},
        {{"text": "本文段落3"}}
      ],
      "illustration_hint": null
    }}
  ]
}}

制約:
- スライド数は10〜20枚の範囲
- 最初の1枚は必ずcover、最後の1枚は必ずsummary
- contentスライドのparagraphsは3〜4個
- summaryスライドのparagraphsは3〜5個
- illustration_hintはcontentのみ必須（cover・summaryはnull）
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
- titleは1〜2行・各15文字以内（2行の場合は\\nで区切る）
- 本文は語りかける口調を維持すること
- cover_linesは各行10文字以内

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
