"""
ПОЛНАЯ ПРОВЕРКА VIREX BOT - ВСЕ КОМПОНЕНТЫ
"""
import ast
import sys
import traceback

print("=" * 70)
print("🔍 ПОЛНАЯ ПРОВЕРКА VIREX BOT v2.8.0")
print("=" * 70)

errors = []
warnings = []

# ═══════════════════════════════════════════════════════════════════════════════
# 1. СИНТАКСИС ВСЕХ ФАЙЛОВ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("1️⃣ ПРОВЕРКА СИНТАКСИСА")
print("─" * 70)

files = ['bot.py', 'config.py', 'rate_limit.py', 'ffmpeg_utils.py']
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            code = file.read()
        ast.parse(code)
        lines = len(code.split('\n'))
        print(f'   ✅ {f} ({lines} строк)')
    except SyntaxError as e:
        errors.append(f'SYNTAX {f}: line {e.lineno} - {e.msg}')
        print(f'   ❌ {f} - Строка {e.lineno}: {e.msg}')

# ═══════════════════════════════════════════════════════════════════════════════
# 2. ИМПОРТЫ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("2️⃣ ПРОВЕРКА ИМПОРТОВ")
print("─" * 70)

# Config
try:
    from config import (
        BOT_TOKEN, BOT_VERSION, TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN,
        PLAN_LIMITS, ADMIN_IDS, ADMIN_USERNAMES,
        MAX_FILE_SIZE_MB, MAX_VIDEO_DURATION_SECONDS,
        MAX_RETRY_ATTEMPTS, RETRY_DELAY_SECONDS,
        DOWNLOAD_TIMEOUT_SECONDS, MEMORY_CLEANUP_INTERVAL_MINUTES,
        Quality, Mode, QUALITY_SETTINGS
    )
    print(f"   ✅ config.py - v{BOT_VERSION}")
except Exception as e:
    errors.append(f"IMPORT config: {e}")
    print(f"   ❌ config.py: {e}")

# Rate limit
try:
    from rate_limit import rate_limiter, UserState
    print(f"   ✅ rate_limit.py - {len(rate_limiter.users)} пользователей")
except Exception as e:
    errors.append(f"IMPORT rate_limit: {e}")
    print(f"   ❌ rate_limit.py: {e}")

# FFmpeg utils
try:
    from ffmpeg_utils import (
        start_workers, add_to_queue, ProcessingTask,
        get_temp_dir, generate_unique_filename, cleanup_file,
        cleanup_old_files, get_queue_size, cancel_task, get_user_task,
        get_user_queue_count, is_maintenance_mode, set_maintenance_mode,
        estimate_queue_time, with_retry, ProgressTracker
    )
    print(f"   ✅ ffmpeg_utils.py")
except Exception as e:
    errors.append(f"IMPORT ffmpeg_utils: {e}")
    print(f"   ❌ ffmpeg_utils.py: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. ПРОВЕРКА ВСЕХ ТЕКСТОВ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("3️⃣ ПРОВЕРКА ТЕКСТОВ (RU/EN синхронизация)")
print("─" * 70)

all_keys = set(TEXTS.keys()) | set(TEXTS_EN.keys())
missing_ru = []
missing_en = []

for key in sorted(all_keys):
    if key not in TEXTS:
        missing_ru.append(key)
    if key not in TEXTS_EN:
        missing_en.append(key)

if missing_ru:
    for k in missing_ru:
        warnings.append(f"Missing RU text: {k}")
    print(f"   ⚠️ Отсутствуют в TEXTS (RU): {len(missing_ru)}")
    for k in missing_ru[:5]:
        print(f"      • {k}")
    if len(missing_ru) > 5:
        print(f"      ... и ещё {len(missing_ru)-5}")
else:
    print(f"   ✅ Все ключи есть в TEXTS (RU)")

if missing_en:
    for k in missing_en:
        warnings.append(f"Missing EN text: {k}")
    print(f"   ⚠️ Отсутствуют в TEXTS_EN (EN): {len(missing_en)}")
    for k in missing_en[:5]:
        print(f"      • {k}")
    if len(missing_en) > 5:
        print(f"      ... и ещё {len(missing_en)-5}")
else:
    print(f"   ✅ Все ключи есть в TEXTS_EN (EN)")

# Проверка кнопок
btn_keys = set(BUTTONS.keys()) | set(BUTTONS_EN.keys())
missing_btn_ru = [k for k in btn_keys if k not in BUTTONS]
missing_btn_en = [k for k in btn_keys if k not in BUTTONS_EN]

if missing_btn_ru or missing_btn_en:
    print(f"   ⚠️ Кнопки: RU missing={len(missing_btn_ru)}, EN missing={len(missing_btn_en)}")
else:
    print(f"   ✅ Все кнопки синхронизированы ({len(BUTTONS)} шт)")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. ПРОВЕРКА ФОРМАТИРОВАНИЯ ТЕКСТОВ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("4️⃣ ПРОВЕРКА ФОРМАТИРОВАНИЯ ТЕКСТОВ")
print("─" * 70)

format_tests = [
    ("stats", {"plan": "VIP", "daily_videos": 1, "daily_limit": 2, "weekly_videos": 5, 
               "weekly_limit": 100, "total_videos": 50, "last_time": "now", 
               "mode": "TikTok", "quality": "MAX", "text_overlay": "ON", "total_downloads": 10}),
    ("allstats", {"total_users": 100, "active_today": 10, "new_today": 5,
                  "free_users": 80, "vip_users": 15, "premium_users": 5,
                  "ru_users": 70, "en_users": 30, "videos_today": 50, 
                  "total_videos": 1000, "total_downloads": 500}),
    ("queue_position", {"position": 3}),
    ("subscription_warning", {"plan": "VIP", "days": 1, "days_word": "день"}),
    ("streak_info", {"streak": 7, "bonus_text": "test"}),
    ("queue_status", {"queue_size": 5, "workers": 2, "eta": "1м"}),
    ("retry_attempt", {"attempt": 1, "max": 3}),
    ("maintenance_mode", {"minutes": 5}),
    ("referral_info", {"link": "https://t.me/bot?start=ref123", "count": 5, "bonus": 15}),
    ("cooldown", {"seconds": 30}),
    ("daily_limit_reached", {"used": 2, "limit": 2}),
    ("weekly_limit_reached", {"used": 100, "limit": 100}),
]

format_ok = 0
format_fail = 0

for key, kwargs in format_tests:
    try:
        if key in TEXTS:
            TEXTS[key].format(**kwargs)
        if key in TEXTS_EN:
            TEXTS_EN[key].format(**kwargs)
        format_ok += 1
    except KeyError as e:
        format_fail += 1
        errors.append(f"FORMAT {key}: missing key {e}")
        print(f"   ❌ {key}: отсутствует ключ {e}")
    except Exception as e:
        format_fail += 1
        errors.append(f"FORMAT {key}: {e}")
        print(f"   ❌ {key}: {e}")

if format_fail == 0:
    print(f"   ✅ Все {format_ok} форматов проверены успешно")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. ПРОВЕРКА МЕТОДОВ RATE_LIMITER
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("5️⃣ ПРОВЕРКА МЕТОДОВ RATE_LIMITER")
print("─" * 70)

test_user = 777777777
methods_to_test = [
    ("get_user", (test_user,), {}),
    ("get_limits", (test_user,), {}),
    ("get_plan", (test_user,), {}),
    ("get_mode", (test_user,), {}),
    ("get_quality", (test_user,), {}),
    ("get_language", (test_user,), {}),
    ("get_stats", (test_user,), {}),
    ("get_daily_remaining", (test_user,), {}),
    ("get_weekly_remaining", (test_user,), {}),
    ("get_referral_stats", (test_user,), {}),
    ("get_referral_link", (test_user,), {}),
    ("get_plan_expiry_info", (test_user,), {}),
    ("get_streak", (test_user,), {}),
    ("get_favorites", (test_user,), {}),
    ("get_logs", (test_user, 10), {}),
    ("get_top_users", (10,), {}),
    ("get_banned_users", (), {}),
    ("get_global_stats", (), {}),
    ("get_daily_stats", (), {}),
    ("get_extended_daily_stats", (), {}),
    ("can_use_trial", (test_user,), {}),
    ("is_trial_used", (test_user,), {}),
    ("is_banned", (test_user,), {}),
    ("is_night_mode", (test_user,), {}),
    ("has_referral_bonus", (test_user,), {}),
]

methods_ok = 0
methods_fail = 0

for method_name, args, kwargs in methods_to_test:
    try:
        method = getattr(rate_limiter, method_name)
        result = method(*args, **kwargs)
        methods_ok += 1
    except Exception as e:
        methods_fail += 1
        errors.append(f"METHOD {method_name}: {e}")
        print(f"   ❌ {method_name}(): {e}")

if methods_fail == 0:
    print(f"   ✅ Все {methods_ok} методов работают корректно")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. ПРОВЕРКА FFMPEG_UTILS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("6️⃣ ПРОВЕРКА FFMPEG_UTILS")
print("─" * 70)

ffmpeg_tests = []

# Temp dir
try:
    temp_dir = get_temp_dir()
    assert temp_dir.exists()
    ffmpeg_tests.append(("get_temp_dir", True))
except Exception as e:
    ffmpeg_tests.append(("get_temp_dir", False))
    errors.append(f"FFMPEG get_temp_dir: {e}")

# Filename
try:
    fn = generate_unique_filename()
    assert fn.startswith("virex_") and fn.endswith(".mp4")
    ffmpeg_tests.append(("generate_unique_filename", True))
except Exception as e:
    ffmpeg_tests.append(("generate_unique_filename", False))
    errors.append(f"FFMPEG generate_unique_filename: {e}")

# Queue size
try:
    size = get_queue_size()
    assert isinstance(size, int)
    ffmpeg_tests.append(("get_queue_size", True))
except Exception as e:
    ffmpeg_tests.append(("get_queue_size", False))
    errors.append(f"FFMPEG get_queue_size: {e}")

# Maintenance
try:
    initial = is_maintenance_mode()
    set_maintenance_mode(True)
    assert is_maintenance_mode() == True
    set_maintenance_mode(False)
    assert is_maintenance_mode() == False
    ffmpeg_tests.append(("maintenance_mode", True))
except Exception as e:
    ffmpeg_tests.append(("maintenance_mode", False))
    errors.append(f"FFMPEG maintenance_mode: {e}")

# Estimate queue time
try:
    eta = estimate_queue_time(10)
    assert isinstance(eta, str)
    ffmpeg_tests.append(("estimate_queue_time", True))
except Exception as e:
    ffmpeg_tests.append(("estimate_queue_time", False))
    errors.append(f"FFMPEG estimate_queue_time: {e}")

# ProgressTracker
try:
    tracker = ProgressTracker(60.0)
    tracker.update(30.0)
    tracker.set_stage("processing")
    percent = tracker.get_percent()
    eta = tracker.get_eta()
    assert percent == 50
    ffmpeg_tests.append(("ProgressTracker", True))
except Exception as e:
    ffmpeg_tests.append(("ProgressTracker", False))
    errors.append(f"FFMPEG ProgressTracker: {e}")

passed = sum(1 for _, ok in ffmpeg_tests if ok)
failed = sum(1 for _, ok in ffmpeg_tests if not ok)

if failed == 0:
    print(f"   ✅ Все {passed} функций ffmpeg_utils работают")
else:
    for name, ok in ffmpeg_tests:
        status = "✅" if ok else "❌"
        print(f"   {status} {name}")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. ПРОВЕРКА USERSTATE ПОЛЕЙ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("7️⃣ ПРОВЕРКА ПОЛЕЙ USERSTATE")
print("─" * 70)

required_fields = [
    'user_id', 'plan', 'mode', 'quality', 'text_overlay',
    'total_videos', 'daily_videos', 'weekly_videos',
    'username', 'language', 'banned', 'ban_reason',
    'referrer_id', 'referral_count', 'referral_bonus',
    'plan_expires', 'night_mode', 'history',
    # v2.8.0
    'trial_used', 'streak_count', 'streak_last_date', 'favorites', 'operation_logs'
]

user = rate_limiter.get_user(test_user)
missing_fields = []

for field in required_fields:
    if not hasattr(user, field):
        missing_fields.append(field)

if missing_fields:
    print(f"   ⚠️ Отсутствуют поля: {missing_fields}")
    for f in missing_fields:
        warnings.append(f"Missing UserState field: {f}")
else:
    print(f"   ✅ Все {len(required_fields)} полей UserState присутствуют")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. ПРОВЕРКА КОНСТАНТ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("8️⃣ ПРОВЕРКА КОНСТАНТ")
print("─" * 70)

constants_ok = True

# Проверка лимитов
if PLAN_LIMITS.get("free") is None:
    errors.append("Missing PLAN_LIMITS['free']")
    constants_ok = False
if PLAN_LIMITS.get("vip") is None:
    errors.append("Missing PLAN_LIMITS['vip']")
    constants_ok = False
if PLAN_LIMITS.get("premium") is None:
    errors.append("Missing PLAN_LIMITS['premium']")
    constants_ok = False

# Проверка качеств
if Quality.LOW not in QUALITY_SETTINGS:
    errors.append("Missing QUALITY_SETTINGS[LOW]")
    constants_ok = False
if Quality.MEDIUM not in QUALITY_SETTINGS:
    errors.append("Missing QUALITY_SETTINGS[MEDIUM]")
    constants_ok = False
if Quality.MAX not in QUALITY_SETTINGS:
    errors.append("Missing QUALITY_SETTINGS[MAX]")
    constants_ok = False

if constants_ok:
    print(f"   ✅ Все константы корректны")
    print(f"      • PLAN_LIMITS: free, vip, premium")
    print(f"      • QUALITY_SETTINGS: low, medium, max")
    print(f"      • MAX_FILE_SIZE_MB: {MAX_FILE_SIZE_MB}")
    print(f"      • MAX_VIDEO_DURATION_SECONDS: {MAX_VIDEO_DURATION_SECONDS}")
    print(f"      • MAX_RETRY_ATTEMPTS: {MAX_RETRY_ATTEMPTS}")
else:
    print(f"   ❌ Проблемы с константами")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. ПРОВЕРКА BOT.PY НА КРИТИЧНЫЕ ЭЛЕМЕНТЫ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("9️⃣ ПРОВЕРКА BOT.PY СТРУКТУРЫ")
print("─" * 70)

with open('bot.py', 'r', encoding='utf-8') as f:
    bot_code = f.read()

# Критичные элементы которые должны быть
critical_elements = [
    ('dp = Dispatcher()', 'Dispatcher инициализация'),
    ('bot = Bot(', 'Bot инициализация'),
    ('@dp.message(Command("start"))', 'Команда /start'),
    ('@dp.message(Command("stats"))', 'Команда /stats'),
    ('@dp.message(Command("help"))', 'Команда /help'),
    ('@dp.message(F.video', 'Обработчик видео'),
    ('@dp.message(F.text)', 'Обработчик текста/URL'),
    ('async def main()', 'Главная функция'),
    ('dp.start_polling', 'Запуск polling'),
    # v2.8.0
    ('@dp.message(Command("trial"))', 'Команда /trial'),
    ('@dp.message(Command("streak"))', 'Команда /streak'),
    ('@dp.message(Command("queue"))', 'Команда /queue'),
    ('@dp.message(Command("maintenance"))', 'Команда /maintenance'),
    ('is_maintenance_mode()', 'Проверка maintenance'),
]

all_found = True
for pattern, desc in critical_elements:
    if pattern in bot_code:
        print(f"   ✅ {desc}")
    else:
        print(f"   ❌ {desc} - НЕ НАЙДЕНО")
        errors.append(f"MISSING in bot.py: {desc}")
        all_found = False

# ═══════════════════════════════════════════════════════════════════════════════
# ИТОГОВЫЙ ОТЧЁТ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("📋 ИТОГОВЫЙ ОТЧЁТ")
print("=" * 70)

if errors:
    print(f"\n❌ НАЙДЕНО {len(errors)} ОШИБОК:")
    for i, e in enumerate(errors, 1):
        print(f"   {i}. {e}")
    
if warnings:
    print(f"\n⚠️ НАЙДЕНО {len(warnings)} ПРЕДУПРЕЖДЕНИЙ:")
    for i, w in enumerate(warnings[:10], 1):
        print(f"   {i}. {w}")
    if len(warnings) > 10:
        print(f"   ... и ещё {len(warnings)-10}")

if not errors:
    print(f"\n✅ ВСЕ КРИТИЧЕСКИЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print(f"   • Синтаксис: OK")
    print(f"   • Импорты: OK")
    print(f"   • Тексты: OK")
    print(f"   • Методы: OK")
    print(f"   • Структура: OK")
    print(f"\n🚀 Бот готов к запуску!")
else:
    print(f"\n🔴 ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ!")
    sys.exit(1)

print("=" * 70)
