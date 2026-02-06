"""
Virex — Telegram Bot
"""
import os
import re
import sys
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
import aiohttp

from config import (
    BOT_TOKEN, Mode, DEFAULT_MODE,
    MAX_FILE_SIZE_MB, MAX_VIDEO_DURATION_SECONDS, ALLOWED_EXTENSIONS,
    TEXTS, BUTTONS, Quality, QUALITY_SETTINGS, SHORT_ID_TTL_SECONDS,
    ADMIN_IDS, ADMIN_USERNAMES, PLAN_LIMITS, MAX_CONCURRENT_TASKS,
    TEXTS_EN, BUTTONS_EN, BOT_VERSION,
    FFMPEG_PATH, FFPROBE_PATH
)
from rate_limit import rate_limiter
from ffmpeg_utils import (
    start_workers, add_to_queue, ProcessingTask,
    get_temp_dir, generate_unique_filename, cleanup_file,
    cleanup_old_files, get_queue_size, cancel_task, get_user_task,
    get_user_queue_count,
    # v2.8.0
    is_maintenance_mode, set_maintenance_mode, estimate_queue_time,
    with_retry, ProgressTracker
)

# v3.2.0: Watermark-Trap detection
try:
    from watermark_trap import get_trap_detector, DetectionResult
    WATERMARK_TRAP_DETECTION_AVAILABLE = True
except ImportError:
    WATERMARK_TRAP_DETECTION_AVAILABLE = False

# v3.3.0: Virex Shield — Content Protection System
try:
    from content_protection import (
        get_virex_shield, VirexShield,
        RiskLevel, DigitalPassport, SafeCheckResult,
        ScanResult, TheftReport, UserAnalytics,
        get_preset_message, SMART_PRESETS
    )
    VIREX_SHIELD_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Virex Shield not available: {e}")
    VIREX_SHIELD_AVAILABLE = False

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


def _get_period_name(days: int) -> str:
    """ Получить название периода по количеству дней """
    if days == 1:
        return "1 день"
    elif days <= 6:
        return f"{days} дней"
    elif days == 7:
        return "неделя"
    elif days == 14:
        return "2 недели"
    elif days == 30 or days == 31:
        return "месяц"
    elif days == 60 or days == 62:
        return "2 месяца"
    elif days == 90 or days == 93:
        return "3 месяца"
    elif days == 180 or days == 186:
        return "6 месяцев"
    elif days == 365 or days == 366:
        return "год"
    elif days == 730 or days == 731:
        return "2 года"
    elif days > 365:
        years = days // 365
        return f"{years} лет"
    elif days > 30:
        months = days // 30
        return f"~{months} мес"
    elif days > 7:
        weeks = days // 7
        return f"~{weeks} нед"
    else:
        return f"{days} дн"


# Увеличенный таймаут для отправки больших файлов (5 минут)
# AiohttpSession принимает timeout в секундах (int)
session = AiohttpSession(timeout=300)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)
dp = Dispatcher()

pending_files: dict = {}
pending_detection: dict = {}  # v3.2.0: Пользователи, ожидающие видео для детекции Watermark-Trap
short_id_map: dict = {}  # short_id -> {file_id, created_at}
pending_referrers: dict = {}  # user_id -> referrer_id (для новых пользователей)
pending_urls: dict = {}  # short_id -> {user_id, url, created_at}

def generate_short_id() -> str:
    return uuid.uuid4().hex[:8]

def cleanup_short_id_map():
    """ Очистка устаревших short_id и pending_urls """
    now = time_module.time()
    expired = [k for k, v in short_id_map.items() 
               if now - v.get("created_at", 0) > SHORT_ID_TTL_SECONDS]
    for k in expired:
        short_id_map.pop(k, None)
        pending_files.pop(k, None)
    
    # Очистка pending_urls (устаревшие ссылки)
    expired_urls = [k for k, v in pending_urls.items() 
                    if now - v.get("created_at", 0) > SHORT_ID_TTL_SECONDS]
    for k in expired_urls:
        pending_urls.pop(k, None)
    
    total_expired = len(expired) + len(expired_urls)
    if total_expired:
        logger.info(f"[CLEANUP] Removed {len(expired)} short_ids, {len(expired_urls)} pending_urls")

def store_short_id(short_id: str, file_id: str):
    """ Сохранить short_id с timestamp """
    short_id_map[short_id] = {
        "file_id": file_id,
        "created_at": time_module.time()
    }

def is_admin(user) -> bool:
    """ Проверка админа по ID, username или динамическому флагу """
    if user.id in ADMIN_IDS:
        return True
    if user.username and user.username.lower() in [u.lower() for u in ADMIN_USERNAMES]:
        return True
    # Проверяем динамический флаг админа
    user_data = rate_limiter.get_user(user.id)
    if getattr(user_data, 'is_admin', False):
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
            [InlineKeyboardButton(text="🛡️ VIREX SHIELD", callback_data="shield_menu")],
            [InlineKeyboardButton(text=get_button(user_id, "help"), callback_data="help")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_button(user_id, "youtube_on"), callback_data="noop")],
            [InlineKeyboardButton(text=get_button(user_id, "switch_tiktok"), callback_data="mode_tiktok")],
            [
                InlineKeyboardButton(text=get_button(user_id, "settings"), callback_data="settings"),
                InlineKeyboardButton(text=get_button(user_id, "how_it_works"), callback_data="how_it_works"),
            ],
            [InlineKeyboardButton(text="🛡️ VIREX SHIELD", callback_data="shield_menu")],
            [InlineKeyboardButton(text=get_button(user_id, "help"), callback_data="help")],
        ])

def get_video_keyboard(short_id: str, user_id: int) -> InlineKeyboardMarkup:
    """ Клавиатура при получении видео — с выбором шаблона """
    quality = rate_limiter.get_quality(user_id)
    
    # Иконки качества
    q_icons = {Quality.LOW: "📉", Quality.MEDIUM: "📊", Quality.MAX: "📈"}
    current_icon = q_icons.get(quality, "📊")
    
    # Текущий шаблон
    from config import VIDEO_TEMPLATES, ANTI_REUPLOAD_LEVELS
    current_template = rate_limiter.get_template(user_id)
    template_name = VIDEO_TEMPLATES.get(current_template, {}).get("name", "🔄 Стандарт")
    
    # v3.2.0: Anti-Reupload Level
    anti_level = rate_limiter.get_anti_reupload_level(user_id)
    level_name = ANTI_REUPLOAD_LEVELS.get(anti_level, {}).get("name", "🟡 Medium")
    
    # v3.2.0: Auto-unique mode
    auto_unique = rate_limiter.get_auto_unique(user_id)
    auto_icon = "🤖 Авто: ВКЛ" if auto_unique else "🤖 Авто: ВЫКЛ"
    
    buttons = [
        [InlineKeyboardButton(text=f"🎨 Шаблон: {template_name}", callback_data=f"select_template:{short_id}")],
        [InlineKeyboardButton(text=f"🛡 Защита: {level_name}", callback_data=f"anti_level:{short_id}")],
        [InlineKeyboardButton(text=auto_icon, callback_data=f"toggle_auto_unique:{short_id}")],
    ]
    
    # Кнопка обработки
    if auto_unique:
        buttons.append([InlineKeyboardButton(
            text=f"⚡ АВТО-УНИКАЛИЗАЦИЯ {current_icon}", 
            callback_data=f"auto_process:{short_id}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text=f"🎯 {get_button(user_id, 'uniqualize')} {current_icon}", 
            callback_data=f"process:{short_id}"
        )])
    
    # Быстрый выбор качества
    buttons.append([
        InlineKeyboardButton(text="📉", callback_data=f"quick_q:low:{short_id}"),
        InlineKeyboardButton(text="📊", callback_data=f"quick_q:medium:{short_id}"),
        InlineKeyboardButton(text="📈", callback_data=f"quick_q:max:{short_id}"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_result_keyboard(short_id: str, user_id: int) -> InlineKeyboardMarkup:
    """ Клавиатура после успешной обработки """
    daily_remaining = rate_limiter.get_daily_remaining(user_id)
    
    buttons = []
    
    # Кнопка повторной обработки если есть лимит
    if daily_remaining > 0:
        buttons.append([InlineKeyboardButton(
            text=f"🔄 {get_button(user_id, 'again')} ({daily_remaining} осталось)", 
            callback_data=f"process:{short_id}"
        )])
    
    # Дополнительные кнопки
    buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
    ])
    buttons.append([
        InlineKeyboardButton(text=get_button(user_id, "change_mode"), callback_data="change_mode")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    
    # Ночной режим
    night_mode = rate_limiter.is_night_mode(user_id)
    night_btn = "🌙 Ночной: ВКЛ" if night_mode else "☀️ Ночной: ВЫКЛ"
    
    # Текущий шаблон
    from config import VIDEO_TEMPLATES
    current_template = rate_limiter.get_template(user_id)
    template_name = VIDEO_TEMPLATES.get(current_template, {}).get("name", "🔄 Стандарт")
    
    # Показываем кнопку купить только для free пользователей
    plan = rate_limiter.get_plan(user_id)
    
    # Получаем username для проверки админа
    username = rate_limiter.get_user(user_id).username
    
    buttons = [
        [
            InlineKeyboardButton(text=q_low, callback_data="quality_low"),
            InlineKeyboardButton(text=q_med, callback_data="quality_medium"),
            InlineKeyboardButton(text=q_max, callback_data="quality_max"),
        ],
        [
            InlineKeyboardButton(text=text_btn, callback_data="toggle_text"),
            InlineKeyboardButton(text=night_btn, callback_data="toggle_night"),
        ],
        [
            InlineKeyboardButton(text=f"🎨 Шаблон: {template_name}", callback_data="templates"),
        ],
        [
            InlineKeyboardButton(text="📜 История проектов", callback_data="project_history"),
        ],
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
    
    # Кнопка Админ только для администраторов
    is_user_admin = user_id in ADMIN_IDS or (username and username.lower() in [u.lower() for u in ADMIN_USERNAMES])
    if is_user_admin:
        buttons.append([InlineKeyboardButton(text="🔧 Админ", callback_data="open_admin")])
    
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stats_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "referral"), callback_data="referral")],
        [InlineKeyboardButton(text=get_button(user_id, "buy_premium"), callback_data="buy_premium")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
    ])

def get_buy_premium_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Полная клавиатура покупки с ценами и скидками"""
    from config import PLAN_PRICES, PAY_AS_YOU_GO, PROMO_CONFIG
    
    plan = rate_limiter.get_plan(user_id)
    is_first = rate_limiter.is_first_purchase(user_id)
    bonus_videos = rate_limiter.get_bonus_videos(user_id)
    
    buttons = []
    
    # Заголовок текущего плана
    plan_icons = {"free": "🆓", "vip": "💠", "premium": "👑"}
    
    # VIP секция (если ещё не VIP/Premium)
    if plan == "free":
        buttons.append([InlineKeyboardButton(
            text="━━━ 💠 VIP ━━━", 
            callback_data="noop"
        )])
        
        for period, data in PLAN_PRICES["vip"].items():
            price = data["price"]
            # Скидка -50% на первый VIP
            if is_first:
                price = price * (1 - PROMO_CONFIG["first_vip_discount"])
                label = f"🔥 {data['label']} → ${price:.2f} (-50%)"
            else:
                label = data["label"]
                if data.get("save"):
                    label += f" (экономия {data['save']})"
            
            if data.get("popular"):
                label = "⭐ " + label
            
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=f"buy:vip:{period}"
            )])
    
    # Premium секция
    buttons.append([InlineKeyboardButton(
        text="━━━ 👑 PREMIUM ━━━", 
        callback_data="noop"
    )])
    
    for period, data in PLAN_PRICES["premium"].items():
        price = data["price"]
        label = data["label"]
        
        # Скидка для VIP на Premium
        if plan == "vip":
            discount = PROMO_CONFIG.get("vip_to_premium_discount", 0.20)
            price = price * (1 - discount)
            label = f"🎁 ${price:.2f} (-{int(discount*100)}% для VIP)"
        elif data.get("save"):
            label += f" (экономия {data['save']})"
        
        if data.get("popular"):
            label = "⭐ " + label
        
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"buy:premium:{period}"
        )])
    
    # Pay-as-you-go секция
    buttons.append([InlineKeyboardButton(
        text="━━━ 🎯 Пакеты видео ━━━", 
        callback_data="noop"
    )])
    
    for pack_id, data in PAY_AS_YOU_GO.items():
        label = data["label"]
        if data.get("popular"):
            label = "🔥 " + label
        if data.get("save"):
            label += f" ({data['save']})"
        
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"buy_pack:{pack_id}"
        )])
    
    # Показать бонусные видео если есть
    if bonus_videos > 0:
        buttons.append([InlineKeyboardButton(
            text=f"🎁 У вас {bonus_videos} бонусных видео",
            callback_data="noop"
        )])
    
    # Контакт для оплаты
    buttons.append([InlineKeyboardButton(
        text="💬 Оплатить через @Null7_x", 
        url="https://t.me/Null7_x"
    )])
    
    buttons.append([InlineKeyboardButton(
        text=get_button(user_id, "main_menu"), 
        callback_data="back_to_start"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    
    # Проверка deep link параметров
    args = message.text.split()
    referrer_id = None
    
    if len(args) > 1:
        param = args[1]
        
        # Авторизация для Android приложения
        if param == "app_auth":
            import secrets
            import json
            auth_code = secrets.token_hex(8)  # Короткий код для удобства
            
            # Сохраняем код авторизации в users_data.json
            users_file = "users_data.json"
            users_data = {}
            if os.path.exists(users_file):
                with open(users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
            
            if str(user_id) not in users_data:
                users_data[str(user_id)] = {}
            users_data[str(user_id)]["app_auth_code"] = auth_code
            users_data[str(user_id)]["username"] = message.from_user.username
            users_data[str(user_id)]["first_name"] = message.from_user.first_name
            
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            
            # Отправляем код для копирования в приложение
            await message.answer(
                f"🔐 <b>Авторизация для приложения VIREX PRO</b>\n\n"
                f"Твой код авторизации:\n\n"
                f"<code>{user_id}:{auth_code}</code>\n\n"
                f"📋 Нажми на код чтобы скопировать, затем вставь его в приложении.\n\n"
                f"⏰ Код действителен 1 час."
            )
            return
        
        # Покупка подписки через приложение
        if param.startswith("buy_"):
            plan = param[4:]  # week, month, year, forever
            # Перенаправляем на покупку
            from aiogram.types import CallbackQuery
            # Симулируем нажатие кнопки подписки
            if plan in ["week", "month", "year", "forever"]:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data=f"buy_{plan}")]
                ])
                await message.answer(
                    f"💎 <b>Покупка подписки</b>\n\n"
                    f"Вы выбрали тариф: <b>{plan}</b>\n"
                    f"Нажмите кнопку ниже для оплаты:",
                    reply_markup=keyboard
                )
                return
        
        # Реферальная ссылка
        if param.startswith("ref"):
            try:
                referrer_id = int(param[3:])
                print(f"[START] User {user_id} came with referral link from {referrer_id}")
            except:
                pass
    
    # Уведомление админа о новом пользователе
    is_new = rate_limiter.is_new_user(user_id)
    if is_new:
        await notify_admin_new_user(message.from_user)
    
    # Выбор языка только один раз (если ещё не был выбран)
    if not rate_limiter.is_language_set(user_id):
        print(f"[START] User {user_id}, language not set, showing language selection")
        
        # Сохраняем реферера если есть
        if referrer_id:
            pending_referrers[user_id] = referrer_id
            print(f"[START] Saved pending referrer: {user_id} -> {referrer_id}")
        
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
    
    # Уведомление об истекающей подписке (≤1 день)
    plan_info = rate_limiter.get_plan_expiry_info(user_id)
    if plan_info["has_expiry"] and plan_info["days_left"] is not None and plan_info["days_left"] <= 1:
        plan = rate_limiter.get_plan(user_id)
        plan_names = {"vip": "VIP", "premium": "Premium"}
        days_word = "день" if plan_info["days_left"] == 1 else "дней"
        await message.answer(get_text(user_id, "subscription_warning",
            plan=plan_names.get(plan, plan),
            days=plan_info["days_left"],
            days_word=days_word
        ))
    
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


async def notify_admin_error(error_type: str, details: str, user_id: int = None):
    """ Уведомить админов о критической ошибке """
    try:
        username = rate_limiter.get_username(user_id) if user_id else "N/A"
        text = (
            f"🚨 <b>Ошибка: {error_type}</b>\n\n"
            f"👤 User: @{username} (ID: {user_id})\n"
            f"📝 Детали: <code>{details[:500]}</code>"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except:
                pass
    except Exception as e:
        logger.error(f"Notify admin error failed: {e}")


async def check_expiring_subscriptions():
    """ Проверить и уведомить об истекающих подписках """
    try:
        expiring = rate_limiter.get_expiring_users(days_before=3)
        for user in expiring:
            user_id = user.get('user_id')
            plan = user.get('plan')
            days_left = user.get('days_left')
            
            # Проверяем, не уведомляли ли уже
            if rate_limiter.should_notify_expiry(user_id):
                try:
                    text = get_text(user_id, 'plan_expiring', plan=plan, days=days_left)
                    await bot.send_message(user_id, text)
                    rate_limiter.mark_expiry_notified(user_id)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Check expiring error: {e}")

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
    
    # Время до сброса лимитов
    daily_reset = rate_limiter.get_time_until_daily_reset(user_id)
    weekly_reset = rate_limiter.get_time_until_weekly_reset(user_id)
    
    # Информация о плане
    plan_info = rate_limiter.get_plan_expiry_info(user_id)
    plan_text = plan_names.get(stats.get("plan", "free"), "🆓 Free")
    if plan_info["has_expiry"] and plan_info["days_left"] is not None:
        plan_text += f" (ещё {plan_info['days_left']} дн)"
    
    text = get_text(user_id, "stats",
        total_videos=stats["total_videos"],
        today_videos=stats["today_videos"],
        daily_videos=stats.get("daily_videos", 0),
        daily_limit=stats.get("daily_limit", 2),
        weekly_videos=stats.get("weekly_videos", 0),
        weekly_limit=stats.get("weekly_limit", 14),
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 14),
        monthly_remaining=stats.get("monthly_remaining", 14),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ON" if stats["text_overlay"] else "OFF",
        plan=plan_text,
        total_downloads=stats.get("total_downloads", 0)
    )
    
    # Добавляем инфо о сбросе лимитов если они использованы
    if stats.get("daily_videos", 0) > 0 or stats.get("weekly_videos", 0) > 0:
        lang = rate_limiter.get_language(user_id)
        if lang == "en":
            text += f"\n\n⏱ Reset: day in {daily_reset}, week in {weekly_reset}"
        else:
            text += f"\n\n⏱ Сброс: день через {daily_reset}, неделя через {weekly_reset}"
    
    await message.answer(text, reply_markup=get_stats_keyboard(user_id))


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: WATERMARK-TRAP DETECTION
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("detect"))
async def cmd_detect(message: Message):
    """
    Команда /detect — проверка видео на Watermark-Trap
    Только для Premium пользователей
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    # Проверяем доступ (только Premium)
    if not rate_limiter.can_use_watermark_trap(user_id):
        if lang == "en":
            await message.answer(
                "🔒 <b>Watermark-Trap Detection</b>\n\n"
                "This feature is available only for Premium users.\n\n"
                "👑 <b>Premium features:</b>\n"
                "• Invisible digital fingerprint\n"
                "• Video source detection\n"
                "• Proof of ownership\n\n"
                "Upgrade to Premium to use this feature!"
            )
        else:
            await message.answer(
                "🔒 <b>Детекция Watermark-Trap</b>\n\n"
                "Эта функция доступна только для Premium пользователей.\n\n"
                "👑 <b>Premium возможности:</b>\n"
                "• Невидимый цифровой отпечаток\n"
                "• Определение источника видео\n"
                "• Доказательство владения\n\n"
                "Повысьте план до Premium!"
            )
        return
    
    if not WATERMARK_TRAP_DETECTION_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Detection module is not available")
        else:
            await message.answer("❌ Модуль детекции недоступен")
        return
    
    # Помечаем пользователя как ожидающего видео для детекции
    pending_detection[user_id] = time_module.time()
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отменить" if lang == "ru" else "❌ Cancel", 
            callback_data="cancel_detection"
        )]
    ])
    
    if lang == "en":
        await message.answer(
            "🔍 <b>Watermark-Trap Detection</b>\n\n"
            "Send the video you want to check for digital fingerprint.\n\n"
            "If this video was processed through Virex, "
            "I will find the hidden signature and show:\n"
            "• User ID of the source\n"
            "• Processing date\n"
            "• Confidence level\n\n"
            "⏳ Waiting for video...",
            reply_markup=cancel_kb
        )
    else:
        await message.answer(
            "🔍 <b>Детекция Watermark-Trap</b>\n\n"
            "Отправьте видео для проверки на наличие цифрового отпечатка.\n\n"
            "Если это видео обрабатывалось через Virex, "
            "я найду скрытую сигнатуру и покажу:\n"
            "• ID пользователя-источника\n"
            "• Дату обработки\n"
            "• Уровень уверенности\n\n"
            "⏳ Жду видео...",
            reply_markup=cancel_kb
        )


@dp.callback_query(F.data == "cancel_detection")
async def cb_cancel_detection(callback: CallbackQuery):
    """Отмена режима детекции"""
    user_id = callback.from_user.id
    pending_detection.pop(user_id, None)
    
    lang = rate_limiter.get_language(user_id)
    if lang == "en":
        await callback.message.edit_text("✅ Detection mode cancelled")
    else:
        await callback.message.edit_text("✅ Режим детекции отменён")
    await callback.answer()


async def handle_detection_video(message: Message):
    """
    Обработка видео для детекции Watermark-Trap
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not WATERMARK_TRAP_DETECTION_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Detection module is not available")
        else:
            await message.answer("❌ Модуль детекции недоступен")
        return
    
    # Статус
    if lang == "en":
        status_msg = await message.answer("🔍 Analyzing video for Watermark-Trap...")
    else:
        status_msg = await message.answer("🔍 Анализирую видео на наличие Watermark-Trap...")
    
    try:
        # Скачиваем видео
        if message.video:
            file = message.video
        elif message.document:
            file = message.document
        else:
            await status_msg.edit_text("❌ Video not found" if lang == "en" else "❌ Видео не найдено")
            return
        
        # Скачиваем файл
        temp_path = str(get_temp_dir() / f"detect_{generate_unique_filename()}")
        
        try:
            file_info = await bot.get_file(file.file_id)
            await bot.download_file(file_info.file_path, temp_path)
        except Exception as e:
            logger.error(f"Detection download error: {e}")
            await status_msg.edit_text(
                "❌ Failed to download video" if lang == "en" else "❌ Не удалось скачать видео"
            )
            return
        
        # Запускаем детекцию
        detector = get_trap_detector()
        result = await detector.detect(temp_path)
        
        # Удаляем временный файл
        cleanup_file(temp_path)
        
        # Показываем результат
        await status_msg.edit_text(result.to_message(lang))
        
    except Exception as e:
        logger.error(f"Detection error: {e}")
        await status_msg.edit_text(
            f"❌ Detection error: {e}" if lang == "en" else f"❌ Ошибка детекции: {e}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 🛡️ VIREX SHIELD COMMANDS — Система защиты контента
# ══════════════════════════════════════════════════════════════════════════════

# Режимы ожидания для shield-функций
pending_safecheck: Dict[int, float] = {}
pending_scan: Dict[int, float] = {}


@dp.message(Command("shield"))
async def cmd_shield(message: Message):
    """
    /shield — информация о системе защиты Virex Shield
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Virex Shield module is not available")
        else:
            await message.answer("❌ Модуль Virex Shield недоступен")
        return
    
    shield = get_virex_shield()
    await message.answer(shield.get_shield_info(lang))


@dp.message(Command("safecheck"))
async def cmd_safecheck(message: Message):
    """
    /safecheck — AI Safe-Check видео перед публикацией
    Доступно для VIP+ пользователей
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    # Проверка доступа (VIP+)
    user_plan = rate_limiter.get_plan(user_id)
    if user_plan not in ["vip", "premium"]:
        if lang == "en":
            await message.answer(
                "🛡 <b>AI Safe-Check</b>\n\n"
                "This feature is available for VIP and Premium users.\n\n"
                "Safe-Check analyzes your video and shows:\n"
                "• Originality score\n"
                "• Ban probability\n"
                "• Strike risk\n"
                "• Shadow ban risk\n\n"
                "Upgrade your plan to use this feature!"
            )
        else:
            await message.answer(
                "🛡 <b>AI Safe-Check</b>\n\n"
                "Эта функция доступна для VIP и Premium пользователей.\n\n"
                "Safe-Check анализирует видео и показывает:\n"
                "• Оценку оригинальности\n"
                "• Вероятность бана\n"
                "• Риск страйка\n"
                "• Риск теневого бана\n\n"
                "Повысьте свой план!"
            )
        return
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Safe-Check module is not available")
        else:
            await message.answer("❌ Модуль Safe-Check недоступен")
        return
    
    # Ставим режим ожидания
    pending_safecheck[user_id] = time_module.time()
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отменить" if lang == "ru" else "❌ Cancel",
            callback_data="cancel_safecheck"
        )]
    ])
    
    if lang == "en":
        await message.answer(
            "🛡 <b>AI Safe-Check</b>\n\n"
            "Send your video for analysis.\n\n"
            "I will check:\n"
            "• Originality compared to our database\n"
            "• Ban probability on platforms\n"
            "• Strike risk\n"
            "• Shadow ban risk\n\n"
            "⏳ Waiting for video...",
            reply_markup=cancel_kb
        )
    else:
        await message.answer(
            "🛡 <b>AI Safe-Check</b>\n\n"
            "Отправьте видео для анализа.\n\n"
            "Я проверю:\n"
            "• Оригинальность по базе\n"
            "• Вероятность бана на платформах\n"
            "• Риск страйка\n"
            "• Риск теневого бана\n\n"
            "⏳ Жду видео...",
            reply_markup=cancel_kb
        )


@dp.callback_query(F.data == "cancel_safecheck")
async def cb_cancel_safecheck(callback: CallbackQuery):
    """Отмена режима safe-check"""
    user_id = callback.from_user.id
    pending_safecheck.pop(user_id, None)
    
    lang = rate_limiter.get_language(user_id)
    if lang == "en":
        await callback.message.edit_text("✅ Safe-Check cancelled")
    else:
        await callback.message.edit_text("✅ Safe-Check отменён")
    await callback.answer()


@dp.message(Command("scan"))
async def cmd_scan(message: Message):
    """
    /scan — сканирование видео на совпадения в базе
    Доступно для VIP+ пользователей
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    # Проверка доступа (VIP+)
    user_plan = rate_limiter.get_plan(user_id)
    if user_plan not in ["vip", "premium"]:
        if lang == "en":
            await message.answer(
                "🔍 <b>Content Scanner</b>\n\n"
                "This feature is available for VIP and Premium users.\n\n"
                "Scanner searches our database for:\n"
                "• Similar videos\n"
                "• Potential copies\n"
                "• Stolen content\n\n"
                "Upgrade your plan to use this feature!"
            )
        else:
            await message.answer(
                "🔍 <b>Сканер контента</b>\n\n"
                "Эта функция доступна для VIP и Premium пользователей.\n\n"
                "Сканер ищет в базе:\n"
                "• Похожие видео\n"
                "• Потенциальные копии\n"
                "• Украденный контент\n\n"
                "Повысьте свой план!"
            )
        return
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Scanner module is not available")
        else:
            await message.answer("❌ Модуль сканера недоступен")
        return
    
    # Ставим режим ожидания
    pending_scan[user_id] = time_module.time()
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отменить" if lang == "ru" else "❌ Cancel",
            callback_data="cancel_scan"
        )]
    ])
    
    if lang == "en":
        await message.answer(
            "🔍 <b>Content Scanner</b>\n\n"
            "Send a video to scan against our database.\n\n"
            "I will find:\n"
            "• Similar videos in our database\n"
            "• Similarity percentage\n"
            "• Risk assessment\n"
            "• Original source (if found)\n\n"
            "⏳ Waiting for video...",
            reply_markup=cancel_kb
        )
    else:
        await message.answer(
            "🔍 <b>Сканер контента</b>\n\n"
            "Отправьте видео для поиска в базе.\n\n"
            "Я найду:\n"
            "• Похожие видео в базе\n"
            "• Процент схожести\n"
            "• Оценку риска\n"
            "• Оригинальный источник (если найден)\n\n"
            "⏳ Жду видео...",
            reply_markup=cancel_kb
        )


@dp.callback_query(F.data == "cancel_scan")
async def cb_cancel_scan(callback: CallbackQuery):
    """Отмена режима сканирования"""
    user_id = callback.from_user.id
    pending_scan.pop(user_id, None)
    
    lang = rate_limiter.get_language(user_id)
    if lang == "en":
        await callback.message.edit_text("✅ Scan cancelled")
    else:
        await callback.message.edit_text("✅ Сканирование отменено")
    await callback.answer()


@dp.message(Command("presets"))
async def cmd_presets(message: Message):
    """
    /presets — список умных пресетов для платформ
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Presets module is not available")
        else:
            await message.answer("❌ Модуль пресетов недоступен")
        return
    
    await message.answer(get_preset_message(lang))


@dp.message(Command("analytics"))
async def cmd_analytics(message: Message):
    """
    /analytics — персональная аналитика (VIP+)
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    # Проверка доступа (VIP+)
    user_plan = rate_limiter.get_plan(user_id)
    if user_plan not in ["vip", "premium"]:
        if lang == "en":
            await message.answer(
                "📊 <b>Personal Analytics</b>\n\n"
                "This feature is available for VIP and Premium users.\n\n"
                "Track your:\n"
                "• Videos processed\n"
                "• Scans performed\n"
                "• Matches found\n"
                "• Protection statistics\n\n"
                "Upgrade your plan to see analytics!"
            )
        else:
            await message.answer(
                "📊 <b>Персональная аналитика</b>\n\n"
                "Эта функция доступна для VIP и Premium пользователей.\n\n"
                "Отслеживайте:\n"
                "• Обработанные видео\n"
                "• Выполненные проверки\n"
                "• Найденные совпадения\n"
                "• Статистику защиты\n\n"
                "Повысьте план для просмотра аналитики!"
            )
        return
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Analytics module is not available")
        else:
            await message.answer("❌ Модуль аналитики недоступен")
        return
    
    shield = get_virex_shield()
    analytics = shield.get_user_analytics(user_id)
    await message.answer(analytics.to_message(lang))


@dp.message(Command("passport"))
async def cmd_passport(message: Message):
    """
    /passport [ID] — просмотр цифрового паспорта
    Без ID — список своих паспортов
    """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Passport module is not available")
        else:
            await message.answer("❌ Модуль паспортов недоступен")
        return
    
    shield = get_virex_shield()
    args = message.text.split()
    
    if len(args) > 1:
        # Просмотр конкретного паспорта
        passport_id = args[1]
        passport = shield.get_passport(passport_id)
        
        if not passport:
            if lang == "en":
                await message.answer(f"❌ Passport {passport_id} not found")
            else:
                await message.answer(f"❌ Паспорт {passport_id} не найден")
            return
        
        # Верифицируем
        shield.verify_passport(passport_id)
        
        created = datetime.fromtimestamp(passport.created_at).strftime('%d.%m.%Y %H:%M')
        
        if lang == "en":
            text = (
                f"🪪 <b>DIGITAL PASSPORT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>ID:</b> <code>{passport.passport_id}</code>\n"
                f"<b>Owner:</b> @{passport.owner_username or f'user_{passport.owner_user_id}'}\n"
                f"<b>Created:</b> {created}\n\n"
                f"<b>Video info:</b>\n"
                f"   • Hash: <code>{passport.video_hash[:16]}...</code>\n"
                f"   • Size: {passport.file_size_bytes // 1024} KB\n"
                f"   • Duration: {passport.duration_seconds:.1f}s\n"
                f"   • Template: {passport.template_used or 'N/A'}\n\n"
                f"<b>Protection:</b>\n"
                f"   • Verifications: {passport.verification_count}\n"
                f"   • Matches found: {passport.matches_found}\n"
                f"   • Trap enabled: {'✅' if passport.trap_enabled else '❌'}"
            )
        else:
            text = (
                f"🪪 <b>ЦИФРОВОЙ ПАСПОРТ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>ID:</b> <code>{passport.passport_id}</code>\n"
                f"<b>Владелец:</b> @{passport.owner_username or f'user_{passport.owner_user_id}'}\n"
                f"<b>Создан:</b> {created}\n\n"
                f"<b>Информация о видео:</b>\n"
                f"   • Хеш: <code>{passport.video_hash[:16]}...</code>\n"
                f"   • Размер: {passport.file_size_bytes // 1024} KB\n"
                f"   • Длительность: {passport.duration_seconds:.1f}с\n"
                f"   • Шаблон: {passport.template_used or 'Н/Д'}\n\n"
                f"<b>Защита:</b>\n"
                f"   • Верификаций: {passport.verification_count}\n"
                f"   • Совпадений: {passport.matches_found}\n"
                f"   • Trap включен: {'✅' if passport.trap_enabled else '❌'}"
            )
        
        await message.answer(text)
    else:
        # Список своих паспортов
        passports = shield.get_user_passports(user_id)
        
        if not passports:
            if lang == "en":
                await message.answer(
                    "🪪 <b>Your Passports</b>\n\n"
                    "You don't have any digital passports yet.\n\n"
                    "Passports are created automatically when you process videos.\n"
                    "They help prove ownership of your content."
                )
            else:
                await message.answer(
                    "🪪 <b>Ваши паспорта</b>\n\n"
                    "У вас пока нет цифровых паспортов.\n\n"
                    "Паспорта создаются автоматически при обработке видео.\n"
                    "Они помогают доказать владение контентом."
                )
            return
        
        # Показываем последние 10
        recent = sorted(passports, key=lambda p: p.created_at, reverse=True)[:10]
        
        if lang == "en":
            text = f"🪪 <b>Your Passports</b> ({len(passports)} total)\n\n"
            for p in recent:
                created = datetime.fromtimestamp(p.created_at).strftime('%d.%m')
                text += f"• <code>{p.passport_id}</code> — {created}\n"
            text += f"\nUse <code>/passport ID</code> to view details."
        else:
            text = f"🪪 <b>Ваши паспорта</b> (всего {len(passports)})\n\n"
            for p in recent:
                created = datetime.fromtimestamp(p.created_at).strftime('%d.%m')
                text += f"• <code>{p.passport_id}</code> — {created}\n"
            text += f"\nИспользуйте <code>/passport ID</code> для деталей."
        
        await message.answer(text)


async def handle_safecheck_video(message: Message):
    """Обработка видео для Safe-Check"""
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Safe-Check module is not available")
        else:
            await message.answer("❌ Модуль Safe-Check недоступен")
        return
    
    status_msg = await message.answer(
        "🔄 Analyzing..." if lang == "en" else "🔄 Анализирую..."
    )
    
    try:
        # Скачиваем видео
        video = message.video or message.document
        file = await bot.get_file(video.file_id)
        
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"safecheck_{user_id}_{int(time_module.time())}.mp4")
        
        await bot.download_file(file.file_path, temp_path)
        
        # Запускаем Safe-Check
        shield = get_virex_shield()
        result = await shield.safe_check(temp_path, user_id, processed=False)
        
        # Удаляем временный файл
        cleanup_file(temp_path)
        
        # Показываем результат
        await status_msg.edit_text(result.to_message(lang))
        
    except Exception as e:
        logger.error(f"Safe-Check error: {e}")
        await status_msg.edit_text(
            f"❌ Error: {e}" if lang == "en" else f"❌ Ошибка: {e}"
        )
    finally:
        pending_safecheck.pop(user_id, None)


async def handle_scan_video(message: Message):
    """Обработка видео для сканирования"""
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if not VIREX_SHIELD_AVAILABLE:
        if lang == "en":
            await message.answer("❌ Scanner module is not available")
        else:
            await message.answer("❌ Модуль сканера недоступен")
        return
    
    status_msg = await message.answer(
        "🔄 Scanning..." if lang == "en" else "🔄 Сканирую..."
    )
    
    try:
        # Скачиваем видео
        video = message.video or message.document
        file = await bot.get_file(video.file_id)
        
        temp_dir = get_temp_dir()
        temp_path = os.path.join(temp_dir, f"scan_{user_id}_{int(time_module.time())}.mp4")
        
        await bot.download_file(file.file_path, temp_path)
        
        # Запускаем сканирование
        shield = get_virex_shield()
        result = await shield.scan_for_matches(temp_path, user_id)
        
        # Удаляем временный файл
        cleanup_file(temp_path)
        
        # Показываем результат
        await status_msg.edit_text(result.to_message(lang))
        
    except Exception as e:
        logger.error(f"Scan error: {e}")
        await status_msg.edit_text(
            f"❌ Error: {e}" if lang == "en" else f"❌ Ошибка: {e}"
        )
    finally:
        pending_scan.pop(user_id, None)


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
        await message.answer(
            "💎 <b>Выдать VIP</b>\n\n"
            "<b>Использование:</b>\n"
            "<code>/vip @username [дней]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/vip @user 7</code> — неделя\n"
            "• <code>/vip @user 30</code> — месяц\n"
            "• <code>/vip @user 180</code> — 6 месяцев\n"
            "• <code>/vip @user 365</code> — год\n\n"
            "По умолчанию: 7 дней (неделя)"
        )
        return
    
    target = args[1]
    days = int(args[2]) if len(args) > 2 and args[2].isdigit() else 7
    
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
    
    # Определяем период для красивого вывода
    period_name = _get_period_name(days)
    
    rate_limiter.set_plan_with_expiry(target_id, "vip", days)
    await message.answer(f"💎 <b>VIP выдан!</b>\n\n👤 @{username} (ID: {target_id})\n⏱ Срок: <b>{days} дней</b> ({period_name})")

@dp.message(Command("premium"))
async def cmd_premium(message: Message):
    """ /premium @username [дней] — выдать Premium пользователю """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "👑 <b>Выдать Premium</b>\n\n"
            "<b>Использование:</b>\n"
            "<code>/premium @username [дней]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/premium @user 7</code> — неделя\n"
            "• <code>/premium @user 30</code> — месяц\n"
            "• <code>/premium @user 180</code> — 6 месяцев\n"
            "• <code>/premium @user 365</code> — год\n\n"
            "По умолчанию: 7 дней (неделя)"
        )
        return
    
    target = args[1]
    days = int(args[2]) if len(args) > 2 and args[2].isdigit() else 7
    
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
    
    # Определяем период для красивого вывода
    period_name = _get_period_name(days)
    
    rate_limiter.set_plan_with_expiry(target_id, "premium", days)
    await message.answer(f"👑 <b>Premium выдан!</b>\n\n👤 @{username} (ID: {target_id})\n⏱ Срок: <b>{days} дней</b> ({period_name})")

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

@dp.message(Command("addadmin"))
async def cmd_addadmin(message: Message):
    """ /addadmin @username — добавить администратора (автоматически даёт Premium) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🔧 <b>Добавить администратора</b>\n\n"
            "<b>Использование:</b>\n"
            "<code>/addadmin @username</code>\n\n"
            "<b>Примечание:</b>\n"
            "При добавлении админа автоматически выдаётся Premium навсегда (99 лет)"
        )
        return
    
    target = args[1]
    
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
    
    # Ставим флаг админа
    user_data = rate_limiter.get_user(target_id)
    user_data.is_admin = True
    rate_limiter.save_data()
    
    # Автоматически даём Premium на 99 лет (36135 дней)
    rate_limiter.set_plan_with_expiry(target_id, "premium", 36135)
    
    await message.answer(
        f"🔧 <b>Администратор добавлен!</b>\n\n"
        f"👤 @{username} (ID: {target_id})\n"
        f"👑 Premium: навсегда (99 лет)\n"
        f"✅ Права администратора активны"
    )

@dp.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message):
    """ /removeadmin @username — убрать администратора """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🔧 <b>Убрать администратора</b>\n\n"
            "<b>Использование:</b>\n"
            "<code>/removeadmin @username</code>"
        )
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
    
    # Убираем флаг админа
    user_data = rate_limiter.get_user(target_id)
    user_data.is_admin = False
    
    # Убираем Premium тоже
    rate_limiter.set_plan(target_id, "free")
    
    await message.answer(
        f"🔧 <b>Администратор удалён</b>\n\n"
        f"👤 @{username} (ID: {target_id})\n"
        f"⚠️ Права администратора отозваны\n"
        f"📉 Premium убран (план: Free)"
    )

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
    daily = rate_limiter.get_daily_stats()
    
    text = (
        f"📊 <b>Глобальная статистика</b>\n\n"
        f"<b>📅 За сегодня:</b>\n"
        f"• Новых: <b>{daily['new_users']}</b>\n"
        f"• Видео: <b>{daily['videos_today']}</b>\n"
        f"• Активных: <b>{stats['active_today']}</b>\n\n"
        f"<b>📈 Всего:</b>\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"🎬 Видео обработано: <b>{stats['total_videos']}</b>\n"
        f"⬇️ Скачиваний: <b>{stats['total_downloads']}</b>\n"
        f"⭐ VIP: <b>{stats['vip_users']}</b>\n"
        f"👑 Premium: <b>{stats['premium_users']}</b>\n"
        f"💾 Кэш видео: <b>{len(video_cache)}</b>"
    )
    await message.answer(text)


@dp.message(Command("dailystats"))
async def cmd_dailystats(message: Message):
    """ /dailystats — отправить ежедневную статистику сейчас """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    await send_daily_stats()
    await message.answer("✅ Ежедневная статистика отправлена!")


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


@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    """ /ref — реферальная ссылка (краткая команда) """
    user_id = message.from_user.id
    stats = rate_limiter.get_referral_stats(user_id)
    link = rate_limiter.get_referral_link(user_id)
    
    text = get_text(user_id, "referral_info",
        link=link,
        count=stats["referral_count"],
        bonus=stats["referral_bonus"]
    )
    await message.answer(text)


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


@dp.message(Command("feedback"))
async def cmd_feedback(message: Message):
    """ /feedback — отправить отзыв админу """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(get_text(user_id, "feedback_prompt"))
        return
    
    feedback_text = args[1]
    username = rate_limiter.get_username(user_id) or str(user_id)
    
    # Отправляем админам
    admin_text = get_text(user_id, "feedback_received",
        username=username,
        user_id=user_id,
        message=feedback_text
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except:
            pass
    
    await message.answer(get_text(user_id, "feedback_sent"))


@dp.message(Command("top"))
async def cmd_top(message: Message):
    """ /top — топ-10 пользователей по обработкам """
    user_id = message.from_user.id
    top_users = rate_limiter.get_top_users(10)
    
    if not top_users:
        await message.answer("📊 Пока нет данных")
        return
    
    top_list = ""
    medals = ["🥇", "🥈", "🥉"]
    plan_icons = {"free": "", "vip": "⭐", "premium": "👑"}
    
    for u in top_users:
        medal = medals[u["position"] - 1] if u["position"] <= 3 else f"{u['position']}."
        icon = plan_icons.get(u["plan"], "")
        # Анонимизируем username
        name = f"User #{u['position']}"
        top_list += f"{medal} {name} {icon} — <b>{u['total_videos']}</b> видео\n"
    
    text = get_text(user_id, "top_users", top_list=top_list)
    await message.answer(text)


@dp.message(Command("banlist"))
async def cmd_banlist(message: Message):
    """ /banlist — список заблокированных пользователей (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    banned = rate_limiter.get_banned_users()
    
    if not banned:
        await message.answer(get_text(message.from_user.id, "banlist_empty"))
        return
    
    ban_list = ""
    for u in banned[:20]:  # максимум 20
        username = u["username"] or str(u["user_id"])
        reason = u["reason"] or "Не указана"
        ban_list += f"• @{username} — {reason}\n"
    
    text = get_text(message.from_user.id, "banlist_title", ban_list=ban_list)
    await message.answer(text)


@dp.message(Command("allstats"))
async def cmd_allstats(message: Message):
    """ /allstats — полная статистика бота (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    stats = rate_limiter.get_global_stats()
    daily = rate_limiter.get_daily_stats()
    
    text = get_text(message.from_user.id, "allstats",
        total_users=stats["total_users"],
        active_today=stats["active_today"],
        new_today=daily.get("new_users", 0),
        free_users=stats["plans"].get("free", 0),
        vip_users=stats["plans"].get("vip", 0),
        premium_users=stats["plans"].get("premium", 0),
        ru_users=stats["languages"].get("ru", 0),
        en_users=stats["languages"].get("en", 0),
        videos_today=daily.get("videos_today", 0),
        total_videos=stats["total_videos"],
        total_downloads=stats["total_downloads"]
    )
    await message.answer(text)


@dp.message(Command("nightmode"))
async def cmd_nightmode(message: Message):
    """ /nightmode — включить/выключить ночной режим """
    user_id = message.from_user.id
    new_value = rate_limiter.toggle_night_mode(user_id)
    
    if new_value:
        await message.answer(get_text(user_id, "night_mode_on"))
    else:
        await message.answer(get_text(user_id, "night_mode_off"))


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
    print(f"[LANG] User {user_id} selected lang {lang}, pending_referrers={pending_referrers}")
    if user_id in pending_referrers:
        referrer_id = pending_referrers.pop(user_id)
        print(f"[LANG] Processing referral: {user_id} -> {referrer_id}")
        result = rate_limiter.set_referrer(user_id, referrer_id)
        print(f"[LANG] set_referrer result: {result}")
    
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


@dp.message(Command("limits"))
async def cmd_limits(message: Message):
    """ /limits — показать информацию о лимитах """
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    stats = rate_limiter.get_stats(user_id)
    daily_reset = rate_limiter.get_time_until_daily_reset(user_id)
    weekly_reset = rate_limiter.get_time_until_weekly_reset(user_id)
    plan_info = rate_limiter.get_plan_expiry_info(user_id)
    
    plan = stats.get("plan", "free")
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    if lang == "en":
        text = (
            f"📊 <b>Your Limits</b>\n\n"
            f"📋 Plan: <b>{plan_names.get(plan, plan)}</b>\n"
        )
        if plan_info["has_expiry"]:
            text += f"⏰ Expires in: <b>{plan_info['days_left']} days</b>\n"
        text += (
            f"\n<b>Today:</b>\n"
            f"• Used: {stats.get('daily_videos', 0)}/{stats.get('daily_limit', 2)}\n"
            f"• Remaining: {stats.get('daily_limit', 2) - stats.get('daily_videos', 0)}\n"
            f"• Reset in: {daily_reset}\n\n"
            f"<b>This week:</b>\n"
            f"• Used: {stats.get('weekly_videos', 0)}/{stats.get('weekly_limit', 14)}\n"
            f"• Remaining: {stats.get('weekly_limit', 14) - stats.get('weekly_videos', 0)}\n"
            f"• Reset in: {weekly_reset}"
        )
    else:
        text = (
            f"📊 <b>Твои лимиты</b>\n\n"
            f"📋 План: <b>{plan_names.get(plan, plan)}</b>\n"
        )
        if plan_info["has_expiry"]:
            text += f"⏰ Истекает через: <b>{plan_info['days_left']} дней</b>\n"
        text += (
            f"\n<b>Сегодня:</b>\n"
            f"• Использовано: {stats.get('daily_videos', 0)}/{stats.get('daily_limit', 2)}\n"
            f"• Осталось: {stats.get('daily_limit', 2) - stats.get('daily_videos', 0)}\n"
            f"• Сброс через: {daily_reset}\n\n"
            f"<b>На этой неделе:</b>\n"
            f"• Использовано: {stats.get('weekly_videos', 0)}/{stats.get('weekly_limit', 14)}\n"
            f"• Осталось: {stats.get('weekly_limit', 14) - stats.get('weekly_videos', 0)}\n"
            f"• Сброс через: {weekly_reset}"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Тарифы" if lang == "ru" else "💰 Pricing", callback_data="buy_premium")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """ /help — показать справку """
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Сообщить о проблеме", callback_data="report_issue")],
        [InlineKeyboardButton(text="💬 Поддержка @Null7_x", url="https://t.me/Null7_x")],
        [InlineKeyboardButton(text=get_button(user_id, "main_menu"), callback_data="back_to_start")],
    ])
    
    await message.answer(get_text(user_id, "help_faq"), reply_markup=keyboard)


@dp.message(Command("ping"))
async def cmd_ping(message: Message):
    """ /ping — проверить работоспособность бота """
    import time
    start = time.time()
    
    # Проверяем очередь
    queue_size = get_queue_size()
    
    # Время отклика
    latency = round((time.time() - start) * 1000, 2)
    
    user_id = message.from_user.id
    lang = rate_limiter.get_language(user_id)
    
    if lang == "en":
        text = (
            f"🏓 <b>Pong!</b>\n\n"
            f"📦 Version: <code>{BOT_VERSION}</code>\n"
            f"⚡ Response: <code>{latency}ms</code>\n"
            f"📥 Queue: <b>{queue_size}</b> tasks\n"
            f"✅ Bot is working!"
        )
    else:
        text = (
            f"🏓 <b>Понг!</b>\n\n"
            f"📦 Версия: <code>{BOT_VERSION}</code>\n"
            f"⚡ Отклик: <code>{latency}ms</code>\n"
            f"📥 Очередь: <b>{queue_size}</b> задач\n"
            f"✅ Бот работает!"
        )
    
    await message.answer(text)


@dp.message(Command("buy"))
async def cmd_buy(message: Message):
    """ /buy — информация о покупке Premium """
    user_id = message.from_user.id
    await message.answer(get_text(user_id, "buy_premium"), reply_markup=get_buy_premium_keyboard(user_id))

@dp.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


# ===== Промо-коды =====
@dp.message(Command("promo"))
async def cmd_promo(message: Message):
    """ /promo <код> — активировать промо-код """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(get_text(user_id, "promo_usage"))
        return
    
    code = args[1].strip().upper()
    success, result = rate_limiter.activate_promo_code(user_id, code)
    
    if success:
        await message.answer(get_text(user_id, "promo_activated", bonus=result))
    else:
        # result содержит причину ошибки
        error_key = f"promo_{result}"
        await message.answer(get_text(user_id, error_key))


@dp.message(Command("createpromo"))
async def cmd_createpromo(message: Message):
    """ /createpromo <код> <тип> <значение> [макс_использований] — создать промо-код (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    # Формат: /createpromo CODE videos 10 100
    # или: /createpromo CODE vip_days 30 50
    # или: /createpromo CODE premium_days 7 10
    args = message.text.split()
    
    if len(args) < 4:
        await message.answer(
            "📝 <b>Создание промо-кода:</b>\n\n"
            "<code>/createpromo КОД тип значение [макс_использований]</code>\n\n"
            "<b>Типы:</b>\n"
            "• <code>videos</code> — бонусные видео\n"
            "• <code>vip_days</code> — дни VIP\n"
            "• <code>premium_days</code> — дни Premium\n\n"
            "<b>Примеры:</b>\n"
            "<code>/createpromo BONUS10 videos 10 100</code>\n"
            "<code>/createpromo VIP7 vip_days 7 50</code>\n"
            "<code>/createpromo PREM3 premium_days 3</code>"
        )
        return
    
    code = args[1].upper()
    bonus_type = args[2].lower()
    
    if bonus_type not in ["videos", "vip_days", "premium_days"]:
        await message.answer("❌ Неверный тип. Используйте: videos, vip_days, premium_days")
        return
    
    try:
        bonus_value = int(args[3])
        max_uses = int(args[4]) if len(args) > 4 else None
    except ValueError:
        await message.answer("❌ Значение и макс_использований должны быть числами")
        return
    
    success = rate_limiter.create_promo_code(code, bonus_type, bonus_value, max_uses)
    
    if success:
        uses_text = f"(макс. {max_uses} использований)" if max_uses else "(безлимитный)"
        await message.answer(f"✅ Промо-код <code>{code}</code> создан!\n\n"
                            f"Тип: {bonus_type}\n"
                            f"Значение: {bonus_value}\n"
                            f"{uses_text}")
    else:
        await message.answer(f"❌ Промо-код <code>{code}</code> уже существует")


@dp.message(Command("deletepromo"))
async def cmd_deletepromo(message: Message):
    """ /deletepromo <код> — удалить промо-код (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("📝 Использование: <code>/deletepromo КОД</code>")
        return
    
    code = args[1].upper()
    success = rate_limiter.delete_promo_code(code)
    
    if success:
        await message.answer(f"✅ Промо-код <code>{code}</code> удалён")
    else:
        await message.answer(f"❌ Промо-код <code>{code}</code> не найден")


@dp.message(Command("listpromo"))
async def cmd_listpromo(message: Message):
    """ /listpromo — список промо-кодов (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    promos = rate_limiter.list_promo_codes()
    
    if not promos:
        await message.answer("📋 Нет активных промо-кодов")
        return
    
    text = "📋 <b>Активные промо-коды:</b>\n\n"
    for p in promos:
        uses = f"{p['uses']}/{p['max_uses']}" if p['max_uses'] else f"{p['uses']}/∞"
        text += f"• <code>{p['code']}</code> — {p['bonus_type']}: {p['bonus_value']} ({uses})\n"
    
    await message.answer(text)


@dp.message(Command("history"))
async def cmd_history(message: Message):
    """ /history — история обработок пользователя """
    user_id = message.from_user.id
    history = rate_limiter.get_history(user_id, limit=10)
    
    if not history:
        await message.answer(get_text(user_id, "history_empty"))
        return
    
    text = get_text(user_id, "history_title") + "\n\n"
    for i, item in enumerate(history, 1):
        date = item.get("date", "")[:10]  # только дата без времени
        video_type = item.get("type", "video")
        source = item.get("source", "unknown")
        text += f"{i}. {date} — {video_type} ({source})\n"
    
    await message.answer(text)


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """ /cancel — отменить текущую обработку """
    user_id = message.from_user.id
    task = get_user_task(user_id)
    
    if not task:
        await message.answer(get_text(user_id, "no_active_task"))
        return
    
    cancelled = cancel_task(user_id)
    if cancelled:
        await message.answer(get_text(user_id, "task_cancelled"))
    else:
        await message.answer(get_text(user_id, "cancel_failed"))


# ═══════════════════════════════════════════════════════════════════════════════
# v2.8.0: NEW COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("trial"))
async def cmd_trial(message: Message):
    """ /trial — активировать пробный VIP на 24 часа """
    user_id = message.from_user.id
    
    if not rate_limiter.can_use_trial(user_id):
        if rate_limiter.is_trial_used(user_id):
            await message.answer(get_text(user_id, "trial_vip_already_used"))
        else:
            await message.answer(get_text(user_id, "trial_vip_not_available"))
        return
    
    # Активируем trial
    success = rate_limiter.activate_trial(user_id)
    if success:
        rate_limiter.add_log(user_id, "trial_activated", "24h VIP")
        await message.answer(get_text(user_id, "trial_vip_activated"))
    else:
        await message.answer(get_text(user_id, "trial_vip_not_available"))


@dp.message(Command("streak"))
async def cmd_streak(message: Message):
    """ /streak — информация о серии использования """
    user_id = message.from_user.id
    streak_info = rate_limiter.get_streak(user_id)
    
    bonus_text = get_text(user_id, "streak_bonus") if streak_info["has_bonus"] else get_text(user_id, "streak_no_bonus")
    
    text = get_text(user_id, "streak_info",
        streak=streak_info["streak"],
        bonus_text=bonus_text
    )
    await message.answer(text)


@dp.message(Command("queue"))
async def cmd_queue(message: Message):
    """ /queue — статус очереди обработки """
    user_id = message.from_user.id
    queue_size = get_queue_size()
    eta = estimate_queue_time(queue_size)
    
    text = get_text(user_id, "queue_status",
        queue_size=queue_size,
        workers=MAX_CONCURRENT_TASKS,
        eta=eta
    )
    await message.answer(text)


@dp.message(Command("favorites"))
async def cmd_favorites(message: Message):
    """ /favorites — список избранных настроек """
    user_id = message.from_user.id
    favorites = rate_limiter.get_favorites(user_id)
    
    if not favorites:
        await message.answer(get_text(user_id, "favorites_empty"))
        return
    
    fav_list = ""
    for i, fav in enumerate(favorites, 1):
        fav_list += f"{i}. <b>{fav['name']}</b> — {fav['quality']}, {'text ON' if fav['text_overlay'] else 'text OFF'}\n"
    
    text = get_text(user_id, "favorites_title", favorites_list=fav_list)
    
    # Кнопки для загрузки
    buttons = []
    for fav in favorites[:5]:
        buttons.append([InlineKeyboardButton(
            text=f"📂 {fav['name']}",
            callback_data=f"load_fav:{fav['name']}"
        )])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.message(Command("savefav"))
async def cmd_savefav(message: Message):
    """ /savefav <имя> — сохранить текущие настройки """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("📝 Использование: <code>/savefav имя</code>\n\nПример: /savefav best_quality")
        return
    
    name = args[1].strip()[:20]  # Макс 20 символов
    rate_limiter.save_favorite(user_id, name)
    rate_limiter.add_log(user_id, "fav_saved", name)
    await message.answer(get_text(user_id, "favorite_saved", name=name))


@dp.message(Command("delfav"))
async def cmd_delfav(message: Message):
    """ /delfav <имя> — удалить избранные настройки """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("📝 Использование: <code>/delfav имя</code>")
        return
    
    name = args[1].strip()
    success = rate_limiter.delete_favorite(user_id, name)
    
    if success:
        await message.answer(get_text(user_id, "favorite_deleted", name=name))
    else:
        await message.answer("❌ Настройки не найдены")


@dp.callback_query(F.data.startswith("load_fav:"))
async def cb_load_favorite(callback: CallbackQuery):
    """ Загрузить избранные настройки """
    user_id = callback.from_user.id
    name = callback.data.split(":", 1)[1]
    
    success = rate_limiter.load_favorite(user_id, name)
    
    if success:
        await callback.answer(get_text(user_id, "favorite_loaded", name=name), show_alert=True)
    else:
        await callback.answer("❌ Настройки не найдены", show_alert=True)


@dp.message(Command("logs"))
async def cmd_logs(message: Message):
    """ /logs — последние операции (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    # Показываем логи указанного пользователя или запрашивающего
    args = message.text.split()
    if len(args) > 1:
        target = args[1]
        if target.startswith("@"):
            target_id = rate_limiter.find_user_by_username(target)
        else:
            try:
                target_id = int(target)
            except:
                target_id = message.from_user.id
    else:
        target_id = message.from_user.id
    
    logs = rate_limiter.get_logs(target_id, 20)
    
    if not logs:
        await message.answer(get_text(message.from_user.id, "logs_empty"))
        return
    
    logs_list = ""
    for log in logs:
        logs_list += f"• {log['time']} — {log['op']}"
        if log.get('details'):
            logs_list += f" ({log['details']})"
        logs_list += "\n"
    
    text = get_text(message.from_user.id, "logs_title", logs_list=logs_list)
    await message.answer(text)


@dp.message(Command("maintenance"))
async def cmd_maintenance(message: Message):
    """ /maintenance — включить/выключить режим техобслуживания (админ) """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    current = is_maintenance_mode()
    set_maintenance_mode(not current)
    
    if not current:
        await message.answer(get_text(message.from_user.id, "maintenance_on"))
    else:
        await message.answer(get_text(message.from_user.id, "maintenance_off"))


# ═══════════════════════════════════════════════════════════════════════════════
# v2.9.0: NEW COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    """ /profile — профиль пользователя с уровнем и достижениями """
    user_id = message.from_user.id
    
    # Получаем данные
    level_info = rate_limiter.get_user_level(user_id)
    achievements_info = rate_limiter.get_achievements(user_id)
    stats = rate_limiter.get_stats(user_id)
    
    # Прогресс до следующего уровня
    if level_info["next_level_points"]:
        progress = level_info["points"] / level_info["next_level_points"] * 100
        progress_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))
        next_lvl_text = f"\n{progress_bar} {progress:.0f}%\n🎯 До {level_info['next_level_name']}: {level_info['next_level_points'] - level_info['points']} очков"
    else:
        next_lvl_text = "\n🏆 Максимальный уровень!"
    
    text = get_text(user_id, "profile_info",
        level=level_info["level"],
        level_name=level_info["name"],
        level_emoji=level_info["emoji"],
        points=level_info["points"],
        achievements_count=len(achievements_info["unlocked"]),
        total_achievements=achievements_info["total"],
        total_videos=stats.get("total_videos", 0),
        next_level_text=next_lvl_text
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "achievements"), callback_data="show_achievements")],
        [InlineKeyboardButton(text=get_button(user_id, "leaderboard"), callback_data="show_leaderboard")],
        [InlineKeyboardButton(text=get_button(user_id, "main_menu"), callback_data="back_to_start")],
    ])
    
    await message.answer(text, reply_markup=keyboard)


@dp.message(Command("achievements"))
async def cmd_achievements(message: Message):
    """ /achievements — список достижений """
    user_id = message.from_user.id
    await show_achievements_menu(message, user_id)


async def show_achievements_menu(target, user_id: int):
    """ Показать меню достижений """
    from config import ACHIEVEMENTS
    
    achievements_info = rate_limiter.get_achievements(user_id)
    unlocked = achievements_info["unlocked"]
    
    text = get_text(user_id, "achievements_title",
        count=len(unlocked),
        total=achievements_info["total"],
        points=achievements_info["total_points"]
    ) + "\n\n"
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            text += f"✅ <b>{ach['name']}</b> — {ach['description']} (+{ach['points']})\n"
        else:
            text += f"🔒 <b>{ach['name']}</b> — {ach['description']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_profile")],
    ])
    
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "show_achievements")
async def cb_show_achievements(callback: CallbackQuery):
    """ Callback для показа достижений """
    await show_achievements_menu(callback, callback.from_user.id)
    await callback.answer()


@dp.callback_query(F.data == "back_to_profile")
async def cb_back_to_profile(callback: CallbackQuery):
    """ Вернуться к профилю """
    user_id = callback.from_user.id
    
    level_info = rate_limiter.get_user_level(user_id)
    achievements_info = rate_limiter.get_achievements(user_id)
    stats = rate_limiter.get_stats(user_id)
    
    if level_info["next_level_points"]:
        progress = level_info["points"] / level_info["next_level_points"] * 100
        progress_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))
        next_lvl_text = f"\n{progress_bar} {progress:.0f}%\n🎯 До {level_info['next_level_name']}: {level_info['next_level_points'] - level_info['points']} очков"
    else:
        next_lvl_text = "\n🏆 Максимальный уровень!"
    
    text = get_text(user_id, "profile_info",
        level=level_info["level"],
        level_name=level_info["name"],
        level_emoji=level_info["emoji"],
        points=level_info["points"],
        achievements_count=len(achievements_info["unlocked"]),
        total_achievements=achievements_info["total"],
        total_videos=stats.get("total_videos", 0),
        next_level_text=next_lvl_text
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "achievements"), callback_data="show_achievements")],
        [InlineKeyboardButton(text=get_button(user_id, "leaderboard"), callback_data="show_leaderboard")],
        [InlineKeyboardButton(text=get_button(user_id, "main_menu"), callback_data="back_to_start")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    """ /leaderboard — таблица лидеров """
    user_id = message.from_user.id
    await show_leaderboard(message, user_id)


async def show_leaderboard(target, user_id: int):
    """ Показать таблицу лидеров """
    leaders = rate_limiter.get_leaderboard(10)
    
    text = get_text(user_id, "leaderboard_title") + "\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, leader in enumerate(leaders):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = leader["username"] or f"User {leader['user_id']}"
        text += f"{medal} <b>{name}</b> — {leader['points']} очков (Ур. {leader['level']})\n"
    
    if not leaders:
        text += "Пока никого нет. Будьте первым!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_profile")],
    ])
    
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "show_leaderboard")
async def cb_show_leaderboard(callback: CallbackQuery):
    """ Callback для показа лидеров """
    await show_leaderboard(callback, callback.from_user.id)
    await callback.answer()


@dp.message(Command("analytics"))
async def cmd_analytics(message: Message):
    """ /analytics — персональная аналитика за неделю """
    user_id = message.from_user.id
    
    analytics = rate_limiter.get_weekly_analytics(user_id)
    
    # Создаём мини-график
    max_count = max([d["count"] for d in analytics["days"]], default=1) or 1
    chart = ""
    for day in analytics["days"]:
        bars = "█" * int(day["count"] / max_count * 5) if max_count > 0 else ""
        chart += f"{day['short']}: {bars} {day['count']}\n"
    
    text = get_text(user_id, "analytics_weekly",
        total=analytics["total"],
        average=analytics["average"],
        chart=chart
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "main_menu"), callback_data="back_to_start")],
    ])
    
    await message.answer(text, reply_markup=keyboard)


@dp.message(Command("trim"))
async def cmd_trim(message: Message):
    """ /trim — обрезать видео по времени """
    user_id = message.from_user.id
    args = message.text.split()
    
    # /trim start end
    if len(args) == 3:
        start_time = args[1]
        end_time = args[2]
        
        # Валидация формата времени (простая проверка)
        import re
        time_pattern = r"^\d+(\:\d{2}){0,2}$"
        if not re.match(time_pattern, start_time) or not re.match(time_pattern, end_time):
            await message.answer(get_text(user_id, "trim_invalid_format"))
            return
        
        rate_limiter.set_trim(user_id, start_time, end_time)
        await message.answer(get_text(user_id, "trim_set", start=start_time, end=end_time))
    elif len(args) == 2 and args[1] == "clear":
        rate_limiter.clear_trim(user_id)
        await message.answer(get_text(user_id, "trim_cleared"))
    else:
        current_start, current_end = rate_limiter.get_trim(user_id)
        if current_start and current_end:
            status = f"⏱ Текущее: {current_start} — {current_end}"
        else:
            status = "Не установлено"
        
        await message.answer(get_text(user_id, "trim_help", status=status))


@dp.message(Command("watermark"))
async def cmd_watermark(message: Message):
    """ /watermark — установить свой водяной знак """
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) > 1 and args[1] == "remove":
        rate_limiter.remove_watermark(user_id)
        await message.answer(get_text(user_id, "watermark_removed"))
        return
    
    # Показываем инструкцию и текущий статус
    wm_file, wm_pos = rate_limiter.get_watermark(user_id)
    
    if wm_file:
        status = f"✅ Установлен (позиция: {wm_pos})"
    else:
        status = "❌ Не установлен"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="↖ Верх-лево", callback_data="wm_pos:tl"),
            InlineKeyboardButton(text="↗ Верх-право", callback_data="wm_pos:tr"),
        ],
        [
            InlineKeyboardButton(text="↙ Низ-лево", callback_data="wm_pos:bl"),
            InlineKeyboardButton(text="↘ Низ-право", callback_data="wm_pos:br"),
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="wm_remove")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
    ])
    
    await message.answer(get_text(user_id, "watermark_help", status=status), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("wm_pos:"))
async def cb_watermark_position(callback: CallbackQuery):
    """ Изменить позицию водяного знака """
    user_id = callback.from_user.id
    position = callback.data.split(":")[1]
    
    wm_file, _ = rate_limiter.get_watermark(user_id)
    if wm_file:
        rate_limiter.set_watermark(user_id, wm_file, position)
        await callback.answer(f"✅ Позиция изменена на: {position}", show_alert=True)
    else:
        await callback.answer("❌ Сначала отправьте изображение для водяного знака", show_alert=True)


@dp.callback_query(F.data == "wm_remove")
async def cb_watermark_remove(callback: CallbackQuery):
    """ Удалить водяной знак """
    user_id = callback.from_user.id
    rate_limiter.remove_watermark(user_id)
    await callback.answer(get_text(user_id, "watermark_removed"), show_alert=True)


@dp.message(Command("resolution"))
async def cmd_resolution(message: Message):
    """ /resolution — изменить разрешение видео """
    user_id = message.from_user.id
    current = rate_limiter.get_resolution(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == 'original' else ''}Оригинал",
                callback_data="res:original"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '1080p' else ''}1080p",
                callback_data="res:1080p"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '720p' else ''}720p",
                callback_data="res:720p"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '480p' else ''}480p",
                callback_data="res:480p"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '360p' else ''}360p",
                callback_data="res:360p"
            ),
        ],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
    ])
    
    await message.answer(get_text(user_id, "resolution_select", current=current), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("res:"))
async def cb_resolution_change(callback: CallbackQuery):
    """ Изменить разрешение """
    user_id = callback.from_user.id
    resolution = callback.data.split(":")[1]
    
    rate_limiter.set_resolution(user_id, resolution)
    await callback.answer(f"✅ Разрешение: {resolution}", show_alert=True)
    
    # Обновляем меню
    current = resolution
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == 'original' else ''}Оригинал",
                callback_data="res:original"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '1080p' else ''}1080p",
                callback_data="res:1080p"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '720p' else ''}720p",
                callback_data="res:720p"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '480p' else ''}480p",
                callback_data="res:480p"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if current == '360p' else ''}360p",
                callback_data="res:360p"
            ),
        ],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
    ])
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)


@dp.message(Command("templates"))
async def cmd_templates(message: Message):
    """ /templates — готовые шаблоны эффектов """
    user_id = message.from_user.id
    from config import EFFECT_TEMPLATES
    
    current = rate_limiter.get_template(user_id)
    
    buttons = []
    for tmpl_id, tmpl in EFFECT_TEMPLATES.items():
        check = "✅ " if current == tmpl_id else ""
        buttons.append([InlineKeyboardButton(
            text=f"{check}{tmpl['emoji']} {tmpl['name']}",
            callback_data=f"tmpl:{tmpl_id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=f"{'✅ ' if not current else ''}Без шаблона",
        callback_data="tmpl:clear"
    )])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")])
    
    await message.answer(
        get_text(user_id, "templates_select", current=EFFECT_TEMPLATES.get(current, {}).get("name", "Не выбран")),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data.startswith("tmpl:"))
async def cb_template_select(callback: CallbackQuery):
    """ Выбрать шаблон """
    user_id = callback.from_user.id
    tmpl_id = callback.data.split(":")[1]
    
    if tmpl_id == "clear":
        rate_limiter.set_template(user_id, "")
        await callback.answer("✅ Шаблон очищен", show_alert=True)
    else:
        from config import EFFECT_TEMPLATES
        if tmpl_id in EFFECT_TEMPLATES:
            rate_limiter.set_template(user_id, tmpl_id)
            await callback.answer(f"✅ Шаблон: {EFFECT_TEMPLATES[tmpl_id]['name']}", show_alert=True)


@dp.callback_query(F.data.startswith("select_template:"))
async def cb_select_template_for_video(callback: CallbackQuery):
    """ Показать все 40 шаблонов для выбора при обработке видео """
    user_id = callback.from_user.id
    short_id = callback.data.split(":")[1]
    
    from config import VIDEO_TEMPLATES
    
    current = rate_limiter.get_template(user_id)
    plan = rate_limiter.get_plan(user_id)
    is_premium = plan in ["vip", "premium"]
    
    buttons = []
    row = []
    
    for tmpl_id, tmpl in VIDEO_TEMPLATES.items():
        # Пропускаем премиум шаблоны для free пользователей
        is_locked = tmpl.get("premium", False) and not is_premium
        check = "✅" if current == tmpl_id else ""
        lock = "🔒" if is_locked else ""
        
        btn_text = f"{check}{lock}{tmpl['name']}"
        
        # Если шаблон заблокирован - показываем уведомление
        if is_locked:
            callback_data = f"locked_tmpl:{short_id}"
        else:
            callback_data = f"vtmpl:{tmpl_id}:{short_id}"
        
        row.append(InlineKeyboardButton(text=btn_text, callback_data=callback_data))
        
        # По 2 кнопки в ряду
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    # Кнопка "Без шаблона" и "Обработать"
    buttons.append([
        InlineKeyboardButton(text="🔄 Без шаблона", callback_data=f"vtmpl:none:{short_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text=f"🎯 Обработать", callback_data=f"process:{short_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_start")
    ])
    
    template_name = VIDEO_TEMPLATES.get(current, {}).get("name", "Не выбран")
    text = f"🎨 <b>Выберите шаблон для видео</b>\n\n" \
           f"Текущий: <b>{template_name}</b>\n\n" \
           f"🔒 = только VIP/Premium"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(F.data.startswith("vtmpl:"))
async def cb_video_template_select(callback: CallbackQuery):
    """ Выбрать шаблон и показать обновлённую клавиатуру """
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    tmpl_id = parts[1]
    short_id = parts[2] if len(parts) > 2 else None
    
    from config import VIDEO_TEMPLATES
    
    if tmpl_id == "none":
        rate_limiter.set_template(user_id, "")
        await callback.answer("✅ Шаблон очищен")
    elif tmpl_id in VIDEO_TEMPLATES:
        rate_limiter.set_template(user_id, tmpl_id)
        await callback.answer(f"✅ {VIDEO_TEMPLATES[tmpl_id]['name']}")
    
    # Обновляем клавиатуру выбора шаблонов
    if short_id:
        current = rate_limiter.get_template(user_id)
        plan = rate_limiter.get_plan(user_id)
        is_premium = plan in ["vip", "premium"]
        
        buttons = []
        row = []
        
        for tid, tmpl in VIDEO_TEMPLATES.items():
            is_locked = tmpl.get("premium", False) and not is_premium
            check = "✅" if current == tid else ""
            lock = "🔒" if is_locked else ""
            
            btn_text = f"{check}{lock}{tmpl['name']}"
            
            if is_locked:
                callback_data = f"locked_tmpl:{short_id}"
            else:
                callback_data = f"vtmpl:{tid}:{short_id}"
            
            row.append(InlineKeyboardButton(text=btn_text, callback_data=callback_data))
            
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        buttons.append([
            InlineKeyboardButton(text="🔄 Без шаблона", callback_data=f"vtmpl:none:{short_id}")
        ])
        buttons.append([
            InlineKeyboardButton(text=f"🎯 Обработать", callback_data=f"process:{short_id}")
        ])
        buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_start")
        ])
        
        template_name = VIDEO_TEMPLATES.get(current, {}).get("name", "Не выбран")
        text = f"🎨 <b>Выберите шаблон для видео</b>\n\n" \
               f"Текущий: <b>{template_name}</b>\n\n" \
               f"🔒 = только VIP/Premium"
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("locked_tmpl:"))
async def cb_locked_template(callback: CallbackQuery):
    """ Уведомление о заблокированном шаблоне """
    await callback.answer("🔒 Этот шаблон доступен только для VIP/Premium пользователей", show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: ANTI-REUPLOAD LEVEL SELECTION
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("anti_level:"))
async def cb_anti_level_select(callback: CallbackQuery):
    """ Выбор уровня Anti-Reupload """
    user_id = callback.from_user.id
    short_id = callback.data.split(":")[1]
    
    from config import ANTI_REUPLOAD_LEVELS
    current = rate_limiter.get_anti_reupload_level(user_id)
    plan = rate_limiter.get_plan(user_id)
    is_premium = plan in ["vip", "premium"]
    
    buttons = []
    for level_id, level_data in ANTI_REUPLOAD_LEVELS.items():
        is_locked = level_data.get("premium_only", False) and not is_premium
        check = "✅ " if current == level_id else ""
        lock = "🔒 " if is_locked else ""
        
        btn_text = f"{check}{lock}{level_data['name']}"
        time_str = f"~{level_data.get('time_seconds', 30)}с"
        
        if is_locked:
            callback_data = f"locked_level:{short_id}"
        else:
            callback_data = f"set_level:{level_id}:{short_id}"
        
        buttons.append([
            InlineKeyboardButton(text=f"{btn_text} ({time_str})", callback_data=callback_data)
        ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_video:{short_id}")
    ])
    
    level_data = ANTI_REUPLOAD_LEVELS.get(current, {})
    text = (
        f"🛡 <b>Уровень защиты Anti-Reupload</b>\n\n"
        f"Текущий: <b>{level_data.get('name', 'Medium')}</b>\n"
        f"📝 {level_data.get('description', '')}\n\n"
        f"🟢 <b>Low</b> — быстро, базовая защита\n"
        f"🟡 <b>Medium</b> — оптимальный баланс\n"
        f"🔴 <b>Hardcore</b> — максимум (VIP/Premium)\n\n"
        f"🔒 = только VIP/Premium"
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(F.data.startswith("set_level:"))
async def cb_set_anti_level(callback: CallbackQuery):
    """ Установить уровень Anti-Reupload """
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    level_id = parts[1]
    short_id = parts[2] if len(parts) > 2 else None
    
    success = rate_limiter.set_anti_reupload_level(user_id, level_id)
    if success:
        from config import ANTI_REUPLOAD_LEVELS
        level_name = ANTI_REUPLOAD_LEVELS.get(level_id, {}).get("name", level_id)
        await callback.answer(f"✅ Уровень защиты: {level_name}")
    else:
        await callback.answer("🔒 Этот уровень доступен только для VIP/Premium", show_alert=True)
        return
    
    # Возвращаемся к видео клавиатуре
    if short_id:
        await callback.message.edit_reply_markup(reply_markup=get_video_keyboard(short_id, user_id))


@dp.callback_query(F.data.startswith("locked_level:"))
async def cb_locked_level(callback: CallbackQuery):
    """ Уведомление о заблокированном уровне """
    await callback.answer("🔒 Hardcore доступен только для VIP/Premium пользователей", show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: AUTO-UNIQUE MODE TOGGLE
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("toggle_auto_unique:"))
async def cb_toggle_auto_unique(callback: CallbackQuery):
    """ Переключить режим автоуникализации """
    user_id = callback.from_user.id
    short_id = callback.data.split(":")[1]
    
    new_state = rate_limiter.toggle_auto_unique(user_id)
    status = "ВКЛ ✅" if new_state else "ВЫКЛ"
    
    await callback.answer(f"🤖 Автоуникализация: {status}")
    await callback.message.edit_reply_markup(reply_markup=get_video_keyboard(short_id, user_id))


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: AUTO-PROCESS (Умная автообработка)
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("auto_process:"))
async def cb_auto_process(callback: CallbackQuery):
    """ Автоматическая умная обработка """
    user_id = callback.from_user.id
    short_id = callback.data.split(":")[1]
    
    # Проверка лимитов
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        await callback.answer(reason, show_alert=True)
        return
    
    # Получаем файл
    input_path = rate_limiter.get_pending_file(user_id, short_id)
    if not input_path or not os.path.exists(input_path):
        await callback.answer("❌ Видео не найдено. Отправьте заново.", show_alert=True)
        return
    
    # Устанавливаем статус обработки
    rate_limiter.set_processing(user_id, True)
    
    await callback.message.edit_text("🤖 <b>Автоуникализация запущена...</b>\n\n"
                                     "⏳ Анализируем видео и подбираем лучшие настройки...")
    
    from ffmpeg_utils import smart_auto_process, get_temp_dir, generate_unique_filename, cleanup_file
    
    output_path = str(get_temp_dir() / generate_unique_filename())
    anti_level = rate_limiter.get_anti_reupload_level(user_id)
    watermark_enabled = rate_limiter.get_watermark_trap(user_id)
    
    try:
        success, error, info = await smart_auto_process(
            input_path, output_path, user_id,
            anti_reupload_level=anti_level,
            enable_watermark_trap=watermark_enabled
        )
        
        if success:
            # Сохраняем в историю проектов
            rate_limiter.add_to_project_history(user_id, {
                "type": "auto_unique",
                "template": info.get("template"),
                "anti_level": anti_level,
                "watermark_hash": info.get("watermark_hash"),
                "file_id": short_id,
            })
            
            # Увеличиваем счётчик
            rate_limiter.increment_usage(user_id)
            
            # Отправляем результат
            try:
                with open(output_path, "rb") as video_file:
                    template_name = info.get("template", "auto")
                    processing_time = info.get("processing_time", 0)
                    
                    caption = (
                        f"✅ <b>Автоуникализация завершена!</b>\n\n"
                        f"🎨 Шаблон: <b>{template_name}</b>\n"
                        f"🛡 Защита: <b>{anti_level}</b>\n"
                        f"⏱ Время: <b>{processing_time}с</b>"
                    )
                    
                    if info.get("watermark_hash"):
                        caption += f"\n🔏 Цифровой отпечаток: <code>{info['watermark_hash'][:8]}...</code>"
                    
                    await bot.send_video(
                        chat_id=user_id,
                        video=video_file,
                        caption=caption,
                        reply_markup=get_result_keyboard(short_id, user_id)
                    )
                    await callback.message.delete()
            except Exception as e:
                logger.error(f"Send error: {e}")
                await callback.message.edit_text("❌ Ошибка отправки видео")
            finally:
                cleanup_file(output_path)
        else:
            await callback.message.edit_text(f"❌ Ошибка обработки: {error}")
    except Exception as e:
        logger.error(f"Auto-process error: {e}")
        await callback.message.edit_text("❌ Ошибка автоуникализации")
    finally:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(input_path)


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: PROJECT HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "project_history")
async def cb_project_history(callback: CallbackQuery):
    """ Показать историю проектов """
    user_id = callback.from_user.id
    history = rate_limiter.get_project_history(user_id)
    
    if not history:
        await callback.answer("📭 История пуста", show_alert=True)
        return
    
    buttons = []
    for project in history[:10]:  # Показываем последние 10
        pid = project.get("id", 0)
        ptype = project.get("type", "unknown")
        timestamp = project.get("timestamp", "")[:10]
        template = project.get("template", "")
        
        type_icons = {
            "auto_unique": "🤖",
            "process": "🎯",
            "download": "📥",
        }
        icon = type_icons.get(ptype, "📁")
        
        btn_text = f"{icon} #{pid} | {template or ptype} | {timestamp}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"repeat_project:{pid}")])
    
    buttons.append([
        InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear_history")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")
    ])
    
    text = (
        f"📜 <b>История проектов</b>\n\n"
        f"Последние {len(history)} обработок.\n"
        f"Нажмите на проект чтобы повторить с теми же настройками."
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(F.data.startswith("repeat_project:"))
async def cb_repeat_project(callback: CallbackQuery):
    """ Повторить обработку из истории """
    user_id = callback.from_user.id
    project_id = int(callback.data.split(":")[1])
    
    project = rate_limiter.get_project_by_id(user_id, project_id)
    if not project:
        await callback.answer("❌ Проект не найден", show_alert=True)
        return
    
    # Применяем настройки из проекта
    if project.get("template"):
        rate_limiter.set_template(user_id, project["template"])
    if project.get("anti_level"):
        rate_limiter.set_anti_reupload_level(user_id, project["anti_level"])
    
    await callback.answer(
        f"✅ Настройки применены!\n"
        f"Шаблон: {project.get('template', 'none')}\n"
        f"Отправьте видео для обработки.",
        show_alert=True
    )


@dp.callback_query(F.data == "clear_history")
async def cb_clear_history(callback: CallbackQuery):
    """ Очистить историю проектов """
    user_id = callback.from_user.id
    rate_limiter.clear_project_history(user_id)
    await callback.answer("🗑 История очищена", show_alert=True)
    await callback.message.edit_text(
        "📜 <b>История проектов</b>\n\n📭 История пуста.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")]
        ])
    )


@dp.callback_query(F.data.startswith("back_video:"))
async def cb_back_to_video(callback: CallbackQuery):
    """ Вернуться к клавиатуре видео """
    user_id = callback.from_user.id
    short_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "📹 <b>Видео готово к обработке</b>\n\nВыберите настройки:",
        reply_markup=get_video_keyboard(short_id, user_id)
    )
    await callback.answer()
async def cmd_convert(message: Message):
    """ /convert — конвертировать видео в другой формат """
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎞 GIF", callback_data="convert:gif"),
            InlineKeyboardButton(text="🎵 MP3", callback_data="convert:mp3"),
        ],
        [
            InlineKeyboardButton(text="🌐 WebM", callback_data="convert:webm"),
        ],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await message.answer(get_text(user_id, "convert_help"), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("convert:"))
async def cb_convert_format(callback: CallbackQuery):
    """ Выбрать формат конвертации """
    user_id = callback.from_user.id
    format_type = callback.data.split(":")[1]
    
    # Сохраняем выбранный формат для следующего видео
    user = rate_limiter.get_user(user_id)
    user.pending_convert_format = format_type
    
    format_names = {"gif": "GIF", "mp3": "MP3 (аудио)", "webm": "WebM"}
    await callback.answer(f"✅ Отправьте видео для конвертации в {format_names.get(format_type, format_type)}", show_alert=True)


@dp.message(Command("music"))
async def cmd_music(message: Message):
    """ /music — добавить музыку к видео """
    user_id = message.from_user.id
    
    # Проверяем есть ли ожидающее аудио
    pending = rate_limiter.get_pending_audio(user_id)
    
    if pending:
        status = "✅ Аудио загружено. Отправьте видео."
    else:
        status = "❌ Сначала отправьте аудиофайл."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить аудио", callback_data="music_clear")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await message.answer(get_text(user_id, "music_help", status=status), reply_markup=keyboard)


@dp.callback_query(F.data == "music_clear")
async def cb_music_clear(callback: CallbackQuery):
    """ Очистить ожидающее аудио """
    user_id = callback.from_user.id
    rate_limiter.clear_pending_audio(user_id)
    await callback.answer("✅ Аудио очищено", show_alert=True)


@dp.message(Command("reminder"))
async def cmd_reminder(message: Message):
    """ /reminder — напоминания о публикации """
    user_id = message.from_user.id
    
    from config import BEST_POSTING_TIMES
    
    reminders = rate_limiter.get_reminders(user_id)
    
    text = get_text(user_id, "reminder_help") + "\n\n"
    text += "<b>🕐 Лучшее время для публикации:</b>\n"
    for platform, times in BEST_POSTING_TIMES.items():
        text += f"• {platform}: {', '.join(times)}\n"
    
    if reminders:
        text += f"\n<b>📋 Ваши напоминания:</b>\n"
        for r in reminders:
            text += f"• {r['platform']} — {r['time']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ TikTok", callback_data="reminder_add:TikTok"),
            InlineKeyboardButton(text="➕ YouTube", callback_data="reminder_add:YouTube"),
        ],
        [
            InlineKeyboardButton(text="➕ Instagram", callback_data="reminder_add:Instagram"),
        ],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("reminder_add:"))
async def cb_reminder_add(callback: CallbackQuery):
    """ Добавить напоминание """
    user_id = callback.from_user.id
    platform = callback.data.split(":")[1]
    
    from config import BEST_POSTING_TIMES
    best_time = BEST_POSTING_TIMES.get(platform, ["12:00"])[0]
    
    rate_limiter.add_reminder(user_id, platform, best_time)
    await callback.answer(f"✅ Напоминание добавлено: {platform} в {best_time}", show_alert=True)


# ═══════════════════════════════════════════════════════════════════════════════
# v3.0.0: NEW COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("merge"))
async def cmd_merge(message: Message):
    """ /merge — склеить несколько видео """
    user_id = message.from_user.id
    args = message.text.split()
    
    # /merge clear
    if len(args) == 2 and args[1] == "clear":
        rate_limiter.clear_merge_queue(user_id)
        await message.answer(get_text(user_id, "merge_cleared"))
        return
    
    from config import MAX_MERGE_VIDEOS
    queue = rate_limiter.get_merge_queue(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "merge_now"), callback_data="merge_now")],
        [InlineKeyboardButton(text=get_button(user_id, "merge_clear"), callback_data="merge_clear")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ]) if len(queue) >= 2 else InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "merge_clear"), callback_data="merge_clear")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await message.answer(
        get_text(user_id, "merge_help", count=len(queue), max=MAX_MERGE_VIDEOS),
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "merge_now")
async def cb_merge_now(callback: CallbackQuery):
    """ Склеить видео из очереди """
    user_id = callback.from_user.id
    queue = rate_limiter.get_merge_queue(user_id)
    
    if len(queue) < 2:
        await callback.answer(get_text(user_id, "merge_need_more"), show_alert=True)
        return
    
    await callback.answer()
    msg = await callback.message.edit_text(get_text(user_id, "merge_processing", count=len(queue)))
    
    # Скачиваем все видео
    from ffmpeg_utils import get_temp_dir, merge_videos, cleanup_file
    import uuid
    
    temp_dir = get_temp_dir()
    temp_files = []
    
    try:
        for i, file_id in enumerate(queue):
            file = await bot.get_file(file_id)
            temp_path = str(temp_dir / f"merge_{user_id}_{i}_{uuid.uuid4().hex[:8]}.mp4")
            await bot.download_file(file.file_path, temp_path)
            temp_files.append(temp_path)
        
        # Склеиваем
        output_path = str(temp_dir / f"merged_{user_id}_{uuid.uuid4().hex[:8]}.mp4")
        success, error = await merge_videos(temp_files, output_path)
        
        if success:
            video = FSInputFile(output_path)
            await callback.message.answer_video(video, caption=get_text(user_id, "merge_done"))
            cleanup_file(output_path)
        else:
            await msg.edit_text(f"❌ Ошибка склейки: {error}")
        
        # Очищаем временные файлы и очередь
        for f in temp_files:
            cleanup_file(f)
        rate_limiter.clear_merge_queue(user_id)
        
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
        for f in temp_files:
            cleanup_file(f)


@dp.callback_query(F.data == "merge_clear")
async def cb_merge_clear(callback: CallbackQuery):
    """ Очистить очередь склейки """
    user_id = callback.from_user.id
    rate_limiter.clear_merge_queue(user_id)
    await callback.answer(get_text(user_id, "merge_cleared"), show_alert=True)


@dp.message(Command("speed"))
async def cmd_speed(message: Message):
    """ /speed — изменить скорость видео """
    user_id = message.from_user.id
    current = rate_limiter.get_speed(user_id)
    
    from config import SPEED_OPTIONS
    buttons = []
    row = []
    for speed_name in SPEED_OPTIONS.keys():
        emoji = "✅ " if speed_name == current else ""
        row.append(InlineKeyboardButton(text=f"{emoji}{speed_name}", callback_data=f"speed:{speed_name}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "speed_menu", current=current), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("speed:"))
async def cb_speed_select(callback: CallbackQuery):
    """ Выбрать скорость """
    user_id = callback.from_user.id
    speed = callback.data.split(":")[1]
    
    rate_limiter.set_speed(user_id, speed)
    await callback.answer(get_text(user_id, "speed_changed", speed=speed), show_alert=True)


@dp.message(Command("rotate"))
async def cmd_rotate(message: Message):
    """ /rotate — повернуть/отразить видео """
    user_id = message.from_user.id
    
    from config import ROTATION_OPTIONS
    buttons = []
    for rot_id, rot_data in ROTATION_OPTIONS.items():
        buttons.append([InlineKeyboardButton(text=rot_data["name"], callback_data=f"rotate:{rot_id}")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "rotate_menu"), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("rotate:"))
async def cb_rotate_select(callback: CallbackQuery):
    """ Выбрать поворот """
    user_id = callback.from_user.id
    rotation = callback.data.split(":")[1]
    
    rate_limiter.set_rotation(user_id, rotation)
    
    from config import ROTATION_OPTIONS
    name = ROTATION_OPTIONS.get(rotation, {}).get("name", rotation)
    await callback.answer(f"✅ {name} — отправьте видео", show_alert=True)


@dp.message(Command("aspect"))
async def cmd_aspect(message: Message):
    """ /aspect — изменить соотношение сторон """
    user_id = message.from_user.id
    current = rate_limiter.get_aspect(user_id) or "Не выбрано"
    
    from config import ASPECT_RATIOS
    buttons = []
    for aspect_id, aspect_data in ASPECT_RATIOS.items():
        emoji = "✅ " if aspect_id == current else ""
        buttons.append([InlineKeyboardButton(text=f"{emoji}{aspect_data['name']}", callback_data=f"aspect:{aspect_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 Сбросить", callback_data="aspect:clear")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "aspect_menu", current=current), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("aspect:"))
async def cb_aspect_select(callback: CallbackQuery):
    """ Выбрать соотношение """
    user_id = callback.from_user.id
    aspect = callback.data.split(":")[1]
    
    if aspect == "clear":
        rate_limiter.clear_aspect(user_id)
        await callback.answer("✅ Сброшено", show_alert=True)
    else:
        rate_limiter.set_aspect(user_id, aspect)
        await callback.answer(get_text(user_id, "aspect_changed", aspect=aspect), show_alert=True)


@dp.message(Command("filter"))
async def cmd_filter(message: Message):
    """ /filter — применить видео-фильтр """
    user_id = message.from_user.id
    current = rate_limiter.get_filter(user_id) or "Нет"
    
    from config import VIDEO_FILTERS
    buttons = []
    row = []
    for filter_id, filter_data in VIDEO_FILTERS.items():
        emoji = "✅" if filter_id == current else ""
        row.append(InlineKeyboardButton(text=f"{emoji}{filter_data['name']}", callback_data=f"filter:{filter_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🗑 Убрать фильтр", callback_data="filter:clear")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "filter_menu", current=current), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("filter:"))
async def cb_filter_select(callback: CallbackQuery):
    """ Выбрать фильтр """
    user_id = callback.from_user.id
    filter_id = callback.data.split(":")[1]
    
    if filter_id == "clear":
        rate_limiter.clear_filter(user_id)
        await callback.answer(get_text(user_id, "filter_removed"), show_alert=True)
    else:
        rate_limiter.set_filter(user_id, filter_id)
        from config import VIDEO_FILTERS
        name = VIDEO_FILTERS.get(filter_id, {}).get("name", filter_id)
        await callback.answer(get_text(user_id, "filter_applied", name=name), show_alert=True)


@dp.message(Command("text"))
async def cmd_text(message: Message):
    """ /text — добавить свой текст на видео """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    # /text clear
    if len(args) == 2 and args[1].lower() == "clear":
        rate_limiter.clear_custom_text(user_id)
        await message.answer(get_text(user_id, "text_overlay_cleared"))
        return
    
    # /text Мой текст
    if len(args) == 2:
        text = args[1]
        rate_limiter.set_custom_text(user_id, text)
        await message.answer(get_text(user_id, "text_overlay_set", text=text[:50]))
        return
    
    # Просто /text
    current = rate_limiter.get_custom_text(user_id) or "Не установлен"
    await message.answer(get_text(user_id, "text_overlay_help", status=current))


@dp.message(Command("caption"))
async def cmd_caption(message: Message):
    """ /caption — выбрать стиль текста """
    user_id = message.from_user.id
    current = rate_limiter.get_caption_style(user_id)
    
    from config import CAPTION_STYLES
    buttons = []
    for style_id, style_data in CAPTION_STYLES.items():
        emoji = "✅ " if style_id == current else ""
        buttons.append([InlineKeyboardButton(text=f"{emoji}{style_data['name']}", callback_data=f"caption:{style_id}")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "caption_menu", current=CAPTION_STYLES.get(current, {}).get("name", current)), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("caption:"))
async def cb_caption_select(callback: CallbackQuery):
    """ Выбрать стиль текста """
    user_id = callback.from_user.id
    style = callback.data.split(":")[1]
    
    rate_limiter.set_caption_style(user_id, style)
    from config import CAPTION_STYLES
    name = CAPTION_STYLES.get(style, {}).get("name", style)
    await callback.answer(get_text(user_id, "caption_changed", name=name), show_alert=True)


@dp.message(Command("compress"))
async def cmd_compress(message: Message):
    """ /compress — сжать видео """
    user_id = message.from_user.id
    
    from config import COMPRESSION_PRESETS
    buttons = []
    for preset_id, preset_data in COMPRESSION_PRESETS.items():
        buttons.append([InlineKeyboardButton(text=preset_data["name"], callback_data=f"compress:{preset_id}")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "compress_menu"), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("compress:"))
async def cb_compress_select(callback: CallbackQuery):
    """ Выбрать пресет сжатия """
    user_id = callback.from_user.id
    preset = callback.data.split(":")[1]
    
    rate_limiter.set_compression(user_id, preset)
    from config import COMPRESSION_PRESETS
    name = COMPRESSION_PRESETS.get(preset, {}).get("name", preset)
    await callback.answer(f"✅ {name} — отправьте видео", show_alert=True)


@dp.message(Command("thumbnail"))
async def cmd_thumbnail(message: Message):
    """ /thumbnail — создать превью """
    user_id = message.from_user.id
    args = message.text.split()
    
    # /thumbnail 00:15 — кастомное время
    if len(args) == 2:
        time_str = args[1]
        # Сохраняем время для следующего видео
        user = rate_limiter.get_user(user_id)
        user.pending_thumbnail_time = time_str
        await message.answer(f"🖼 Время {time_str} установлено. Отправьте видео.")
        return
    
    from config import THUMBNAIL_OPTIONS
    buttons = []
    row = []
    for opt_id, opt_data in THUMBNAIL_OPTIONS.items():
        row.append(InlineKeyboardButton(text=opt_data["name"], callback_data=f"thumb:{opt_id}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "thumbnail_menu"), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("thumb:"))
async def cb_thumb_select(callback: CallbackQuery):
    """ Выбрать время для превью """
    user_id = callback.from_user.id
    opt = callback.data.split(":")[1]
    
    user = rate_limiter.get_user(user_id)
    user.pending_thumbnail_time = opt
    await callback.answer(f"✅ Выбрано: {opt} — отправьте видео", show_alert=True)


@dp.message(Command("info"))
async def cmd_info(message: Message):
    """ /info — получить информацию о видео """
    user_id = message.from_user.id
    
    # Ставим флаг для следующего видео
    user = rate_limiter.get_user(user_id)
    user.pending_video_info = True
    
    await message.answer("📊 Отправьте видео для получения информации")


@dp.message(Command("volume"))
async def cmd_volume(message: Message):
    """ /volume — изменить громкость """
    user_id = message.from_user.id
    current = rate_limiter.get_volume(user_id)
    
    from config import VOLUME_OPTIONS
    buttons = []
    row = []
    for vol_id, vol_data in VOLUME_OPTIONS.items():
        emoji = "✅" if vol_id == current else ""
        row.append(InlineKeyboardButton(text=f"{emoji}{vol_data['name']}", callback_data=f"volume:{vol_id}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔄 Сбросить", callback_data="volume:clear")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(get_text(user_id, "volume_menu", current=current), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("volume:"))
async def cb_volume_select(callback: CallbackQuery):
    """ Выбрать громкость """
    user_id = callback.from_user.id
    vol = callback.data.split(":")[1]
    
    if vol == "clear":
        rate_limiter.clear_volume(user_id)
        await callback.answer("✅ Громкость сброшена", show_alert=True)
    else:
        rate_limiter.set_volume(user_id, vol)
        from config import VOLUME_OPTIONS
        name = VOLUME_OPTIONS.get(vol, {}).get("name", vol)
        await callback.answer(get_text(user_id, "volume_changed", level=name), show_alert=True)


@dp.message(Command("schedule"))
async def cmd_schedule(message: Message):
    """ /schedule — запланировать задачу """
    user_id = message.from_user.id
    
    tasks = rate_limiter.get_scheduled_tasks(user_id)
    
    if tasks:
        task_list = ""
        for t in tasks:
            task_list += f"• {t['time']} — {t['action']} (ID: {t['id']})\n"
    else:
        task_list = "Нет задач"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить все", callback_data="schedule_clear")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await message.answer(get_text(user_id, "schedule_help", count=len(tasks)) + f"\n\n{task_list}", reply_markup=keyboard)


@dp.callback_query(F.data == "schedule_clear")
async def cb_schedule_clear(callback: CallbackQuery):
    """ Очистить запланированные задачи """
    user_id = callback.from_user.id
    rate_limiter.clear_scheduled_tasks(user_id)
    await callback.answer("✅ Все задачи удалены", show_alert=True)


@dp.message(Command("autoprocess"))
async def cmd_autoprocess(message: Message):
    """ /autoprocess — авто-обработка по шаблону """
    user_id = message.from_user.id
    current = rate_limiter.get_auto_process(user_id) or "Выключено"
    
    from config import AUTO_PROCESS_TEMPLATES
    buttons = []
    for tpl_id, tpl_data in AUTO_PROCESS_TEMPLATES.items():
        emoji = "✅ " if tpl_id == current else ""
        buttons.append([InlineKeyboardButton(text=f"{emoji}{tpl_data['name']}", callback_data=f"autoprocess:{tpl_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Выключить", callback_data="autoprocess:off")])
    buttons.append([InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    desc = ""
    if current and current != "Выключено":
        template = AUTO_PROCESS_TEMPLATES.get(current)
        if template:
            desc = f"\n\n📝 {template['description']}"
    
    await message.answer(get_text(user_id, "autoprocess_menu", current=current) + desc, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("autoprocess:"))
async def cb_autoprocess_select(callback: CallbackQuery):
    """ Выбрать шаблон авто-обработки """
    user_id = callback.from_user.id
    tpl = callback.data.split(":")[1]
    
    if tpl == "off":
        rate_limiter.clear_auto_process(user_id)
        await callback.answer(get_text(user_id, "autoprocess_disabled"), show_alert=True)
    else:
        rate_limiter.set_auto_process(user_id, tpl)
        from config import AUTO_PROCESS_TEMPLATES
        template = AUTO_PROCESS_TEMPLATES.get(tpl, {})
        await callback.answer(get_text(user_id, "autoprocess_enabled", name=template.get("name", tpl), description=template.get("description", "")), show_alert=True)


# ===== Админ-панель =====
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """ /admin — панель администратора """
    if not is_admin(message.from_user):
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промо-коды", callback_data="admin_promo"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="⏰ Истекающие", callback_data="admin_expiring"),
            InlineKeyboardButton(text="📥 Очередь", callback_data="admin_queue"),
        ],
        [
            InlineKeyboardButton(text="� Источники", callback_data="admin_sources"),
            InlineKeyboardButton(text="💾 Backup", callback_data="admin_backup"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить yt-dlp", callback_data="admin_update_ytdlp"),
            InlineKeyboardButton(text="🏥 Health", callback_data="admin_health"),
        ],
        [
            InlineKeyboardButton(text="📝 Команды", callback_data="admin_commands"),
        ],
    ])
    
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=keyboard)


@dp.callback_query(F.data == "admin_commands")
async def cb_admin_commands(callback: CallbackQuery):
    """ Список всех админских команд """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = (
        "📝 <b>Команды администратора</b>\n\n"
        "<b>👤 Подписки (любое кол-во дней):</b>\n"
        "• <code>/vip @user 7</code> — неделя\n"
        "• <code>/vip @user 30</code> — месяц\n"
        "• <code>/vip @user 180</code> — 6 мес\n"
        "• <code>/vip @user 365</code> — год\n"
        "• <code>/premium @user [дней]</code> — Premium\n"
        "• <code>/removeplan @user</code> — убрать\n\n"
        "<b>👤 Управление:</b>\n"
        "• <code>/userinfo @user</code> — инфо\n"
        "• <code>/ban @user [причина]</code>\n"
        "• <code>/unban @user</code>\n\n"
        "<b>🔧 Администраторы:</b>\n"
        "• <code>/addadmin @user</code> — добавить (+ Premium навсегда)\n"
        "• <code>/removeadmin @user</code> — убрать (+ сброс Premium)\n\n"
        "<b>🎟 Промо-коды:</b>\n"
        "• <code>/createpromo КОД тип знач [макс]</code>\n"
        "• <code>/deletepromo КОД</code>\n"
        "• <code>/listpromo</code>\n\n"
        "<b>📊 Статистика:</b>\n"
        "• <code>/globalstats</code> • <code>/dailystats</code>\n"
        "• <code>/checkexpiry</code>\n\n"
        "<b>🔧 Система:</b>\n"
        "• <code>/broadcast текст</code>\n"
        "• <code>/update_ytdlp</code> • <code>/ping</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """ Статистика в админ-панели """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    stats = rate_limiter.get_global_stats()
    
    text = (
        f"📊 <b>Глобальная статистика:</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🟢 Активных сегодня: {stats['active_today']}\n"
        f"🎬 Обработано видео: {stats['total_videos']}\n\n"
        f"<b>Подписки:</b>\n"
        f"• Free: {stats['plans']['free']}\n"
        f"• VIP: {stats['plans']['vip']}\n"
        f"• Premium: {stats['plans']['premium']}\n\n"
        f"<b>Языки:</b>\n"
        f"• 🇷🇺 RU: {stats['languages'].get('ru', 0)}\n"
        f"• 🇬🇧 EN: {stats['languages'].get('en', 0)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    """ Информация о пользователях """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Найти", callback_data="admin_find_user"),
            InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans"),
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "• <code>/userinfo ID/@username</code> — инфо о пользователе\n"
        "• <code>/vip ID/@username</code> — выдать VIP\n"
        "• <code>/premium ID/@username</code> — выдать Premium\n"
        "• <code>/removeplan ID/@username</code> — убрать подписку\n"
        "• <code>/ban ID/@username причина</code> — заблокировать\n"
        "• <code>/unban ID/@username</code> — разблокировать",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_promo")
async def cb_admin_promo(callback: CallbackQuery):
    """ Управление промо-кодами """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    promos = rate_limiter.list_promo_codes()
    
    text = "🎟 <b>Промо-коды</b>\n\n"
    if promos:
        for p in promos[:10]:  # показываем максимум 10
            uses = f"{p['uses']}/{p['max_uses']}" if p['max_uses'] else f"{p['uses']}/∞"
            text += f"• <code>{p['code']}</code> — {p['bonus_type']}: {p['bonus_value']} ({uses})\n"
    else:
        text += "Нет активных промо-кодов\n"
    
    text += (
        "\n<b>Команды:</b>\n"
        "• <code>/createpromo КОД тип значение [макс]</code>\n"
        "• <code>/deletepromo КОД</code>\n"
        "• <code>/listpromo</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery):
    """ Рассылка """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Для отправки рассылки используйте команду:\n"
        "<code>/broadcast текст сообщения</code>\n\n"
        "⚠️ Сообщение будет отправлено всем пользователям бота.",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_expiring")
async def cb_admin_expiring(callback: CallbackQuery):
    """ Истекающие подписки """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    expiring = rate_limiter.get_expiring_users(days_before=7)
    
    text = "⏰ <b>Истекающие подписки (7 дней)</b>\n\n"
    if expiring:
        for u in expiring[:15]:  # максимум 15
            text += f"• @{u['username'] or u['user_id']} — {u['plan']} ({u['days_left']} дн.)\n"
    else:
        text += "Нет истекающих подписок"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_queue")
async def cb_admin_queue(callback: CallbackQuery):
    """ Информация об очереди """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    queue_size = get_queue_size()
    
    text = (
        f"📥 <b>Очередь обработки</b>\n\n"
        f"Задач в очереди: {queue_size}\n"
        f"Воркеров: {MAX_CONCURRENT_TASKS}\n\n"
        f"ℹ️ VIP и Premium пользователи имеют приоритет в очереди."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_update_ytdlp")
async def cb_admin_update_ytdlp(callback: CallbackQuery):
    """ Обновить yt-dlp """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.answer("🔄 Обновляю yt-dlp...", show_alert=True)
    await callback.message.edit_text("🔄 Обновляю yt-dlp...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["pip", "install", "-U", "yt-dlp"],
            capture_output=True, text=True, timeout=120
        )
        
        if result.returncode == 0:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
            ])
            await callback.message.edit_text("✅ yt-dlp успешно обновлён!", reply_markup=keyboard)
        else:
            await callback.message.edit_text(f"❌ Ошибка обновления:\n<code>{result.stderr[:500]}</code>")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")


@dp.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery):
    """ Назад в админ-панель """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промо-коды", callback_data="admin_promo"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="⏰ Истекающие", callback_data="admin_expiring"),
            InlineKeyboardButton(text="📥 Очередь", callback_data="admin_queue"),
        ],
        [
            InlineKeyboardButton(text="� Источники", callback_data="admin_sources"),
            InlineKeyboardButton(text="💾 Backup", callback_data="admin_backup"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить yt-dlp", callback_data="admin_update_ytdlp"),
            InlineKeyboardButton(text="🏥 Health", callback_data="admin_health"),
        ],
        [
            InlineKeyboardButton(text="📝 Команды", callback_data="admin_commands"),
        ],
    ])
    
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_sources")
async def cb_admin_sources(callback: CallbackQuery):
    """ Статистика по источникам """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    sources = rate_limiter.get_source_stats()
    total = sum(sources.values())
    
    text = "📈 <b>Статистика по источникам:</b>\n\n"
    
    icons = {
        "file": "📁",
        "tiktok": "🎵",
        "youtube": "▶️",
        "instagram": "📸",
        "chinese": "🇨🇳",
        "url": "🔗",
    }
    
    for source, count in sorted(sources.items(), key=lambda x: -x[1]):
        pct = (count / total * 100) if total > 0 else 0
        icon = icons.get(source, "📦")
        text += f"{icon} {source}: <b>{count}</b> ({pct:.1f}%)\n"
    
    text += f"\n📊 Всего: <b>{total}</b> обработок"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_backup")
async def cb_admin_backup(callback: CallbackQuery):
    """ Меню backup """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Экспорт", callback_data="admin_do_backup")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        "💾 <b>Backup данных</b>\n\n"
        "📤 <b>Экспорт</b> — скачать все данные\n"
        "📥 <b>Импорт</b> — отправьте JSON файл боту\n\n"
        "⚠️ При импорте существующие данные будут перезаписаны!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_do_backup")
async def cb_admin_do_backup(callback: CallbackQuery):
    """ Выполнить backup """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.answer("📤 Создаю backup...", show_alert=True)
    
    try:
        import datetime
        backup_data = rate_limiter.export_backup()
        
        # Создаём временный файл
        filename = f"virex_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = str(get_temp_dir() / filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(backup_data)
        
        # Отправляем файл
        from aiogram.types import FSInputFile
        doc = FSInputFile(filepath, filename=filename)
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=doc,
            caption=f"💾 Backup создан\n📊 Пользователей: {len(rate_limiter.users)}"
        )
        
        # Удаляем временный файл
        cleanup_file(filepath)
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")


@dp.callback_query(F.data == "admin_health")
async def cb_admin_health(callback: CallbackQuery):
    """ Health check """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        uptime_seconds = time_module.time() - process.create_time()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
    except ImportError:
        memory_mb = 0
        uptime_str = "N/A (psutil not installed)"
    
    import sys
    
    # Очередь
    queue_size = get_queue_size()
    
    # Temp папка
    from ffmpeg_utils import get_temp_dir_size
    temp_size_mb, temp_files = get_temp_dir_size()
    
    text = (
        f"🏥 <b>Health Check</b>\n\n"
        f"✅ Бот работает\n"
        f"⏱ Uptime: {uptime_str}\n"
        f"🐍 Python: {sys.version.split()[0]}\n\n"
        f"<b>Ресурсы:</b>\n"
        f"💾 Память: {memory_mb:.1f} MB\n"
        f"📁 Temp: {temp_size_mb} MB ({temp_files} файлов)\n\n"
        f"<b>Очередь:</b>\n"
        f"📥 Задач: {queue_size}/{MAX_CONCURRENT_TASKS * 10}\n"
        f"👷 Воркеров: {MAX_CONCURRENT_TASKS}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Очистить temp", callback_data="admin_cleanup_temp")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_cleanup_temp")
async def cb_admin_cleanup_temp(callback: CallbackQuery):
    """ Очистить temp файлы """
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    deleted = cleanup_old_files(max_age_seconds=0)  # Удалить все файлы
    await callback.answer(f"🧹 Удалено {deleted} файлов", show_alert=True)
    
    # Обновляем health check
    await cb_admin_health(callback)


# ===== Быстрый выбор качества =====
@dp.callback_query(F.data.startswith("quick_q:"))
async def cb_quick_quality(callback: CallbackQuery):
    """ Быстрая смена качества перед обработкой """
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
    
    quality_map = {"low": Quality.LOW, "medium": Quality.MEDIUM, "max": Quality.MAX}
    new_quality = quality_map.get(parts[1])
    short_id = parts[2]
    
    if new_quality:
        rate_limiter.set_quality(user_id, new_quality)
        quality_names = {"low": "📉 Быстрое", "medium": "📊 Среднее", "max": "📈 Максимум"}
        await callback.answer(f"✅ Качество: {quality_names.get(parts[1], parts[1])}", show_alert=False)
        
        # Обновляем клавиатуру
        await callback.message.edit_reply_markup(
            reply_markup=get_video_keyboard(short_id, user_id)
        )
    else:
        await callback.answer()


# ===== Кнопка отмены при обработке =====
@dp.callback_query(F.data == "cancel_processing")
async def cb_cancel_processing(callback: CallbackQuery):
    """ Отмена обработки по кнопке """
    user_id = callback.from_user.id
    task = get_user_task(user_id)
    
    if not task:
        await callback.answer(get_text(user_id, "no_active_task"), show_alert=True)
        return
    
    cancelled = cancel_task(user_id)
    if cancelled:
        await callback.message.edit_text(get_text(user_id, "task_cancelled"))
        await callback.answer()
    else:
        await callback.answer(get_text(user_id, "cancel_failed"), show_alert=True)

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


# ═══════════════════════════════════════════════════════════════════
# 🛡️ VIREX SHIELD MENU — Кнопки системы защиты
# ═══════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "shield_menu")
async def cb_shield_menu(callback: CallbackQuery):
    """Меню VIREX SHIELD"""
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    plan = rate_limiter.get_plan(user_id)
    is_vip = plan in ["vip", "premium", "admin"]
    is_premium = plan in ["premium", "admin"]
    
    # Базовые кнопки (доступны всем)
    buttons = [
        [InlineKeyboardButton(text="🛡️ О системе SHIELD", callback_data="shield_info")],
        [InlineKeyboardButton(text="🎨 Smart Presets", callback_data="shield_presets")],
        [InlineKeyboardButton(text="🎫 Мои паспорта", callback_data="shield_passport")],
    ]
    
    # VIP+ кнопки
    if is_vip:
        buttons.append([InlineKeyboardButton(text="🔍 AI Safe-Check", callback_data="shield_safecheck")])
        buttons.append([InlineKeyboardButton(text="📡 Scanner", callback_data="shield_scan")])
        buttons.append([InlineKeyboardButton(text="📊 Analytics", callback_data="shield_analytics")])
    else:
        buttons.append([InlineKeyboardButton(text="🔒 AI Safe-Check (VIP)", callback_data="need_vip")])
        buttons.append([InlineKeyboardButton(text="🔒 Scanner (VIP)", callback_data="need_vip")])
        buttons.append([InlineKeyboardButton(text="🔒 Analytics (VIP)", callback_data="need_vip")])
    
    # Premium кнопка
    if is_premium:
        buttons.append([InlineKeyboardButton(text="🕵️ Detect Watermark", callback_data="shield_detect")])
    else:
        buttons.append([InlineKeyboardButton(text="🔒 Detect (Premium)", callback_data="need_premium")])
    
    # Назад
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    text = (
        "🛡️ <b>VIREX SHIELD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Комплексная система защиты контента</i>\n\n"
        "🎨 <b>Smart Presets</b> — готовые настройки\n"
        "🔍 <b>Safe-Check</b> — AI анализ рисков\n"
        "📡 <b>Scanner</b> — определение платформы\n"
        "🎫 <b>Passports</b> — цифровые паспорта\n"
        "📊 <b>Analytics</b> — статистика защиты\n"
        "🕵️ <b>Detect</b> — поиск Watermark-Trap\n\n"
        f"📋 Ваш план: <b>{plan.upper()}</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_info")
async def cb_shield_info(callback: CallbackQuery):
    """Информация о VIREX SHIELD"""
    user_id = callback.from_user.id
    
    if not VIREX_SHIELD_AVAILABLE:
        await callback.answer("❌ SHIELD недоступен", show_alert=True)
        return
    
    shield = get_virex_shield()
    lang = rate_limiter.get_language(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="shield_menu")]
    ])
    
    await callback.message.edit_text(shield.get_shield_info(lang), reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_presets")
async def cb_shield_presets(callback: CallbackQuery):
    """Список Smart Presets"""
    user_id = callback.from_user.id
    
    if not VIREX_SHIELD_AVAILABLE:
        await callback.answer("❌ SHIELD недоступен", show_alert=True)
        return
    
    lang = rate_limiter.get_language(user_id)
    
    # Кнопки для каждого пресета
    preset_buttons = []
    for preset_id, preset in SMART_PRESETS.items():
        icon = preset.get("icon", "🎯")
        name = preset.get("name_ru" if lang == "ru" else "name", preset_id)
        preset_buttons.append([
            InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"apply_preset:{preset_id}")
        ])
    
    preset_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="shield_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=preset_buttons)
    
    text = (
        "🎨 <b>SMART PRESETS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Выберите пресет для автоматической настройки:</i>\n\n"
        "Каждый пресет оптимизирован под конкретную платформу "
        "и тип контента для максимальной защиты."
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("apply_preset:"))
async def cb_apply_preset(callback: CallbackQuery):
    """Применить Smart Preset"""
    user_id = callback.from_user.id
    preset_id = callback.data.split(":")[1]
    
    if preset_id not in SMART_PRESETS:
        await callback.answer("❌ Пресет не найден", show_alert=True)
        return
    
    preset = SMART_PRESETS[preset_id]
    settings = preset.get("settings", {})
    
    # Применяем настройки
    if "template" in settings:
        rate_limiter.set_template(user_id, settings["template"])
    if "anti_level" in settings:
        rate_limiter.set_anti_reupload_level(user_id, settings["anti_level"])
    if "quality" in settings:
        rate_limiter.set_quality(user_id, settings["quality"])
    
    lang = rate_limiter.get_language(user_id)
    name = preset.get("name_ru" if lang == "ru" else "name", preset_id)
    icon = preset.get("icon", "🎯")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Другие пресеты", callback_data="shield_presets")],
        [InlineKeyboardButton(text="◀️ В меню SHIELD", callback_data="shield_menu")]
    ])
    
    text = (
        f"✅ <b>Пресет применён!</b>\n\n"
        f"{icon} <b>{name}</b>\n\n"
        f"📋 Настройки обновлены:\n"
        f"• Шаблон: {settings.get('template', 'default')}\n"
        f"• Защита: {settings.get('anti_level', 'medium')}\n"
        f"• Качество: {settings.get('quality', 'medium')}"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(f"✅ {name} применён!")


@dp.callback_query(F.data == "shield_passport")
async def cb_shield_passport(callback: CallbackQuery):
    """Показать паспорта пользователя"""
    user_id = callback.from_user.id
    
    if not VIREX_SHIELD_AVAILABLE:
        await callback.answer("❌ SHIELD недоступен", show_alert=True)
        return
    
    shield = get_virex_shield()
    lang = rate_limiter.get_language(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="shield_menu")]
    ])
    
    await callback.message.edit_text(shield.get_user_passports(user_id, lang), reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_safecheck")
async def cb_shield_safecheck(callback: CallbackQuery):
    """Запуск Safe-Check"""
    user_id = callback.from_user.id
    
    plan = rate_limiter.get_plan(user_id)
    if plan not in ["vip", "premium", "admin"]:
        await callback.answer("🔒 Требуется VIP подписка", show_alert=True)
        return
    
    pending_safecheck[user_id] = True
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="shield_menu")]
    ])
    
    text = (
        "🔍 <b>AI SAFE-CHECK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📹 <b>Отправьте видео</b> для анализа рисков.\n\n"
        "AI проанализирует контент и определит:\n"
        "• 📊 Уровень риска детекции\n"
        "• 🎯 Рекомендуемые настройки\n"
        "• ⚠️ Потенциальные проблемы"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_scan")
async def cb_shield_scan(callback: CallbackQuery):
    """Запуск Scanner"""
    user_id = callback.from_user.id
    
    plan = rate_limiter.get_plan(user_id)
    if plan not in ["vip", "premium", "admin"]:
        await callback.answer("🔒 Требуется VIP подписка", show_alert=True)
        return
    
    pending_scan[user_id] = True
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="shield_menu")]
    ])
    
    text = (
        "📡 <b>CONTENT SCANNER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📹 <b>Отправьте видео</b> для сканирования.\n\n"
        "Scanner определит:\n"
        "• 🎬 Оригинальную платформу\n"
        "• 🔍 Технические характеристики\n"
        "• 🛡️ Следы предыдущей обработки"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_analytics")
async def cb_shield_analytics(callback: CallbackQuery):
    """Показать аналитику"""
    user_id = callback.from_user.id
    
    plan = rate_limiter.get_plan(user_id)
    if plan not in ["vip", "premium", "admin"]:
        await callback.answer("🔒 Требуется VIP подписка", show_alert=True)
        return
    
    if not VIREX_SHIELD_AVAILABLE:
        await callback.answer("❌ SHIELD недоступен", show_alert=True)
        return
    
    shield = get_virex_shield()
    lang = rate_limiter.get_language(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="shield_menu")]
    ])
    
    await callback.message.edit_text(shield.get_analytics(user_id, lang), reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shield_detect")
async def cb_shield_detect(callback: CallbackQuery):
    """Запуск Detect Watermark-Trap"""
    user_id = callback.from_user.id
    
    plan = rate_limiter.get_plan(user_id)
    if plan not in ["premium", "admin"]:
        await callback.answer("🔒 Требуется Premium подписка", show_alert=True)
        return
    
    # Используем существующий pending_detection если есть
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="shield_menu")]
    ])
    
    text = (
        "🕵️ <b>WATERMARK-TRAP DETECTOR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📹 <b>Отправьте видео</b> для анализа.\n\n"
        "Система проверит наличие:\n"
        "• 🔍 Скрытых Watermark-Trap\n"
        "• 📊 Невидимых метаданных\n"
        "• 🎯 Следов VIREX обработки"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "need_vip")
async def cb_need_vip(callback: CallbackQuery):
    """Уведомление о необходимости VIP"""
    await callback.answer(
        "🔒 Эта функция доступна только для VIP+\n\n"
        "Используйте /premium для апгрейда!",
        show_alert=True
    )


@dp.callback_query(F.data == "need_premium")
async def cb_need_premium(callback: CallbackQuery):
    """Уведомление о необходимости Premium"""
    await callback.answer(
        "🔒 Эта функция доступна только для Premium\n\n"
        "Используйте /premium для апгрейда!",
        show_alert=True
    )


@dp.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    """ FAQ и помощь """
    if rate_limiter.check_button_spam(callback.from_user.id):
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Сообщить о проблеме", callback_data="report_issue")],
        [InlineKeyboardButton(text="💬 Поддержка @Null7_x", url="https://t.me/Null7_x")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="back_to_start")],
    ])
    
    await callback.message.edit_text(
        get_text(user_id, "help_faq"),
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "report_issue")
async def cb_report_issue(callback: CallbackQuery):
    """ Сообщить о проблеме """
    user_id = callback.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Видео не скачивается", callback_data="issue_download")],
        [InlineKeyboardButton(text="⚠️ Ошибка обработки", callback_data="issue_processing")],
        [InlineKeyboardButton(text="🐛 Другая проблема", callback_data="issue_other")],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="help")],
    ])
    
    await callback.message.edit_text(
        get_text(user_id, "report_issue"),
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("issue_"))
async def cb_issue(callback: CallbackQuery):
    """ Обработка типа проблемы """
    user_id = callback.from_user.id
    issue_type = callback.data.split("_", 1)[1]
    
    issue_names = {
        "download": "Видео не скачивается",
        "processing": "Ошибка обработки",
        "other": "Другая проблема"
    }
    
    # Уведомляем админов
    username = rate_limiter.get_username(user_id) or str(user_id)
    text = (
        f"📩 <b>Новый репорт!</b>\n\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"⚠️ Тип: {issue_names.get(issue_type, issue_type)}\n"
        f"📅 Время: {time_module.strftime('%d.%m.%Y %H:%M')}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except:
            pass
    
    await callback.message.edit_text(
        get_text(user_id, "issue_reported"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_button(user_id, "main_menu"), callback_data="back_to_start")]
        ])
    )
    await callback.answer("✅ Отправлено!", show_alert=True)


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


@dp.callback_query(F.data == "open_admin")
async def cb_open_admin(callback: CallbackQuery):
    """ Открыть админ-панель через кнопку """
    user_id = callback.from_user.id
    
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промо-коды", callback_data="admin_promo"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="⏰ Истекающие", callback_data="admin_expiring"),
            InlineKeyboardButton(text="📥 Очередь", callback_data="admin_queue"),
        ],
        [
            InlineKeyboardButton(text="📈 Источники", callback_data="admin_sources"),
            InlineKeyboardButton(text="💾 Backup", callback_data="admin_backup"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить yt-dlp", callback_data="admin_update_ytdlp"),
            InlineKeyboardButton(text="🏥 Health", callback_data="admin_health"),
        ],
        [
            InlineKeyboardButton(text="📝 Команды", callback_data="admin_commands"),
        ],
    ])
    
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", reply_markup=keyboard)
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

# ══════════════════════════════════════════════════════════════════════════════
# v3.1.0: TEMPLATES MENU
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "templates")
async def cb_templates(callback: CallbackQuery):
    """Показать меню шаблонов"""
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    from config import VIDEO_TEMPLATES
    current = rate_limiter.get_template(user_id)
    plan = rate_limiter.get_plan(user_id)
    
    text = "🎨 <b>Шаблоны видео</b>\n\n"
    text += "Выбери шаблон для обработки видео:\n\n"
    
    # Группируем шаблоны
    buttons = []
    row = []
    
    for tpl_id, tpl in VIDEO_TEMPLATES.items():
        name = tpl["name"]
        is_premium = tpl.get("premium", False)
        is_current = tpl_id == current
        
        # Добавляем метку текущего
        if is_current:
            name = "✅ " + name
        
        # Добавляем замок для премиум шаблонов
        if is_premium and plan not in ["vip", "premium"]:
            name = "🔒 " + name
        
        row.append(InlineKeyboardButton(text=name, callback_data=f"tpl:{tpl_id}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("tpl:"))
async def cb_select_template(callback: CallbackQuery):
    """Выбрать шаблон"""
    user_id = callback.from_user.id
    template_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    from config import VIDEO_TEMPLATES
    
    if template_id not in VIDEO_TEMPLATES:
        await callback.answer("❌ Шаблон не найден")
        return
    
    tpl = VIDEO_TEMPLATES[template_id]
    
    # Проверяем доступ к премиум шаблонам
    if not rate_limiter.can_use_template(user_id, template_id):
        await callback.answer("🔒 Этот шаблон доступен только для VIP/Premium", show_alert=True)
        return
    
    rate_limiter.set_template(user_id, template_id)
    await callback.answer(f"✅ Шаблон {tpl['name']} выбран!")
    
    # Обновляем меню
    current = rate_limiter.get_template(user_id)
    plan = rate_limiter.get_plan(user_id)
    
    text = "🎨 <b>Шаблоны видео</b>\n\n"
    text += f"Текущий шаблон: <b>{tpl['name']}</b>\n"
    text += f"📝 {tpl['description']}\n\n"
    
    buttons = []
    row = []
    
    for tpl_id, t in VIDEO_TEMPLATES.items():
        name = t["name"]
        is_premium = t.get("premium", False)
        is_current = tpl_id == current
        
        if is_current:
            name = "✅ " + name
        
        if is_premium and plan not in ["vip", "premium"]:
            name = "🔒 " + name
        
        row.append(InlineKeyboardButton(text=name, callback_data=f"tpl:{tpl_id}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)

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
        daily_videos=stats.get("daily_videos", 0),
        daily_limit=stats.get("daily_limit", 2),
        weekly_videos=stats.get("weekly_videos", 0),
        weekly_limit=stats.get("weekly_limit", 14),
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 14),
        monthly_remaining=stats.get("monthly_remaining", 14),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ON" if stats["text_overlay"] else "OFF",
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free"),
        total_downloads=stats.get("total_downloads", 0)
    )
    
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "buy_premium")
async def cb_buy_premium(callback: CallbackQuery):
    """ Показать полную информацию о тарифах """
    user_id = callback.from_user.id
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    plan = rate_limiter.get_plan(user_id)
    is_first = rate_limiter.is_first_purchase(user_id)
    lang = rate_limiter.get_language(user_id)
    
    if lang == "en":
        text = """💎 <b>VIREX PRO — Pricing</b>

<b>🆓 FREE</b> — Try it
• 2 videos/day
• Up to 1080p
• 7 basic templates
• Low Anti-Algorithm
• Slow queue

<b>💠 VIP</b> — Work tool
• 15 videos/day
• Up to 4K
• 25+ templates
• Medium Anti-Algorithm
• Priority queue
• Project history (7 days)
• +2 videos per referral

<b>👑 PREMIUM</b> — Unlimited power
• ♾ Unlimited
• Up to 8K
• All 40+ templates
• Hardcore Anti-Algorithm
• Instant render
• 🤖 Auto-Unique Mode
• 🧬 Watermark-Trap
• History 30 days
• 🎖 PREMIUM badge"""
    else:
        text = """💎 <b>VIREX PRO — Тарифы</b>

<b>🆓 FREE</b> — Попробовать
• 2 видео/день
• До 1080p
• 7 базовых шаблонов
• Low Anti-Algorithm
• Медленная очередь
• ❌ Нет авто-режима
• ❌ Нет истории

<b>💠 VIP</b> — Рабочий инструмент
• 15 видео/день
• До 4K
• 25+ шаблонов
• Medium Anti-Algorithm  
• Приоритет в очереди
• ✅ История проектов (7 дней)
• 🎁 +2 видео за реферала

<b>👑 PREMIUM</b> — Безлимитная сила
• ♾ Без лимитов
• До 8K
• Все 40+ шаблонов
• Hardcore Anti-Algorithm
• ⚡ Мгновенный рендер
• 🤖 Auto-Unique Mode
• 🧬 Watermark-Trap
• 📜 История 30 дней
• 🎖 Значок PREMIUM"""
    
    if is_first:
        if lang == "en":
            text += "\n\n🔥 <b>FIRST TIME: -50% on VIP!</b>"
        else:
            text += "\n\n🔥 <b>ВПЕРВЫЕ: -50% на VIP!</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_buy_premium_keyboard(user_id)
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# v3.2.0: PURCHASE HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("buy:"))
async def cb_buy_plan(callback: CallbackQuery):
    """Обработка нажатия на покупку плана"""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    plan_type = parts[1]  # vip or premium
    period = parts[2]     # 1_month, 3_months, 1_year
    
    from config import PLAN_PRICES, PROMO_CONFIG
    
    plan_data = PLAN_PRICES.get(plan_type, {}).get(period)
    if not plan_data:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    
    price = plan_data["price"]
    days = plan_data["days"]
    
    # Применяем скидки
    current_plan = rate_limiter.get_plan(user_id)
    is_first = rate_limiter.is_first_purchase(user_id)
    
    discount_text = ""
    if plan_type == "vip" and is_first:
        price = price * (1 - PROMO_CONFIG["first_vip_discount"])
        discount_text = " (🔥 -50% первый раз)"
    elif plan_type == "premium" and current_plan == "vip":
        discount = PROMO_CONFIG.get("vip_to_premium_discount", 0.20)
        price = price * (1 - discount)
        discount_text = f" (🎁 -{int(discount*100)}% для VIP)"
    
    plan_names = {"vip": "💠 VIP", "premium": "👑 Premium"}
    period_names = {"1_month": "1 месяц", "3_months": "3 месяца", "1_year": "1 год"}
    
    text = (
        f"🛒 <b>Оформление заказа</b>\n\n"
        f"📦 Тариф: <b>{plan_names.get(plan_type)}</b>\n"
        f"⏱ Период: <b>{period_names.get(period)}</b>\n"
        f"💰 Цена: <b>${price:.2f}</b>{discount_text}\n\n"
        f"Для оплаты напишите @Null7_x:\n"
        f"<code>Хочу {plan_type.upper()} на {period_names.get(period)}</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @Null7_x", url="https://t.me/Null7_x")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_premium")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_pack:"))
async def cb_buy_pack(callback: CallbackQuery):
    """Обработка покупки пакета видео (pay-as-you-go)"""
    user_id = callback.from_user.id
    pack_id = callback.data.split(":")[1]
    
    from config import PAY_AS_YOU_GO
    
    pack_data = PAY_AS_YOU_GO.get(pack_id)
    if not pack_data:
        await callback.answer("❌ Пакет не найден", show_alert=True)
        return
    
    text = (
        f"🎯 <b>Покупка пакета видео</b>\n\n"
        f"📦 Пакет: <b>{pack_data['label']}</b>\n"
        f"🎬 Видео: <b>+{pack_data['videos']}</b>\n"
        f"💰 Цена: <b>${pack_data['price']:.2f}</b>\n\n"
        f"💡 Эти видео не сгорают и добавляются к вашему лимиту.\n\n"
        f"Для оплаты напишите @Null7_x:\n"
        f"<code>Хочу пакет +{pack_data['videos']} видео</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @Null7_x", url="https://t.me/Null7_x")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_premium")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
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
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "language")
async def cb_language(callback: CallbackQuery):
    """ Выбор языка """
    user_id = callback.from_user.id
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
        [InlineKeyboardButton(text=get_button(user_id, "back"), callback_data="settings")],
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


@dp.callback_query(F.data == "toggle_night")
async def cb_toggle_night(callback: CallbackQuery):
    """ Переключить ночной режим """
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    new_value = rate_limiter.toggle_night_mode(user_id)
    
    quality = rate_limiter.get_quality(user_id)
    quality_names = {Quality.LOW: "📉 Quick", Quality.MEDIUM: "📊 Medium", Quality.MAX: "📈 Maximum"}
    
    text = get_text(user_id, "settings",
        quality=quality_names.get(quality, quality),
        text_overlay="ON" if rate_limiter.get_text_overlay(user_id) else "OFF"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
    await callback.answer(get_text(user_id, "night_mode_on") if new_value else get_text(user_id, "night_mode_off"))


# ═══════════════════════════════════════════════════════════════════════════════
# v2.9.0: PHOTO HANDLER (WATERMARK)
# ═══════════════════════════════════════════════════════════════════════════════

@dp.message(F.photo)
async def handle_photo(message: Message):
    """ Обработка фото для водяного знака """
    user_id = message.from_user.id
    
    # Получаем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Сохраняем как водяной знак
    rate_limiter.set_watermark(user_id, file_id, "br")
    
    await message.answer(get_text(user_id, "watermark_set"))


# ═══════════════════════════════════════════════════════════════════════════════
# v2.9.0: AUDIO HANDLER (MUSIC OVERLAY)
# ═══════════════════════════════════════════════════════════════════════════════

@dp.message(F.audio | F.voice)
async def handle_audio(message: Message):
    """ Обработка аудио для наложения на видео """
    user_id = message.from_user.id
    
    if message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id
    else:
        return
    
    # Сохраняем как pending audio
    rate_limiter.set_pending_audio(user_id, file_id)
    
    await message.answer(get_text(user_id, "music_received"))


@dp.message(F.video | F.document)
async def handle_video(message: Message):
    user_id = message.from_user.id
    
    # v3.2.0: Проверяем режим детекции Watermark-Trap
    if user_id in pending_detection:
        # Удаляем из ожидания
        pending_detection.pop(user_id, None)
        
        # Обрабатываем видео для детекции
        await handle_detection_video(message)
        return
    
    # v3.3.0: Проверяем режим Safe-Check
    if user_id in pending_safecheck:
        pending_safecheck.pop(user_id, None)
        await handle_safecheck_video(message)
        return
    
    # v3.3.0: Проверяем режим сканирования
    if user_id in pending_scan:
        pending_scan.pop(user_id, None)
        await handle_scan_video(message)
        return
    
    # v2.8.0: Проверка режима техобслуживания
    if is_maintenance_mode() and not is_admin(message.from_user):
        await message.answer(get_text(user_id, "maintenance_mode", minutes=5))
        return
    
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
    
    # v3.0.0: Проверка на режим склейки
    from config import MAX_MERGE_VIDEOS
    merge_queue = rate_limiter.get_merge_queue(user_id)
    if len(merge_queue) > 0 or hasattr(rate_limiter.get_user(user_id), 'merge_mode') and getattr(rate_limiter.get_user(user_id), 'merge_mode', False):
        count = rate_limiter.add_to_merge(user_id, file.file_id)
        if count == -1:
            await message.answer(get_text(user_id, "merge_limit", max=MAX_MERGE_VIDEOS))
        elif count >= 2:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_button(user_id, "merge_now"), callback_data="merge_now")],
                [InlineKeyboardButton(text=get_button(user_id, "merge_clear"), callback_data="merge_clear")],
            ])
            await message.answer(get_text(user_id, "merge_ready", count=count), reply_markup=keyboard)
        else:
            await message.answer(get_text(user_id, "merge_added", count=count, max=MAX_MERGE_VIDEOS))
        return
    
    # v3.0.0: Проверка на режим video info
    user = rate_limiter.get_user(user_id)
    if getattr(user, 'pending_video_info', False):
        user.pending_video_info = False
        # Скачиваем и анализируем видео
        try:
            from ffmpeg_utils import get_temp_dir, get_detailed_video_info, cleanup_file
            temp_path = str(get_temp_dir() / f"info_{user_id}_{uuid.uuid4().hex[:8]}.mp4")
            tg_file = await bot.get_file(file.file_id)
            await bot.download_file(tg_file.file_path, temp_path)
            
            info = await get_detailed_video_info(temp_path)
            
            text = get_text(user_id, "video_info",
                video_codec=info.get("video_codec", "N/A"),
                width=info.get("width", 0),
                height=info.get("height", 0),
                fps=info.get("fps", "N/A"),
                video_bitrate=info.get("video_bitrate", "N/A"),
                duration=info.get("duration", "N/A"),
                audio_codec=info.get("audio_codec", "N/A"),
                audio_bitrate=info.get("audio_bitrate", "N/A"),
                channels=info.get("channels", 0),
                sample_rate=info.get("sample_rate", "N/A"),
                file_size=info.get("file_size", "N/A"),
                format=info.get("format", "N/A"),
            )
            
            cleanup_file(temp_path)
            await message.answer(text)
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)[:100]}")
            return
    
    # v3.0.0: Проверка на режим thumbnail
    if getattr(user, 'pending_thumbnail_time', None):
        thumbnail_time = user.pending_thumbnail_time
        user.pending_thumbnail_time = None
        
        try:
            from ffmpeg_utils import get_temp_dir, extract_thumbnail, cleanup_file
            temp_path = str(get_temp_dir() / f"thumb_src_{user_id}_{uuid.uuid4().hex[:8]}.mp4")
            out_path = str(get_temp_dir() / f"thumb_{user_id}_{uuid.uuid4().hex[:8]}.jpg")
            
            tg_file = await bot.get_file(file.file_id)
            await bot.download_file(tg_file.file_path, temp_path)
            
            success, error = await extract_thumbnail(temp_path, out_path, thumbnail_time)
            
            if success:
                photo = FSInputFile(out_path)
                await message.answer_photo(photo, caption=get_text(user_id, "thumbnail_done"))
                cleanup_file(out_path)
            else:
                await message.answer(f"❌ Ошибка: {error}")
            
            cleanup_file(temp_path)
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)[:100]}")
            return
    
    mode = rate_limiter.get_mode(user_id)
    mode_text = "TikTok MAX" if mode == Mode.TIKTOK else "YouTube Shorts MAX"
    daily_remaining = rate_limiter.get_daily_remaining(user_id)
    stats = rate_limiter.get_stats(user_id)
    plan_names = {"free": "🆓", "vip": "⭐", "premium": "👑"}
    plan_icon = plan_names.get(stats.get("plan", "free"), "🆓")
    
    # Форматируем размер и длительность
    size_str = f"{file_size_mb:.1f} MB"
    duration_str = ""
    if message.video and message.video.duration:
        mins = message.video.duration // 60
        secs = message.video.duration % 60
        duration_str = f" • {mins}:{secs:02d}"
    
    lang = rate_limiter.get_language(user_id)
    if lang == "en":
        text = (
            f"{get_text(user_id, 'video_received')}\n"
            f"📁 <code>{size_str}{duration_str}</code>\n"
            f"🎯 Mode: <b>{mode_text}</b>\n"
            f"📊 Today left: {daily_remaining} {plan_icon}"
        )
    else:
        text = (
            f"{get_text(user_id, 'video_received')}\n"
            f"📁 <code>{size_str}{duration_str}</code>\n"
            f"🎯 Режим: <b>{mode_text}</b>\n"
            f"📊 Сегодня осталось: {daily_remaining} {plan_icon}"
        )
    
    await message.answer(text, reply_markup=get_video_keyboard(short_id, user_id))

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
        elif reason == "daily_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "daily_limit_reached",
                    used=stats.get("daily_videos", 0),
                    limit=stats.get("daily_limit", 2)
                ), 
                show_alert=True
            )
        elif reason == "weekly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "weekly_limit_reached",
                    used=stats.get("weekly_videos", 0),
                    limit=stats.get("weekly_limit", 14)
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
    
    # Лимит задач на одного пользователя (максимум 2)
    user_queue_count = get_user_queue_count(user_id)
    max_per_user = 3 if rate_limiter.get_plan(user_id) in ["vip", "premium"] else 2
    if user_queue_count >= max_per_user:
        await callback.answer(get_text(user_id, "user_queue_limit"), show_alert=True)
        return
    
    rate_limiter.register_request(user_id, file_unique_id)
    rate_limiter.set_processing(user_id, True, file_id)
    
    # Кнопка отмены при обработке
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_processing")]
    ])
    await callback.message.edit_text(get_text(user_id, "processing"), reply_markup=cancel_kb)
    await callback.answer()
    
    try:
        logger.info(f"[PROCESS] Getting file {file_id} for user {user_id}")
        tg_file = await bot.get_file(file_id)
        logger.info(f"[PROCESS] File path: {tg_file.file_path}")
        input_path = str(get_temp_dir() / generate_unique_filename())
        logger.info(f"[PROCESS] Downloading to: {input_path}")
        
        # Retry logic для скачивания (до 3 попыток)
        for attempt in range(3):
            try:
                await bot.download_file(tg_file.file_path, input_path)
                logger.info(f"[PROCESS] Download complete (attempt {attempt + 1})")
                break
            except asyncio.TimeoutError:
                logger.warning(f"[PROCESS] Download timeout, attempt {attempt + 1}/3")
                if attempt == 2:
                    raise
                await asyncio.sleep(2)
        
        # Проверяем что файл скачался корректно
        if not os.path.exists(input_path):
            logger.error(f"[PROCESS] File not found after download: {input_path}")
            rate_limiter.set_processing(user_id, False)
            await callback.message.edit_text(get_text(user_id, "error_download"))
            return
        
        file_size = os.path.getsize(input_path)
        if file_size < 1000:  # Меньше 1KB = битый файл
            logger.error(f"[PROCESS] Downloaded file too small: {file_size} bytes")
            cleanup_file(input_path)
            rate_limiter.set_processing(user_id, False)
            await callback.message.edit_text(get_text(user_id, "error_download"))
            return
        
        logger.info(f"[PROCESS] File downloaded successfully: {file_size} bytes")
        
    except Exception as e:
        logger.error(f"Download error: {type(e).__name__}: {e}")
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(get_text(user_id, "error_download"))
        return
    
    mode = rate_limiter.get_mode(user_id)
    quality = rate_limiter.get_quality(user_id)
    text_overlay = rate_limiter.get_text_overlay(user_id)
    template = rate_limiter.get_template(user_id) or "none"  # v3.1.0: шаблон
    
    # Определяем приоритет на основе плана
    plan = rate_limiter.get_plan(user_id)
    priority = {"free": 0, "vip": 1, "premium": 2}.get(plan, 0)
    
    async def on_complete(success: bool, output_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and output_path:
            try:
                # Увеличиваем счётчик статистики
                rate_limiter.increment_video_count(user_id)
                # v2.8.0: Обновляем streak
                streak, bonus = rate_limiter.update_streak(user_id)
                # Сохраняем в историю
                rate_limiter.add_to_history(user_id, "unique", "file")
                # v2.8.0: Добавляем в лог
                rate_limiter.add_log(user_id, "video_processed", "file")
                
                # v3.3.0: Virex Shield — аналитика и паспорт
                if VIREX_SHIELD_AVAILABLE:
                    try:
                        shield = get_virex_shield()
                        shield.record_processing(user_id, template=template, mode=mode)
                    except Exception as shield_err:
                        logger.warning(f"[SHIELD] Analytics error: {shield_err}")
                
                # v2.9.0: Gamification
                new_level, level_up = rate_limiter.add_points(user_id, 10, "video_processed")
                achievements = rate_limiter.check_achievements(user_id)
                rate_limiter.update_weekly_stats(user_id)
                
                video_file = FSInputFile(output_path)
                
                # Формируем caption с учётом level up и achievements
                caption = get_text(user_id, "done")
                if level_up:
                    caption += f"\n\n🎉 Новый уровень: {new_level}!"
                if achievements:
                    for ach in achievements:
                        caption += f"\n🏆 Достижение: {ach['name']}!"
                
                # Retry для отправки видео (до 3 попыток)
                for send_attempt in range(3):
                    try:
                        await bot.send_video(
                            chat_id=user_id,
                            video=video_file,
                            caption=caption,
                            reply_markup=get_result_keyboard(short_id, user_id)
                        )
                        await callback.message.delete()
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"[SEND] Timeout, attempt {send_attempt + 1}/3")
                        if send_attempt == 2:
                            raise
                        await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Send error: {e}")
                await callback.message.edit_text(get_text(user_id, "error"))
            finally:
                cleanup_file(output_path)
        else:
            await callback.message.edit_text(get_text(user_id, "error"))
    
    # v3.2.0: Проверяем доступ к Watermark-Trap (только Premium)
    enable_watermark_trap = rate_limiter.can_use_watermark_trap(user_id)
    
    task = ProcessingTask(
        user_id=user_id,
        input_path=input_path,
        mode=mode,
        callback=on_complete,
        quality=quality,
        text_overlay=text_overlay,
        priority=priority,
        template=template,
        enable_watermark_trap=enable_watermark_trap
    )
    
    logger.info(f"[PROCESS] Adding task to queue for user {user_id}")
    queued, position = await add_to_queue(task)
    logger.info(f"[PROCESS] Queue result: queued={queued}, position={position}")
    
    if not queued:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(input_path)
        await callback.message.edit_text(get_text(user_id, "queue_full"))
    elif position > 1:
        # Показываем позицию в очереди если не первый
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_processing")]
        ])
        await callback.message.edit_text(
            f"{get_text(user_id, 'queue_position', position=position)}\n{get_text(user_id, 'processing')}",
            reply_markup=cancel_kb
        )

# ══════════════════════════════════════════════════════════════════════════════
# URL VIDEO DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:'
    r'tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
    r'youtube\.com(?:/shorts|/watch)?|youtu\.be|'
    r'instagram\.com(?:/reel|/p)?|'
    r'vk\.com(?:/clip|/video)?|'
    r'twitter\.com|x\.com|'
    r'douyin\.com|'
    r'bilibili\.com|b23\.tv|'
    r'weibo\.com|'
    r'youku\.com|v\.youku\.com|'
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

async def download_youtube_video(url: str, output_path: str) -> bool:
    """Скачать YouTube видео через Invidious API или публичные прокси"""
    try:
        import aiohttp
        import re
        
        # Извлекаем video_id
        video_id = None
        patterns = [
            r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        
        if not video_id:
            logger.warning(f"[YouTube] Could not extract video ID from {url}")
            return False
        
        logger.info(f"[YouTube] Extracted video_id: {video_id}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with aiohttp.ClientSession() as session:
            video_url = None
            
            # 1. Пробуем Invidious инстансы (открытый YouTube прокси)
            invidious_instances = [
                "https://vid.puffyan.us",
                "https://invidious.snopyta.org",
                "https://yewtu.be",
                "https://invidious.kavin.rocks",
                "https://inv.riverside.rocks",
                "https://invidious.namazso.eu",
            ]
            
            for instance in invidious_instances:
                try:
                    api_url = f"{instance}/api/v1/videos/{video_id}"
                    async with session.get(api_url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # Ищем MP4 формат
                            formats = data.get('formatStreams', []) + data.get('adaptiveFormats', [])
                            for fmt in formats:
                                if fmt.get('type', '').startswith('video/mp4') and fmt.get('url'):
                                    # Предпочитаем 720p или ниже
                                    quality = fmt.get('qualityLabel', '')
                                    if '720' in quality or '480' in quality or '360' in quality:
                                        video_url = fmt['url']
                                        logger.info(f"[YouTube] Invidious ({instance}) success: {quality}")
                                        break
                            if video_url:
                                break
                            # Если не нашли нужное качество, берём первый mp4
                            for fmt in formats:
                                if fmt.get('type', '').startswith('video/mp4') and fmt.get('url'):
                                    video_url = fmt['url']
                                    logger.info(f"[YouTube] Invidious ({instance}) success")
                                    break
                            if video_url:
                                break
                except Exception as e:
                    logger.debug(f"[YouTube] Invidious {instance} failed: {e}")
                    continue
            
            # 2. Пробуем Piped API (другой открытый прокси)
            if not video_url:
                piped_instances = [
                    "https://pipedapi.kavin.rocks",
                    "https://api.piped.yt",
                    "https://pipedapi.tokhmi.xyz",
                ]
                for instance in piped_instances:
                    try:
                        api_url = f"{instance}/streams/{video_id}"
                        async with session.get(api_url, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                # Пробуем videoStreams
                                streams = data.get('videoStreams', [])
                                for stream in streams:
                                    if stream.get('format') == 'MPEG_4' and stream.get('videoOnly') == False:
                                        video_url = stream.get('url')
                                        logger.info(f"[YouTube] Piped ({instance}) success")
                                        break
                                if video_url:
                                    break
                    except Exception as e:
                        logger.debug(f"[YouTube] Piped {instance} failed: {e}")
                        continue
            
            if not video_url:
                logger.warning("[YouTube] All APIs failed, falling back to yt-dlp")
                return False
            
            # Скачиваем видео
            logger.info(f"[YouTube] Downloading...")
            async with session.get(video_url, headers=headers, timeout=180, allow_redirects=True) as video_resp:
                if video_resp.status != 200:
                    logger.error(f"[YouTube] Download failed: HTTP {video_resp.status}")
                    return False
                
                with open(output_path, 'wb') as f:
                    while True:
                        chunk = await video_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                logger.info(f"[YouTube] Download successful: {os.path.getsize(output_path)} bytes")
                return True
            return False
            
    except Exception as e:
        logger.error(f"[YouTube] API error: {e}")
        return False

async def download_video_from_url(url: str, output_path: str) -> bool:
    """Скачать видео по ссылке без водяного знака используя yt-dlp или специальные методы"""
    try:
        # Специальная обработка TikTok/Douyin - без водяного знака
        if any(domain in url.lower() for domain in ['tiktok.com', 'douyin.com']):
            result = await download_tiktok_no_watermark(url, output_path)
            if result:
                return True
            # Fallback на yt-dlp если не получилось
        
        # Специальная обработка YouTube
        if any(d in url.lower() for d in ['youtube.com', 'youtu.be']):
            result = await download_youtube_video(url, output_path)
            if result:
                return True
            # Fallback на yt-dlp если API не сработали
        
        # Специальная обработка Kuaishou - с fallback на yt-dlp
        if any(domain in url.lower() for domain in ['kuaishou.com', 'gifshow.com']):
            result = await download_kuaishou_video(url, output_path)
            if result:
                return True
            # Fallback на yt-dlp
        
        # Специальная обработка Instagram
        if 'instagram.com' in url.lower():
            result = await download_instagram_video(url, output_path)
            if result:
                return True
            # Fallback на yt-dlp
        
        import yt_dlp
        
        # Определяем, YouTube ли это
        is_youtube = any(d in url.lower() for d in ['youtube.com', 'youtu.be'])
        
        ydl_opts = {
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
            'socket_timeout': 60,
            'retries': 5,
            'fragment_retries': 5,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded', 'android'],
                }
            },
            # Используем cookies из браузера если доступны
            'cookiesfrombrowser': ('chrome',),
            'age_limit': None,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'nocheckcertificate': True,
        }
        
        # Дополнительные опции для YouTube
        if is_youtube:
            ydl_opts['format'] = 'best[ext=mp4][height<=1080]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            ydl_opts['merge_output_format'] = 'mp4'
            # tv_embedded работает лучше для обхода блокировки
            ydl_opts['extractor_args']['youtube']['player_client'] = ['tv_embedded']
        
        loop = asyncio.get_event_loop()
        
        def download():
            try:
                # Сначала пробуем без cookies
                ydl_opts_simple = ydl_opts.copy()
                ydl_opts_simple.pop('cookiesfrombrowser', None)
                with yt_dlp.YoutubeDL(ydl_opts_simple) as ydl:
                    ydl.download([url])
            except Exception as e:
                logger.warning(f"[YT-DLP] First attempt failed: {e}")
                # Пробуем с другими настройками
                ydl_opts_simple['extractor_args'] = {
                    'youtube': {'player_client': ['android']},
                }
                ydl_opts_simple['http_headers']['User-Agent'] = 'com.google.android.youtube/17.31.35 (Linux; U; Android 11) gzip'
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_simple) as ydl:
                        ydl.download([url])
                except Exception as e2:
                    logger.error(f"[YT-DLP] Second attempt failed: {e2}")
                    raise e2
        
        await loop.run_in_executor(None, download)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        logger.error(f"[YT-DLP] Error downloading {url}: {e}")
        return False


async def download_instagram_video(url: str, output_path: str) -> bool:
    """Скачать Instagram Reels/Post видео"""
    try:
        import aiohttp
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
        }
        
        # Используем публичные API
        api_endpoints = [
            f"https://api.savefrom.biz/api/convert?url={url}",
            f"https://igdownloader.app/api/ajaxSearch",
        ]
        
        async with aiohttp.ClientSession() as session:
            video_url = None
            
            # Пробуем разные API
            for i, api_url in enumerate(api_endpoints):
                try:
                    if i == 1:  # igdownloader.app
                        async with session.post(api_url, data={'q': url}, headers=headers, timeout=15) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                # Ищем URL видео в HTML ответе
                                import re
                                match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', text)
                                if match:
                                    video_url = match.group(1)
                                    break
                    else:
                        async with session.get(api_url, headers=headers, timeout=15) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if 'url' in data:
                                    video_url = data['url']
                                    break
                except Exception as e:
                    logger.debug(f"[Instagram] API {i} failed: {e}")
                    continue
            
            if not video_url:
                logger.warning("[Instagram] No video URL found via APIs")
                return False
            
            logger.info(f"[Instagram] Found video URL")
            
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
        logger.error(f"[Instagram] Error: {e}")
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
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        async with aiohttp.ClientSession() as session:
            # 1. Пробуем через публичный API
            try:
                api_url = f"https://api.douyin.wtf/api?url={url}"
                async with session.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        video_url = data.get('nwm_video_url') or data.get('video_url')
                        if video_url:
                            logger.info(f"[Kuaishou] API found video URL")
                            # Скачиваем
                            async with session.get(video_url, headers=headers, timeout=120) as video_resp:
                                if video_resp.status == 200:
                                    with open(output_path, 'wb') as f:
                                        while True:
                                            chunk = await video_resp.content.read(8192)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                                        return True
            except Exception as e:
                logger.debug(f"[Kuaishou] API failed: {e}")
            
            # 2. Пробуем через мобильный User-Agent с редиректами
            try:
                async with session.get(url, headers=headers, allow_redirects=True, timeout=30) as resp:
                    final_url = str(resp.url)
                    html = await resp.text()
                    logger.info(f"[Kuaishou] Final URL: {final_url[:80]}...")
                    
                    # Ищем URL видео в разных форматах
                    video_patterns = [
                        r'"srcNoMark"\s*:\s*"([^"]+)"',
                        r'"photoUrl"\s*:\s*"([^"]+)"',
                        r'"playUrl"\s*:\s*"([^"]+)"',
                        r'"videoUrl"\s*:\s*"([^"]+)"',
                        r'"url"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
                        r'video[^>]*src="([^"]+\.mp4[^"]*)"',
                        r'"video_url"\s*:\s*"([^"]+)"',
                        r'playAddr["\s:]+["\'](https?://[^"\']+)["\']',
                    ]
                    
                    video_url = None
                    for pattern in video_patterns:
                        match = re.search(pattern, html)
                        if match:
                            video_url = match.group(1)
                            video_url = video_url.encode().decode('unicode_escape')
                            video_url = video_url.replace('\\u002F', '/').replace('\\/', '/')
                            if video_url.startswith('http'):
                                logger.info(f"[Kuaishou] Found via pattern: {pattern[:30]}...")
                                break
                            video_url = None
                    
                    if video_url:
                        async with session.get(video_url, headers=headers, timeout=120) as video_resp:
                            if video_resp.status == 200:
                                with open(output_path, 'wb') as f:
                                    while True:
                                        chunk = await video_resp.content.read(8192)
                                        if not chunk:
                                            break
                                        f.write(chunk)
                                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                                    return True
            except Exception as e:
                logger.debug(f"[Kuaishou] Direct fetch failed: {e}")
            
            logger.error("[Kuaishou] All methods failed")
            return False
            
    except Exception as e:
        logger.error(f"[Kuaishou] Error: {e}")
        return False

def get_url_keyboard(short_id: str, user_id: int) -> InlineKeyboardMarkup:
    """ Клавиатура для ссылки: уникализировать или только скачать """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_button(user_id, "uniqualize"), callback_data=f"url_process:{short_id}")],
        [InlineKeyboardButton(text=get_button(user_id, "download_only"), callback_data=f"url_download:{short_id}")],
    ])

@dp.message(F.text & ~F.text.startswith("/"))
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
    
    # v2.8.0: Проверка режима техобслуживания
    if is_maintenance_mode() and not is_admin(message.from_user):
        await message.answer(get_text(user_id, "maintenance_mode", minutes=5))
        return
    
    if rate_limiter.is_processing(user_id):
        await message.answer(get_text(user_id, "duplicate"))
        return
    
    # Сохраняем URL и показываем кнопки выбора
    short_id = generate_short_id()
    pending_urls[short_id] = {
        "user_id": user_id,
        "url": url,
        "created_at": time_module.time()
    }
    
    await message.answer(
        get_text(user_id, "url_received"),
        reply_markup=get_url_keyboard(short_id, user_id)
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
        await callback.answer(get_text(user_id, "duplicate"))
        return
    
    # Проверка лимита
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        if reason == "daily_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "daily_limit_reached",
                    used=stats.get("daily_videos", 0),
                    limit=stats.get("daily_limit", 2)
                ),
                show_alert=True
            )
        elif reason == "weekly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "weekly_limit_reached",
                    used=stats.get("weekly_videos", 0),
                    limit=stats.get("weekly_limit", 14)
                ),
                show_alert=True
            )
        elif reason == "soft_block":
            await callback.answer(get_text(user_id, "soft_block"), show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(get_text(user_id, "cooldown", seconds=seconds), show_alert=True)
        return
    
    await callback.message.edit_text(get_text(user_id, "downloading"))
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
            await callback.message.edit_text(get_text(user_id, "error_download"))
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
        await callback.message.edit_text(get_text(user_id, "file_too_large"))
        return
    
    try:
        # Увеличиваем счётчик скачиваний
        rate_limiter.increment_download_count(user_id)
        rate_limiter.increment_video_count(user_id)
        
        video_file = FSInputFile(output_path)
        await bot.send_video(
            chat_id=user_id,
            video=video_file,
            caption=get_text(user_id, "downloaded")
        )
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Send error: {e}")
        await callback.message.edit_text(get_text(user_id, "error"))
    
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
        await callback.answer(get_text(user_id, "error"))
        return
    
    url_data = pending_urls[short_id]
    url = url_data["url"]
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(get_text(user_id, "duplicate"))
        return
    
    # Проверка лимита
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        if reason == "daily_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "daily_limit_reached",
                    used=stats.get("daily_videos", 0),
                    limit=stats.get("daily_limit", 2)
                ),
                show_alert=True
            )
        elif reason == "weekly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                get_text(user_id, "weekly_limit_reached",
                    used=stats.get("weekly_videos", 0),
                    limit=stats.get("weekly_limit", 14)
                ),
                show_alert=True
            )
        elif reason == "soft_block":
            await callback.answer(get_text(user_id, "soft_block"), show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(get_text(user_id, "cooldown", seconds=seconds), show_alert=True)
        return
    
    await callback.message.edit_text(get_text(user_id, "downloading"))
    await callback.answer()
    
    rate_limiter.set_processing(user_id, True)
    
    output_path = str(get_temp_dir() / generate_unique_filename())
    
    # Скачиваем видео
    success = await download_video_from_url(url, output_path)
    
    if not success or not os.path.exists(output_path):
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(get_text(user_id, "error_download"))
        pending_urls.pop(short_id, None)
        return
    
    # Проверяем размер файла
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        cleanup_file(output_path)
        rate_limiter.set_processing(user_id, False)
        await callback.message.edit_text(get_text(user_id, "file_too_large"))
        pending_urls.pop(short_id, None)
        return
    
    # Получаем режим и начинаем обработку
    mode = rate_limiter.get_mode(user_id)
    quality = rate_limiter.get_quality(user_id)
    text_overlay = rate_limiter.get_text_overlay(user_id)
    template = rate_limiter.get_template(user_id) or "none"  # v3.1.0: шаблон
    
    # Определяем приоритет на основе плана
    plan = rate_limiter.get_plan(user_id)
    priority = {"free": 0, "vip": 1, "premium": 2}.get(plan, 0)
    
    # Кнопка отмены
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_processing")]
    ])
    await callback.message.edit_text(get_text(user_id, "processing"), reply_markup=cancel_kb)
    
    # Сохраняем message для callback
    status_message = callback.message
    
    # Определяем источник по URL
    url_source = "url"
    if "tiktok" in url:
        url_source = "tiktok"
    elif "youtube" in url or "youtu.be" in url:
        url_source = "youtube"
    elif "instagram" in url:
        url_source = "instagram"
    elif "douyin" in url or "bilibili" in url or "kuaishou" in url or "xiaohongshu" in url:
        url_source = "chinese"
    
    async def on_complete(success: bool, result_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and result_path:
            try:
                rate_limiter.increment_video_count(user_id)
                rate_limiter.add_to_history(user_id, "unique", url_source)
                
                # v2.9.0: Gamification
                new_level, level_up = rate_limiter.add_points(user_id, 10, "video_processed")
                achievements = rate_limiter.check_achievements(user_id)
                rate_limiter.update_weekly_stats(user_id)
                
                video_file = FSInputFile(result_path)
                new_short_id = generate_short_id()
                
                # Формируем caption с учётом level up и achievements
                caption = get_text(user_id, "done")
                if level_up:
                    caption += f"\n\n🎉 Новый уровень: {new_level}!"
                if achievements:
                    for ach in achievements:
                        caption += f"\n🏆 Достижение: {ach['name']}!"
                
                # Retry для отправки видео (до 3 попыток)
                for send_attempt in range(3):
                    try:
                        await bot.send_video(
                            chat_id=user_id,
                            video=video_file,
                            caption=caption,
                            reply_markup=get_result_keyboard(new_short_id, user_id)
                        )
                        await status_message.delete()
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"[SEND] Timeout, attempt {send_attempt + 1}/3")
                        if send_attempt == 2:
                            raise
                        await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Send error: {e}")
                await status_message.edit_text(get_text(user_id, "error"))
            finally:
                cleanup_file(result_path)
        else:
            await status_message.edit_text(get_text(user_id, "error"))
        
        cleanup_file(output_path)
        pending_urls.pop(short_id, None)
    
    # v3.2.0: Проверяем доступ к Watermark-Trap (только Premium)
    enable_watermark_trap = rate_limiter.can_use_watermark_trap(user_id)
    
    task = ProcessingTask(
        user_id=user_id,
        input_path=output_path,
        mode=mode,
        callback=on_complete,
        quality=quality,
        text_overlay=text_overlay,
        priority=priority,
        template=template,
        enable_watermark_trap=enable_watermark_trap
    )
    
    queued, position = await add_to_queue(task)
    if not queued:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(output_path)
        await callback.message.edit_text(get_text(user_id, "queue_full"))
        pending_urls.pop(short_id, None)
    elif position > 1:
        # Показываем позицию в очереди если не первый
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_processing")]
        ])
        await callback.message.edit_text(
            f"{get_text(user_id, 'queue_position', position=position)}\n{get_text(user_id, 'processing')}",
            reply_markup=cancel_kb
        )

@dp.message()
async def handle_other(message: Message):
    pass

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def on_startup():
    # Диагностика FFmpeg
    import shutil
    logger.info(f"[FFMPEG] FFMPEG_PATH = {FFMPEG_PATH}")
    logger.info(f"[FFMPEG] FFPROBE_PATH = {FFPROBE_PATH}")
    logger.info(f"[FFMPEG] which ffmpeg = {shutil.which('ffmpeg')}")
    logger.info(f"[FFMPEG] which ffprobe = {shutil.which('ffprobe')}")
    logger.info(f"[FFMPEG] OS = {os.name}, Platform = {sys.platform}")
    
    # Автоматическое обновление yt-dlp при старте (в фоне)
    asyncio.create_task(auto_update_ytdlp())
    await start_workers()
    cleanup_old_files()
    cleanup_short_id_map()
    logger.info("Virex started")


async def auto_update_ytdlp():
    """ Автоматическое обновление yt-dlp в фоне """
    try:
        import subprocess
        loop = asyncio.get_event_loop()
        
        def update():
            result = subprocess.run(
                ["pip", "install", "-U", "yt-dlp"],
                capture_output=True, text=True, timeout=120
            )
            return result.returncode == 0
        
        success = await loop.run_in_executor(None, update)
        if success:
            logger.info("[YT-DLP] Auto-updated successfully")
        else:
            logger.warning("[YT-DLP] Auto-update failed")
    except Exception as e:
        logger.error(f"[YT-DLP] Auto-update error: {e}")

async def periodic_cleanup():
    """ Периодическая очистка """
    while True:
        await asyncio.sleep(600)  # каждые 10 минут
        cleanup_short_id_map()
        cleanup_old_files()


async def periodic_expiry_check():
    """ Проверка истекающих подписок раз в день """
    while True:
        await asyncio.sleep(86400)  # раз в 24 часа
        try:
            await check_expiring_subscriptions()
        except Exception as e:
            logger.error(f"Expiry check error: {e}")


async def send_daily_stats():
    """ Отправить ежедневную статистику админам """
    try:
        stats = rate_limiter.get_global_stats()
        daily = rate_limiter.get_daily_stats()
        
        text = (
            f"📊 <b>Ежедневный отчёт</b>\n\n"
            f"📅 За сегодня:\n"
            f"• Новых пользователей: <b>{daily.get('new_users', 0)}</b>\n"
            f"• Обработано видео: <b>{daily.get('videos_today', 0)}</b>\n"
            f"• Скачиваний: <b>{daily.get('downloads_today', 0)}</b>\n\n"
            f"📈 Всего:\n"
            f"• Пользователей: <b>{stats['total_users']}</b>\n"
            f"• VIP: <b>{stats['vip_users']}</b>\n"
            f"• Premium: <b>{stats['premium_users']}</b>\n"
            f"• Видео обработано: <b>{stats['total_videos']}</b>"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except:
                pass
    except Exception as e:
        logger.error(f"Daily stats error: {e}")


async def periodic_daily_stats():
    """ Отправка ежедневной статистики в 00:00 """
    import datetime
    while True:
        # Вычисляем время до полуночи
        now = datetime.datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        
        await asyncio.sleep(seconds_until_midnight)
        await send_daily_stats()
        rate_limiter.reset_daily_stats()


async def periodic_autosave():
    """ Автосохранение данных каждые 5 минут """
    while True:
        await asyncio.sleep(300)  # 5 минут
        try:
            rate_limiter.save_data()
            logger.debug("Autosave completed")
        except Exception as e:
            logger.error(f"Autosave error: {e}")


async def on_shutdown():
    """ Graceful shutdown """
    logger.info("Shutting down...")
    rate_limiter.save_data()
    cleanup_old_files()
    logger.info("Data saved, shutdown complete")

async def main():
    await on_startup()
    asyncio.create_task(periodic_cleanup())
    asyncio.create_task(periodic_expiry_check())
    asyncio.create_task(periodic_daily_stats())
    asyncio.create_task(periodic_autosave())
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
