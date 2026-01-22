"""
VIREX BOT - Полный тест всех компонентов
"""
import sys

def test_all():
    print("=" * 60)
    print("   VIREX BOT - ПОЛНЫЙ ТЕСТ")
    print("=" * 60)
    
    errors = []
    
    # 1. Тест импортов
    print("\n1. ТЕСТ ИМПОРТОВ")
    try:
        from config import BOT_TOKEN, ADMIN_IDS, ADMIN_USERNAMES, PLAN_LIMITS, TEXTS, BUTTONS, Quality
        print("   ✅ config.py - OK")
    except Exception as e:
        print(f"   ❌ config.py - {e}")
        errors.append(f"config: {e}")
    
    try:
        from rate_limit import rate_limiter
        print("   ✅ rate_limit.py - OK")
    except Exception as e:
        print(f"   ❌ rate_limit.py - {e}")
        errors.append(f"rate_limit: {e}")
    
    try:
        from ffmpeg_utils import ProcessingTask, get_temp_dir
        print("   ✅ ffmpeg_utils.py - OK")
    except Exception as e:
        print(f"   ❌ ffmpeg_utils.py - {e}")
        errors.append(f"ffmpeg_utils: {e}")
    
    # 2. Тест конфигурации
    print("\n2. ТЕСТ КОНФИГУРАЦИИ")
    from config import ADMIN_USERNAMES, PLAN_LIMITS
    print(f"   ADMIN_USERNAMES: {ADMIN_USERNAMES}")
    print(f"   Plans: {list(PLAN_LIMITS.keys())}")
    print(f"   Free: {PLAN_LIMITS['free'].videos_per_month} videos/30 days")
    print(f"   VIP: {PLAN_LIMITS['vip'].videos_per_month} videos/30 days")
    print(f"   Premium: {PLAN_LIMITS['premium'].videos_per_month} (unlimited)")
    
    # 3. Тест rate_limiter
    print("\n3. ТЕСТ RATE_LIMITER")
    from rate_limit import rate_limiter as r
    
    # Username
    r.set_username(999, "testuser")
    found = r.find_user_by_username("@testuser")
    status = "✅" if found == 999 else "❌"
    print(f"   {status} set/find username: found={found}")
    
    # Plan
    r.set_plan(999, "vip")
    plan = r.get_plan(999)
    status = "✅" if plan == "vip" else "❌"
    print(f"   {status} set/get plan: {plan}")
    
    # Monthly limit
    remaining = r.get_monthly_remaining(999)
    print(f"   ✅ monthly remaining (VIP): {remaining}")
    
    # Stats
    stats = r.get_stats(999)
    print(f"   ✅ stats: plan={stats['plan']}, monthly={stats['monthly_videos']}/{stats['monthly_limit']}")
    
    # 4. Тест текстов
    print("\n4. ТЕСТ ТЕКСТОВ")
    from config import TEXTS
    required = ["start", "done", "downloaded", "buy_premium", "monthly_limit_reached"]
    for t in required:
        status = "✅" if t in TEXTS else "❌"
        print(f"   {status} TEXTS['{t}']")
        if t not in TEXTS:
            errors.append(f"TEXTS['{t}'] missing")
    
    # 5. Тест кнопок
    print("\n5. ТЕСТ КНОПОК")
    from config import BUTTONS
    required = ["uniqualize", "download_only", "buy_premium"]
    for b in required:
        status = "✅" if b in BUTTONS else "❌"
        print(f"   {status} BUTTONS['{b}']")
        if b not in BUTTONS:
            errors.append(f"BUTTONS['{b}'] missing")
    
    # 6. Тест bot.py функций
    print("\n6. ТЕСТ BOT.PY ФУНКЦИЙ")
    try:
        # Импортируем только функции, не запуская бота
        import importlib.util
        spec = importlib.util.spec_from_file_location("bot_module", "bot.py")
        bot_module = importlib.util.module_from_spec(spec)
        
        # Читаем файл и проверяем наличие функций
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        funcs = ["def is_admin", "def get_url_keyboard", "def get_buy_premium_keyboard", "pending_urls"]
        for func in funcs:
            status = "✅" if func in content else "❌"
            print(f"   {status} {func}")
            if func not in content:
                errors.append(f"{func} not in bot.py")
        
        # Проверяем обработчики
        handlers = ["cb_url_download", "cb_url_process", "cb_buy_premium", "cmd_buy"]
        for h in handlers:
            status = "✅" if h in content else "❌"
            print(f"   {status} handler: {h}")
            if h not in content:
                errors.append(f"handler {h} not in bot.py")
                
    except Exception as e:
        print(f"   ❌ Error reading bot.py: {e}")
        errors.append(f"bot.py: {e}")
    
    # Итоги
    print("\n" + "=" * 60)
    if errors:
        print(f"   ❌ НАЙДЕНО ОШИБОК: {len(errors)}")
        for e in errors:
            print(f"      - {e}")
    else:
        print("   ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    
    return len(errors) == 0

if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
