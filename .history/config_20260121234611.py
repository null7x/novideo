"""
Virex — Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any

# ══════════════════════════════════════════════════════════════════════════════
# BOT SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# Токен из переменной окружения или fallback для тестирования
_DEFAULT_TOKEN = "8270727558:AAHt1m_VBB9u6iVZl777qfURuD5YO6gzDZo"
BOT_TOKEN = os.getenv("BOT_TOKEN", _DEFAULT_TOKEN).strip()
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

# Админы бота (могут выдавать VIP/Premium)
ADMIN_IDS = [
    123456789,  # Замените на свой Telegram ID
    # Добавьте других админов здесь
]

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG PATH (auto-detect or from env)
# ══════════════════════════════════════════════════════════════════════════════

import shutil

def _find_ffmpeg(name: str) -> str:
    """Найти ffmpeg/ffprobe: сначала env, потом PATH, потом стандартные места"""
    env_path = os.getenv(f"{name.upper()}_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    
    # Поиск в PATH
    found = shutil.which(name)
    if found:
        return found
    
    # Windows стандартные места
    if os.name == "nt":
        for path in [
            rf"C:\ffmpeg\bin\{name}.exe",
            rf"C:\Program Files\ffmpeg\bin\{name}.exe",
            rf"C:\tools\ffmpeg\bin\{name}.exe",
        ]:
            if os.path.exists(path):
                return path
    
    return name  # fallback: надеемся что в PATH

FFMPEG_PATH = _find_ffmpeg("ffmpeg")
FFPROBE_PATH = _find_ffmpeg("ffprobe")

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
# QUALITY PRESETS
# ══════════════════════════════════════════════════════════════════════════════

class Quality:
    LOW = "low"
    MEDIUM = "medium"
    MAX = "max"

QUALITY_SETTINGS = {
    Quality.LOW: {
        "crf_offset": 6,       # +6 к CRF (меньше качество, быстрее)
        "bitrate_mult": 0.5,   # 50% от bitrate
        "preset": "fast",
        "noise_mult": 1.5,     # больше шума
    },
    Quality.MEDIUM: {
        "crf_offset": 3,
        "bitrate_mult": 0.75,
        "preset": "medium",
        "noise_mult": 1.0,
    },
    Quality.MAX: {
        "crf_offset": 0,
        "bitrate_mult": 1.0,
        "preset": None,        # использовать из конфига
        "noise_mult": 0.8,
    },
}

DEFAULT_QUALITY = Quality.MAX

# TTL для кэша short_id (секунды)
SHORT_ID_TTL_SECONDS = 3600

# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITS (ANTI-ABUSE)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlanLimits:
    videos_per_week: int = 3          # Видео в неделю
    videos_per_hour: int = 999999     # Legacy (не используется)
    cooldown_seconds: int = 0
    max_file_size_mb: int = 100
    priority: int = 0
    can_disable_text: bool = False    # Может отключать текст
    quality_options: list = None      # Доступные качества

PLAN_LIMITS: Dict[str, PlanLimits] = {
    "free": PlanLimits(
        videos_per_week=3,
        cooldown_seconds=30,
        max_file_size_mb=50,
        priority=0,
        can_disable_text=False,
        quality_options=["low", "medium"],
    ),
    "vip": PlanLimits(
        videos_per_week=15,
        cooldown_seconds=10,
        max_file_size_mb=100,
        priority=1,
        can_disable_text=True,
        quality_options=["low", "medium", "max"],
    ),
    "premium": PlanLimits(
        videos_per_week=999999,  # Безлимит
        cooldown_seconds=0,
        max_file_size_mb=100,
        priority=2,
        can_disable_text=True,
        quality_options=["low", "medium", "max"],
    ),
}

RATE_LIMIT_WINDOW_SECONDS = 604800  # 7 дней (неделя)
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
    "fps_options": [30, 60, 120],
    "gop_min": 15,
    "gop_max": 60,
    "bitrate_min": 20000,
    "bitrate_max": 100000,
    "crf_min": 14,
    "crf_max": 18,
    "presets": ["slow", "slower"],
    "scalers": ["lanczos", "spline"],
    "max_width": 7680,
    "max_height": 4320,
}

TIKTOK_AUDIO = {
    "volume_min": 0.97,
    "volume_max": 1.03,
    "audio_bitrate": "320k",
}

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG VIDEO SETTINGS — YOUTUBE SHORTS MAX
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_VIDEO = {
    **TIKTOK_VIDEO,
    "fps_options": [30, 60, 120],
    "noise_min": 2,
    "noise_max": 4,
    "bitrate_min": 30000,
    "bitrate_max": 150000,
    "crf_min": 12,
    "crf_max": 16,
}

YOUTUBE_AUDIO = {
    "volume_min": 0.96,
    "volume_max": 1.04,
    "audio_bitrate": "320k",
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
    "stats": (
        "📊 <b>Твоя статистика</b>\n\n"
        "📋 План: <b>{plan}</b>\n"
        "📈 Недельный лимит: <b>{weekly_videos}/{weekly_limit}</b>\n\n"
        "🎬 Обработано видео: <b>{total_videos}</b>\n"
        "📅 За сегодня: <b>{today_videos}</b>\n"
        "⏱ Последняя обработка: {last_time}\n\n"
        "🎯 Режим: <b>{mode}</b>\n"
        "🎚 Качество: <b>{quality}</b>\n"
        "📝 Текст: <b>{text_overlay}</b>"
    ),
    "stats_never": "никогда",
    "text_on": "✅ Текст включён",
    "text_off": "❌ Текст выключен",
    "quality_changed": "🎚 Качество: {quality}",
    "settings": (
        "⚙️ <b>Настройки</b>\n\n"
        "🎚 Качество: <b>{quality}</b>\n"
        "📝 Текст на видео: <b>{text_overlay}</b>"
    ),
    "weekly_limit": "⚠️ Лимит исчерпан! Осталось {remaining} видео на этой неделе.\n\n💎 Хочешь больше? Напиши админу для VIP/Premium!",
    "weekly_limit_reached": "⚠️ Ты достиг лимита ({limit} видео/неделю).\n\n💎 Получи VIP или Premium для большего!",
    "vip_granted": "💎 Пользователю {user_id} выдан VIP статус!",
    "premium_granted": "👑 Пользователю {user_id} выдан Premium статус!",
    "plan_removed": "❌ У пользователя {user_id} снят статус, теперь Free.",
    "not_admin": "⛔ У тебя нет прав для этой команды.",
    "invalid_user_id": "⚠️ Неверный ID пользователя. Используй: /vip 123456789",
    "user_info": (
        "👤 <b>Пользователь:</b> {user_id}\n"
        "📋 <b>План:</b> {plan}\n"
        "🎬 <b>Видео за неделю:</b> {weekly_videos}/{weekly_limit}\n"
        "📊 <b>Всего обработано:</b> {total_videos}"
    ),
    "text_disabled_premium": "📝 Отключение текста доступно только для VIP/Premium",
    "quality_locked": "🎚 Качество '{quality}' доступно только для VIP/Premium",
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
    "settings": "⚙️ Настройки",
    "quality_low": "📉 Быстрое",
    "quality_medium": "📊 Среднее",
    "quality_max": "📈 Максимум",
    "text_on": "📝 Текст: ВКЛ",
    "text_off": "📝 Текст: ВЫКЛ",
    "stats": "📊 Статистика",
}
