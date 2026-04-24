from __future__ import annotations
import io
import zipfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

from src.content_generator import generate_carousel, revise_carousel
from src.models import Carousel
from src.image_renderer import render_slide
from src import illustration_generator as _ilgen
from src.csv_exporter import export_csv, save_csv

_IL_CACHE  = Path("output/.illustrations_cache")
_CSV_PATH  = Path("output/canva_import.csv")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Insta カルーセル生成ツール",
    page_icon="📸",
    layout="wide",
)

# ── Session state ────────────────────────────────────────────────────────────
if "images" not in st.session_state:
    st.session_state.images = []
if "slides" not in st.session_state:
    st.session_state.slides = []
if "illustrations" not in st.session_state:
    st.session_state.illustrations = {}
if "theme_done" not in st.session_state:
    st.session_state.theme_done = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📸 カルーセル生成")
    if not _ilgen.is_available():
        st.warning("OPENAI_API_KEY が未設定のため、イラストはプレースホルダーになります。", icon="⚠️")
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

    if st.session_state.images:
        st.divider()
        st.caption(f"生成済み: {len(st.session_state.images)} 枚")
        st.caption(f"テーマ: {st.session_state.theme_done}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(st.session_state.images):
                buf = io.BytesIO()
                img.save(buf, "PNG")
                zf.writestr(f"slide_{i+1:02d}.png", buf.getvalue())

        st.download_button(
            "📥 ZIP でまとめてDL",
            zip_buf.getvalue(),
            file_name=f"{st.session_state.theme_done}_carousel.zip",
            mime="application/zip",
            use_container_width=True,
        )

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
st.caption("テーマを入力して「生成する」を押すと、10〜20枚の投稿スライドを自動生成します。")

if generate_btn and theme:
    st.session_state.images = []
    st.session_state.slides = []

    with st.status("生成中...", expanded=True) as status:
        st.write("📝 Claude API でコンテンツを生成中...")
        carousel = generate_carousel(theme, num_slides, instructions)
        st.write(f"✅ {len(carousel.slides)} 枚分のテキスト生成完了")

        # ── Illustration generation ──────────────────────────────────────────
        content_slides = [s for s in carousel.slides
                          if s.slide_type == "content" and s.illustration_hint]
        illustrations: dict[int, Image.Image] = {}
        if _ilgen.is_available() and content_slides:
            st.write(f"🖼️ イラスト生成中（{len(content_slides)} 枚）…")
            il_prog = st.progress(0)
            for idx, slide in enumerate(content_slides):
                il = _ilgen.generate(slide.illustration_hint, _IL_CACHE)
                if il:
                    illustrations[slide.slide_number] = il
                il_prog.progress((idx + 1) / len(content_slides))
            il_prog.empty()
            st.write(f"✅ イラスト {len(illustrations)} 枚生成完了")

        # ── Slide rendering ──────────────────────────────────────────────────
        st.write("🎨 スライド画像をレンダリング中...")
        prog = st.progress(0)
        images: list[Image.Image] = []
        for i, slide in enumerate(carousel.slides):
            il = illustrations.get(slide.slide_number)
            images.append(render_slide(slide, illustration=il))
            prog.progress((i + 1) / len(carousel.slides))
        prog.empty()

        status.update(label=f"✅ {len(images)} 枚の生成完了！", state="complete")

    save_csv(carousel, _CSV_PATH)

    st.session_state.images        = images
    st.session_state.slides        = carousel.slides
    st.session_state.illustrations = illustrations
    st.session_state.theme_done    = theme
    st.rerun()

# ── Slide grid ───────────────────────────────────────────────────────────────
if st.session_state.images:
    st.divider()
    st.subheader(f"生成結果 — {st.session_state.theme_done}")

    cols_n = 3
    for row_start in range(0, len(st.session_state.images), cols_n):
        cols = st.columns(cols_n, gap="medium")
        for col_idx in range(cols_n):
            abs_idx = row_start + col_idx
            if abs_idx >= len(st.session_state.images):
                break
            img   = st.session_state.images[abs_idx]
            slide = st.session_state.slides[abs_idx]
            with cols[col_idx]:
                st.image(img, use_container_width=True)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                st.download_button(
                    f"↓ slide_{abs_idx+1:02d}.png",
                    buf.getvalue(),
                    file_name=f"slide_{abs_idx+1:02d}.png",
                    mime="image/png",
                    use_container_width=True,
                    key=f"dl_{abs_idx}",
                )

else:
    st.info("👈 左のサイドバーにテーマを入力して「生成する」を押してください。")

# ── Revision panel ────────────────────────────────────────────────────────────
if st.session_state.slides:
    st.divider()
    with st.expander("🔧 スライドを修正する", expanded=False):
        def _slide_label(s):
            if s.slide_type == "cover":
                first = s.cover_lines[0].text if s.cover_lines else "表紙"
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
                st.write("🎨 修正スライドを再レンダリング中...")

                updated_map = {s.slide_number: s for s in updated.slides}
                new_slides, new_images = [], []
                for i, old_slide in enumerate(st.session_state.slides):
                    new_slide = updated_map[old_slide.slide_number]
                    new_slides.append(new_slide)
                    if new_slide is not old_slide:
                        il = st.session_state.illustrations.get(new_slide.slide_number)
                        new_images.append(render_slide(new_slide, illustration=il))
                    else:
                        new_images.append(st.session_state.images[i])

                rev_status.update(label="✅ 修正完了！", state="complete")

            st.session_state.slides = new_slides
            st.session_state.images = new_images
            st.rerun()
