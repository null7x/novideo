"""
Virex — Telegram Bot
"""
import os
import re
import asyncio
import logging
import uuid
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import (
    BOT_TOKEN, Mode, DEFAULT_MODE,
    MAX_FILE_SIZE_MB, MAX_VIDEO_DURATION_SECONDS, ALLOWED_EXTENSIONS,
    TEXTS, BUTTONS, Quality, QUALITY_SETTINGS, SHORT_ID_TTL_SECONDS,
    ADMIN_IDS, ADMIN_USERNAMES, PLAN_LIMITS,
    TEXTS_EN, BUTTONS_EN
)
from rate_limit import rate_limiter
from ffmpeg_utils import (
    start_workers, add_to_queue, ProcessingTask,
    get_temp_dir, generate_unique_filename, cleanup_file,
    cleanup_old_files, get_queue_size
)
import time as time_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_text(user_id: int, key: str, **kwargs) -> str:
    """ Получить текст на языке пользователя """
    lang = rate_limiter.get_language(user_id)
    texts = TEXTS_EN if lang == "en" else TEXTS
    text = texts.get(key, TEXTS.get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text


def get_button(user_id: int, key: str) -> str:
    """ Получить текст кнопки на языке пользователя """
    lang = rate_limiter.get_language(user_id)
    buttons = BUTTONS_EN if lang == "en" else BUTTONS
    return buttons.get(key, BUTTONS.get(key, key))

# Увеличенный таймаут для отправки больших файлов (5 минут)
session = AiohttpSession(timeout=300)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)
dp = Dispatcher()

pending_files: dict = {}
short_id_map: dict = {}  # short_id -> {file_id, created_at}
pending_referrers: dict = {}  # user_id -> referrer_id (для новых пользователей)

def generate_short_id() -> str:
    return uuid.uuid4().hex[:8]

def cleanup_short_id_map():
    """ Очистка устаревших short_id """
    now = time_module.time()
    expired = [k for k, v in short_id_map.items() 
               if now - v.get("created_at", 0) > SHORT_ID_TTL_SECONDS]
    for k in expired:
        short_id_map.pop(k, None)
        pending_files.pop(k, None)
    if expired:
        logger.info(f"[CLEANUP] Removed {len(expired)} expired short_ids")

def store_short_id(short_id: str, file_id: str):
    """ Сохранить short_id с timestamp """
    short_id_map[short_id] = {
        "file_id": file_id,
        "created_at": time_module.time()
    }

def is_admin(user) -> bool:
    """ Проверка админа по ID или username """
    if user.id in ADMIN_IDS:
        return True
    if user.username and user.username.lower() in [u.lower() for u in ADMIN_USERNAMES]:
        return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def get_start_keyboard(mode: str, user_id: int) -> InlineKeyboardMarkup:
    if mode == Mode.TIKTOK:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_button(user_id, "tiktok_on"), callback_data="noop")],
            [InlineKeyboardButton(text=get_button(user_id, "switch_youtube"), callback_data="mode_youtube")],
            [
                InlineKeyboardButton(text=get_button(user_id, "settings"), callback_data="settings"),
                InlineKeyboardButton(text=get_button(user_id, "how_it_works"), callback_data="how_it_works"),
            ],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_button(user_id, "youtube_on"), callback_data="noop")],
            [InlineKeyboardButton(text=get_button(user_id, "switch_tiktok"), callback_data="mode_tiktok")],
            [
                InlineKeyboardButton(text=get_button(user_id, "settings"), callback_data="settings"),
                InlineKeyboardButton(text=get_button(user_id, "how_it_works"), callback_data="how_it_works"),
            ],
        ])

def get_video_keyboard(short_id: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "uniqualize"), callback_data=f"process:{short_id}")],
    ])

def get_result_keyboard(short_id: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "again"), callback_data=f"process:{short_id}")],
        [InlineKeyboardButton(text=get_button(user_id, "change_mode"), callback_data="change_mode")],
    ])

def get_how_it_works_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])

def get_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """ Клавиатура настроек """
    quality = rate_limiter.get_quality(user_id)
    text_on = rate_limiter.get_text_overlay(user_id)
    
    # Кнопки качества с отметкой текущего
    q_low = "✅ " + get_button(user_id, "quality_low") if quality == Quality.LOW else get_button(user_id, "quality_low")
    q_med = "✅ " + get_button(user_id, "quality_medium") if quality == Quality.MEDIUM else get_button(user_id, "quality_medium")
    q_max = "✅ " + get_button(user_id, "quality_max") if quality == Quality.MAX else get_button(user_id, "quality_max")
    
    text_btn = get_button(user_id, "text_on") if text_on else get_button(user_id, "text_off")
    
    # Показываем кнопку купить только для free пользователей
    plan = rate_limiter.get_plan(user_id)
    
    buttons = [
        [
            InlineKeyboardButton(text=q_low, callback_data="quality_low"),
            InlineKeyboardButton(text=q_med, callback_data="quality_medium"),
            InlineKeyboardButton(text=q_max, callback_data="quality_max"),
        ],
        [InlineKeyboardButton(text=text_btn, callback_data="toggle_text")],
        [
            InlineKeyboardButton(text=get_button(user_id, "stats"), callback_data="stats"),
            InlineKeyboardButton(text=get_button(user_id, "referral"), callback_data="referral"),
        ],
        [
            InlineKeyboardButton(text=get_button(user_id, "language"), callback_data="language"),
        ],
    ]
    
    # Кнопка купить Premium для free пользователей
    if plan == "free":
        buttons.append([InlineKeyboardButton(text=get_button(user_id, "buy_premium"), callback_data="buy_premium")])
    
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["referral"], callback_data="referral")],
        [InlineKeyboardButton(text=BUTTONS["buy_premium"], callback_data="buy_premium")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="settings")],
    ])

def get_buy_premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @Null7_x", url="https://t.me/Null7_x")],
        [InlineKeyboardButton(text=BUTTONS.get("main_menu", "🏠 Главное меню"), callback_data="back_to_start")],
    ])

# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Проверка бана
    if rate_limiter.is_banned(user_id):
        reason = rate_limiter.get_ban_reason(user_id) or "Не указана"
        await message.answer(get_text(user_id, "banned", reason=reason))
        return
    
    # Сохраняем username
    if message.from_user.username:
        rate_limiter.set_username(user_id, message.from_user.username)
    
    # Проверка реферальной ссылки
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            referrer_id = int(args[1][3:])
        except:
            pass
    
    # Новый пользователь — сначала выбор языка
    is_new = rate_limiter.is_new_user(user_id)
    if is_new:
        await notify_admin_new_user(message.from_user)
        
        # Сохраняем реферера если есть
        if referrer_id:
            pending_referrers[user_id] = referrer_id
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="start_lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="start_lang_en"),
            ],
        ])
        await message.answer(
            "🌐 <b>Выбери язык / Choose language</b>",
            reply_markup=keyboard
        )
        return
    
    # Обработка реферала для не-новых (если перешли по ссылке повторно)
    if referrer_id:
        rate_limiter.set_referrer(user_id, referrer_id)
    
    mode = rate_limiter.get_mode(user_id)
    
    # Проверка истечения плана
    if rate_limiter.check_plan_expiry(user_id):
        plan = rate_limiter.get_plan(user_id)
        await message.answer(get_text(user_id, "plan_expired", plan=plan))
    
    text = get_text(user_id, "start") if mode == Mode.TIKTOK else get_text(user_id, "start_youtube")
    await message.answer(text, reply_markup=get_start_keyboard(mode, user_id))


async def notify_admin_new_user(user):
    """ Уведомить админа о новом пользователе """
    try:
        total_users = rate_limiter.get_total_users()
        username = f"@{user.username}" if user.username else "без username"
        name = user.full_name or "Без имени"
        
        text = (
            f"🆕 <b>Новый пользователь!</b>\n\n"
            f"👤 {name} ({username})\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📊 Всего пользователей: <b>{total_users}</b>"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except:
                pass
    except Exception as e:
        logger.error(f"Notify admin error: {e}")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """ Команда /stats — статистика пользователя """
    user_id = message.from_user.id
    stats = rate_limiter.get_stats(user_id)
    
    # Форматирование времени
    if stats["last_process_time"] > 0:
        import datetime
        last_time = datetime.datetime.fromtimestamp(stats["last_process_time"]).strftime("%d.%m.%Y %H:%M")
    else:
        last_time = get_text(user_id, "stats_never")
    
    # Названия режимов и качества
    mode_names = {Mode.TIKTOK: "TikTok MAX", Mode.YOUTUBE: "YouTube Shorts"}
    quality_names = {Quality.LOW: "📉 Quickly", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = get_text(user_id, "stats",
        total_videos=stats["total_videos"],
        today_videos=stats["today_videos"],
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 3),
        monthly_remaining=stats.get("monthly_remaining", 3),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ON" if stats["text_overlay"] else "OFF",
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free")
    )
    
    await message.answer(text, reply_markup=get_stats_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("vip"))
async def cmd_vip(message: Message):
    """ /vip @username [дней] — выдать VIP пользователю """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /vip @username [дней]\nПо умолчанию: 30 дней")
        return
    
    target = args[1]
    days = int(args[2]) if len(args) > 2 and args[2].isdigit() else 30
    
    # Поиск по @username или ID
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден. Он должен хотя бы раз написать боту.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer(TEXTS.get("invalid_user_id", "⚠️ Неверный ID"))
            return
    
    rate_limiter.set_plan_with_expiry(target_id, "vip", days)
    await message.answer(f"💎 VIP выдан @{username} (ID: {target_id}) на <b>{days} дней</b>!")

@dp.message(Command("premium"))
async def cmd_premium(message: Message):
    """ /premium @username [дней] — выдать Premium пользователю """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /premium @username [дней]\nПо умолчанию: 30 дней")
        return
    
    target = args[1]
    days = int(args[2]) if len(args) > 2 and args[2].isdigit() else 30
    
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден. Он должен хотя бы раз написать боту.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer(TEXTS.get("invalid_user_id", "⚠️ Неверный ID"))
            return
    
    rate_limiter.set_plan_with_expiry(target_id, "premium", days)
    await message.answer(f"👑 Premium выдан @{username} (ID: {target_id}) на <b>{days} дней</b>!")

@dp.message(Command("removeplan"))
async def cmd_removeplan(message: Message):
    """ /removeplan @username или /removeplan user_id — убрать план (сделать free) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /removeplan @username или /removeplan user_id")
        return
    
    target = args[1]
    
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer(TEXTS.get("invalid_user_id", "⚠️ Неверный ID"))
            return
    
    rate_limiter.set_plan(target_id, "free")
    await message.answer(TEXTS.get("plan_removed", "✅ План сброшен").format(user_id=target_id, username=username))

@dp.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    """ /userinfo @username или /userinfo user_id — информация о пользователе """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /userinfo @username или /userinfo user_id")
        return
    
    target = args[1]
    
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer(TEXTS.get("invalid_user_id", "⚠️ Неверный ID"))
            return
    
    stats = rate_limiter.get_stats(target_id)
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = TEXTS.get("user_info", """👤 <b>Пользователь</b> @{username} (ID: {user_id})
📋 План: {plan}
📊 Видео за 30 дней: {monthly_videos}/{monthly_limit}
📈 Всего видео: {total_videos}""").format(
        user_id=target_id,
        username=username,
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free"),
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 3),
        total_videos=stats.get("total_videos", 0)
    )
    await message.answer(text)


@dp.message(Command("update_ytdlp"))
async def cmd_update_ytdlp(message: Message):
    """ /update_ytdlp — обновить yt-dlp (только для админов) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    await message.answer("🔄 Обновляю yt-dlp...")
    
    try:
        import subprocess
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True,
                text=True
            )
        )
        
        if result.returncode == 0:
            # Получаем новую версию
            import yt_dlp
            version = yt_dlp.version.__version__
            await message.answer(f"✅ yt-dlp обновлён!\n📦 Версия: <code>{version}</code>")
        else:
            await message.answer(f"⚠️ Ошибка обновления:\n<code>{result.stderr[:500]}</code>")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")


@dp.message(Command("globalstats"))
async def cmd_globalstats(message: Message):
    """ /globalstats — глобальная статистика бота (только для админов) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    stats = rate_limiter.get_global_stats()
    
    text = (
        f"📊 <b>Глобальная статистика</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"🎬 Видео обработано: <b>{stats['total_videos']}</b>\n"
        f"⬇️ Скачиваний: <b>{stats['total_downloads']}</b>\n"
        f"⭐ VIP: <b>{stats['vip_users']}</b>\n"
        f"👑 Premium: <b>{stats['premium_users']}</b>\n"
        f"💾 Кэш видео: <b>{len(video_cache)}</b>"
    )
    await message.answer(text)


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    """ /ban @username или /ban user_id [причина] — заблокировать пользователя """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Использование: /ban @username [причина]")
        return
    
    target = args[1]
    reason = args[2] if len(args) > 2 else "Не указана"
    
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer("⚠️ Неверный ID")
            return
    
    rate_limiter.ban_user(target_id, reason)
    await message.answer(TEXTS.get("user_banned", "🚫 Заблокирован").format(
        user_id=target_id, username=username, reason=reason
    ))


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    """ /unban @username или /unban user_id — разблокировать пользователя """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unban @username")
        return
    
    target = args[1]
    
    if target.startswith("@"):
        target_id = rate_limiter.find_user_by_username(target)
        if not target_id:
            await message.answer(f"⚠️ Пользователь {target} не найден.")
            return
        username = target.lstrip("@")
    else:
        try:
            target_id = int(target)
            username = rate_limiter.get_username(target_id) or str(target_id)
        except ValueError:
            await message.answer("⚠️ Неверный ID")
            return
    
    rate_limiter.unban_user(target_id)
    await message.answer(TEXTS.get("user_unbanned", "✅ Разблокирован").format(
        user_id=target_id, username=username
    ))


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """ /broadcast текст — рассылка всем пользователям """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /broadcast текст сообщения")
        return
    
    text = args[1]
    users = rate_limiter.get_all_users()
    
    await message.answer(TEXTS.get("broadcast_start", "📨 Начинаю рассылку..."))
    
    sent = 0
    failed = 0
    
    for user_id in users:
        if rate_limiter.is_banned(user_id):
            continue
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)  # Чтобы не превысить лимиты
        except Exception:
            failed += 1
    
    await message.answer(TEXTS.get("broadcast_done", "✅ Готово").format(sent=sent, failed=failed))
    rate_limiter.save_data()


@dp.message(Command("referral"))
async def cmd_referral(message: Message):
    """ /referral — реферальная программа """
    user_id = message.from_user.id
    stats = rate_limiter.get_referral_stats(user_id)
    link = rate_limiter.get_referral_link(user_id)
    
    text = get_text(user_id, "referral_info",
        link=link,
        count=stats["referral_count"],
        bonus=stats["referral_bonus"]
    )
    await message.answer(text)


@dp.message(Command("lang"))
async def cmd_lang(message: Message):
    """ /lang — выбор языка """
    user_id = message.from_user.id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
    ])
    await message.answer("🌐 Выбери язык / Choose language:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("lang_"))
async def cb_lang(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split("_")[1]
    
    rate_limiter.set_language(user_id, lang)
    
    lang_names = {"ru": "Русский 🇷🇺", "en": "English 🇬🇧"}
    await callback.message.edit_text(
        get_text(user_id, "language_changed", lang=lang_names.get(lang, lang))
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("start_lang_"))
async def cb_start_lang(callback: CallbackQuery):
    """ Выбор языка при первом запуске """
    user_id = callback.from_user.id
    lang = callback.data.split("_")[2]  # start_lang_ru -> ru
    
    # Устанавливаем язык
    rate_limiter.set_language(user_id, lang)
    
    # Обрабатываем реферала если есть
    if user_id in pending_referrers:
        referrer_id = pending_referrers.pop(user_id)
        rate_limiter.set_referrer(user_id, referrer_id)
    
    # Сохраняем данные
    rate_limiter.save_data()
    
    # Показываем основной интерфейс
    mode = rate_limiter.get_mode(user_id)
    text = get_text(user_id, "start") if mode == Mode.TIKTOK else get_text(user_id, "start_youtube")
    
    await callback.message.edit_text(text, reply_markup=get_start_keyboard(mode, user_id))
    await callback.answer()


@dp.message(Command("checkexpiry"))
async def cmd_checkexpiry(message: Message):
    """ /checkexpiry — проверить истекающие подписки (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    expiring = rate_limiter.get_expiring_users(days_before=5)
    
    if not expiring:
        await message.answer("✅ Нет истекающих подписок в ближайшие 5 дней")
        return
    
    text = "⚠️ <b>Истекающие подписки:</b>\n\n"
    for u in expiring:
        text += f"• @{u['username'] or u['user_id']} — {u['plan']} (осталось {u['days_left']} дн.)\n"
    
    await message.answer(text)

@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    """ /myid — показать свой ID """
    await message.answer(f"🆔 Ваш ID: <code>{message.from_user.id}</code>")

@dp.message(Command("buy"))
async def cmd_buy(message: Message):
    """ /buy — информация о покупке Premium """
    await message.answer(get_text(message.from_user.id, "buy_premium"), reply_markup=get_buy_premium_keyboard())

@dp.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "mode_tiktok")
async def cb_mode_tiktok(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    rate_limiter.set_mode(user_id, Mode.TIKTOK)
    await callback.message.edit_text(
        get_text(user_id, "start"),
        reply_markup=get_start_keyboard(Mode.TIKTOK, user_id)
    )
    await callback.answer(get_text(user_id, "mode_tiktok"))

@dp.callback_query(F.data == "mode_youtube")
async def cb_mode_youtube(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    rate_limiter.set_mode(user_id, Mode.YOUTUBE)
    await callback.message.edit_text(
        get_text(user_id, "start_youtube"),
        reply_markup=get_start_keyboard(Mode.YOUTUBE, user_id)
    )
    await callback.answer(get_text(user_id, "mode_youtube"))

@dp.callback_query(F.data == "change_mode")
async def cb_change_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    current_mode = rate_limiter.get_mode(user_id)
    new_mode = Mode.YOUTUBE if current_mode == Mode.TIKTOK else Mode.TIKTOK
    rate_limiter.set_mode(user_id, new_mode)
    
    text = get_text(user_id, "start") if new_mode == Mode.TIKTOK else get_text(user_id, "start_youtube")
    await callback.message.edit_text(text, reply_markup=get_start_keyboard(new_mode, user_id))
    
    answer_text = get_text(user_id, "mode_tiktok") if new_mode == Mode.TIKTOK else get_text(user_id, "mode_youtube")
    await callback.answer(answer_text)

@dp.callback_query(F.data == "how_it_works")
async def cb_how_it_works(callback: CallbackQuery):
    if rate_limiter.check_button_spam(callback.from_user.id):
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    await callback.message.edit_text(
        get_text(user_id, "how_it_works"),
        reply_markup=get_how_it_works_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def cb_back_to_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    mode = rate_limiter.get_mode(user_id)
    text = get_text(user_id, "start") if mode == Mode.TIKTOK else get_text(user_id, "start_youtube")
    await callback.message.edit_text(text, reply_markup=get_start_keyboard(mode, user_id))
    await callback.answer()

# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    quality = rate_limiter.get_quality(user_id)
    text_on = rate_limiter.get_text_overlay(user_id)
    
    quality_names = {Quality.LOW: "📉 Quick", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
    
    text = get_text(user_id, "settings",
        quality=quality_names.get(quality, quality),
        text_overlay="ON" if text_on else "OFF"
    )
    
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    stats = rate_limiter.get_stats(user_id)
    
    if stats["last_process_time"] > 0:
        import datetime
        last_time = datetime.datetime.fromtimestamp(stats["last_process_time"]).strftime("%d.%m.%Y %H:%M")
    else:
        last_time = get_text(user_id, "stats_never")
    
    mode_names = {Mode.TIKTOK: "TikTok MAX", Mode.YOUTUBE: "YouTube Shorts"}
    quality_names = {Quality.LOW: "📉 Quick", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = get_text(user_id, "stats",
        total_videos=stats["total_videos"],
        today_videos=stats["today_videos"],
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 3),
        monthly_remaining=stats.get("monthly_remaining", 3),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ON" if stats["text_overlay"] else "OFF",
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free")
    )
    
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "buy_premium")
async def cb_buy_premium(callback: CallbackQuery):
    """ Показать информацию о покупке Premium """
    user_id = callback.from_user.id
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    await callback.message.edit_text(
        get_text(user_id, "buy_premium"),
        reply_markup=get_buy_premium_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    """ Реферальная программа """
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    stats = rate_limiter.get_referral_stats(user_id)
    link = rate_limiter.get_referral_link(user_id)
    
    text = get_text(user_id, "referral_info",
        link=link,
        count=stats["referral_count"],
        bonus=stats["referral_bonus"]
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="settings")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "language")
async def cb_language(callback: CallbackQuery):
    """ Выбор языка """
    if rate_limiter.check_button_spam(callback.from_user.id):
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="settings")],
    ])
    await callback.message.edit_text("🌐 Выбери язык / Choose language:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("quality_"))
async def cb_quality(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    quality_map = {
        "quality_low": Quality.LOW,
        "quality_medium": Quality.MEDIUM,
        "quality_max": Quality.MAX,
    }
    
    new_quality = quality_map.get(callback.data)
    if new_quality:
        rate_limiter.set_quality(user_id, new_quality)
        quality_names = {Quality.LOW: "📉 Quick", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
        
        # Обновляем клавиатуру
        text_on = rate_limiter.get_text_overlay(user_id)
        text = get_text(user_id, "settings",
            quality=quality_names.get(new_quality, new_quality),
            text_overlay="ON" if text_on else "OFF"
        )
        await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
        await callback.answer(get_text(user_id, "quality_changed", quality=quality_names.get(new_quality)))
    else:
        await callback.answer()

@dp.callback_query(F.data == "toggle_text")
async def cb_toggle_text(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    new_value = rate_limiter.toggle_text_overlay(user_id)
    
    quality = rate_limiter.get_quality(user_id)
    quality_names = {Quality.LOW: "📉 Quick", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
    
    text = get_text(user_id, "settings",
        quality=quality_names.get(quality, quality),
        text_overlay="ON" if new_value else "OFF"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
    await callback.answer(get_text(user_id, "text_on") if new_value else get_text(user_id, "text_off"))

@dp.message(F.video | F.document)
async def handle_video(message: Message):
    user_id = message.from_user.id
    
    if rate_limiter.is_processing(user_id):
        await message.answer(get_text(user_id, "duplicate"))
        return
    
    if message.video:
        file = message.video
        file_name = f"video_{file.file_id[-8:]}.mp4"
    elif message.document:
        file = message.document
        file_name = file.file_name or "document.mp4"
    else:
        return
    
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        await message.answer(get_text(user_id, "invalid_format"))
        return
    
    file_size_mb = (file.file_size or 0) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(get_text(user_id, "file_too_large"))
        return
    
    # Проверка длительности видео (только для video, не document)
    if message.video and message.video.duration:
        if message.video.duration > MAX_VIDEO_DURATION_SECONDS:
            await message.answer(get_text(user_id, "video_too_long"))
            return
    
    file_unique_id = file.file_unique_id
    
    if rate_limiter.check_duplicate_file(user_id, file_unique_id):
        await message.answer(get_text(user_id, "duplicate"))
        return
    
    short_id = generate_short_id()
    store_short_id(short_id, file.file_id)
    
    pending_files[short_id] = {
        "user_id": user_id,
        "file_id": file.file_id,
        "file_unique_id": file_unique_id,
        "message_id": message.message_id,
    }
    
    mode = rate_limiter.get_mode(user_id)
    mode_text = "TikTok MAX" if mode == Mode.TIKTOK else "YouTube Shorts MAX"
    monthly_remaining = rate_limiter.get_monthly_remaining(user_id)
    stats = rate_limiter.get_stats(user_id)
    plan_names = {"free": "🆓", "vip": "⭐", "premium": "👑"}
    plan_icon = plan_names.get(stats.get("plan", "free"), "🆓")
    
    await message.answer(
        f"{get_text(user_id, 'video_received')}\n🎯 Режим: <b>{mode_text}</b>\n📊 Осталось (30 дн.): {monthly_remaining} видео {plan_icon}",
        reply_markup=get_video_keyboard(short_id, user_id)
    )

@dp.callback_query(F.data.startswith("process:"))
async def cb_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    short_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(get_text(user_id, "duplicate"))
        return
    
    if short_id not in pending_files:
        await callback.answer(get_text(user_id, "error"))
        return
    
    file_data = pending_files[short_id]
    file_id = file_data["file_id"]
    file_unique_id = file_data["file_unique_id"]
    
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    
    if not can_process:
        if reason == "soft_block":
            await callback.answer(get_text(user_id, "soft_block"), show_alert=True)
        elif reason == "monthly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "monthly_limit_reached",
                    used=stats.get("monthly_videos", 0),
                    limit=stats.get("monthly_limit", 3)
                ), 
                show_alert=True
            )
        elif reason == "rate_limit":
            await callback.answer(get_text(user_id, "rate_limit"), show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(get_text(user_id, "cooldown", seconds=seconds), show_alert=True)
        return
    
    if get_queue_size() >= 8:
        await callback.answer(get_text(user_id, "queue_full"), show_alert=True)
        return
    
    rate_limiter.register_request(user_id, file_unique_id)
    rate_limiter.set_processing(user_id, True, file_id)
    
    await callback.message.edit_text(get_text(user_id, "processing"))
    await callback.answer()
    
    try:
        tg_file = await bot.get_file(file_id)
        input_path = str(get_temp_dir() / generate_unique_filename())
        await bot.download_file(tg_file.file_path, input_path)
    except Exception as e:
        logger.error(f"Download error: {e}")
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(TEXTS["error"])
        return
    
    mode = rate_limiter.get_mode(user_id)
    quality = rate_limiter.get_quality(user_id)
    text_overlay = rate_limiter.get_text_overlay(user_id)
    
    async def on_complete(success: bool, output_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and output_path:
            try:
                # Увеличиваем счётчик статистики
                rate_limiter.increment_video_count(user_id)
                
                video_file = FSInputFile(output_path)
                await bot.send_video(
                    chat_id=user_id,
                    video=video_file,
                    caption=get_text(user_id, "done"),
                    reply_markup=get_result_keyboard(short_id, user_id)
                )
                await callback.message.delete()
            except Exception as e:
                logger.error(f"Send error: {e}")
                await callback.message.edit_text(TEXTS["error"])
            finally:
                cleanup_file(output_path)
        else:
            await callback.message.edit_text(TEXTS["error"])
    
    task = ProcessingTask(
        user_id=user_id,
        input_path=input_path,
        mode=mode,
        callback=on_complete,
        quality=quality,
        text_overlay=text_overlay
    )
    
    queued = await add_to_queue(task)
    if not queued:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(input_path)
        await callback.message.edit_text(TEXTS["queue_full"])

# ══════════════════════════════════════════════════════════════════════════════
# URL VIDEO DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:'
    r'tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
    r'youtube\.com/shorts|youtu\.be|youtube\.com/watch|'
    r'instagram\.com/(?:reel|p)|'
    r'vk\.com/clip|vk\.com/video|'
    r'twitter\.com|x\.com|'
    r'douyin\.com|'
    r'bilibili\.com|b23\.tv|'
    r'weibo\.com|'
    r'youku\.com|'
    r'iqiyi\.com|'
    r'kuaishou\.com|gifshow\.com|v\.kuaishou\.com|c\.kuaishou\.com|'
    r'xiaohongshu\.com|xhslink\.com|'
    r'qq\.com|v\.qq\.com'
    r')[^\s]+'
)

# Кэш скачанных видео: url_hash -> file_path
video_cache: dict = {}
CACHE_MAX_SIZE = 50
CACHE_TTL_SECONDS = 3600  # 1 час

async def download_video_from_url(url: str, output_path: str) -> bool:
    """Скачать видео по ссылке без водяного знака используя yt-dlp или специальные методы"""
    try:
        # Специальная обработка TikTok/Douyin - без водяного знака
        if any(domain in url.lower() for domain in ['tiktok.com', 'douyin.com']):
            result = await download_tiktok_no_watermark(url, output_path)
            if result:
                return True
            # Fallback на yt-dlp если не получилось
        
        # Специальная обработка Kuaishou
        if any(domain in url.lower() for domain in ['kuaishou.com', 'gifshow.com']):
            return await download_kuaishou_video(url, output_path)
        
        import yt_dlp
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
            'socket_timeout': 30,
        }
        
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        await loop.run_in_executor(None, download)
        return os.path.exists(output_path)
        
    except Exception as e:
        logger.error(f"[YT-DLP] Error downloading {url}: {e}")
        return False


async def download_tiktok_no_watermark(url: str, output_path: str) -> bool:
    """Скачать TikTok/Douyin видео без водяного знака"""
    try:
        import aiohttp
        
        # Используем API для получения видео без водяного знака
        api_urls = [
            f"https://www.tikwm.com/api/?url={url}",
            f"https://api.douyin.wtf/api?url={url}",
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        async with aiohttp.ClientSession() as session:
            video_url = None
            
            for api_url in api_urls:
                try:
                    async with session.get(api_url, headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # tikwm.com format
                            if 'data' in data and 'play' in data.get('data', {}):
                                video_url = data['data']['play']
                                break
                            # douyin.wtf format
                            if 'nwm_video_url' in data:
                                video_url = data['nwm_video_url']
                                break
                except:
                    continue
            
            if not video_url:
                logger.warning("[TikTok] No watermark-free URL found, will use yt-dlp")
                return False
            
            logger.info(f"[TikTok] Found no-watermark URL")
            
            # Скачиваем видео
            async with session.get(video_url, headers=headers, timeout=120) as video_resp:
                if video_resp.status != 200:
                    return False
                
                with open(output_path, 'wb') as f:
                    while True:
                        chunk = await video_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
            
    except Exception as e:
        logger.error(f"[TikTok] No-watermark error: {e}")
        return False


async def download_kuaishou_video(url: str, output_path: str) -> bool:
    """Скачать видео из Kuaishou без водяного знака"""
    try:
        import aiohttp
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.kuaishou.com/',
        }
        
        async with aiohttp.ClientSession() as session:
            # Получаем страницу
            async with session.get(url, headers=headers, allow_redirects=True, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"[Kuaishou] HTTP {resp.status}")
                    return False
                html = await resp.text()
            
            # Ищем URL видео БЕЗ водяного знака (srcNoMark имеет приоритет)
            video_patterns = [
                r'"srcNoMark"\s*:\s*"([^"]+)"',  # Без водяного знака - приоритет!
                r'"photoUrl"\s*:\s*"([^"]+)"',   # Альтернатива без WM
                r'"playUrl"\s*:\s*"([^"]+)"',
                r'"url"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
                r'video\s+src="([^"]+)"',
                r'"videoUrl"\s*:\s*"([^"]+)"',
            ]
            
            video_url = None
            for pattern in video_patterns:
                match = re.search(pattern, html)
                if match:
                    video_url = match.group(1)
                    # Декодируем Unicode escape
                    video_url = video_url.encode().decode('unicode_escape')
                    video_url = video_url.replace('\\u002F', '/')
                    break
            
            if not video_url:
                logger.error("[Kuaishou] Video URL not found in page")
                return False
            
            logger.info(f"[Kuaishou] Found video URL: {video_url[:100]}...")
            
            # Скачиваем видео
            async with session.get(video_url, headers=headers, timeout=120) as video_resp:
                if video_resp.status != 200:
                    logger.error(f"[Kuaishou] Video download HTTP {video_resp.status}")
                    return False
                
                with open(output_path, 'wb') as f:
                    while True:
                        chunk = await video_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
            
    except Exception as e:
        logger.error(f"[Kuaishou] Error: {e}")
        return False

# Хранилище URL для скачивания
pending_urls: dict = {}  # short_id -> {user_id, url}

def get_url_keyboard(short_id: str) -> InlineKeyboardMarkup:
    """ Клавиатура для ссылки: уникализировать или только скачать """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["uniqualize"], callback_data=f"url_process:{short_id}")],
        [InlineKeyboardButton(text=BUTTONS["download_only"], callback_data=f"url_download:{short_id}")],
    ])

@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Сохраняем username
    if message.from_user.username:
        rate_limiter.set_username(user_id, message.from_user.username)
    
    logger.info(f"[URL] Received text: {text[:100]}")
    
    # Проверяем, есть ли ссылка в сообщении
    url_match = URL_PATTERN.search(text)
    if not url_match:
        logger.info(f"[URL] No URL match found")
        return
    
    url = url_match.group(0)
    logger.info(f"[URL] Found URL: {url}")
    
    if rate_limiter.is_processing(user_id):
        await message.answer(TEXTS["duplicate"])
        return
    
    # Сохраняем URL и показываем кнопки выбора
    short_id = generate_short_id()
    pending_urls[short_id] = {
        "user_id": user_id,
        "url": url,
        "created_at": time_module.time()
    }
    
    await message.answer(
        f"🔗 <b>Ссылка получена</b>\n\nВыбери действие:",
        reply_markup=get_url_keyboard(short_id)
    )

@dp.callback_query(F.data.startswith("url_download:"))
async def cb_url_download(callback: CallbackQuery):
    """ Только скачать видео без уникализации """
    user_id = callback.from_user.id
    short_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    if short_id not in pending_urls:
        await callback.answer("⚠️ Ссылка устарела, отправь заново")
        return
    
    url_data = pending_urls[short_id]
    url = url_data["url"]
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(TEXTS["duplicate"])
        return
    
    # Проверка лимита
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        if reason == "monthly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                TEXTS.get("monthly_limit_reached", "⚠️ Лимит исчерпан ({used}/{limit})").format(
                    used=stats.get("monthly_videos", 0),
                    limit=stats.get("monthly_limit", 3)
                ),
                show_alert=True
            )
        elif reason == "soft_block":
            await callback.answer(TEXTS["soft_block"], show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(TEXTS["cooldown"].format(seconds=seconds), show_alert=True)
        return
    
    await callback.message.edit_text("⬇️ Скачиваю видео...")
    await callback.answer()
    
    rate_limiter.set_processing(user_id, True)
    
    # Проверяем кэш
    import hashlib
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cached_path = video_cache.get(url_hash)
    
    if cached_path and os.path.exists(cached_path.get("path", "")):
        output_path = cached_path["path"]
        logger.info(f"[CACHE] Hit for {url[:50]}...")
    else:
        output_path = str(get_temp_dir() / generate_unique_filename())
        success = await download_video_from_url(url, output_path)
        
        if not success or not os.path.exists(output_path):
            rate_limiter.set_processing(user_id, False)
            await callback.message.edit_text(TEXTS["error_download"])
            return
        
        # Сохраняем в кэш
        if len(video_cache) >= CACHE_MAX_SIZE:
            # Удаляем старые записи
            oldest = sorted(video_cache.items(), key=lambda x: x[1].get("time", 0))[:10]
            for k, v in oldest:
                cleanup_file(v.get("path", ""))
                video_cache.pop(k, None)
        
        video_cache[url_hash] = {"path": output_path, "time": time_module.time()}
    
    rate_limiter.set_processing(user_id, False)
    
    # Проверяем размер
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        await callback.message.edit_text(TEXTS["file_too_large"])
        return
    
    try:
        # Увеличиваем счётчик скачиваний
        rate_limiter.increment_download_count(user_id)
        rate_limiter.increment_video_count(user_id)
        
        video_file = FSInputFile(output_path)
        await bot.send_video(
            chat_id=user_id,
            video=video_file,
            caption=TEXTS.get("downloaded", "⬇️ Видео скачано")
        )
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Send error: {e}")
        await callback.message.edit_text(TEXTS["error"])
    
    # Удаляем из pending
    pending_urls.pop(short_id, None)

@dp.callback_query(F.data.startswith("url_process:"))
async def cb_url_process(callback: CallbackQuery):
    """ Скачать и уникализировать видео """
    user_id = callback.from_user.id
    short_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    if short_id not in pending_urls:
        await callback.answer("⚠️ Ссылка устарела, отправь заново")
        return
    
    url_data = pending_urls[short_id]
    url = url_data["url"]
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(TEXTS["duplicate"])
        return
    
    # Проверка лимита
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        if reason == "monthly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                TEXTS.get("monthly_limit_reached", "⚠️ Лимит исчерпан ({used}/{limit})").format(
                    used=stats.get("monthly_videos", 0),
                    limit=stats.get("monthly_limit", 3)
                ),
                show_alert=True
            )
        elif reason == "soft_block":
            await callback.answer(TEXTS["soft_block"], show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(TEXTS["cooldown"].format(seconds=seconds), show_alert=True)
        return
    
    await callback.message.edit_text("⬇️ Скачиваю видео...")
    await callback.answer()
    
    rate_limiter.set_processing(user_id, True)
    
    output_path = str(get_temp_dir() / generate_unique_filename())
    
    # Скачиваем видео
    success = await download_video_from_url(url, output_path)
    
    if not success or not os.path.exists(output_path):
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(TEXTS["error_download"])
        pending_urls.pop(short_id, None)
        return
    
    # Проверяем размер файла
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        cleanup_file(output_path)
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(TEXTS["file_too_large"])
        pending_urls.pop(short_id, None)
        return
    
    # Получаем режим и начинаем обработку
    mode = rate_limiter.get_mode(user_id)
    quality = rate_limiter.get_quality(user_id)
    text_overlay = rate_limiter.get_text_overlay(user_id)
    
    await callback.message.edit_text(TEXTS["processing"])
    
    # Сохраняем message для callback
    status_message = callback.message
    
    async def on_complete(success: bool, result_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and result_path:
            try:
                rate_limiter.increment_video_count(user_id)
                
                video_file = FSInputFile(result_path)
                new_short_id = generate_short_id()
                await bot.send_video(
                    chat_id=user_id,
                    video=video_file,
                    caption=get_text(user_id, "done"),
                    reply_markup=get_result_keyboard(new_short_id, user_id)
                )
                await status_message.delete()
            except Exception as e:
                logger.error(f"Send error: {e}")
                await status_message.edit_text(TEXTS["error"])
            finally:
                cleanup_file(result_path)
        else:
            await status_message.edit_text(TEXTS["error"])
        
        cleanup_file(output_path)
        pending_urls.pop(short_id, None)
    
    task = ProcessingTask(
        user_id=user_id,
        input_path=output_path,
        mode=mode,
        callback=on_complete,
        quality=quality,
        text_overlay=text_overlay
    )
    
    queued = await add_to_queue(task)
    if not queued:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(output_path)
        await callback.message.edit_text(TEXTS["queue_full"])
        pending_urls.pop(short_id, None)

@dp.message()
async def handle_other(message: Message):
    pass

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def on_startup():
    await start_workers()
    cleanup_old_files()
    cleanup_short_id_map()
    logger.info("Virex started")

async def periodic_cleanup():
    """ Периодическая очистка """
    while True:
        await asyncio.sleep(600)  # каждые 10 минут
        cleanup_short_id_map()
        cleanup_old_files()

async def main():
    await on_startup()
    asyncio.create_task(periodic_cleanup())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
