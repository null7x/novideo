"""
Virex — Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any

# ══════════════════════════════════════════════════════════════════════════════
# BOT SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "8270727558:AAHt1m_VBB9u6iVZl777qfURuD5YO6gzDZo")

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG PATH
# ══════════════════════════════════════════════════════════════════════════════

# Windows: полный путь, Linux/Docker: просто ffmpeg
FFMPEG_PATH = os.getenv("FFMPEG_PATH", r"C:\ffmpeg\ffmpeg-N-122487-g43dbc011fa-win64-gpl-shared\bin\ffmpeg.exe")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", r"C:\ffmpeg\ffmpeg-N-122487-g43dbc011fa-win64-gpl-shared\bin\ffprobe.exe")

# ══════════════════════════════════════════════════════════════════════════════
# PROCESSING MODES
# ══════════════════════════════════════════════════════════════════════════════

class Mode:
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"

DEFAULT_MODE = Mode.TIKTOK

# ══════════════════════════════════════════════════════════════════════════════
# FILE LIMITS
# ══════════════════════════════════════════════════════════════════════════════

MAX_FILE_SIZE_MB = 100
MAX_VIDEO_DURATION_SECONDS = 120
ALLOWED_EXTENSIONS = (".mp4", ".mov")
FFMPEG_TIMEOUT_SECONDS = 600
MAX_QUEUE_SIZE = 10
MAX_CONCURRENT_TASKS = 2

# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITS (ANTI-ABUSE)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlanLimits:
    videos_per_hour: int = 999999
    cooldown_seconds: int = 0
    max_file_size_mb: int = 100
    priority: int = 0

PLAN_LIMITS: Dict[str, PlanLimits] = {
    "free": PlanLimits(
        videos_per_hour=999999,
        cooldown_seconds=0,
        max_file_size_mb=100,
        priority=0
    ),
    "pro": PlanLimits(
        videos_per_hour=999999,
        cooldown_seconds=0,
        max_file_size_mb=100,
        priority=1
    ),
}

RATE_LIMIT_WINDOW_SECONDS = 3600
ABUSE_THRESHOLD_HITS = 10
SOFT_BLOCK_DURATION_SECONDS = 1800
BUTTON_COOLDOWN_SECONDS = 2
DUPLICATE_FILE_BLOCK_SECONDS = 60

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG VIDEO SETTINGS — TIKTOK MAX
# ══════════════════════════════════════════════════════════════════════════════

TIKTOK_VIDEO = {
    "crop_min": 0.965,
    "crop_max": 0.985,
    "speed_min": 0.965,
    "speed_max": 1.035,
    "gamma_min": 0.97,
    "gamma_max": 1.03,
    "brightness_min": -0.04,
    "brightness_max": 0.04,
    "contrast_min": 0.95,
    "contrast_max": 1.08,
    "saturation_min": 0.96,
    "saturation_max": 1.04,
    "noise_min": 1,
    "noise_max": 3,
    "fps_options": [29.97, 30, 30.01],
    "gop_min": 15,
    "gop_max": 30,
    "bitrate_min": 1400,
    "bitrate_max": 2600,
    "presets": ["veryfast", "fast"],
    "scalers": ["bicubic", "lanczos"],
}

TIKTOK_AUDIO = {
    "volume_min": 0.97,
    "volume_max": 1.03,
    "audio_bitrate": "128k",
}

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG VIDEO SETTINGS — YOUTUBE SHORTS MAX
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_VIDEO = {
    **TIKTOK_VIDEO,
    "fps_options": [30],
    "noise_min": 2,
    "noise_max": 4,
    "bitrate_min": 1600,
    "bitrate_max": 2800,
}

YOUTUBE_AUDIO = {
    "volume_min": 0.96,
    "volume_max": 1.04,
    "audio_bitrate": "192k",
    "background_noise_db": -45,
    "resample_rate": 48000,
}

# ══════════════════════════════════════════════════════════════════════════════
# UI TEXTS
# ══════════════════════════════════════════════════════════════════════════════

TEXTS = {
    "start": (
        "🎬 <b>Virex</b>\n"
        "Умная уникализация видео для TikTok\n\n"
        "🔥 Режим: <b>TikTok MAX</b>\n"
        "Просто отправь видео ⬇️"
    ),
    "start_youtube": (
        "🎬 <b>Virex</b>\n"
        "Умная уникализация видео для YouTube Shorts\n\n"
        "▶️ Режим: <b>YouTube Shorts MAX</b>\n"
        "Просто отправь видео ⬇️"
    ),
    "mode_tiktok": "🔥 Режим изменён на <b>TikTok MAX</b>",
    "mode_youtube": "▶️ Режим изменён на <b>YouTube Shorts MAX</b>",
    "how_it_works": (
        "🎯 <b>Как это работает</b>\n\n"
        "1. Отправь видео (MP4/MOV, до 100 МБ, до 2 мин)\n"
        "2. Нажми «Уникализировать»\n"
        "3. Получи уникальное видео\n\n"
        "Каждый рендер — уникален. Без лимитов!"
    ),
    "video_received": "🎬 Видео получено",
    "processing": "⏳ Обрабатываем видео...",
    "done": "✅ Готово",
    "error": "⚠️ Не удалось обработать видео. Попробуй другой файл.",
    "error_download": "⚠️ Не удалось скачать видео. Проверь ссылку.",
    "invalid_format": "⚠️ Отправь видео в формате MP4 или MOV",
    "file_too_large": "⚠️ Видео слишком большое. Максимум — 100 МБ",
    "video_too_long": "⚠️ Видео слишком длинное. Максимум — 2 минуты",
    "rate_limit": "⏱ Подожди немного.",
    "cooldown": "⏱ Подожди {seconds} сек перед следующим видео",
    "queue_full": "🔄 Сейчас много запросов. Попробуй через минуту.",
    "duplicate": "🔁 Это видео уже обрабатывается",
    "soft_block": "⏱ Слишком много запросов. Попробуй через 30 минут.",
    "button_spam": "",
}

# ══════════════════════════════════════════════════════════════════════════════
# BUTTONS
# ══════════════════════════════════════════════════════════════════════════════

BUTTONS = {
    "tiktok_on": "🔥 TikTok MAX — ВКЛ",
    "youtube_on": "▶️ YouTube Shorts — ВКЛ",
    "switch_youtube": "▶️ Переключить на YouTube Shorts",
    "switch_tiktok": "🔥 Переключить на TikTok MAX",
    "how_it_works": "ℹ️ Как это работает",
    "uniqualize": "🎯 Уникализировать",
    "download": "⬇️ Скачать видео",
    "again": "🔁 Уникализировать ещё раз",
    "change_mode": "🔀 Сменить режим",
    "back": "◀️ Назад",
}
