#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOSKA OVERLAY — YORDAMCHI MODUL
================================
Classroom GIF/video ustiga doska rasmini qo'yib preview yaratadi.

Asosiy pipeline uchun: python tayyorlash.py --all
Bu fayl faqat alohida preview/test uchun ishlatiladi.

Ishlatish:
    python doska_overlay.py --image Rasim/1.png
    python doska_overlay.py --image Rasim/5.png --speaker oquvchi
    python doska_overlay.py --image Rasim/1.png --duration 5 --output output/test.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

from config import BASE_DIR, CLASSROOM_DIR, TEMP_DIR, BOARD, WIDTH, HEIGHT

try:
    from moviepy import ImageClip, VideoFileClip, CompositeVideoClip
except ImportError:
    from moviepy.editor import ImageClip, VideoFileClip, CompositeVideoClip


# ============================================================
# IMAGE PREPARATION
# ============================================================

def prepare_board_image(image_path: str | Path) -> Path:
    """
    Rasmni doska o'lchamiga (BOARD[w] x BOARD[h]) aspect ratio
    saqlab moslashtiradi va keshga saqlaydi.
    """
    image_path = Path(image_path)
    if not image_path.is_absolute():
        image_path = BASE_DIR / image_path

    if not image_path.exists():
        raise FileNotFoundError(f"Rasm topilmadi: {image_path}")

    cache_dir = TEMP_DIR / "board_prepared"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output    = cache_dir / f"{image_path.stem}_board.jpg"

    img    = Image.open(image_path).convert("RGB")
    fitted = ImageOps.contain(
        img, (BOARD["w"], BOARD["h"]),
        method=Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (BOARD["w"], BOARD["h"]), BOARD["bg"])
    x = (BOARD["w"] - fitted.width)  // 2
    y = (BOARD["h"] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    canvas.save(output, quality=95)
    return output


# ============================================================
# OVERLAY
# ============================================================

def overlay_board(
    board_image:     str | Path,
    output:          str | Path  = "output/preview.mp4",
    speaker:         str         = "ustoz",
    start:           float       = 0.0,
    duration:        float | None = None,
) -> Path:
    """
    Classroom GIF ustiga doska rasmini joylashtiradi.

    Args:
        board_image: Doska rasmi yo'li (masalan, "Rasim/1.png")
        output:      Natija fayli yo'li
        speaker:     "ustoz" yoki "oquvchi"
        start:       GIF da boshlash vaqti (sekund)
        duration:    Klip davomiyligi (None = GIF to'la uzunligi)

    Returns:
        Natija fayl yo'li (Path)
    """
    output = Path(output)

    # GIF tanlash
    if speaker == "ustoz":
        gif_candidates = [
            CLASSROOM_DIR / "ustoz.gif",
            CLASSROOM_DIR / "teacher.gif",
        ]
    else:
        gif_candidates = [
            CLASSROOM_DIR / "oquvchi.gif",
            CLASSROOM_DIR / "student.gif",
        ]

    gif_path = None
    for candidate in gif_candidates:
        if candidate.exists():
            gif_path = candidate
            break

    if gif_path is None:
        raise FileNotFoundError(
            f"'{speaker}' uchun GIF topilmadi: {CLASSROOM_DIR}"
        )

    # Rasm tayyorlash
    prepared = prepare_board_image(board_image)

    # Video yaratish
    base = VideoFileClip(str(gif_path))
    dur  = duration or (float(base.duration) - start)
    dur  = max(0.01, min(dur, float(base.duration) - start))

    base = base.subclipped(start, start + dur) \
        if hasattr(base, "subclipped") \
        else base.subclip(start, start + dur)

    board = ImageClip(str(prepared))
    if hasattr(board, "with_position"):
        board = board.with_position((BOARD["x"], BOARD["y"]))
        board = board.with_duration(dur)
    else:
        board = board.set_position((BOARD["x"], BOARD["y"]))
        board = board.set_duration(dur)

    result = CompositeVideoClip([base, board], size=(WIDTH, HEIGHT))

    output.parent.mkdir(parents=True, exist_ok=True)
    result.write_videofile(
        str(output),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="5000k",
        preset="medium",
        logger="bar",
    )

    for clip in [base, board, result]:
        try:
            clip.close()
        except Exception:
            pass

    return output


def board_region() -> tuple[int, int, int, int]:
    """Doska koordinatalarini qaytaradi: (x, y, w, h)."""
    return BOARD["x"], BOARD["y"], BOARD["w"], BOARD["h"]


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Doska overlay preview yaratish",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Misollar:
  python doska_overlay.py --image Rasim/1.png
  python doska_overlay.py --image Rasim/5.png --speaker oquvchi
  python doska_overlay.py --image Rasim/1.png --duration 5
        """,
    )
    parser.add_argument(
        "--image",    required=True,
        help="Doska rasmi (masalan: Rasim/1.png)"
    )
    parser.add_argument(
        "--speaker",  default="ustoz",
        choices=["ustoz", "oquvchi"],
        help="GIF tanlash uchun (default: ustoz)"
    )
    parser.add_argument(
        "--output",   default="output/preview.mp4",
        help="Natija fayli (default: output/preview.mp4)"
    )
    parser.add_argument(
        "--start",    type=float, default=0.0,
        help="GIF boshlash vaqti sekund (default: 0)"
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="Klip davomiyligi sekund (default: GIF to'la uzunligi)"
    )

    args = parser.parse_args()

    print(f"  Rasm    : {args.image}")
    print(f"  Speaker : {args.speaker}")
    print(f"  Chiqish : {args.output}")

    try:
        out = overlay_board(
            board_image=args.image,
            output=args.output,
            speaker=args.speaker,
            start=args.start,
            duration=args.duration,
        )
        print(f"✅ Tayyor: {out}")
    except Exception as exc:
        print(f"❌ Xato: {exc}")
        sys.exit(1)
