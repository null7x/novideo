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
    ADMIN_IDS, PLAN_LIMITS
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

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def get_start_keyboard(mode: str) -> InlineKeyboardMarkup:
    if mode == Mode.TIKTOK:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS["tiktok_on"], callback_data="noop")],
            [InlineKeyboardButton(text=BUTTONS["switch_youtube"], callback_data="mode_youtube")],
            [InlineKeyboardButton(text=BUTTONS["settings"], callback_data="settings")],
            [InlineKeyboardButton(text=BUTTONS["how_it_works"], callback_data="how_it_works")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS["youtube_on"], callback_data="noop")],
            [InlineKeyboardButton(text=BUTTONS["switch_tiktok"], callback_data="mode_tiktok")],
            [InlineKeyboardButton(text=BUTTONS["settings"], callback_data="settings")],
            [InlineKeyboardButton(text=BUTTONS["how_it_works"], callback_data="how_it_works")],
        ])

def get_video_keyboard(short_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["uniqualize"], callback_data=f"process:{short_id}")],
    ])

def get_result_keyboard(short_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["again"], callback_data=f"process:{short_id}")],
        [InlineKeyboardButton(text=BUTTONS["change_mode"], callback_data="change_mode")],
    ])

def get_how_it_works_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_start")],
    ])

def get_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """ Клавиатура настроек """
    quality = rate_limiter.get_quality(user_id)
    text_on = rate_limiter.get_text_overlay(user_id)
    
    # Кнопки качества с отметкой текущего
    q_low = "✅ " + BUTTONS["quality_low"] if quality == Quality.LOW else BUTTONS["quality_low"]
    q_med = "✅ " + BUTTONS["quality_medium"] if quality == Quality.MEDIUM else BUTTONS["quality_medium"]
    q_max = "✅ " + BUTTONS["quality_max"] if quality == Quality.MAX else BUTTONS["quality_max"]
    
    text_btn = BUTTONS["text_on"] if text_on else BUTTONS["text_off"]
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=q_low, callback_data="quality_low"),
            InlineKeyboardButton(text=q_med, callback_data="quality_medium"),
            InlineKeyboardButton(text=q_max, callback_data="quality_max"),
        ],
        [InlineKeyboardButton(text=text_btn, callback_data="toggle_text")],
        [InlineKeyboardButton(text=BUTTONS["stats"], callback_data="stats")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_start")],
    ])

def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="settings")],
    ])

# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    mode = rate_limiter.get_mode(user_id)
    
    # Сохраняем username
    if message.from_user.username:
        rate_limiter.set_username(user_id, message.from_user.username)
    
    text = TEXTS["start"] if mode == Mode.TIKTOK else TEXTS["start_youtube"]
    await message.answer(text, reply_markup=get_start_keyboard(mode))

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
        last_time = TEXTS["stats_never"]
    
    # Названия режимов и качества
    mode_names = {Mode.TIKTOK: "TikTok MAX", Mode.YOUTUBE: "YouTube Shorts"}
    quality_names = {Quality.LOW: "📉 Быстрое", Quality.MEDIUM: "📊 Среднее", Quality.MAX: "📈 Максимум"}
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = TEXTS["stats"].format(
        total_videos=stats["total_videos"],
        today_videos=stats["today_videos"],
        monthly_videos=stats.get("monthly_videos", 0),
        monthly_limit=stats.get("monthly_limit", 3),
        monthly_remaining=stats.get("monthly_remaining", 3),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ВКЛ" if stats["text_overlay"] else "ВЫКЛ",
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free")
    )
    
    await message.answer(text, reply_markup=get_stats_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("vip"))
async def cmd_vip(message: Message):
    """ /vip @username или /vip user_id — выдать VIP пользователю """
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /vip @username или /vip user_id")
        return
    
    target = args[1]
    
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
    
    rate_limiter.set_plan(target_id, "vip")
    await message.answer(TEXTS.get("vip_granted", "✅ VIP выдан").format(user_id=target_id, username=username))

@dp.message(Command("premium"))
async def cmd_premium(message: Message):
    """ /premium @username или /premium user_id — выдать Premium пользователю """
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /premium @username или /premium user_id")
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
    
    rate_limiter.set_plan(target_id, "premium")
    await message.answer(TEXTS.get("premium_granted", "✅ Premium выдан").format(user_id=target_id, username=username))

@dp.message(Command("removeplan"))
async def cmd_removeplan(message: Message):
    """ /removeplan @username или /removeplan user_id — убрать план (сделать free) """
    if message.from_user.id not in ADMIN_IDS:
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
    await message.answer(TEXTS.get("plan_removed", "✅ План сброшен").format(user_id=target_id))

@dp.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    """ /userinfo user_id — информация о пользователе """
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(TEXTS.get("not_admin", "⛔ Нет доступа"))
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /userinfo user_id")
        return
    
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer(TEXTS.get("invalid_user_id", "⚠️ Неверный ID"))
        return
    
    stats = rate_limiter.get_stats(target_id)
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = TEXTS.get("user_info", """👤 <b>Пользователь</b> {user_id}
📋 План: {plan}
📊 Видео за неделю: {weekly_videos}/{weekly_limit}
📈 Всего видео: {total_videos}""").format(
        user_id=target_id,
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free"),
        weekly_videos=stats.get("weekly_videos", 0),
        weekly_limit=stats.get("weekly_limit", 3),
        total_videos=stats.get("total_videos", 0)
    )
    await message.answer(text)

@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    """ /myid — показать свой ID """
    await message.answer(f"🆔 Ваш ID: <code>{message.from_user.id}</code>")

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
        TEXTS["start"],
        reply_markup=get_start_keyboard(Mode.TIKTOK)
    )
    await callback.answer(TEXTS["mode_tiktok"])

@dp.callback_query(F.data == "mode_youtube")
async def cb_mode_youtube(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    rate_limiter.set_mode(user_id, Mode.YOUTUBE)
    await callback.message.edit_text(
        TEXTS["start_youtube"],
        reply_markup=get_start_keyboard(Mode.YOUTUBE)
    )
    await callback.answer(TEXTS["mode_youtube"])

@dp.callback_query(F.data == "change_mode")
async def cb_change_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    current_mode = rate_limiter.get_mode(user_id)
    new_mode = Mode.YOUTUBE if current_mode == Mode.TIKTOK else Mode.TIKTOK
    rate_limiter.set_mode(user_id, new_mode)
    
    text = TEXTS["start"] if new_mode == Mode.TIKTOK else TEXTS["start_youtube"]
    await callback.message.edit_text(text, reply_markup=get_start_keyboard(new_mode))
    
    answer_text = TEXTS["mode_tiktok"] if new_mode == Mode.TIKTOK else TEXTS["mode_youtube"]
    await callback.answer(answer_text)

@dp.callback_query(F.data == "how_it_works")
async def cb_how_it_works(callback: CallbackQuery):
    if rate_limiter.check_button_spam(callback.from_user.id):
        await callback.answer()
        return
    
    await callback.message.edit_text(
        TEXTS["how_it_works"],
        reply_markup=get_how_it_works_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def cb_back_to_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    mode = rate_limiter.get_mode(user_id)
    text = TEXTS["start"] if mode == Mode.TIKTOK else TEXTS["start_youtube"]
    await callback.message.edit_text(text, reply_markup=get_start_keyboard(mode))
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
    
    quality_names = {Quality.LOW: "📉 Быстрое", Quality.MEDIUM: "📊 Среднее", Quality.MAX: "📈 Максимум"}
    
    text = TEXTS["settings"].format(
        quality=quality_names.get(quality, quality),
        text_overlay="ВКЛ" if text_on else "ВЫКЛ"
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
        last_time = TEXTS["stats_never"]
    
    mode_names = {Mode.TIKTOK: "TikTok MAX", Mode.YOUTUBE: "YouTube Shorts"}
    quality_names = {Quality.LOW: "📉 Быстрое", Quality.MEDIUM: "📊 Среднее", Quality.MAX: "📈 Максимум"}
    plan_names = {"free": "🆓 Free", "vip": "⭐ VIP", "premium": "👑 Premium"}
    
    text = TEXTS["stats"].format(
        total_videos=stats["total_videos"],
        today_videos=stats["today_videos"],
        weekly_videos=stats.get("weekly_videos", 0),
        weekly_limit=stats.get("weekly_limit", 3),
        weekly_remaining=stats.get("weekly_remaining", 3),
        last_time=last_time,
        mode=mode_names.get(stats["mode"], stats["mode"]),
        quality=quality_names.get(stats["quality"], stats["quality"]),
        text_overlay="ВКЛ" if stats["text_overlay"] else "ВЫКЛ",
        plan=plan_names.get(stats.get("plan", "free"), "🆓 Free")
    )
    
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
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
        quality_names = {Quality.LOW: "📉 Быстрое", Quality.MEDIUM: "📊 Среднее", Quality.MAX: "📈 Максимум"}
        
        # Обновляем клавиатуру
        text_on = rate_limiter.get_text_overlay(user_id)
        text = TEXTS["settings"].format(
            quality=quality_names.get(new_quality, new_quality),
            text_overlay="ВКЛ" if text_on else "ВЫКЛ"
        )
        await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
        await callback.answer(TEXTS["quality_changed"].format(quality=quality_names.get(new_quality)))
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
    quality_names = {Quality.LOW: "📉 Быстрое", Quality.MEDIUM: "📊 Среднее", Quality.MAX: "📈 Максимум"}
    
    text = TEXTS["settings"].format(
        quality=quality_names.get(quality, quality),
        text_overlay="ВКЛ" if new_value else "ВЫКЛ"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard(user_id))
    await callback.answer(TEXTS["text_on"] if new_value else TEXTS["text_off"])

@dp.message(F.video | F.document)
async def handle_video(message: Message):
    user_id = message.from_user.id
    
    if rate_limiter.is_processing(user_id):
        await message.answer(TEXTS["duplicate"])
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
        await message.answer(TEXTS["invalid_format"])
        return
    
    file_size_mb = (file.file_size or 0) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(TEXTS["file_too_large"])
        return
    
    # Проверка длительности видео (только для video, не document)
    if message.video and message.video.duration:
        if message.video.duration > MAX_VIDEO_DURATION_SECONDS:
            await message.answer(TEXTS["video_too_long"])
            return
    
    file_unique_id = file.file_unique_id
    
    if rate_limiter.check_duplicate_file(user_id, file_unique_id):
        await message.answer(TEXTS["duplicate"])
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
    weekly_remaining = rate_limiter.get_weekly_remaining(user_id)
    stats = rate_limiter.get_stats(user_id)
    plan_names = {"free": "🆓", "vip": "⭐", "premium": "👑"}
    plan_icon = plan_names.get(stats.get("plan", "free"), "🆓")
    
    await message.answer(
        f"{TEXTS['video_received']}\n🎯 Режим: <b>{mode_text}</b>\n📊 Осталось на неделю: {weekly_remaining} видео {plan_icon}",
        reply_markup=get_video_keyboard(short_id)
    )

@dp.callback_query(F.data.startswith("process:"))
async def cb_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    short_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(TEXTS["duplicate"])
        return
    
    if short_id not in pending_files:
        await callback.answer("⚠️ Отправь видео заново")
        return
    
    file_data = pending_files[short_id]
    file_id = file_data["file_id"]
    file_unique_id = file_data["file_unique_id"]
    
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    
    if not can_process:
        if reason == "soft_block":
            await callback.answer(TEXTS["soft_block"], show_alert=True)
        elif reason == "weekly_limit":
            stats = rate_limiter.get_stats(user_id)
            await callback.answer(
                TEXTS.get("weekly_limit_reached", "⚠️ Лимит на неделю исчерпан ({used}/{limit})").format(
                    used=stats.get("weekly_videos", 0),
                    limit=stats.get("weekly_limit", 3)
                ), 
                show_alert=True
            )
        elif reason == "rate_limit":
            await callback.answer(TEXTS["rate_limit"], show_alert=True)
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await callback.answer(TEXTS["cooldown"].format(seconds=seconds), show_alert=True)
        return
    
    if get_queue_size() >= 8:
        await callback.answer(TEXTS["queue_full"], show_alert=True)
        return
    
    rate_limiter.register_request(user_id, file_unique_id)
    rate_limiter.set_processing(user_id, True, file_id)
    
    await callback.message.edit_text(TEXTS["processing"])
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
                    caption=TEXTS["done"],
                    reply_markup=get_result_keyboard(short_id)
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
    r'twitter\.com|x\.com'
    r')[^\s]+'
)

async def download_video_from_url(url: str, output_path: str) -> bool:
    """Скачать видео по ссылке используя yt-dlp"""
    try:
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

@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
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
    
    # Проверка недельного лимита ПЕРЕД скачиванием
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    if not can_process:
        if reason == "weekly_limit":
            stats = rate_limiter.get_stats(user_id)
            await message.answer(
                TEXTS.get("weekly_limit_reached", "⚠️ Лимит на неделю исчерпан ({used}/{limit})").format(
                    used=stats.get("weekly_videos", 0),
                    limit=stats.get("weekly_limit", 3)
                )
            )
        elif reason == "soft_block":
            await message.answer(TEXTS["soft_block"])
        elif reason and reason.startswith("cooldown:"):
            seconds = reason.split(":")[1]
            await message.answer(TEXTS["cooldown"].format(seconds=seconds))
        return
    
    # Отправляем сообщение о начале скачивания
    status_msg = await message.answer("⬇️ Скачиваю видео...")
    
    rate_limiter.set_processing(user_id, True)
    
    # Генерируем путь для скачивания
    output_path = str(get_temp_dir() / generate_unique_filename())
    
    # Скачиваем видео
    success = await download_video_from_url(url, output_path)
    
    if not success or not os.path.exists(output_path):
        rate_limiter.set_processing(user_id, False)
        await status_msg.edit_text(TEXTS["error_download"])
        return
    
    # Проверяем размер файла
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        cleanup_file(output_path)
        rate_limiter.set_processing(user_id, False)
        await status_msg.edit_text(TEXTS["file_too_large"])
        return
    
    # Получаем режим и начинаем обработку
    mode = rate_limiter.get_mode(user_id)
    quality = rate_limiter.get_quality(user_id)
    text_overlay = rate_limiter.get_text_overlay(user_id)
    
    await status_msg.edit_text(TEXTS["processing"])
    
    async def on_complete(success: bool, result_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and result_path:
            try:
                # Увеличиваем счётчик статистики
                rate_limiter.increment_video_count(user_id)
                
                video_file = FSInputFile(result_path)
                short_id = generate_short_id()
                await bot.send_video(
                    chat_id=user_id,
                    video=video_file,
                    caption=TEXTS["done"],
                    reply_markup=get_result_keyboard(short_id)
                )
                await status_msg.delete()
            except Exception as e:
                logger.error(f"Send error: {e}")
                await status_msg.edit_text(TEXTS["error"])
            finally:
                cleanup_file(result_path)
        else:
            await status_msg.edit_text(TEXTS["error"])
        
        cleanup_file(output_path)
    
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
        await status_msg.edit_text(TEXTS["queue_full"])

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
