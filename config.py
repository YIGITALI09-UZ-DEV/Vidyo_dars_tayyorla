#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LOYIHA KONFIGURATSIYASI
=======================
Barcha texnik sozlamalar shu yerda.

Foydalanuvchi FAQAT dars.json ni tahrirlaydi.
Bu faylni o'zgartirish odatda shart emas.

Ishlatish tartibi:
    python tayyorlash.py --all
"""

from pathlib import Path

# ============================================================
# ASOSIY PAPKA
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# ============================================================
# FAYLLAR VA PAPKALAR
# ============================================================

DARS_JSON     = BASE_DIR / "dars.json"
CLASSROOM_DIR = BASE_DIR / "classroom"
IMAGE_DIR     = BASE_DIR / "Rasim"
AUDIO_DIR     = BASE_DIR / "audio"
TIMELINE_DIR  = BASE_DIR / "timeline"
TIMELINE_JSON = TIMELINE_DIR / "timeline.json"
TEMP_DIR      = BASE_DIR / "temp"
OUTPUT_DIR    = BASE_DIR / "output"

AUDIO_SCRIPT  = BASE_DIR / "audyo_dars.py"
VIDEO_SCRIPT  = BASE_DIR / "video_yarat.py"

# ============================================================
# VIDEO SOZLAMALARI
# ============================================================

WIDTH   = 800
HEIGHT  = 450
FPS     = 30
BITRATE = "5000k"
PRESET  = "medium"
THREADS = 4

# ============================================================
# DOSKA KOORDINATALARI (800x450 classroom ichida)
# ============================================================

BOARD = {
    "x":  48,
    "y":  67,
    "w":  456,
    "h":  201,
    "bg": (25, 65, 48),   # yashil doska rangi (RGB)
}

# ============================================================
# TTS OVOZLAR
# Jinsni dars.json ovozlar bo'limida o'zgartiring:
#   "ustoz": {"jins": "ayol"}  yoki  "jins": "erkak"
# ============================================================

VOICES: dict[str, str] = {
    "ayol":  "uz-UZ-MadinaNeural",
    "erkak": "uz-UZ-SardorNeural",
}

DEFAULT_VOICE_GENDER: dict[str, str] = {
    "ustoz":   "ayol",
    "oquvchi": "erkak",
}

# ============================================================
# AUDIO SEGMENT SOZLAMALARI
# ============================================================

# True  → har bir dialog uchun mp3 fayl saqlanadi
# False → faqat yakuniy audio saqlanadi
KEEP_SEGMENTS = True
