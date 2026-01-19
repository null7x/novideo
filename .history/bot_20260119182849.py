"""
Virex — Telegram Bot
"""
import os
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

from config import (
    BOT_TOKEN, Mode, DEFAULT_MODE,
    MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS,
    TEXTS, BUTTONS
)
from rate_limit import rate_limiter
from ffmpeg_utils import (
    start_workers, add_to_queue, ProcessingTask,
    get_temp_dir, generate_unique_filename, cleanup_file,
    cleanup_old_files, get_queue_size
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

pending_files: dict = {}
short_id_map: dict = {}  # short_id -> file_id

def generate_short_id() -> str:
    return uuid.uuid4().hex[:8]

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def get_start_keyboard(mode: str) -> InlineKeyboardMarkup:
    if mode == Mode.TIKTOK:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS["tiktok_on"], callback_data="noop")],
            [InlineKeyboardButton(text=BUTTONS["switch_youtube"], callback_data="mode_youtube")],
            [InlineKeyboardButton(text=BUTTONS["how_it_works"], callback_data="how_it_works")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS["youtube_on"], callback_data="noop")],
            [InlineKeyboardButton(text=BUTTONS["switch_tiktok"], callback_data="mode_tiktok")],
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

# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    mode = rate_limiter.get_mode(user_id)
    
    text = TEXTS["start"] if mode == Mode.TIKTOK else TEXTS["start_youtube"]
    await message.answer(text, reply_markup=get_start_keyboard(mode))

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
    
    file_unique_id = file.file_unique_id
    
    if rate_limiter.check_duplicate_file(user_id, file_unique_id):
        await message.answer(TEXTS["duplicate"])
        return
    
    pending_files[file.file_id] = {
        "user_id": user_id,
        "file_unique_id": file_unique_id,
        "message_id": message.message_id,
    }
    
    mode = rate_limiter.get_mode(user_id)
    mode_text = "TikTok MAX" if mode == Mode.TIKTOK else "YouTube Shorts MAX"
    remaining = rate_limiter.get_remaining_videos(user_id)
    
    await message.answer(
        f"{TEXTS['video_received']}\n🎯 Режим: <b>{mode_text}</b>\n📊 Осталось: {remaining} видео",
        reply_markup=get_video_keyboard(file.file_id)
    )

@dp.callback_query(F.data.startswith("process:"))
async def cb_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    file_id = callback.data.split(":", 1)[1]
    
    if rate_limiter.check_button_spam(user_id):
        await callback.answer()
        return
    
    if rate_limiter.is_processing(user_id):
        await callback.answer(TEXTS["duplicate"])
        return
    
    if file_id not in pending_files:
        await callback.answer("⚠️ Отправь видео заново")
        return
    
    file_data = pending_files[file_id]
    file_unique_id = file_data["file_unique_id"]
    
    can_process, reason = rate_limiter.check_rate_limit(user_id)
    
    if not can_process:
        if reason == "soft_block":
            await callback.answer(TEXTS["soft_block"], show_alert=True)
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
    
    async def on_complete(success: bool, output_path: str):
        rate_limiter.set_processing(user_id, False)
        
        if success and output_path:
            try:
                video_file = FSInputFile(output_path)
                await bot.send_video(
                    chat_id=user_id,
                    video=video_file,
                    caption=TEXTS["done"],
                    reply_markup=get_result_keyboard(file_id)
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
        callback=on_complete
    )
    
    queued = await add_to_queue(task)
    if not queued:
        rate_limiter.set_processing(user_id, False)
        cleanup_file(input_path)
        await callback.message.edit_text(TEXTS["queue_full"])

@dp.message()
async def handle_other(message: Message):
    pass

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def on_startup():
    await start_workers()
    cleanup_old_files()
    logger.info("Virex started")

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
