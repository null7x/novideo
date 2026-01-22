"""Полная проверка проекта на ошибки и баги"""
import sys
import traceback

print("=" * 60)
print("ПОЛНАЯ ПРОВЕРКА ПРОЕКТА VIREX BOT")
print("=" * 60)

errors = []
warnings = []

# 1. Проверка config.py
print("\n1️⃣ Проверка config.py...")
try:
    from config import (
        PLAN_LIMITS, TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN, 
        BOT_VERSION, BOT_TOKEN, ADMIN_USERNAMES,
        Mode, Quality, QUALITY_SETTINGS
    )
    print(f"   ✅ BOT_VERSION: {BOT_VERSION}")
    print(f"   ✅ PLAN_LIMITS: {list(PLAN_LIMITS.keys())}")
    
    # Проверка лимитов
    for plan, limits in PLAN_LIMITS.items():
        if not hasattr(limits, 'videos_per_day'):
            errors.append(f"PLAN_LIMITS['{plan}'] не имеет videos_per_day")
        if not hasattr(limits, 'videos_per_week'):
            errors.append(f"PLAN_LIMITS['{plan}'] не имеет videos_per_week")
        print(f"      {plan}: day={limits.videos_per_day}, week={limits.videos_per_week}")
    
    print(f"   ✅ TEXTS: {len(TEXTS)} ключей")
    print(f"   ✅ TEXTS_EN: {len(TEXTS_EN)} ключей")
    print(f"   ✅ BUTTONS: {len(BUTTONS)} ключей")
    print(f"   ✅ BUTTONS_EN: {len(BUTTONS_EN)} ключей")
    
except Exception as e:
    errors.append(f"config.py: {e}")
    traceback.print_exc()

# 2. Проверка обязательных текстов
print("\n2️⃣ Проверка обязательных текстов...")
required_texts = [
    "start", "start_youtube", "video_received", "processing", "done",
    "error", "error_download", "daily_limit_reached", "weekly_limit_reached",
    "stats", "buy_premium", "settings", "cooldown", "duplicate"
]
for key in required_texts:
    if key not in TEXTS:
        errors.append(f"TEXTS отсутствует ключ: {key}")
    else:
        print(f"   ✅ TEXTS['{key}']")
    if key not in TEXTS_EN:
        warnings.append(f"TEXTS_EN отсутствует ключ: {key}")

# 3. Проверка rate_limit.py
print("\n3️⃣ Проверка rate_limit.py...")
try:
    from rate_limit import RateLimiter
    rl = RateLimiter()
    
    # Тест всех методов
    test_user = 999999999
    
    # get_limits
    limits = rl.get_limits(test_user)
    print(f"   ✅ get_limits(): day={limits.videos_per_day}")
    
    # check_rate_limit
    can, reason = rl.check_rate_limit(test_user)
    print(f"   ✅ check_rate_limit(): {can}, {reason}")
    
    # get_daily_remaining
    daily = rl.get_daily_remaining(test_user)
    print(f"   ✅ get_daily_remaining(): {daily}")
    
    # get_weekly_remaining
    weekly = rl.get_weekly_remaining(test_user)
    print(f"   ✅ get_weekly_remaining(): {weekly}")
    
    # get_time_until_daily_reset
    daily_reset = rl.get_time_until_daily_reset(test_user)
    print(f"   ✅ get_time_until_daily_reset(): {daily_reset}")
    
    # get_time_until_weekly_reset
    weekly_reset = rl.get_time_until_weekly_reset(test_user)
    print(f"   ✅ get_time_until_weekly_reset(): {weekly_reset}")
    
    # get_plan_expiry_info
    expiry = rl.get_plan_expiry_info(test_user)
    print(f"   ✅ get_plan_expiry_info(): {expiry}")
    
    # get_stats
    stats = rl.get_stats(test_user)
    required_stat_keys = ['daily_videos', 'daily_limit', 'weekly_videos', 'weekly_limit', 'total_videos', 'plan']
    for key in required_stat_keys:
        if key not in stats:
            errors.append(f"get_stats() отсутствует ключ: {key}")
    print(f"   ✅ get_stats(): {len(stats)} ключей")
    
except Exception as e:
    errors.append(f"rate_limit.py: {e}")
    traceback.print_exc()

# 4. Проверка ffmpeg_utils.py
print("\n4️⃣ Проверка ffmpeg_utils.py...")
try:
    from ffmpeg_utils import (
        start_workers, add_to_queue, ProcessingTask,
        get_temp_dir, generate_unique_filename, cleanup_file,
        get_queue_size
    )
    print(f"   ✅ Все функции импортируются")
    
    # Проверка temp директории
    temp_dir = get_temp_dir()
    print(f"   ✅ Temp dir: {temp_dir}")
    
    # Проверка генерации имён
    filename = generate_unique_filename()
    print(f"   ✅ generate_unique_filename(): {filename}")
    
except Exception as e:
    errors.append(f"ffmpeg_utils.py: {e}")
    traceback.print_exc()

# 5. Проверка форматирования текстов
print("\n5️⃣ Проверка форматирования текстов...")
try:
    # stats
    stats_text = TEXTS["stats"].format(
        plan="🆓 Free",
        daily_videos=1,
        daily_limit=2,
        weekly_videos=5,
        weekly_limit=14,
        total_videos=10,
        last_time="сейчас",
        mode="TikTok",
        quality="Medium",
        text_overlay="ON"
    )
    print("   ✅ TEXTS['stats'] форматируется")
    
    # daily_limit_reached
    TEXTS["daily_limit_reached"].format(used=2, limit=2)
    print("   ✅ TEXTS['daily_limit_reached'] форматируется")
    
    # weekly_limit_reached
    TEXTS["weekly_limit_reached"].format(used=14, limit=14)
    print("   ✅ TEXTS['weekly_limit_reached'] форматируется")
    
    # cooldown
    TEXTS["cooldown"].format(seconds=30)
    print("   ✅ TEXTS['cooldown'] форматируется")
    
except KeyError as e:
    errors.append(f"Форматирование текста - отсутствует ключ: {e}")
except Exception as e:
    errors.append(f"Форматирование текста: {e}")

# 6. Проверка английских текстов
print("\n6️⃣ Проверка английских текстов...")
try:
    TEXTS_EN["stats"].format(
        plan="🆓 Free",
        daily_videos=1,
        daily_limit=2,
        weekly_videos=5,
        weekly_limit=14,
        total_videos=10,
        last_time="now",
        mode="TikTok",
        quality="Medium",
        text_overlay="ON",
        total_downloads=5
    )
    print("   ✅ TEXTS_EN['stats'] форматируется")
    
    TEXTS_EN["daily_limit_reached"].format(used=2, limit=2)
    print("   ✅ TEXTS_EN['daily_limit_reached'] форматируется")
    
except Exception as e:
    errors.append(f"Английские тексты: {e}")

# 7. Проверка bot.py (AST парсинг)
print("\n7️⃣ Проверка bot.py (синтаксис)...")
try:
    import ast
    with open("bot.py", "r", encoding="utf-8") as f:
        code = f.read()
    ast.parse(code)
    print(f"   ✅ bot.py синтаксически корректен ({len(code)} символов)")
    
    # Подсчёт функций и классов
    tree = ast.parse(code)
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef)]
    print(f"   ✅ Найдено {len(functions)} функций")
    
except SyntaxError as e:
    errors.append(f"bot.py синтаксическая ошибка: {e}")
except Exception as e:
    errors.append(f"bot.py: {e}")

# 8. Проверка импортов в bot.py
print("\n8️⃣ Проверка критических импортов...")
try:
    import aiogram
    print(f"   ✅ aiogram: {aiogram.__version__}")
except ImportError:
    errors.append("aiogram не установлен")

try:
    import aiohttp
    print(f"   ✅ aiohttp установлен")
except ImportError:
    warnings.append("aiohttp не установлен")

# 9. Проверка целостности данных
print("\n9️⃣ Проверка файлов данных...")
import os
import json

data_files = ["users_data.json", "promo_codes.json"]
for file in data_files:
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"   ✅ {file}: {len(data)} записей")
        except json.JSONDecodeError as e:
            errors.append(f"{file} повреждён: {e}")
    else:
        print(f"   ⚠️ {file} не существует (будет создан)")

# 10. Финальный отчёт
print("\n" + "=" * 60)
print("РЕЗУЛЬТАТЫ ПРОВЕРКИ")
print("=" * 60)

if errors:
    print(f"\n❌ ОШИБКИ ({len(errors)}):")
    for err in errors:
        print(f"   • {err}")
else:
    print("\n✅ Ошибок не найдено!")

if warnings:
    print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):")
    for warn in warnings:
        print(f"   • {warn}")

print("\n" + "=" * 60)
if errors:
    print("❌ ПРОВЕРКА НЕ ПРОЙДЕНА - есть критические ошибки!")
    sys.exit(1)
else:
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    sys.exit(0)
