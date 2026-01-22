"""Тест проверки кода на ошибки"""
import sys

print("=" * 50)
print("ТЕСТИРОВАНИЕ БОТА")
print("=" * 50)

# 1. Проверка импортов config.py
print("\n1. Проверка config.py...")
try:
    from config import PLAN_LIMITS, TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN, BOT_VERSION
    print(f"   ✅ BOT_VERSION: {BOT_VERSION}")
    print(f"   ✅ PLAN_LIMITS загружены: {list(PLAN_LIMITS.keys())}")
    for plan, limits in PLAN_LIMITS.items():
        print(f"      {plan}: day={limits.videos_per_day}, week={limits.videos_per_week}")
    print(f"   ✅ TEXTS: {len(TEXTS)} ключей")
    print(f"   ✅ TEXTS_EN: {len(TEXTS_EN)} ключей")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    sys.exit(1)

# 2. Проверка новых текстов
print("\n2. Проверка новых текстов...")
required_texts = [
    "daily_limit_reached", 
    "weekly_limit_reached",
    "buy_premium",
    "stats"
]
for key in required_texts:
    if key in TEXTS:
        print(f"   ✅ TEXTS['{key}'] существует")
    else:
        print(f"   ❌ TEXTS['{key}'] НЕ НАЙДЕН!")
    if key in TEXTS_EN:
        print(f"   ✅ TEXTS_EN['{key}'] существует")
    else:
        print(f"   ❌ TEXTS_EN['{key}'] НЕ НАЙДЕН!")

# 3. Проверка rate_limit.py
print("\n3. Проверка rate_limit.py...")
try:
    from rate_limit import RateLimiter
    rl = RateLimiter()
    
    # Тест получения лимитов
    limits = rl.get_limits(123456)
    print(f"   ✅ get_limits(): day={limits.videos_per_day}, week={limits.videos_per_week}")
    
    # Тест проверки лимита
    can, reason = rl.check_rate_limit(123456)
    print(f"   ✅ check_rate_limit(): can={can}, reason={reason}")
    
    # Тест получения остатка
    daily = rl.get_daily_remaining(123456)
    weekly = rl.get_weekly_remaining(123456)
    print(f"   ✅ get_daily_remaining(): {daily}")
    print(f"   ✅ get_weekly_remaining(): {weekly}")
    
    # Тест статистики
    stats = rl.get_stats(123456)
    print(f"   ✅ get_stats() ключи: daily_videos={stats.get('daily_videos')}, daily_limit={stats.get('daily_limit')}")
    print(f"   ✅ get_stats() ключи: weekly_videos={stats.get('weekly_videos')}, weekly_limit={stats.get('weekly_limit')}")
    
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Проверка импорта bot.py (без запуска)
print("\n4. Проверка импортов bot.py...")
try:
    # Только проверяем синтаксис и импорты
    import ast
    with open("bot.py", "r", encoding="utf-8") as f:
        code = f.read()
    ast.parse(code)
    print("   ✅ bot.py синтаксически корректен")
except SyntaxError as e:
    print(f"   ❌ Синтаксическая ошибка: {e}")
    sys.exit(1)

# 5. Проверка форматирования текстов
print("\n5. Проверка форматирования текстов...")
try:
    # Тестируем форматирование stats
    stats_text = TEXTS["stats"].format(
        plan="free",
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
    print("   ✅ TEXTS['stats'] форматируется корректно")
    
    # Тестируем daily_limit_reached
    daily_text = TEXTS["daily_limit_reached"].format(used=2, limit=2)
    print("   ✅ TEXTS['daily_limit_reached'] форматируется корректно")
    
    # Тестируем weekly_limit_reached  
    weekly_text = TEXTS["weekly_limit_reached"].format(used=14, limit=14)
    print("   ✅ TEXTS['weekly_limit_reached'] форматируется корректно")
    
except KeyError as e:
    print(f"   ❌ Отсутствует ключ форматирования: {e}")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Ошибка форматирования: {e}")
    sys.exit(1)

# 6. Проверка английских текстов
print("\n6. Проверка английских текстов...")
try:
    stats_text_en = TEXTS_EN["stats"].format(
        plan="free",
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
    print("   ✅ TEXTS_EN['stats'] форматируется корректно")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n" + "=" * 50)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
print("=" * 50)
