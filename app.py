from __future__ import annotations
from pathlib import Path

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Streamlit Cloud stores secrets in st.secrets — copy to env vars if present
for _key in ("ANTHROPIC_API_KEY",):
    if _key not in os.environ and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

from src.content_generator import generate_carousel, revise_carousel
from src.models import Carousel
from src.csv_exporter import export_csv, save_csv

_CSV_PATH = Path("output/canva_import.csv")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Insta カルーセル生成ツール",
    page_icon="📸",
    layout="wide",
)

# ── Session state ────────────────────────────────────────────────────────────
if "slides" not in st.session_state:
    st.session_state.slides = []
if "theme_done" not in st.session_state:
    st.session_state.theme_done = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📸 カルーセル生成")
    st.divider()

    theme = st.text_input(
        "テーマ",
        placeholder="例: E判定からの逆転合格",
        help="投稿のテーマを日本語で入力してください。",
    )
    instructions = st.text_area(
        "追加指示（任意）",
        placeholder=(
            "例:\n"
            "・ターゲットは高校2年生の文系女子\n"
            "・英語の勉強法に特化した内容にして\n"
            "・3枚目は単語の暗記法だけを掘り下げて\n"
            "・口調はやさしく共感的に"
        ),
        height=180,
        help="スライドの内容・トーン・構成などを自由に指示できます。空欄でも動作します。",
    )
    slide_mode = st.radio(
        "スライド枚数",
        options=["AIに任せる", "手動で指定"],
        horizontal=True,
    )
    if slide_mode == "手動で指定":
        num_slides = st.slider("枚数", min_value=10, max_value=20, value=10)
    else:
        num_slides = None
        st.caption("AIがテーマ・指示の量に応じて10〜20枚で自動決定します。")

    generate_btn = st.button("✨ 生成する", type="primary", use_container_width=True,
                             disabled=not theme)

    if st.session_state.slides:
        st.divider()
        st.caption(f"生成済み: {len(st.session_state.slides)} 枚")
        st.caption(f"テーマ: {st.session_state.theme_done}")

        _csv_bytes = export_csv(
            Carousel(theme=st.session_state.theme_done,
                     slides=st.session_state.slides)
        ).encode("utf-8")
        st.download_button(
            "📊 Canva用CSVをダウンロード",
            _csv_bytes,
            file_name="canva_import.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_csv",
        )

# ── Main ──────────────────────────────────────────────────────────────────────
st.header("Instagram カルーセル生成ツール")
st.caption("テーマを入力して「生成する」を押すと、10〜20枚分のコンテンツをCSVで出力します。")

if generate_btn and theme:
    st.session_state.slides = []

    with st.status("生成中...", expanded=True) as status:
        st.write("📝 Claude API でコンテンツを生成中...")
        carousel = generate_carousel(theme, num_slides, instructions)
        st.write(f"✅ {len(carousel.slides)} 枚分のテキスト生成完了")
        st.write("💾 CSVを保存中...")
        save_csv(carousel, _CSV_PATH)
        status.update(label=f"✅ {len(carousel.slides)} 枚分のCSV生成完了！", state="complete")

    st.session_state.slides     = carousel.slides
    st.session_state.theme_done = theme
    st.rerun()

# ── Slide preview table ───────────────────────────────────────────────────────
if st.session_state.slides:
    st.divider()
    st.subheader(f"生成結果 — {st.session_state.theme_done}")

    for slide in st.session_state.slides:
        if slide.slide_type == "cover":
            lines = " / ".join(slide.cover_lines)
            label = f"**【表紙】** {slide.cover_subtitle or ''} | {lines}"
        elif slide.slide_type == "summary":
            label = f"**【まとめ】** {slide.title.replace(chr(10), ' ')}"
        else:
            label = f"**{slide.title.replace(chr(10), ' ')}**"

        with st.expander(f"スライド {slide.slide_number}　{label}", expanded=False):
            if slide.slide_type == "cover":
                if slide.cover_subtitle:
                    st.write(f"キャッチコピー: {slide.cover_subtitle}")
                for line in slide.cover_lines:
                    st.write(f"- {line}")
            else:
                st.write(f"タイトル: {slide.title}")
                for i, p in enumerate(slide.paragraphs, 1):
                    st.write(f"本文{i}: {p.text}")

else:
    st.info("👈 左のサイドバーにテーマを入力して「生成する」を押してください。")

# ── Revision panel ────────────────────────────────────────────────────────────
if st.session_state.slides:
    st.divider()
    with st.expander("🔧 スライドを修正する", expanded=False):
        def _slide_label(s):
            if s.slide_type == "cover":
                first = s.cover_lines[0] if s.cover_lines else "表紙"
                return f"スライド {s.slide_number}【表紙】{first}…"
            label = s.title.replace("\n", " ")
            kind = "【まとめ】" if s.slide_type == "summary" else ""
            return f"スライド {s.slide_number}{kind}：{label}"

        slide_labels = {s.slide_number: _slide_label(s) for s in st.session_state.slides}
        selected_numbers = st.multiselect(
            "修正するスライドを選択（空欄 = すべて修正）",
            options=list(slide_labels.keys()),
            format_func=lambda n: slide_labels[n],
        )

        revision_text = st.text_area(
            "修正指示",
            placeholder=(
                "例: タイトルをもっとキャッチーにして\n"
                "例: 3枚目の内容をより具体的な勉強法にして\n"
                "例: ポジティブな表現を増やしてテンションを上げて\n"
                "例: CTAスライドにLINE登録を促す文言を入れて"
            ),
            height=150,
        )

        revise_btn = st.button(
            "🔄 修正する",
            type="primary",
            disabled=not revision_text.strip(),
        )

        if revise_btn and revision_text.strip():
            target_numbers = selected_numbers if selected_numbers else None
            label = (
                f"スライド {', '.join(str(n) for n in target_numbers)} を修正中..."
                if target_numbers
                else "全スライドを修正中..."
            )

            with st.status(label, expanded=True) as rev_status:
                st.write("📝 Claude API で修正中...")
                current = Carousel(
                    theme=st.session_state.theme_done,
                    slides=st.session_state.slides,
                )
                updated = revise_carousel(current, revision_text, target_numbers)
                save_csv(updated, _CSV_PATH)
                rev_status.update(label="✅ 修正完了！", state="complete")

            st.session_state.slides = updated.slides
            st.rerun()
