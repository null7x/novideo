"""
Virex — Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any

# ══════════════════════════════════════════════════════════════════════════════
# BOT VERSION
# ══════════════════════════════════════════════════════════════════════════════
BOT_VERSION = "2.9.0"

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
    # Добавьте сюда свой Telegram ID (узнать: /myid)
]

# Админы по username (без @)
ADMIN_USERNAMES = [
    "Null7_x",
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

# v2.8.0: Auto-retry & Timeout protection
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
DOWNLOAD_TIMEOUT_SECONDS = 120
MEMORY_CLEANUP_INTERVAL_MINUTES = 30

# v2.8.0: Maintenance mode
MAINTENANCE_MODE = False

# v2.9.0: Batch processing
MAX_BATCH_SIZE = 5  # Максимум видео за раз

# v2.9.0: Templates/Presets
EFFECT_TEMPLATES = {
    "viral_tiktok": {
        "name": "🔥 Viral TikTok",
        "description": "Максимум эффектов для TikTok",
        "mode": "tiktok",
        "quality": "max",
        "effects": {"contrast": 1.1, "saturation": 1.1, "noise": 3}
    },
    "clean_youtube": {
        "name": "▶️ Clean YouTube", 
        "description": "Минимальные изменения для YouTube",
        "mode": "youtube",
        "quality": "max",
        "effects": {"contrast": 1.02, "saturation": 1.0, "noise": 1}
    },
    "reels_style": {
        "name": "📸 Reels Style",
        "description": "Оптимизировано для Instagram Reels",
        "mode": "tiktok",
        "quality": "medium",
        "effects": {"contrast": 1.05, "saturation": 1.05, "noise": 2}
    },
    "shorts_format": {
        "name": "📺 Shorts Format",
        "description": "Для YouTube Shorts",
        "mode": "youtube",
        "quality": "max",
        "effects": {"contrast": 1.03, "saturation": 1.02, "noise": 1}
    },
}

# v2.9.0: Resolution options
RESOLUTION_OPTIONS = {
    "1080p": {"width": 1920, "height": 1080},
    "720p": {"width": 1280, "height": 720},
    "480p": {"width": 854, "height": 480},
    "original": None,  # Оставить оригинальное
}

# v2.9.0: Best posting times (UTC+3 Moscow)
BEST_POSTING_TIMES = {
    "tiktok": [
        (7, 9),   # 07:00-09:00
        (12, 14), # 12:00-14:00
        (19, 22), # 19:00-22:00
    ],
    "youtube": [
        (14, 17), # 14:00-17:00
        (20, 23), # 20:00-23:00
    ],
    "instagram": [
        (11, 13), # 11:00-13:00
        (19, 21), # 19:00-21:00
    ],
}

# v2.9.0: Achievements
ACHIEVEMENTS = {
    "first_video": {"name": "🎬 Первое видео", "description": "Обработай первое видео", "points": 10},
    "videos_10": {"name": "⭐ 10 видео", "description": "Обработай 10 видео", "points": 50},
    "videos_50": {"name": "🌟 50 видео", "description": "Обработай 50 видео", "points": 100},
    "videos_100": {"name": "💫 100 видео", "description": "Обработай 100 видео", "points": 200},
    "videos_500": {"name": "🏆 500 видео", "description": "Обработай 500 видео", "points": 500},
    "streak_7": {"name": "🔥 7-дневная серия", "description": "Используй бота 7 дней подряд", "points": 100},
    "streak_30": {"name": "💪 30-дневная серия", "description": "Используй бота 30 дней подряд", "points": 300},
    "referral_1": {"name": "👥 Первый реферал", "description": "Пригласи первого друга", "points": 50},
    "referral_10": {"name": "👥 10 рефералов", "description": "Пригласи 10 друзей", "points": 200},
    "night_owl": {"name": "🌙 Ночная сова", "description": "Обработай видео после полуночи", "points": 20},
    "early_bird": {"name": "🌅 Ранняя пташка", "description": "Обработай видео до 7 утра", "points": 20},
    "speed_demon": {"name": "⚡ Скоростной", "description": "5 видео за 1 час", "points": 50},
    "quality_master": {"name": "💎 Мастер качества", "description": "10 видео в MAX качестве", "points": 30},
    "batch_master": {"name": "📦 Мастер пакетов", "description": "Обработай 5 видео за раз", "points": 50},
}

# v2.9.0: User levels
USER_LEVELS = [
    {"level": 1, "name": "Новичок", "points": 0, "emoji": "🌱"},
    {"level": 2, "name": "Любитель", "points": 100, "emoji": "🌿"},
    {"level": 3, "name": "Опытный", "points": 300, "emoji": "🌳"},
    {"level": 4, "name": "Профи", "points": 600, "emoji": "⭐"},
    {"level": 5, "name": "Эксперт", "points": 1000, "emoji": "🌟"},
    {"level": 6, "name": "Мастер", "points": 2000, "emoji": "💫"},
    {"level": 7, "name": "Гуру", "points": 5000, "emoji": "👑"},
    {"level": 8, "name": "Легенда", "points": 10000, "emoji": "🏆"},
]

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
    videos_per_day: int = 2           # Видео в день
    videos_per_week: int = 14         # Видео в неделю
    cooldown_seconds: int = 0
    max_file_size_mb: int = 100
    priority: int = 0
    can_disable_text: bool = False    # Может отключать текст
    quality_options: list = None      # Доступные качества

# ══════════════════════════════════════════════════════════════════════════════
# PRICING / ЦЕНЫ
# ══════════════════════════════════════════════════════════════════════════════
# Free:    $0       - 2 видео/день
# VIP:     $5/нед   - 100 видео/неделя  ($18/мес, $90/6мес, $150/год)
# Premium: $9/нед   - ∞ безлимит        ($30/мес, $150/6мес, $250/год)
# ══════════════════════════════════════════════════════════════════════════════

PLAN_LIMITS: Dict[str, PlanLimits] = {
    "free": PlanLimits(
        videos_per_day=2,             # 2 видео в день
        videos_per_week=14,           # ~14 в неделю
        cooldown_seconds=60,
        max_file_size_mb=50,
        priority=0,
        can_disable_text=False,
        quality_options=["low", "medium"],
    ),
    "vip": PlanLimits(
        videos_per_day=15,            # 15 видео в день
        videos_per_week=100,          # 100 видео в неделю
        cooldown_seconds=10,
        max_file_size_mb=100,
        priority=1,
        can_disable_text=True,
        quality_options=["low", "medium", "max"],
    ),
    "premium": PlanLimits(
        videos_per_day=999999,        # Безлимит
        videos_per_week=999999,       # Безлимит
        cooldown_seconds=0,
        max_file_size_mb=100,
        priority=2,
        can_disable_text=True,
        quality_options=["low", "medium", "max"],
    ),
}

RATE_LIMIT_WINDOW_SECONDS = 2592000   # 30 дней
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
        "🎬 <b>Virex — Уникализация видео</b>\n\n"
        "📥 Отправь <b>видео</b> или <b>ссылку</b>:\n"
        "• TikTok, YouTube Shorts\n"
        "• Instagram Reels\n"
        "• VK клипы, Twitter/X\n\n"
        "🔥 Режим: <b>TikTok MAX</b>"
    ),
    "start_youtube": (
        "🎬 <b>Virex — Уникализация видео</b>\n\n"
        "📥 Отправь <b>видео</b> или <b>ссылку</b>:\n"
        "• TikTok, YouTube Shorts\n"
        "• Instagram Reels\n"
        "• VK клипы, Twitter/X\n\n"
        "▶️ Режим: <b>YouTube Shorts MAX</b>"
    ),
    "mode_tiktok": "🔥 Режим изменён на <b>TikTok MAX</b>",
    "mode_youtube": "▶️ Режим изменён на <b>YouTube Shorts MAX</b>",
    "how_it_works": (
        "❓ <b>Как это работает</b>\n\n"
        "📥 <b>Скачивание без водяного знака:</b>\n"
        "TikTok, YouTube, Instagram, VK, Twitter/X\n"
        "Douyin, Bilibili, Weibo, Youku, iQiyi, Kuaishou, Xiaohongshu, QQ\n\n"
        "🎬 <b>Уникализация:</b>\n"
        "Бот меняет метаданные, цвета, кадрирование и добавляет шум\n\n"
        "✅ <b>Результат:</b>\n"
        "Видео не определяется как повтор!"
    ),
    "video_received": "🎬 Видео получено",
    "processing": "⏳ Обрабатываем видео...",
    "processing_download": "📥 Скачиваем видео...",
    "processing_analyze": "🔍 Анализируем контент...",
    "processing_unique": "🎨 Уникализируем видео...",
    "processing_upload": "📤 Отправляем результат...",
    "done": "✅ Готово",
    "downloaded": "⬇️ Видео скачано",
    "error": "⚠️ Не удалось обработать видео. Попробуй другой файл.",
    "error_download": "⚠️ Не удалось скачать видео. Проверь ссылку.",
    "error_timeout": "⏱ Превышено время обработки. Попробуй позже.",
    "error_server": "🔧 Сервер перегружен. Попробуй через минуту.",
    "invalid_format": "⚠️ Отправь видео в формате MP4 или MOV",
    "file_too_large": "⚠️ Видео слишком большое. Максимум — 100 МБ",
    "video_too_long": "⚠️ Видео слишком длинное. Максимум — 2 минуты",
    "rate_limit": "⏱ Подожди немного.",
    "cooldown": "⏱ Подожди {seconds} сек перед следующим видео",
    "queue_full": "🔄 Сейчас много запросов. Попробуй через минуту.",
    "duplicate": "🔁 Это видео уже обрабатывается",
    "soft_block": "⏱ Слишком много запросов. Попробуй через 30 минут.",
    "daily_limit_reached": "⚠️ Дневной лимит исчерпан ({used}/{limit}).\n\n💎 Купи VIP/Premium для большего!",
    "weekly_limit_reached": "⚠️ Недельный лимит исчерпан ({used}/{limit}).\n\n💎 Купи VIP/Premium для большего!",
    "button_spam": "",
    "stats": (
        "📊 <b>Твоя статистика</b>\n\n"
        "📋 План: <b>{plan}</b>\n"
        "📅 Сегодня: <b>{daily_videos}/{daily_limit}</b>\n"
        "📆 Неделя: <b>{weekly_videos}/{weekly_limit}</b>\n\n"
        "🎬 Обработано всего: <b>{total_videos}</b>\n"
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
    "monthly_limit": "⚠️ Лимит исчерпан! Осталось {remaining} видео на 30 дней.\n\n💎 Хочешь больше? Напиши админу для VIP/Premium!",
    "monthly_limit_reached": "⚠️ Ты достиг лимита ({used}/{limit} видео за 30 дней).\n\n💎 Получи VIP или Premium для большего!",
    "vip_granted": "💎 Пользователю @{username} (ID: {user_id}) выдан VIP на 30 дней!",
    "premium_granted": "👑 Пользователю @{username} (ID: {user_id}) выдан Premium на 30 дней!",
    "plan_removed": "❌ У @{username} (ID: {user_id}) снят статус, теперь Free.",
    "not_admin": "⛔ У тебя нет прав для этой команды.",
    "invalid_user_id": "⚠️ Неверный ID пользователя. Используй: /vip 123456789",
    "user_info": (
        "👤 <b>Пользователь:</b> @{username} (ID: {user_id})\n"
        "📋 <b>План:</b> {plan}\n"
        "🎬 <b>Видео за 30 дней:</b> {monthly_videos}/{monthly_limit}\n"
        "⬇️ <b>Скачиваний:</b> {total_downloads}\n"
        "📊 <b>Всего обработано:</b> {total_videos}"
    ),
    "text_disabled_premium": "📝 Отключение текста доступно только для VIP/Premium",
    "quality_locked": "🎚 Качество '{quality}' доступно только для VIP/Premium",
    "buy_premium": (
        "� <b>Тарифные планы</b>\n\n"
        "🆓 <b>FREE</b> — бесплатно\n"
        "• 2 видео в день\n"
        "• Стандартное качество\n\n"
        "⭐ <b>VIP</b> — 100 видео/неделя\n"
        "• $5/неделя\n"
        "• $18/месяц\n"
        "• $90/6 месяцев\n"
        "• $150/год\n\n"
        "👑 <b>PREMIUM</b> — безлимит\n"
        "• $9/неделя\n"
        "• $30/месяц\n"
        "• $150/6 месяцев\n"
        "• $250/год\n\n"
        "✅ VIP/Premium: макс. качество, без текста\n\n"
        "💬 Для покупки: @Null7_x"
    ),
    "banned": "🚫 Вы заблокированы.\nПричина: {reason}",
    "referral_info": (
        "👥 <b>Реферальная программа</b>\n\n"
        "🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        "👤 Приглашено: <b>{count}</b> человек\n"
        "🎁 Бонусных видео: <b>{bonus}</b>\n\n"
        "💪 Приглашай друзей и получай <b>+3 видео</b> за каждого!"
    ),
    "referral_bonus_used": "🎁 Использован 1 бонус! Осталось: {remaining}",
    "referral_welcome": "🎉 Ты пришёл по приглашению! Твой друг получил бонус.",
    "plan_expiring": "⚠️ Твой {plan} истекает через {days} дней!\n\nПродли, чтобы сохранить преимущества.",
    "plan_expired": "😔 Твой {plan} истёк. Теперь у тебя Free план.",
    "broadcast_start": "📨 Начинаю рассылку...",
    "broadcast_done": "✅ Рассылка завершена!\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}",
    "user_banned": "🚫 Пользователь @{username} (ID: {user_id}) заблокирован.\nПричина: {reason}",
    "user_unbanned": "✅ Пользователь @{username} (ID: {user_id}) разблокирован.",
    "language_changed": "🌐 Язык изменён на: <b>{lang}</b>",
    "url_received": "🔗 <b>Ссылка получена</b>\n\nВыбери действие:",
    "downloading": "⬇️ Скачиваю видео...",
    # Промо-коды
    "promo_usage": "🎟 Использование: <code>/promo КОД</code>",
    "promo_activated": "🎉 Промо-код активирован!\n\n🎁 Бонус: {bonus}",
    "promo_not_found": "❌ Промо-код не найден",
    "promo_already_used": "⚠️ Ты уже использовал этот промо-код",
    "promo_expired": "⚠️ Промо-код больше не действует",
    # История и отмена
    "history_empty": "📋 История обработок пуста",
    "history_title": "📋 <b>Последние обработки:</b>",
    "no_active_task": "❌ Нет активной задачи для отмены",
    "task_cancelled": "✅ Обработка отменена",
    "cancel_failed": "❌ Не удалось отменить (возможно уже обработано)",
    # Лимит очереди
    "user_queue_limit": "⚠️ У тебя уже есть задачи в очереди. Дождись завершения!",
    # Улучшенные ошибки
    "error_download": "❌ Не удалось скачать видео. Попробуй другую ссылку.",
    "error_youtube": "❌ Ошибка YouTube. Видео может быть недоступно или ограничено.",
    # Help/FAQ
    "help_faq": (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "<b>Q: Почему видео не скачивается?</b>\n"
        "A: Проверь ссылку. Некоторые видео могут быть приватными.\n\n"
        "<b>Q: Что делает уникализация?</b>\n"
        "A: Меняет метаданные, цвета, кадрирование — видео не определяется как повтор.\n\n"
        "<b>Q: Как получить больше видео?</b>\n"
        "A: Купи VIP или Premium, или приглашай друзей!\n\n"
        "<b>Q: Какие платформы поддерживаются?</b>\n"
        "A: TikTok, YouTube, Instagram, VK, Twitter, Douyin, Bilibili, Kuaishou и другие."
    ),
    "report_issue": "📝 <b>Какая проблема?</b>\n\nВыбери тип проблемы:",
    "issue_reported": "✅ <b>Спасибо за репорт!</b>\n\nАдмин скоро рассмотрит твою проблему.",
    # Feedback система
    "feedback_prompt": "📝 <b>Отправь свой отзыв или предложение</b>\n\nНапиши сообщение в ответ:",
    "feedback_sent": "✅ Спасибо за отзыв! Админ скоро его прочитает.",
    "feedback_received": "📩 <b>Новый отзыв!</b>\n\n👤 @{username} (ID: {user_id})\n\n💬 {message}",
    # Allstats для админа
    "allstats": (
        "📊 <b>Полная статистика бота</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        "• Всего: <b>{total_users}</b>\n"
        "• Активных сегодня: <b>{active_today}</b>\n"
        "• Новых сегодня: <b>{new_today}</b>\n\n"
        "📋 <b>По тарифам:</b>\n"
        "• Free: {free_users}\n"
        "• VIP: {vip_users}\n"
        "• Premium: {premium_users}\n\n"
        "🌐 <b>Языки:</b>\n"
        "• 🇷🇺 RU: {ru_users}\n"
        "• 🇬🇧 EN: {en_users}\n\n"
        "🎬 <b>Обработка:</b>\n"
        "• Видео сегодня: <b>{videos_today}</b>\n"
        "• Видео всего: <b>{total_videos}</b>\n"
        "• Скачиваний: <b>{total_downloads}</b>"
    ),
    # Топ пользователей
    "top_users": "🏆 <b>Топ-10 по обработкам:</b>\n\n{top_list}",
    # Банлист
    "banlist_empty": "✅ Нет заблокированных пользователей",
    "banlist_title": "🚫 <b>Заблокированные:</b>\n\n{ban_list}",
    # Очередь
    "queue_position": "📥 Позиция в очереди: #{position}",
    "queue_started": "🎬 Обработка началась...",
    # Быстрые настройки качества
    "quick_quality": "🎚 Выбери качество для этого видео:",
    # Уведомление о подписке
    "subscription_warning": "⚠️ <b>Внимание!</b> Твоя подписка {plan} истекает через {days} {days_word}!",
    # Ночной режим
    "night_mode_on": "🌙 Ночной режим включён (тихие уведомления)",
    "night_mode_off": "☀️ Ночной режим выключен",
    # v2.8.0: Auto-retry & Progress
    "retry_attempt": "🔄 Повторная попытка ({attempt}/{max})...",
    "timeout_error": "⏱ Превышено время ожидания. Попробуй позже.",
    "progress_downloading": "📥 Скачиваю: {percent}%",
    "progress_processing": "🎨 Обрабатываю: {percent}%",
    "progress_uploading": "📤 Отправляю: {percent}%",
    "eta_remaining": "⏱ Осталось: ~{time}",
    # v2.8.0: Maintenance mode
    "maintenance_mode": "🔧 Бот на техобслуживании. Попробуй через {minutes} минут.",
    "maintenance_on": "🔧 Режим техобслуживания ВКЛЮЧЁН",
    "maintenance_off": "✅ Режим техобслуживания ВЫКЛЮЧЕН",
    # v2.8.0: Trial VIP
    "trial_vip_available": "🎁 Попробуй VIP бесплатно на 24 часа!\n\nНажми /trial чтобы активировать.",
    "trial_vip_activated": "🎉 <b>Trial VIP активирован!</b>\n\n⏱ Действует 24 часа\n🎬 100 видео в неделю\n📈 Максимальное качество",
    "trial_vip_already_used": "⚠️ Ты уже использовал пробный период.",
    "trial_vip_not_available": "⚠️ Trial доступен только для Free пользователей.",
    # v2.8.0: Streak bonus
    "streak_info": "🔥 <b>Твоя серия:</b> {streak} дней\n\n{bonus_text}",
    "streak_bonus": "🎁 Бонус за 7-дневную серию: <b>+1 видео/день</b>",
    "streak_no_bonus": "Используй бота каждый день чтобы получить бонус!",
    "streak_lost": "😔 Серия сброшена. Начни заново!",
    "streak_continued": "🔥 Отлично! Серия продолжается: {streak} дней",
    # v2.8.0: History
    "history_title": "📜 <b>Последние 10 видео:</b>\n\n{history_list}",
    "history_empty": "📜 История пуста",
    "history_item": "{num}. {date} — {mode} ({source})",
    # v2.8.0: Queue status
    "queue_status": "📊 <b>Статус очереди</b>\n\n📥 В очереди: {queue_size}\n👷 Воркеров: {workers}\n⏱ Примерное время: ~{eta}",
    # v2.8.0: Logs
    "logs_title": "📝 <b>Последние операции:</b>\n\n{logs_list}",
    "logs_empty": "📝 Логи пусты",
    # v2.8.0: Error details
    "error_details": "⚠️ <b>Ошибка:</b> {error_type}\n\n<code>{details}</code>\n\n💡 {suggestion}",
    # v2.8.0: Broadcast confirm
    "broadcast_confirm": "📢 <b>Подтверди рассылку</b>\n\n👥 Получателей: {count}\n\n📝 Текст:\n{text}",
    "broadcast_cancelled": "❌ Рассылка отменена",
    # v2.8.0: Favorites
    "favorites_title": "⭐ <b>Избранные настройки:</b>\n\n{favorites_list}",
    "favorites_empty": "⭐ Нет сохранённых настроек\n\nИспользуй /savefav для сохранения текущих настроек.",
    "favorite_saved": "⭐ Настройки сохранены как '{name}'",
    "favorite_loaded": "✅ Загружены настройки '{name}'",
    "favorite_deleted": "🗑 Удалены настройки '{name}'",
    
    # v2.9.0: Batch processing
    "batch_start": "📦 <b>Пакетная обработка</b>\n\n🎬 Видео в очереди: {count}/{max}\n⏳ Начинаю обработку...",
    "batch_progress": "📦 Обработка: {current}/{total}\n{progress_bar}",
    "batch_done": "✅ <b>Пакетная обработка завершена!</b>\n\n✅ Успешно: {success}\n❌ Ошибок: {errors}",
    "batch_limit": "⚠️ Максимум {max} видео за раз",
    
    # v2.9.0: Trim video
    "trim_usage": "✂️ <b>Обрезка видео</b>\n\n📝 Формат: <code>/trim MM:SS MM:SS</code>\n📝 Пример: <code>/trim 00:10 00:45</code>\n\n⚠️ Сначала отправь видео!",
    "trim_invalid": "⚠️ Неверный формат времени.\n\nИспользуй: <code>/trim 00:10 00:45</code>",
    "trim_processing": "✂️ Обрезаю видео с {start} по {end}...",
    "trim_done": "✅ Видео обрезано!",
    "trim_set": "✂️ Обрезка установлена: {start} → {end}\n\nТеперь отправь видео для обработки.",
    
    # v2.9.0: Add music
    "music_usage": "🎵 <b>Добавление музыки</b>\n\n1️⃣ Отправь видео\n2️⃣ Ответь на него аудио/голосовым\n\nИли используй: <code>/music</code> после отправки видео",
    "music_waiting": "🎵 Теперь отправь аудиофайл или голосовое сообщение",
    "music_processing": "🎵 Накладываю музыку...",
    "music_done": "✅ Музыка добавлена!",
    "music_invalid": "⚠️ Отправь аудиофайл в формате MP3, OGG или M4A",
    
    # v2.9.0: Convert format
    "convert_menu": "🔄 <b>Конвертер форматов</b>\n\nВыбери формат:",
    "convert_processing": "🔄 Конвертирую в {format}...",
    "convert_done": "✅ Конвертация завершена!",
    "convert_to_gif": "🔄 Создаю GIF...",
    "convert_to_mp3": "🎵 Извлекаю аудио...",
    
    # v2.9.0: Custom watermark
    "watermark_usage": "🖼 <b>Свой водяной знак</b>\n\n📝 Отправь изображение (PNG с прозрачностью)\n\n💎 Доступно для VIP/Premium",
    "watermark_set": "✅ Водяной знак установлен!",
    "watermark_removed": "🗑 Водяной знак удалён",
    "watermark_position": "📍 Выбери позицию водяного знака:",
    "watermark_vip_only": "⚠️ Свой водяной знак доступен только для VIP/Premium",
    
    # v2.9.0: Resolution
    "resolution_menu": "📐 <b>Изменение разрешения</b>\n\nТекущее: {current}\nВыбери новое:",
    "resolution_changed": "📐 Разрешение изменено на {resolution}",
    
    # v2.9.0: Effect templates
    "templates_menu": "🎨 <b>Шаблоны эффектов</b>\n\nВыбери готовый пресет:",
    "template_applied": "✅ Применён шаблон: {name}\n\n{description}",
    
    # v2.9.0: Posting reminder
    "reminder_set": "⏰ <b>Напоминание установлено!</b>\n\nПлатформа: {platform}\nВремя: {time}\n\nЯ напомню когда лучше выложить видео!",
    "reminder_notify": "⏰ <b>Время публиковать!</b>\n\n📱 Сейчас лучшее время для {platform}\n🎬 Выложи своё видео!",
    "best_times": "📊 <b>Лучшее время для публикации:</b>\n\n{times_list}",
    
    # v2.9.0: Gamification
    "achievement_unlocked": "🏆 <b>Достижение разблокировано!</b>\n\n{name}\n{description}\n\n+{points} очков",
    "achievements_list": "🏆 <b>Твои достижения</b>\n\n{achievements}\n\n📊 Очков: <b>{total_points}</b>",
    "level_up": "🎉 <b>Новый уровень!</b>\n\n{emoji} <b>{level_name}</b>\n\nПоздравляем! Ты достиг уровня {level}!",
    "profile": "👤 <b>Твой профиль</b>\n\n{emoji} <b>{level_name}</b> (Уровень {level})\n📊 Очков: {points}/{next_level_points}\n{progress_bar}\n\n🎬 Видео: {total_videos}\n🔥 Серия: {streak} дней\n👥 Рефералов: {referrals}",
    "leaderboard": "🏆 <b>Таблица лидеров</b>\n\n{leaderboard}",
    "daily_challenge": "📅 <b>Ежедневное задание</b>\n\n{challenge}\n\nНаграда: +{reward} очков",
    "challenge_completed": "✅ <b>Задание выполнено!</b>\n\n+{reward} очков",
    
    # v2.9.0: Analytics
    "analytics": "📈 <b>Твоя аналитика</b>\n\n📊 <b>За неделю:</b>\n{weekly_chart}\n\n🎬 Видео: {weekly_videos}\n⏱ Среднее время: {avg_time}\n\n💡 <b>Рекомендация:</b>\n{recommendation}",
    "analytics_chart": "{day}: {bar} {count}",
}

# ══════════════════════════════════════════════════════════════════════════════
# ENGLISH TEXTS
# ══════════════════════════════════════════════════════════════════════════════

TEXTS_EN = {
    "start": (
        "🎬 <b>Virex — Video Uniqualization</b>\n\n"
        "📥 Send <b>video</b> or <b>link</b>:\n"
        "• TikTok, YouTube Shorts\n"
        "• Instagram Reels\n"
        "• VK clips, Twitter/X\n\n"
        "🔥 Mode: <b>TikTok MAX</b>"
    ),
    "start_youtube": (
        "🎬 <b>Virex — Video Uniqualization</b>\n\n"
        "📥 Send <b>video</b> or <b>link</b>:\n"
        "• TikTok, YouTube Shorts\n"
        "• Instagram Reels\n"
        "• VK clips, Twitter/X\n\n"
        "▶️ Mode: <b>YouTube Shorts MAX</b>"
    ),
    "mode_tiktok": "🔥 Mode changed to <b>TikTok MAX</b>",
    "mode_youtube": "▶️ Mode changed to <b>YouTube Shorts MAX</b>",
    "how_it_works": (
        "❓ <b>How it works</b>\n\n"
        "📥 <b>Download without watermark:</b>\n"
        "TikTok, YouTube, Instagram, VK, Twitter/X\n"
        "Douyin, Bilibili, Weibo, Youku, iQiyi, Kuaishou, Xiaohongshu, QQ\n\n"
        "🎬 <b>Uniqualization:</b>\n"
        "Bot changes metadata, colors, crop and adds noise\n\n"
        "✅ <b>Result:</b>\n"
        "Video is not detected as duplicate!"
    ),
    "video_received": "🎬 Video received",
    "processing": "⏳ Processing video...",
    "processing_download": "📥 Downloading video...",
    "processing_analyze": "🔍 Analyzing content...",
    "processing_unique": "🎨 Making video unique...",
    "processing_upload": "📤 Uploading result...",
    "done": "✅ Done",
    "downloaded": "⬇️ Video downloaded",
    "error": "⚠️ Failed to process video. Try another file.",
    "error_download": "⚠️ Failed to download video. Check the link.",
    "error_timeout": "⏱ Processing timeout. Try later.",
    "error_server": "🔧 Server overloaded. Try in a minute.",
    "invalid_format": "⚠️ Send video in MP4 or MOV format",
    "file_too_large": "⚠️ Video is too large. Maximum — 100 MB",
    "video_too_long": "⚠️ Video is too long. Maximum — 2 minutes",
    "rate_limit": "⏱ Please wait.",
    "cooldown": "⏱ Wait {seconds} sec before next video",
    "queue_full": "🔄 Too many requests. Try in a minute.",
    "duplicate": "🔁 This video is already processing",
    "soft_block": "⏱ Too many requests. Try in 30 minutes.",
    "daily_limit_reached": "⚠️ Daily limit reached ({used}/{limit}).\n\n💎 Get VIP/Premium for more!",
    "weekly_limit_reached": "⚠️ Weekly limit reached ({used}/{limit}).\n\n💎 Get VIP/Premium for more!",
    "stats": (
        "📊 <b>Your Statistics</b>\n\n"
        "📋 Plan: <b>{plan}</b>\n"
        "📅 Today: <b>{daily_videos}/{daily_limit}</b>\n"
        "📆 Week: <b>{weekly_videos}/{weekly_limit}</b>\n\n"
        "🎬 Total processed: <b>{total_videos}</b>\n"
        "⬇️ Downloads: <b>{total_downloads}</b>\n\n"
        "🔥 Mode: <b>{mode}</b>\n"
        "🎚 Quality: <b>{quality}</b>\n"
        "📝 Text: <b>{text_overlay}</b>"
    ),
    "monthly_limit_reached": "⚠️ Limit reached ({used}/{limit} videos per week).\n\n💎 Get VIP or Premium for more!",
    "buy_premium": (
        "� <b>Pricing Plans</b>\n\n"
        "🆓 <b>FREE</b> — free\n"
        "• 2 videos per day\n"
        "• Standard quality\n\n"
        "⭐ <b>VIP</b> — 100 videos/week\n"
        "• $5/week\n"
        "• $18/month\n"
        "• $90/6 months\n"
        "• $150/year\n\n"
        "👑 <b>PREMIUM</b> — unlimited\n"
        "• $9/week\n"
        "• $30/month\n"
        "• $150/6 months\n"
        "• $250/year\n\n"
        "✅ VIP/Premium: max quality, no watermark\n\n"
        "💬 To purchase: @Null7_x"
    ),
    "banned": "🚫 You are banned.\nReason: {reason}",
    "referral_info": (
        "👥 <b>Referral Program</b>\n\n"
        "🔗 Your link:\n<code>{link}</code>\n\n"
        "👤 Invited: <b>{count}</b> people\n"
        "🎁 Bonus videos: <b>{bonus}</b>\n\n"
        "💪 Invite friends and get <b>+3 videos</b> for each!"
    ),
    "plan_expiring": "⚠️ Your {plan} expires in {days} days!\n\nRenew to keep benefits.",
    "plan_expired": "😔 Your {plan} has expired. You now have Free plan.",
    "broadcast_start": "📨 Starting broadcast...",
    "broadcast_done": "✅ Broadcast complete!\n\n📨 Sent: {sent}\n❌ Errors: {failed}",
    "user_banned": "🚫 User @{username} (ID: {user_id}) has been banned.\nReason: {reason}",
    "user_unbanned": "✅ User @{username} (ID: {user_id}) has been unbanned.",
    "language_changed": "🌐 Language changed to: <b>{lang}</b>",
    "url_received": "🔗 <b>Link received</b>\n\nChoose action:",
    "downloading": "⬇️ Downloading video...",
    "stats_never": "never",
    "text_on": "✅ Text enabled",
    "text_off": "❌ Text disabled",
    "quality_changed": "🎚 Quality: {quality}",
    "settings": (
        "⚙️ <b>Settings</b>\n\n"
        "🎚 Quality: <b>{quality}</b>\n"
        "📝 Text on video: <b>{text_overlay}</b>"
    ),
    "referral_bonus_used": "🎁 Used 1 bonus! Remaining: {remaining}",
    "referral_welcome": "🎉 You came from a referral! Your friend got a bonus.",
    "user_info": (
        "👤 <b>User:</b> @{username} (ID: {user_id})\n"
        "📋 <b>Plan:</b> {plan}\n"
        "🎬 <b>Videos (30 days):</b> {monthly_videos}/{monthly_limit}\n"
        "⬇️ <b>Downloads:</b> {total_downloads}\n"
        "📊 <b>Total processed:</b> {total_videos}"
    ),
    "invalid_user_id": "⚠️ Invalid user ID. Use: /vip 123456789",
    "text_disabled_premium": "📝 Disabling text is only available for VIP/Premium",
    "plan_removed": "❌ @{username} (ID: {user_id}) status removed, now Free.",
    "button_spam": "",
    "quality_locked": "🎚 Quality '{quality}' is only available for VIP/Premium",
    "not_admin": "⛔ You don't have permission for this command.",
    "premium_granted": "👑 User @{username} (ID: {user_id}) received Premium for 30 days!",
    "vip_granted": "💎 User @{username} (ID: {user_id}) received VIP for 30 days!",
    "monthly_limit": "⚠️ Limit exhausted! {remaining} videos left for 30 days.\n\n💎 Want more? Contact admin for VIP/Premium!",
    # Promo codes
    "promo_usage": "🎟 Usage: <code>/promo CODE</code>",
    "promo_activated": "🎉 Promo code activated!\n\n🎁 Bonus: {bonus}",
    "promo_not_found": "❌ Promo code not found",
    "promo_already_used": "⚠️ You've already used this promo code",
    "promo_expired": "⚠️ This promo code is no longer valid",
    # History and cancel
    "history_empty": "📋 Processing history is empty",
    "history_title": "📋 <b>Recent processing:</b>",
    "no_active_task": "❌ No active task to cancel",
    "task_cancelled": "✅ Processing cancelled",
    "cancel_failed": "❌ Could not cancel (possibly already processed)",
    # Queue limit
    "user_queue_limit": "⚠️ You already have tasks in queue. Wait for completion!",
    # Improved errors
    "error_download": "❌ Could not download video. Try another link.",
    "error_youtube": "❌ YouTube error. Video may be unavailable or restricted.",
    # Help/FAQ
    "help_faq": (
        "❓ <b>Frequently Asked Questions</b>\n\n"
        "<b>Q: Why won't the video download?</b>\n"
        "A: Check the link. Some videos may be private.\n\n"
        "<b>Q: What does uniqualization do?</b>\n"
        "A: Changes metadata, colors, cropping — video is not detected as duplicate.\n\n"
        "<b>Q: How to get more videos?</b>\n"
        "A: Buy VIP or Premium, or invite friends!\n\n"
        "<b>Q: What platforms are supported?</b>\n"
        "A: TikTok, YouTube, Instagram, VK, Twitter, Douyin, Bilibili, Kuaishou and others."
    ),
    "report_issue": "📝 <b>What's the problem?</b>\n\nChoose issue type:",
    "issue_reported": "✅ <b>Thanks for the report!</b>\n\nAdmin will review your issue soon.",
    # Feedback system
    "feedback_prompt": "📝 <b>Send your feedback or suggestion</b>\n\nReply with your message:",
    "feedback_sent": "✅ Thanks for the feedback! Admin will read it soon.",
    "feedback_received": "📩 <b>New feedback!</b>\n\n👤 @{username} (ID: {user_id})\n\n💬 {message}",
    # Allstats for admin
    "allstats": (
        "📊 <b>Full Bot Statistics</b>\n\n"
        "👥 <b>Users:</b>\n"
        "• Total: <b>{total_users}</b>\n"
        "• Active today: <b>{active_today}</b>\n"
        "• New today: <b>{new_today}</b>\n\n"
        "📋 <b>By plan:</b>\n"
        "• Free: {free_users}\n"
        "• VIP: {vip_users}\n"
        "• Premium: {premium_users}\n\n"
        "🌐 <b>Languages:</b>\n"
        "• 🇷🇺 RU: {ru_users}\n"
        "• 🇬🇧 EN: {en_users}\n\n"
        "🎬 <b>Processing:</b>\n"
        "• Videos today: <b>{videos_today}</b>\n"
        "• Videos total: <b>{total_videos}</b>\n"
        "• Downloads: <b>{total_downloads}</b>"
    ),
    # Top users
    "top_users": "🏆 <b>Top 10 by processing:</b>\n\n{top_list}",
    # Banlist
    "banlist_empty": "✅ No banned users",
    "banlist_title": "🚫 <b>Banned users:</b>\n\n{ban_list}",
    # Queue
    "queue_position": "📥 Queue position: #{position}",
    "queue_started": "🎬 Processing started...",
    # Quick quality settings
    "quick_quality": "🎚 Choose quality for this video:",
    # Subscription warning
    "subscription_warning": "⚠️ <b>Warning!</b> Your {plan} subscription expires in {days} {days_word}!",
    # Night mode
    "night_mode_on": "🌙 Night mode enabled (quiet notifications)",
    "night_mode_off": "☀️ Night mode disabled",
    # v2.8.0: Auto-retry & Progress
    "retry_attempt": "🔄 Retry attempt ({attempt}/{max})...",
    "timeout_error": "⏱ Timeout exceeded. Try again later.",
    "progress_downloading": "📥 Downloading: {percent}%",
    "progress_processing": "🎨 Processing: {percent}%",
    "progress_uploading": "📤 Uploading: {percent}%",
    "eta_remaining": "⏱ Remaining: ~{time}",
    # v2.8.0: Maintenance mode
    "maintenance_mode": "🔧 Bot is under maintenance. Try again in {minutes} minutes.",
    "maintenance_on": "🔧 Maintenance mode ENABLED",
    "maintenance_off": "✅ Maintenance mode DISABLED",
    # v2.8.0: Trial VIP
    "trial_vip_available": "🎁 Try VIP free for 24 hours!\n\nPress /trial to activate.",
    "trial_vip_activated": "🎉 <b>Trial VIP activated!</b>\n\n⏱ Valid for 24 hours\n🎬 100 videos per week\n📈 Maximum quality",
    "trial_vip_already_used": "⚠️ You've already used your trial period.",
    "trial_vip_not_available": "⚠️ Trial is only available for Free users.",
    # v2.8.0: Streak bonus
    "streak_info": "🔥 <b>Your streak:</b> {streak} days\n\n{bonus_text}",
    "streak_bonus": "🎁 7-day streak bonus: <b>+1 video/day</b>",
    "streak_no_bonus": "Use the bot daily to get a bonus!",
    "streak_lost": "😔 Streak reset. Start again!",
    "streak_continued": "🔥 Great! Streak continues: {streak} days",
    # v2.8.0: History
    "history_title": "📜 <b>Last 10 videos:</b>\n\n{history_list}",
    "history_empty": "📜 History is empty",
    "history_item": "{num}. {date} — {mode} ({source})",
    # v2.8.0: Queue status
    "queue_status": "📊 <b>Queue Status</b>\n\n📥 In queue: {queue_size}\n👷 Workers: {workers}\n⏱ Estimated time: ~{eta}",
    # v2.8.0: Logs
    "logs_title": "📝 <b>Recent operations:</b>\n\n{logs_list}",
    "logs_empty": "📝 Logs are empty",
    # v2.8.0: Error details
    "error_details": "⚠️ <b>Error:</b> {error_type}\n\n<code>{details}</code>\n\n💡 {suggestion}",
    # v2.8.0: Broadcast confirm
    "broadcast_confirm": "📢 <b>Confirm broadcast</b>\n\n👥 Recipients: {count}\n\n📝 Text:\n{text}",
    "broadcast_cancelled": "❌ Broadcast cancelled",
    # v2.8.0: Favorites
    "favorites_title": "⭐ <b>Favorite settings:</b>\n\n{favorites_list}",
    "favorites_empty": "⭐ No saved settings\n\nUse /savefav to save current settings.",
    "favorite_saved": "⭐ Settings saved as '{name}'",
    "favorite_loaded": "✅ Loaded settings '{name}'",
    "favorite_deleted": "🗑 Deleted settings '{name}'",
    
    # v2.9.0: Batch processing
    "batch_start": "📦 <b>Batch Processing</b>\n\n🎬 Videos in queue: {count}/{max}\n⏳ Starting...",
    "batch_progress": "📦 Processing: {current}/{total}\n{progress_bar}",
    "batch_done": "✅ <b>Batch processing complete!</b>\n\n✅ Success: {success}\n❌ Errors: {errors}",
    "batch_limit": "⚠️ Maximum {max} videos at once",
    
    # v2.9.0: Trim video
    "trim_usage": "✂️ <b>Trim Video</b>\n\n📝 Format: <code>/trim MM:SS MM:SS</code>\n📝 Example: <code>/trim 00:10 00:45</code>\n\n⚠️ Send video first!",
    "trim_invalid": "⚠️ Invalid time format.\n\nUse: <code>/trim 00:10 00:45</code>",
    "trim_processing": "✂️ Trimming video from {start} to {end}...",
    "trim_done": "✅ Video trimmed!",
    "trim_set": "✂️ Trim set: {start} → {end}\n\nNow send a video to process.",
    
    # v2.9.0: Add music
    "music_usage": "🎵 <b>Add Music</b>\n\n1️⃣ Send video\n2️⃣ Reply with audio/voice\n\nOr use: <code>/music</code> after sending video",
    "music_waiting": "🎵 Now send an audio file or voice message",
    "music_processing": "🎵 Adding music...",
    "music_done": "✅ Music added!",
    "music_invalid": "⚠️ Send audio file in MP3, OGG or M4A format",
    
    # v2.9.0: Convert format
    "convert_menu": "🔄 <b>Format Converter</b>\n\nChoose format:",
    "convert_processing": "🔄 Converting to {format}...",
    "convert_done": "✅ Conversion complete!",
    "convert_to_gif": "🔄 Creating GIF...",
    "convert_to_mp3": "🎵 Extracting audio...",
    
    # v2.9.0: Custom watermark
    "watermark_usage": "🖼 <b>Custom Watermark</b>\n\n📝 Send image (PNG with transparency)\n\n💎 Available for VIP/Premium",
    "watermark_set": "✅ Watermark set!",
    "watermark_removed": "🗑 Watermark removed",
    "watermark_position": "📍 Choose watermark position:",
    "watermark_vip_only": "⚠️ Custom watermark is VIP/Premium only",
    
    # v2.9.0: Resolution
    "resolution_menu": "📐 <b>Change Resolution</b>\n\nCurrent: {current}\nChoose new:",
    "resolution_changed": "📐 Resolution changed to {resolution}",
    
    # v2.9.0: Effect templates
    "templates_menu": "🎨 <b>Effect Templates</b>\n\nChoose a preset:",
    "template_applied": "✅ Applied template: {name}\n\n{description}",
    
    # v2.9.0: Posting reminder
    "reminder_set": "⏰ <b>Reminder set!</b>\n\nPlatform: {platform}\nTime: {time}\n\nI'll remind you when to post!",
    "reminder_notify": "⏰ <b>Time to post!</b>\n\n📱 Best time for {platform} now\n🎬 Upload your video!",
    "best_times": "📊 <b>Best posting times:</b>\n\n{times_list}",
    
    # v2.9.0: Gamification
    "achievement_unlocked": "🏆 <b>Achievement Unlocked!</b>\n\n{name}\n{description}\n\n+{points} points",
    "achievements_list": "🏆 <b>Your Achievements</b>\n\n{achievements}\n\n📊 Points: <b>{total_points}</b>",
    "level_up": "🎉 <b>Level Up!</b>\n\n{emoji} <b>{level_name}</b>\n\nCongrats! You reached level {level}!",
    "profile": "👤 <b>Your Profile</b>\n\n{emoji} <b>{level_name}</b> (Level {level})\n📊 Points: {points}/{next_level_points}\n{progress_bar}\n\n🎬 Videos: {total_videos}\n🔥 Streak: {streak} days\n👥 Referrals: {referrals}",
    "leaderboard": "🏆 <b>Leaderboard</b>\n\n{leaderboard}",
    "daily_challenge": "📅 <b>Daily Challenge</b>\n\n{challenge}\n\nReward: +{reward} points",
    "challenge_completed": "✅ <b>Challenge Completed!</b>\n\n+{reward} points",
    
    # v2.9.0: Analytics
    "analytics": "📈 <b>Your Analytics</b>\n\n📊 <b>This week:</b>\n{weekly_chart}\n\n🎬 Videos: {weekly_videos}\n⏱ Avg time: {avg_time}\n\n💡 <b>Recommendation:</b>\n{recommendation}",
    "analytics_chart": "{day}: {bar} {count}",
}

BUTTONS_EN = {
    "tiktok_on": "🔥 TikTok MAX — ON",
    "youtube_on": "▶️ YouTube Shorts — ON",
    "switch_youtube": "▶️ Switch to YouTube Shorts",
    "switch_tiktok": "🔥 Switch to TikTok MAX",
    "how_it_works": "ℹ️ How it works",
    "uniqualize": "🎯 Uniqualize",
    "download_only": "⬇️ Download only",
    "download": "⬇️ Download video",
    "again": "🔁 Uniqualize again",
    "change_mode": "🔀 Change mode",
    "back": "◀️ Back",
    "settings": "⚙️ Settings",
    "quality_low": "📉 Fast",
    "quality_medium": "📊 Medium",
    "quality_max": "📈 Maximum",
    "text_on": "📝 Text: ON",
    "text_off": "📝 Text: OFF",
    "stats": "📊 My Statistics",
    "buy_premium": "� Pricing Plans",
    "main_menu": "🏠 Main Menu",
    "referral": "👥 Referrals",
    "language": "🌐 Language",
    "update_ytdlp": "🔄 Update yt-dlp",
    "admin_stats": "📊 Global Statistics",
    "help": "❓ Help / FAQ",
    "feedback": "📝 Feedback",
    "top": "🏆 Top Users",
    "night_mode": "🌙 Night Mode",
    # v2.8.0
    "history": "📜 History",
    "queue": "📊 Queue",
    "favorites": "⭐ Favorites",
    "streak": "🔥 Streak",
    "trial": "🎁 Trial VIP",
    # v2.9.0
    "trim": "✂️ Trim",
    "add_music": "🎵 Add Music",
    "convert": "🔄 Convert",
    "watermark": "🖼 Watermark",
    "resolution": "📐 Resolution",
    "templates": "🎨 Templates",
    "reminder": "⏰ Reminder",
    "achievements": "🏆 Achievements",
    "profile": "👤 Profile",
    "leaderboard": "🏆 Leaderboard",
    "analytics": "📈 Analytics",
    "to_gif": "GIF",
    "to_mp3": "MP3",
    "to_webm": "WebM",
    "1080p": "1080p",
    "720p": "720p",
    "480p": "480p",
    "original": "Original",
    "position_tl": "↖️ Top-Left",
    "position_tr": "↗️ Top-Right",
    "position_bl": "↙️ Bottom-Left",
    "position_br": "↘️ Bottom-Right",
    "position_center": "⭕ Center",
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
    "download_only": "⬇️ Только скачать",
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
    "stats": "📊 Моя статистика",
    "buy_premium": "� Тарифы и цены",
    "main_menu": "🏠 Главное меню",
    "update_ytdlp": "🔄 Обновить yt-dlp",
    "admin_stats": "📊 Глобальная статистика",
    "referral": "👥 Рефералы",
    "language": "🌐 Язык",
    "help": "❓ Помощь / FAQ",
    "feedback": "📝 Отзыв",
    "top": "🏆 Топ юзеров",
    "night_mode": "🌙 Ночной режим",
    # v2.8.0
    "history": "📜 История",
    "queue": "📊 Очередь",
    "favorites": "⭐ Избранное",
    "streak": "🔥 Серия",
    "trial": "🎁 Пробный VIP",
}
