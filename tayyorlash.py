#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TAYYORLASH — PIPELINE BOSHQARUVI
==================================

Foydalanuvchi FAQAT dars.json ni tahrirlaydi,
keyin quyidagi buyruqlardan birini ishga tushiradi:

    python tayyorlash.py           → tekshirish
    python tayyorlash.py --audio   → audio yaratish
    python tayyorlash.py --video   → video yaratish
    python tayyorlash.py --all     → hammasi (tavsiya etiladi)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from config import (
    BASE_DIR,
    DARS_JSON,
    TIMELINE_JSON,
    CLASSROOM_DIR,
    IMAGE_DIR,
    AUDIO_DIR,
    TIMELINE_DIR,
    TEMP_DIR,
    OUTPUT_DIR,
    AUDIO_SCRIPT,
    VIDEO_SCRIPT,
)


# ============================================================
# PRINT HELPERS
# ============================================================

def ok(msg: str)   -> None: print(f"  ✅ {msg}")
def warn(msg: str) -> None: print(f"  ⚠️  {msg}")
def err(msg: str)  -> None: print(f"  ❌ {msg}")


# ============================================================
# PAPKALAR YARATISH
# ============================================================

def create_dirs() -> None:
    for d in [CLASSROOM_DIR, IMAGE_DIR, AUDIO_DIR,
              TIMELINE_DIR, TEMP_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    ok("Barcha papkalar tayyor.")


# ============================================================
# DARS.JSON TEKSHIRUVI
# ============================================================

def load_and_validate() -> tuple[dict, int, int]:
    """
    dars.json ni yuklaydi va validatsiya qiladi.
    Qaytaradi: (data, dialog_count, visual_count)
    """
    if not DARS_JSON.exists():
        raise FileNotFoundError(
            f"dars.json topilmadi: {DARS_JSON}\n"
            "Loyiha papkasida dars.json yarating."
        )

    try:
        data = json.loads(DARS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"dars.json noto'g'ri JSON:\n"
            f"  Qator {exc.lineno}, Ustun {exc.colno}: {exc.msg}"
        )

    # Metadata tekshiruvi
    meta = data.get("metadata", {})
    for key in ["fan", "dars", "mavzu"]:
        if key not in meta:
            raise ValueError(f"dars.json → metadata.{key} yo'q.")

    # Dialog tekshiruvi
    dialog = data.get("dialog", [])
    if not dialog:
        raise ValueError("dars.json → dialog bo'sh.")

    ids: set         = set()
    visual_count: int = 0

    for i, item in enumerate(dialog, start=1):
        iid = item.get("id")
        if iid is None:
            raise ValueError(f"dialog[{i}] ichida 'id' yo'q.")
        if iid in ids:
            raise ValueError(f"Takrorlangan dialog ID: {iid}")
        ids.add(iid)

        if not item.get("speaker"):
            raise ValueError(f"ID {iid}: 'speaker' yo'q.")
        if not item.get("text"):
            raise ValueError(f"ID {iid}: 'text' bo'sh.")

        if isinstance(item.get("visual"), dict) and item["visual"].get("image"):
            visual_count += 1

    ok(
        f"dars.json: {len(dialog)} ta dialog, "
        f"{visual_count} ta visual mapping."
    )
    return data, len(dialog), visual_count


# ============================================================
# CLASSROOM GIF TEKSHIRUVI
# ============================================================

def check_classroom() -> bool:
    all_ok = True
    for name in ["ustoz.gif", "oquvchi.gif"]:
        p = CLASSROOM_DIR / name
        if p.exists():
            ok(f"classroom/{name}")
        else:
            err(f"classroom/{name} topilmadi.")
            all_ok = False
    return all_ok


# ============================================================
# RASMLAR TEKSHIRUVI
# ============================================================

def check_images(data: dict) -> bool:
    exts   = {".png", ".jpg", ".jpeg", ".webp"}
    images = (
        [p for p in IMAGE_DIR.iterdir()
         if p.is_file() and p.suffix.lower() in exts]
        if IMAGE_DIR.exists() else []
    )

    if not images:
        warn("Rasim/ papkasida hali rasm yo'q.")
        return True

    ok(f"Rasim/ ichida {len(images)} ta rasm topildi.")

    missing = []
    for item in data.get("dialog", []):
        visual  = item.get("visual")
        if not isinstance(visual, dict):
            continue
        img_val = visual.get("image")
        if not img_val:
            continue

        img_path = BASE_DIR / img_val
        if not img_path.exists():
            img_path = IMAGE_DIR / Path(img_val).name
        if not img_path.exists():
            missing.append(f"ID {item.get('id')}: {img_val}")

    for m in missing:
        warn(f"Rasm topilmadi: {m}")

    return len(missing) == 0


# ============================================================
# TIMELINE TEKSHIRUVI
# ============================================================

def check_timeline() -> bool:
    if not TIMELINE_JSON.exists():
        warn("timeline.json hali mavjud emas (audyo_dars.py yaratadi).")
        return False

    try:
        tl = json.loads(TIMELINE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        err("timeline.json o'qilmadi (noto'g'ri JSON).")
        return False

    segments = tl.get("segments", [])
    duration = float(tl.get("metadata", {}).get("actual_duration_seconds", 0))

    if not segments:
        err("timeline.json ichida segments yo'q.")
        return False

    ok(f"Timeline: {len(segments)} ta segment, {duration:.1f}s")
    return True


# ============================================================
# TO'LIQ TEKSHIRUV
# ============================================================

def full_check() -> bool:
    print("=" * 60)
    print("TEKSHIRUV")
    print("=" * 60)

    create_dirs()

    try:
        data, _, _ = load_and_validate()
    except Exception as exc:
        err(str(exc))
        return False

    classroom_ok = check_classroom()
    images_ok    = check_images(data)
    timeline_ok  = check_timeline()

    print()
    print("─" * 60)

    if classroom_ok:
        ok("Classroom GIFlar: tayyor")
    else:
        err("Classroom GIFlar: yetishmayapti")

    if images_ok:
        ok("Doska rasmlari: OK")
    else:
        warn("Ba'zi doska rasmlari topilmadi")

    if timeline_ok:
        ok("Timeline: tayyor")
    else:
        warn("Timeline hali yaratilmagan")

    print("=" * 60)
    return classroom_ok


# ============================================================
# SKRIPT ISHLATISH
# ============================================================

def run_script(script: Path) -> bool:
    if not script.exists():
        err(f"Skript topilmadi: {script.name}")
        return False

    print()
    print("=" * 60)
    print(f"▶  {script.name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BASE_DIR),
    )

    if result.returncode == 0:
        ok(f"{script.name} muvaffaqiyatli tugadi.")
        return True

    err(f"{script.name} xato bilan tugadi (kod: {result.returncode}).")
    return False


# ============================================================
# PIPELINE
# ============================================================

def run_audio() -> bool:
    return run_script(AUDIO_SCRIPT)


def run_video() -> bool:
    if not check_timeline():
        err("Video yaratish uchun avval audio kerak: python audyo_dars.py")
        return False
    return run_script(VIDEO_SCRIPT)


def run_all() -> bool:
    """To'liq pipeline: tekshirish → audio → video."""
    print("=" * 60)
    print("TO'LIQ PIPELINE")
    print("=" * 60)

    if not full_check():
        err("Tekshiruvdan o'tilmadi. Yetishmayotgan fayllarni to'ldiring.")
        return False

    if not run_audio():
        return False

    if not check_timeline():
        err("Audio yaratilgandan keyin timeline topilmadi.")
        return False

    if not run_video():
        return False

    print()
    print("=" * 60)
    ok("🎉 VIDEO TAYYOR! → output/ papkasini oching.")
    print("=" * 60)
    return True


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="DARS loyiha pipeline boshqaruvi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Misollar:
  python tayyorlash.py           # faqat tekshirish
  python tayyorlash.py --audio   # audio va timeline yaratish
  python tayyorlash.py --video   # video yaratish (timeline kerak)
  python tayyorlash.py --all     # hammasi (tavsiya etiladi)
        """,
    )
    parser.add_argument("--audio", action="store_true", help="audio yaratish")
    parser.add_argument("--video", action="store_true", help="video yaratish")
    parser.add_argument("--all",   action="store_true", help="to'liq pipeline")

    args = parser.parse_args()

    if args.all:   return 0 if run_all()   else 1
    if args.audio: return 0 if run_audio() else 1
    if args.video: return 0 if run_video() else 1

    # Argument yo'q → tekshirish
    return 0 if full_check() else 1


if __name__ == "__main__":
    raise SystemExit(main())
