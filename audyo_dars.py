#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DARS AUDIO GENERATOR
====================
dars.json → TTS audio segmentlar → yakuniy MP3 → timeline/timeline.json

Foydalanuvchi FAQAT dars.json ni tahrirlaydi.

Ishga tushirish:
    python audyo_dars.py

Talablar:
    pip install edge-tts pydub
    FFmpeg PATH da bo'lishi kerak.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from config import (
    BASE_DIR,
    DARS_JSON,
    AUDIO_DIR,
    TIMELINE_DIR,
    TIMELINE_JSON,
    TEMP_DIR,
    VOICES,
    DEFAULT_VOICE_GENDER,
    KEEP_SEGMENTS,
)


# ============================================================
# HELPERS
# ============================================================

def safe_name(text: str) -> str:
    """Fayl nomi uchun xavfsiz string hosil qiladi."""
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text or "dars"


def ms_to_sec(ms: int) -> float:
    return round(ms / 1000.0, 3)


async def tts_save(text: str, voice: str, output: Path) -> None:
    """Edge TTS orqali matnni ovozga aylantiradi va faylga saqlaydi."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output))


def make_dirs() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def load_lesson() -> dict:
    if not DARS_JSON.exists():
        raise FileNotFoundError(
            f"dars.json topilmadi: {DARS_JSON}\n"
            "Loyiha papkasida dars.json mavjud emasligini tekshiring."
        )
    try:
        with DARS_JSON.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"dars.json noto'g'ri JSON formatida:\n"
            f"  Qator: {exc.lineno}, Ustun: {exc.colno}\n"
            f"  Xato: {exc.msg}"
        )


def get_voice(speaker: str, ovozlar: dict) -> str:
    """
    dars.json ovozlar bo'limidan speaker uchun TTS ovoz ID ni qaytaradi.

    Misol:
        ovozlar = {"ustoz": {"jins": "ayol"}, "oquvchi": {"jins": "erkak"}}
        get_voice("ustoz", ovozlar)  →  "uz-UZ-MadinaNeural"
        get_voice("oquvchi", ovozlar) →  "uz-UZ-SardorNeural"
    """
    speaker_cfg = ovozlar.get(speaker, {})
    gender = speaker_cfg.get("jins") or DEFAULT_VOICE_GENDER.get(speaker, "ayol")
    return VOICES.get(gender, VOICES["ayol"])


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    make_dirs()
    data = load_lesson()

    metadata  = data.get("metadata", {})
    ovozlar   = data.get("ovozlar", {})
    fan       = metadata.get("fan", "Dars")
    lesson_no = int(metadata.get("dars", 1))
    topic     = metadata.get("mavzu", "Noma'lum mavzu")

    audio_dir   = AUDIO_DIR / safe_name(fan)
    segment_dir = audio_dir / "segments"
    audio_dir.mkdir(parents=True, exist_ok=True)
    segment_dir.mkdir(parents=True, exist_ok=True)

    final_name       = f"{lesson_no:02d}_{safe_name(topic)}.mp3"
    final_audio_path = audio_dir / final_name

    dialog = data.get("dialog", [])
    if not dialog:
        raise ValueError("dars.json ichida dialog bo'sh yoki mavjud emas.")

    final_audio = AudioSegment.empty()
    timeline    = []
    current_ms  = 0

    print("=" * 60)
    print("AUDIO + TIMELINE YARATISH")
    print(f"  Fan   : {fan}")
    print(f"  Mavzu : {topic}")
    print(f"  Dialog: {len(dialog)} ta")
    print("=" * 60)

    for item in dialog:
        item_id  = int(item["id"])
        speaker  = item.get("speaker", "ustoz")
        text     = item.get("text", "").strip()
        pause_ms = int(item.get("pause", 500))

        if not text:
            print(f"  ⚠️  ID {item_id}: matn bo'sh, o'tkazildi.")
            continue

        voice        = get_voice(speaker, ovozlar)
        segment_path = segment_dir / f"{item_id:03d}.mp3"

        print(f"  [{item_id:03d}] {speaker:8s} → TTS...")

        asyncio.run(tts_save(text, voice, segment_path))

        part      = AudioSegment.from_mp3(segment_path)
        speech_ms = len(part)

        speech_start_ms = current_ms
        speech_end_ms   = current_ms + speech_ms
        final_audio    += part
        current_ms      = speech_end_ms

        pause_start_ms  = current_ms
        final_audio    += AudioSegment.silent(duration=pause_ms)
        current_ms     += pause_ms
        pause_end_ms    = current_ms

        visual = item.get("visual", {})

        timeline.append({
            "id":              item_id,
            "speaker":         speaker,
            "type":            item.get("type", ""),
            "text":            text,

            "audio_file":      str(
                segment_path.relative_to(BASE_DIR)
            ).replace("\\", "/"),
            "voice":           voice,

            "speech_start":    ms_to_sec(speech_start_ms),
            "speech_end":      ms_to_sec(speech_end_ms),
            "speech_duration": ms_to_sec(speech_ms),

            "pause_ms":        pause_ms,
            "pause_start":     ms_to_sec(pause_start_ms),
            "pause_end":       ms_to_sec(pause_end_ms),

            "start":           ms_to_sec(speech_start_ms),
            "end":             ms_to_sec(pause_end_ms),
            "duration":        ms_to_sec(speech_ms + pause_ms),

            "visual":          visual,
        })

        print(
            f"         nutq={speech_ms / 1000:.2f}s  "
            f"pauza={pause_ms / 1000:.2f}s  "
            f"jami={current_ms / 1000:.2f}s"
        )

    # --------------------------------------------------------
    # YAKUNIY AUDIO EKSPORT
    # --------------------------------------------------------

    final_audio.export(final_audio_path, format="mp3")
    total_sec = len(final_audio) / 1000.0

    # --------------------------------------------------------
    # TIMELINE JSON
    # --------------------------------------------------------

    timeline_data = {
        "version": 1,
        "metadata": {
            "fan":   fan,
            "dars":  lesson_no,
            "mavzu": topic,

            "declared_duration":       metadata.get("davomiyligi"),
            "actual_duration_seconds": round(total_sec, 3),
            "actual_duration": (
                f"{int(total_sec // 60):02d}:"
                f"{int(total_sec % 60):02d}."
                f"{int((total_sec % 1) * 1000):03d}"
            ),

            "language":     metadata.get("til", "uz"),
            "audio_file":   str(
                final_audio_path.relative_to(BASE_DIR)
            ).replace("\\", "/"),
            "segments_dir": str(
                segment_dir.relative_to(BASE_DIR)
            ).replace("\\", "/"),
        },
        "video": {
            "fps":                 30,
            "width":               800,
            "height":              450,
            "format":              "mp4",
            "board_images_folder": "Rasim",
            "classroom_folder":    "classroom",
        },
        "segments": timeline,
    }

    with TIMELINE_JSON.open("w", encoding="utf-8") as f:
        json.dump(timeline_data, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------
    # TEMP TOZALASH
    # --------------------------------------------------------

    if not KEEP_SEGMENTS and TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        TEMP_DIR.mkdir()

    # --------------------------------------------------------
    # NATIJA
    # --------------------------------------------------------

    mins = int(total_sec // 60)
    secs = int(total_sec % 60)

    print("=" * 60)
    print("✅ AUDIO YARATILDI")
    print(f"  Audio    : {final_audio_path}")
    print(f"  Timeline : {TIMELINE_JSON}")
    print(f"  Davomiylik: {total_sec:.1f}s ({mins} daq {secs} sek)")
    print("=" * 60)


if __name__ == "__main__":
    main()
