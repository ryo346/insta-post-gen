#!/usr/bin/env python3
"""Instagram carousel generator.

Usage:
    python main.py "E判定からの逆転合格"
    python main.py "E判定からの逆転合格" --slides 15
    python main.py "E判定からの逆転合格" --slides 10 --preview
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.content_generator import generate_carousel
from src.image_renderer import render_carousel


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram carousel generator")
    parser.add_argument("theme", help="投稿テーマ（例: 'E判定からの逆転合格'）")
    parser.add_argument("--slides", type=int, default=10,
                        help="生成枚数 10〜20（デフォルト: 10）")
    parser.add_argument("--preview", action="store_true",
                        help="最初の1枚を画像プレビューで表示")
    args = parser.parse_args()

    if not (10 <= args.slides <= 20):
        print("--slides は 10〜20 の範囲で指定してください。")
        sys.exit(1)

    print(f"テーマ: {args.theme}")
    print(f"スライド数: {args.slides}")
    print("コンテンツ生成中 …")

    carousel = generate_carousel(args.theme, args.slides)
    print(f"  {len(carousel.slides)} 枚分のコンテンツを生成しました。")

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_theme = args.theme.replace("/", "_").replace(" ", "_")[:30]
    out_dir    = Path("output") / f"{safe_theme}_{timestamp}"

    print(f"画像生成中 → {out_dir}/")
    paths = render_carousel(carousel.slides, str(out_dir))
    for p in paths:
        print(f"  {p}")

    print(f"\n完了: {len(paths)} 枚を {out_dir}/ に保存しました。")

    if args.preview and paths:
        from PIL import Image
        Image.open(paths[0]).show()


if __name__ == "__main__":
    main()
