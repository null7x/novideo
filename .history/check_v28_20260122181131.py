"""Полная проверка v2.8.0"""
import ast
import sys

print("=" * 60)
print("ПРОВЕРКА VIREX BOT v2.8.0")
print("=" * 60)

files = ['bot.py', 'config.py', 'rate_limit.py', 'ffmpeg_utils.py']
errors = []

# 1. Синтаксис
print("\n1️⃣ Проверка синтаксиса...")
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            code = file.read()
        ast.parse(code)
        print(f'   ✅ {f}')
    except SyntaxError as e:
        errors.append(f'{f}: {e}')
        print(f'   ❌ {f} - {e}')

# 2. Импорты config
print("\n2️⃣ Проверка импортов config.py...")
try:
    from config import (
        TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN, BOT_VERSION, PLAN_LIMITS,
        MAX_RETRY_ATTEMPTS, RETRY_DELAY_SECONDS, DOWNLOAD_TIMEOUT_SECONDS,
        MEMORY_CLEANUP_INTERVAL_MINUTES, MAINTENANCE_MODE
    )
    print(f"   ✅ config.py - BOT_VERSION={BOT_VERSION}")
except Exception as e:
    errors.append(f"config import: {e}")
    print(f"   ❌ config: {e}")

# 3. Импорты rate_limit
print("\n3️⃣ Проверка импортов rate_limit.py...")
try:
    from rate_limit import rate_limiter
    print(f"   ✅ rate_limit.py - {len(rate_limiter.users)} users")
except Exception as e:
    errors.append(f"rate_limit import: {e}")
    print(f"   ❌ rate_limit: {e}")

# 4. Импорты ffmpeg_utils
print("\n4️⃣ Проверка импортов ffmpeg_utils.py...")
try:
    from ffmpeg_utils import (
        add_to_queue, get_queue_size, is_maintenance_mode,
        set_maintenance_mode, estimate_queue_time, with_retry,
        ProgressTracker, periodic_cleanup
    )
    print("   ✅ ffmpeg_utils.py")
except Exception as e:
    errors.append(f"ffmpeg_utils import: {e}")
    print(f"   ❌ ffmpeg_utils: {e}")

# 5. Новые тексты v2.8.0
print("\n5️⃣ Проверка новых текстов v2.8.0...")
new_texts = [
    'retry_attempt', 'timeout_error', 'progress_downloading', 'progress_processing',
    'maintenance_mode', 'maintenance_on', 'maintenance_off',
    'trial_vip_available', 'trial_vip_activated', 'trial_vip_already_used',
    'streak_info', 'streak_bonus', 'streak_no_bonus',
    'history_title', 'history_empty', 'queue_status',
    'logs_title', 'logs_empty', 'error_details', 'broadcast_confirm',
    'favorites_title', 'favorites_empty', 'favorite_saved'
]
for key in new_texts:
    if key in TEXTS and key in TEXTS_EN:
        print(f"   ✅ {key}")
    else:
        ru = "✓" if key in TEXTS else "✗"
        en = "✓" if key in TEXTS_EN else "✗"
        errors.append(f"Missing text: {key} (RU:{ru}, EN:{en})")
        print(f"   ❌ {key} (RU:{ru}, EN:{en})")

# 6. Новые методы rate_limiter v2.8.0
print("\n6️⃣ Проверка новых методов rate_limiter...")
new_methods = [
    'can_use_trial', 'activate_trial', 'is_trial_used',
    'update_streak', 'get_streak', 'get_streak_bonus_videos',
    'save_favorite', 'load_favorite', 'delete_favorite', 'get_favorites',
    'add_log', 'get_logs', 'get_extended_daily_stats'
]
for m in new_methods:
    if hasattr(rate_limiter, m):
        print(f"   ✅ rate_limiter.{m}()")
    else:
        errors.append(f"Missing method: {m}")
        print(f"   ❌ rate_limiter.{m}()")

# 7. Новые функции ffmpeg_utils
print("\n7️⃣ Проверка функций ffmpeg_utils...")
funcs = ['is_maintenance_mode', 'set_maintenance_mode', 'estimate_queue_time', 'with_retry', 'periodic_cleanup']
for fn in funcs:
    try:
        func = eval(fn)
        print(f"   ✅ {fn}")
    except:
        errors.append(f"Missing ffmpeg func: {fn}")
        print(f"   ❌ {fn}")

# 8. Тест ProgressTracker
print("\n8️⃣ Проверка ProgressTracker...")
try:
    tracker = ProgressTracker(60.0)
    tracker.update(30.0)
    tracker.set_stage("processing")
    percent = tracker.get_percent()
    eta = tracker.get_eta()
    print(f"   ✅ ProgressTracker: {percent}% ETA={eta}")
except Exception as e:
    errors.append(f"ProgressTracker: {e}")
    print(f"   ❌ ProgressTracker: {e}")

# 9. Тест streak
print("\n9️⃣ Тест streak методов...")
test_user = 999999999
try:
    streak, bonus = rate_limiter.update_streak(test_user)
    info = rate_limiter.get_streak(test_user)
    bonus_videos = rate_limiter.get_streak_bonus_videos(test_user)
    print(f"   ✅ streak: {streak}, info={info['streak']}, bonus_videos={bonus_videos}")
except Exception as e:
    errors.append(f"streak: {e}")
    print(f"   ❌ streak: {e}")

# 10. Тест trial
print("\n🔟 Тест trial методов...")
try:
    can = rate_limiter.can_use_trial(test_user)
    used = rate_limiter.is_trial_used(test_user)
    print(f"   ✅ trial: can_use={can}, used={used}")
except Exception as e:
    errors.append(f"trial: {e}")
    print(f"   ❌ trial: {e}")

# 11. Тест favorites
print("\n1️⃣1️⃣ Тест favorites методов...")
try:
    rate_limiter.save_favorite(test_user, "test_fav")
    favs = rate_limiter.get_favorites(test_user)
    loaded = rate_limiter.load_favorite(test_user, "test_fav")
    deleted = rate_limiter.delete_favorite(test_user, "test_fav")
    print(f"   ✅ favorites: saved, count={len(favs)}, loaded={loaded}, deleted={deleted}")
except Exception as e:
    errors.append(f"favorites: {e}")
    print(f"   ❌ favorites: {e}")

# 12. Тест logs
print("\n1️⃣2️⃣ Тест logs методов...")
try:
    rate_limiter.add_log(test_user, "test_op", "test_details")
    logs = rate_limiter.get_logs(test_user, 5)
    print(f"   ✅ logs: count={len(logs)}")
except Exception as e:
    errors.append(f"logs: {e}")
    print(f"   ❌ logs: {e}")

# 13. Тест maintenance mode
print("\n1️⃣3️⃣ Тест maintenance mode...")
try:
    initial = is_maintenance_mode()
    set_maintenance_mode(True)
    after_set = is_maintenance_mode()
    set_maintenance_mode(False)
    after_reset = is_maintenance_mode()
    print(f"   ✅ maintenance: init={initial}, after_set={after_set}, after_reset={after_reset}")
except Exception as e:
    errors.append(f"maintenance: {e}")
    print(f"   ❌ maintenance: {e}")

# 14. Тест estimate_queue_time
print("\n1️⃣4️⃣ Тест estimate_queue_time...")
try:
    eta = estimate_queue_time(5)
    print(f"   ✅ estimate_queue_time(5) = {eta}")
except Exception as e:
    errors.append(f"estimate_queue_time: {e}")
    print(f"   ❌ estimate_queue_time: {e}")

# Итог
print("\n" + "=" * 60)
if errors:
    print(f"❌ НАЙДЕНО {len(errors)} ОШИБОК:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ ВСЕ ПРОВЕРКИ v2.8.0 ПРОЙДЕНЫ!")
    print("=" * 60)
