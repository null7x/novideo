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
    videos_per_month: int = 3         # Видео на 30 дней
    cooldown_seconds: int = 0
    max_file_size_mb: int = 100
    priority: int = 0
    can_disable_text: bool = False    # Может отключать текст
    quality_options: list = None      # Доступные качества

PLAN_LIMITS: Dict[str, PlanLimits] = {
    "free": PlanLimits(
        videos_per_month=3,           # 3 видео на 30 дней
        cooldown_seconds=30,
        max_file_size_mb=50,
        priority=0,
        can_disable_text=False,
        quality_options=["low", "medium"],
    ),
    "vip": PlanLimits(
        videos_per_month=30,          # 30 видео на 30 дней
        cooldown_seconds=10,
        max_file_size_mb=100,
        priority=1,
        can_disable_text=True,
        quality_options=["low", "medium", "max"],
    ),
    "premium": PlanLimits(
        videos_per_month=999999,      # Безлимит
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
    "done": "✅ Готово",
    "downloaded": "⬇️ Видео скачано",
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
        "📈 Лимит (30 дней): <b>{monthly_videos}/{monthly_limit}</b>\n\n"
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
        "💎 <b>Получи Premium!</b>\n\n"
        "✅ <b>30 видео</b> в месяц (вместо 3)\n"
        "✅ <b>Максимальное качество</b> обработки\n"
        "✅ <b>Отключение текста</b> на видео\n"
        "✅ <b>Минимальный cooldown</b>\n\n"
        "💵 <b>Цена: $3/месяц</b>\n\n"
        "💬 Для покупки напиши: @Null7_x"
    ),
    "banned": "🚫 Вы заблокированы.\nПричина: {reason}",
    "referral_info": (
        "👥 <b>Реферальная программа</b>\n\n"
        "🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        "👤 Приглашено: <b>{count}</b> человек\n"
        "🎁 Бонусных видео: <b>{bonus}</b>\n\n"
        "Приглашай друзей и получай +1 видео за каждого!"
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
    "done": "✅ Done",
    "downloaded": "⬇️ Video downloaded",
    "error": "⚠️ Failed to process video. Try another file.",
    "error_download": "⚠️ Failed to download video. Check the link.",
    "invalid_format": "⚠️ Send video in MP4 or MOV format",
    "file_too_large": "⚠️ Video is too large. Maximum — 100 MB",
    "video_too_long": "⚠️ Video is too long. Maximum — 2 minutes",
    "rate_limit": "⏱ Please wait.",
    "cooldown": "⏱ Wait {seconds} sec before next video",
    "queue_full": "🔄 Too many requests. Try in a minute.",
    "duplicate": "🔁 This video is already processing",
    "soft_block": "⏱ Too many requests. Try in 30 minutes.",
    "stats": (
        "📊 <b>Your Statistics</b>\n\n"
        "📋 Plan: <b>{plan}</b>\n"
        "🎬 Videos (30 days): <b>{monthly_videos}/{monthly_limit}</b> (left: {monthly_remaining})\n"
        "📈 Total processed: <b>{total_videos}</b>\n"
        "⬇️ Downloads: <b>{total_downloads}</b>\n\n"
        "🔥 Mode: <b>{mode}</b>\n"
        "🎚 Quality: <b>{quality}</b>\n"
        "📝 Text: <b>{text_overlay}</b>"
    ),
    "monthly_limit_reached": "⚠️ Limit reached ({used}/{limit} videos per 30 days).\n\n💎 Get VIP or Premium for more!",
    "buy_premium": (
        "💎 <b>Get Premium!</b>\n\n"
        "✅ <b>30 videos</b> per month (instead of 3)\n"
        "✅ <b>Maximum quality</b> processing\n"
        "✅ <b>Disable text</b> on video\n"
        "✅ <b>Minimum cooldown</b>\n\n"
        "💵 <b>Price: $3/month</b>\n\n"
        "💬 To purchase write: @Null7_x"
    ),
    "banned": "🚫 You are banned.\nReason: {reason}",
    "referral_info": (
        "👥 <b>Referral Program</b>\n\n"
        "🔗 Your link:\n<code>{link}</code>\n\n"
        "👤 Invited: <b>{count}</b> people\n"
        "🎁 Bonus videos: <b>{bonus}</b>\n\n"
        "Invite friends and get +1 video for each!"
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
    "buy_premium": "💎 Buy Premium — $3",
    "main_menu": "🏠 Main Menu",
    "referral": "👥 Referrals",
    "language": "🌐 Language",
    "update_ytdlp": "🔄 Update yt-dlp",
    "admin_stats": "📊 Global Statistics",
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
    "buy_premium": "💎 Купить Premium — $3",
    "main_menu": "🏠 Главное меню",
    "update_ytdlp": "🔄 Обновить yt-dlp",
    "admin_stats": "📊 Глобальная статистика",
    "referral": "👥 Рефералы",
    "language": "🌐 Язык",
}
