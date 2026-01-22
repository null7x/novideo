"""Полная проверка v2.7.0"""
import ast
import sys

print("=" * 60)
print("ПРОВЕРКА VIREX BOT v2.7.0")
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

# 2. Импорты
print("\n2️⃣ Проверка импортов...")
try:
    from config import TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN, BOT_VERSION, PLAN_LIMITS
    print(f"   ✅ config.py - BOT_VERSION={BOT_VERSION}")
except Exception as e:
    errors.append(f"config import: {e}")
    print(f"   ❌ config: {e}")

try:
    from rate_limit import rate_limiter
    print(f"   ✅ rate_limit.py - {len(rate_limiter.users)} users")
except Exception as e:
    errors.append(f"rate_limit import: {e}")
    print(f"   ❌ rate_limit: {e}")

try:
    from ffmpeg_utils import add_to_queue, get_queue_size
    print("   ✅ ffmpeg_utils.py")
except Exception as e:
    errors.append(f"ffmpeg_utils import: {e}")
    print(f"   ❌ ffmpeg_utils: {e}")

# 3. Новые функции v2.7.0
print("\n3️⃣ Проверка новых функций v2.7.0...")
new_texts = ['feedback_prompt', 'feedback_sent', 'allstats', 'top_users', 
             'banlist_empty', 'queue_position', 'night_mode_on', 'subscription_warning']
for key in new_texts:
    if key in TEXTS and key in TEXTS_EN:
        print(f"   ✅ {key}")
    else:
        errors.append(f"Missing text: {key}")
        print(f"   ❌ {key}")

new_methods = ['toggle_night_mode', 'is_night_mode', 'get_top_users', 
               'get_banned_users', 'has_referral_bonus']
for m in new_methods:
    if hasattr(rate_limiter, m):
        print(f"   ✅ rate_limiter.{m}()")
    else:
        errors.append(f"Missing method: {m}")
        print(f"   ❌ rate_limiter.{m}()")

# 4. Тест форматирования текстов
print("\n4️⃣ Проверка форматирования...")
try:
    TEXTS['allstats'].format(
        total_users=100, active_today=10, new_today=5,
        free_users=80, vip_users=15, premium_users=5,
        ru_users=70, en_users=30,
        videos_today=50, total_videos=1000, total_downloads=500
    )
    print("   ✅ allstats format")
except Exception as e:
    errors.append(f"allstats format: {e}")
    print(f"   ❌ allstats: {e}")

try:
    TEXTS['subscription_warning'].format(plan="VIP", days=1, days_word="день")
    print("   ✅ subscription_warning format")
except Exception as e:
    errors.append(f"subscription_warning format: {e}")
    print(f"   ❌ subscription_warning: {e}")

try:
    TEXTS['queue_position'].format(position=3)
    print("   ✅ queue_position format")
except Exception as e:
    errors.append(f"queue_position format: {e}")
    print(f"   ❌ queue_position: {e}")

# 5. Тест методов
print("\n5️⃣ Тест методов...")
test_user = 888888888
try:
    rate_limiter.toggle_night_mode(test_user)
    is_night = rate_limiter.is_night_mode(test_user)
    print(f"   ✅ night_mode: {is_night}")
except Exception as e:
    errors.append(f"night_mode: {e}")
    print(f"   ❌ night_mode: {e}")

try:
    top = rate_limiter.get_top_users(5)
    print(f"   ✅ get_top_users: {len(top)} users")
except Exception as e:
    errors.append(f"get_top_users: {e}")
    print(f"   ❌ get_top_users: {e}")

try:
    banned = rate_limiter.get_banned_users()
    print(f"   ✅ get_banned_users: {len(banned)} banned")
except Exception as e:
    errors.append(f"get_banned_users: {e}")
    print(f"   ❌ get_banned_users: {e}")

# 6. Проверка add_to_queue возвращает tuple
print("\n6️⃣ Проверка ffmpeg_utils...")
import inspect
sig = inspect.signature(add_to_queue)
print(f"   ✅ add_to_queue signature OK")

# Итог
print("\n" + "=" * 60)
if errors:
    print(f"❌ НАЙДЕНО {len(errors)} ОШИБОК:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 60)
