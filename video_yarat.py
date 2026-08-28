#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DARS VIDEO GENERATOR
====================

Kirish:
    timeline/timeline.json   ← audyo_dars.py yaratadi
    classroom/ustoz.gif
    classroom/oquvchi.gif
    Rasim/*.png              ← siz tayyorlaysiz

Chiqish:
    output/<N>_<mavzu>.mp4

Ishga tushirish:
    python video_yarat.py

Talablar:
    pip install moviepy pillow imageio imageio-ffmpeg numpy
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageOps

from config import (
    BASE_DIR,
    TIMELINE_JSON,
    CLASSROOM_DIR,
    IMAGE_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    WIDTH,
    HEIGHT,
    FPS,
    BITRATE,
    PRESET,
    THREADS,
    BOARD,
)

try:
    from moviepy import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_videoclips,
    )
except ImportError:
    from moviepy.editor import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_videoclips,
    )


# ============================================================
# MOVIEPY 1.x / 2.x COMPATIBILITY
# ============================================================

def _apply(clip, **kwargs):
    """
    MoviePy versiyasiga qarab set_X() yoki with_X() ishlatadi.
    Foydalanish:
        clip = _apply(clip, start=1.0, duration=5.0, position=(10, 20))
    """
    for attr, value in kwargs.items():
        setter_new = f"with_{attr}"
        setter_old = f"set_{attr}"
        if hasattr(clip, setter_new):
            clip = getattr(clip, setter_new)(value)
        elif hasattr(clip, setter_old):
            clip = getattr(clip, setter_old)(value)
    return clip


def _subclip(clip, t_start: float, t_end: float):
    if hasattr(clip, "subclipped"):
        return clip.subclipped(t_start, t_end)
    return clip.subclip(t_start, t_end)


def _resize(clip, size: tuple[int, int]):
    if hasattr(clip, "resized"):
        return clip.resized(new_size=size)
    return clip.resize(size)


def _set_audio(video_clip, audio_clip):
    if hasattr(video_clip, "with_audio"):
        return video_clip.with_audio(audio_clip)
    return video_clip.set_audio(audio_clip)


# ============================================================
# FILE HELPERS
# ============================================================

def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def load_timeline() -> dict:
    if not TIMELINE_JSON.exists():
        raise FileNotFoundError(
            f"timeline.json topilmadi: {TIMELINE_JSON}\n"
            "Avval ishga tushiring: python audyo_dars.py"
        )
    with TIMELINE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# IMAGE HELPERS
# ============================================================

def fit_to_board(image_path: Path, output_path: Path) -> None:
    """
    Rasmni doska o'lchamiga (BOARD[w] x BOARD[h]) aspect ratio
    saqlab moslashtiradi. Qolgan joy doska rangiga to'ldiriladi.
    """
    w = BOARD["w"]
    h = BOARD["h"]

    img    = Image.open(image_path).convert("RGB")
    fitted = ImageOps.contain(img, (w, h), method=Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (w, h), BOARD["bg"])
    x      = (w - fitted.width)  // 2
    y      = (h - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    canvas.save(output_path, quality=95)


def resolve_image(image_value: str | None) -> Path | None:
    """
    visual.image qiymatidan haqiqiy fayl yo'lini topadi.
    "Rasim/1.png"  →  /loyiha/Rasim/1.png  (agar mavjud bo'lsa)
    """
    if not image_value:
        return None

    p = Path(image_value)
    if not p.is_absolute():
        p = BASE_DIR / p

    if p.exists():
        return p

    # Fallback: IMAGE_DIR / filename
    p2 = IMAGE_DIR / Path(image_value).name
    return p2 if p2.exists() else None


# ============================================================
# VISUAL TIMELINE
# ============================================================

def build_visual_timeline(segments: list[dict]) -> list[dict]:
    """
    Har bir segmentga doskadagi rasmni biriktiradi.

    Qoidalar:
    - oquvchi gapirganda → doska rasmi yo'q (None)
    - ustoz gapirganda   → yangi rasm bo'lsa yangi, bo'lmasa oldingi
    """
    result: list[dict]  = []
    current_image: Path | None = None

    for seg in segments:
        speaker = seg.get("speaker", "ustoz")

        if speaker == "oquvchi":
            result.append({**seg, "_board_image": None})
            continue

        # ustoz: visual.image mavjudmi?
        visual    = seg.get("visual") or {}
        image_val = visual.get("image") if isinstance(visual, dict) else visual

        if image_val:
            found = resolve_image(image_val)
            if found:
                current_image = found
            else:
                print(f"  ⚠️  ID {seg['id']}: rasm topilmadi → {image_val}")

        result.append({**seg, "_board_image": current_image})

    return result


# ============================================================
# CLASSROOM GIF
# ============================================================

def find_gif(speaker: str) -> Path:
    """Speaker uchun classroom GIF faylini topadi."""
    if speaker == "ustoz":
        candidates = [
            CLASSROOM_DIR / "ustoz.gif",
            CLASSROOM_DIR / "teacher.gif",
        ]
    else:
        candidates = [
            CLASSROOM_DIR / "oquvchi.gif",
            CLASSROOM_DIR / "student.gif",
        ]

    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        f"'{speaker}' uchun GIF topilmadi.\n"
        f"Kerakli papka: {CLASSROOM_DIR}"
    )


def make_classroom_clip(gif_path: Path, duration: float, start: float):
    """
    GIF ni kerakli vaqt segmentiga aylantiradi.
    GIF qisqa bo'lsa avtomatik loop qiladi.
    """
    clip = VideoFileClip(str(gif_path), has_mask=False)
    clip = _resize(clip, (WIDTH, HEIGHT))

    src_dur = float(clip.duration or 0)
    if src_dur <= 0:
        raise ValueError(f"GIF davomiyligi noto'g'ri: {gif_path}")

    # GIF qisqa bo'lsa, ko'paytirish
    if duration > src_dur:
        loops = math.ceil(duration / src_dur)
        parts = [clip.copy() for _ in range(loops)]
        clip  = concatenate_videoclips(parts, method="compose")

    clip = _subclip(clip, 0, min(duration, float(clip.duration)))
    clip = _apply(clip, start=start)
    return clip


# ============================================================
# BOARD IMAGE CLIP
# ============================================================

def make_board_clip(image_path: Path, start: float, duration: float):
    """Doska rasmini tayyor qilib, to'g'ri pozitsiyaga joylashtiradi."""
    cache_dir = TEMP_DIR / "board_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Kesh: bir xil rasm qayta qayta resize bo'lmasligi uchun
    key      = abs(hash(str(image_path.resolve())))
    prepared = cache_dir / f"{key}_{image_path.stem}.jpg"

    if not prepared.exists():
        fit_to_board(image_path, prepared)

    clip = ImageClip(str(prepared))
    clip = _apply(
        clip,
        position=(BOARD["x"], BOARD["y"]),
        start=start,
        duration=duration,
    )
    return clip


# ============================================================
# MAIN
# ============================================================

def create_video() -> Path:
    ensure_dirs()

    data     = load_timeline()
    metadata = data.get("metadata", {})
    segments = data.get("segments", [])

    if not segments:
        raise ValueError("timeline.json ichida segments yo'q.")

    actual_duration = float(metadata.get("actual_duration_seconds", 0))
    if actual_duration <= 0:
        actual_duration = max(float(s["end"]) for s in segments)

    audio_path = BASE_DIR / metadata["audio_file"]
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio topilmadi: {audio_path}\n"
            "Avval ishga tushiring: python audyo_dars.py"
        )

    print("=" * 60)
    print("VIDEO YARATISH")
    print(f"  Mavzu     : {metadata.get('mavzu', '')}")
    print(f"  Davomiylik: {actual_duration:.1f}s")
    print(f"  Segmentlar: {len(segments)} ta")
    print("=" * 60)

    # --------------------------------------------------------
    # VISUAL TIMELINE QURILISHI
    # --------------------------------------------------------

    visual_segments = build_visual_timeline(segments)

    # --------------------------------------------------------
    # CLIP YARATISH
    # --------------------------------------------------------

    audio_clip     = AudioFileClip(str(audio_path))
    final_duration = float(audio_clip.duration)

    clips = []

    for seg in visual_segments:
        start    = float(seg["start"])
        end      = min(float(seg["end"]), final_duration)
        duration = end - start

        if duration <= 0:
            continue

        speaker = seg.get("speaker", "ustoz")

        print(
            f"  [{int(seg['id']):03d}] {speaker:8s}  "
            f"{start:7.2f}s → {end:7.2f}s"
        )

        # Classroom GIF qatlami
        gif_path = find_gif(speaker)
        clips.append(make_classroom_clip(gif_path, duration, start))

        # Doska rasmi qatlami (faqat ustoz segmentlarida)
        board_image = seg.get("_board_image")
        if board_image:
            clips.append(make_board_clip(board_image, start, duration))

    # --------------------------------------------------------
    # QATLAMLARNI BIRLASHTIRISH
    # --------------------------------------------------------

    print("  🎬 Qatlamlar birlashtirilmoqda...")

    try:
        final = CompositeVideoClip(clips, size=(WIDTH, HEIGHT))
    except TypeError:
        final = CompositeVideoClip(clips)

    final = _apply(final, duration=final_duration)
    final = _set_audio(final, audio_clip)

    # --------------------------------------------------------
    # CHIQISH FAYLI
    # --------------------------------------------------------

    lesson_no  = int(metadata.get("dars", 1))
    topic      = metadata.get("mavzu", "dars")
    safe_topic = "".join(
        c if c.isalnum() or c in "_-" else "_"
        for c in topic
    ).strip("_")

    output_path = OUTPUT_DIR / f"{lesson_no:02d}_{safe_topic}.mp4"

    print(f"  💾 Saqlanmoqda: {output_path.name}")

    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate=BITRATE,
        preset=PRESET,
        threads=THREADS,
        logger="bar",
    )

    # --------------------------------------------------------
    # RESURSLARNI YOPISH
    # --------------------------------------------------------

    for clip in [audio_clip, final, *clips]:
        try:
            clip.close()
        except Exception:
            pass

    print("=" * 60)
    print("✅ VIDEO TAYYOR")
    print(f"  Fayl      : {output_path}")
    print(f"  Davomiylik: {final_duration:.1f}s")
    print("=" * 60)

    return output_path


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    try:
        create_video()
    except KeyboardInterrupt:
        print("\n❌ Foydalanuvchi to'xtatdi.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ XATO: {exc}")
        sys.exit(1)
