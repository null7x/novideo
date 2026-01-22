"""
Тестовый скрипт для проверки всех компонентов Virex
"""
import sys
import asyncio

def test_imports():
    """Тест импортов"""
    print("=" * 50)
    print("1. ТЕСТ ИМПОРТОВ")
    print("=" * 50)
    
    try:
        from config import (
            BOT_TOKEN, Mode, Quality, QUALITY_SETTINGS,
            TEXTS, BUTTONS, SHORT_ID_TTL_SECONDS
        )
        print("✅ config.py - OK")
    except Exception as e:
        print(f"❌ config.py - {e}")
        return False
    
    try:
        from rate_limit import rate_limiter
        print("✅ rate_limit.py - OK")
    except Exception as e:
        print(f"❌ rate_limit.py - {e}")
        return False
    
    try:
        from ffmpeg_utils import (
            ProcessingTask, process_video, get_video_info,
            get_temp_dir, generate_unique_filename
        )
        print("✅ ffmpeg_utils.py - OK")
    except Exception as e:
        print(f"❌ ffmpeg_utils.py - {e}")
        return False
    
    return True

def test_config():
    """Тест конфигурации"""
    print("\n" + "=" * 50)
    print("2. ТЕСТ КОНФИГУРАЦИИ")
    print("=" * 50)
    
    from config import (
        BOT_TOKEN, Mode, Quality, QUALITY_SETTINGS,
        FFMPEG_PATH, FFPROBE_PATH
    )
    
    print(f"BOT_TOKEN: {'***' + BOT_TOKEN[-10:] if BOT_TOKEN else 'NOT SET'}")
    print(f"FFMPEG_PATH: {FFMPEG_PATH}")
    print(f"FFPROBE_PATH: {FFPROBE_PATH}")
    print(f"Quality presets: {list(QUALITY_SETTINGS.keys())}")
    print(f"Modes: {Mode.TIKTOK}, {Mode.YOUTUBE}")
    
    return True

def test_rate_limiter():
    """Тест rate limiter"""
    print("\n" + "=" * 50)
    print("3. ТЕСТ RATE LIMITER")
    print("=" * 50)
    
    from rate_limit import rate_limiter
    from config import Quality, Mode
    
    test_user_id = 123456789
    
    # Тест режима
    rate_limiter.set_mode(test_user_id, Mode.TIKTOK)
    assert rate_limiter.get_mode(test_user_id) == Mode.TIKTOK
    print("✅ set_mode / get_mode - OK")
    
    # Тест качества
    rate_limiter.set_quality(test_user_id, Quality.LOW)
    assert rate_limiter.get_quality(test_user_id) == Quality.LOW
    rate_limiter.set_quality(test_user_id, Quality.MAX)
    assert rate_limiter.get_quality(test_user_id) == Quality.MAX
    print("✅ set_quality / get_quality - OK")
    
    # Тест текста
    initial = rate_limiter.get_text_overlay(test_user_id)
    toggled = rate_limiter.toggle_text_overlay(test_user_id)
    assert toggled != initial
    print("✅ toggle_text_overlay - OK")
    
    # Тест статистики
    rate_limiter.increment_video_count(test_user_id)
    stats = rate_limiter.get_stats(test_user_id)
    assert stats["total_videos"] >= 1
    assert "today_videos" in stats
    assert "quality" in stats
    assert "text_overlay" in stats
    print("✅ increment_video_count / get_stats - OK")
    
    # Тест processing
    rate_limiter.set_processing(test_user_id, True, "test_file")
    assert rate_limiter.is_processing(test_user_id) == True
    rate_limiter.set_processing(test_user_id, False)
    assert rate_limiter.is_processing(test_user_id) == False
    print("✅ set_processing / is_processing - OK")
    
    return True

def test_ffmpeg_utils():
    """Тест ffmpeg utils"""
    print("\n" + "=" * 50)
    print("4. ТЕСТ FFMPEG UTILS")
    print("=" * 50)
    
    from ffmpeg_utils import (
        get_temp_dir, generate_unique_filename,
        _escape_ffmpeg_text, _rand, ProcessingTask
    )
    from config import Quality
    
    # Тест temp dir
    temp_dir = get_temp_dir()
    assert temp_dir.exists()
    print(f"✅ get_temp_dir - {temp_dir}")
    
    # Тест filename generation
    filename = generate_unique_filename()
    assert filename.startswith("virex_")
    assert filename.endswith(".mp4")
    print(f"✅ generate_unique_filename - {filename}")
    
    # Тест escape
    escaped = _escape_ffmpeg_text("Test: text's here")
    assert "\\:" in escaped
    print(f"✅ _escape_ffmpeg_text - OK")
    
    # Тест rand
    val = _rand(0.5, 1.5)
    assert 0.5 <= val <= 1.5
    print(f"✅ _rand - {val}")
    
    # Тест ProcessingTask с quality и text_overlay
    def dummy_callback(success, path):
        pass
    
    task = ProcessingTask(
        user_id=123,
        input_path="/tmp/test.mp4",
        mode="tiktok",
        callback=dummy_callback,
        quality=Quality.MAX,
        text_overlay=True
    )
    assert task.quality == Quality.MAX
    assert task.text_overlay == True
    print("✅ ProcessingTask with quality/text_overlay - OK")
    
    return True

def test_keyboards():
    """Тест клавиатур"""
    print("\n" + "=" * 50)
    print("5. ТЕСТ КЛАВИАТУР")
    print("=" * 50)
    
    # Импортируем напрямую из bot.py
    import sys
    sys.path.insert(0, '.')
    
    from bot import (
        get_start_keyboard, get_settings_keyboard,
        get_stats_keyboard, get_video_keyboard,
        get_result_keyboard
    )
    from config import Mode
    
    test_user_id = 123456
    
    # Start keyboard
    kb = get_start_keyboard(Mode.TIKTOK, test_user_id)
    assert kb is not None
    print("✅ get_start_keyboard (TikTok) - OK")
    
    kb = get_start_keyboard(Mode.YOUTUBE, test_user_id)
    assert kb is not None
    print("✅ get_start_keyboard (YouTube) - OK")
    
    # Settings keyboard
    kb = get_settings_keyboard(test_user_id)
    assert kb is not None
    print("✅ get_settings_keyboard - OK")
    
    # Stats keyboard
    kb = get_stats_keyboard(test_user_id)
    assert kb is not None
    print("✅ get_stats_keyboard - OK")
    
    # Video keyboard
    kb = get_video_keyboard("abc123", test_user_id)
    assert kb is not None
    print("✅ get_video_keyboard - OK")
    
    # Result keyboard
    kb = get_result_keyboard("abc123", test_user_id)
    assert kb is not None
    print("✅ get_result_keyboard - OK")
    
    return True

def test_texts():
    """Тест текстов"""
    print("\n" + "=" * 50)
    print("6. ТЕСТ ТЕКСТОВ")
    print("=" * 50)
    
    from config import TEXTS, BUTTONS
    
    required_texts = [
        "start", "start_youtube", "stats", "settings",
        "quality_changed", "text_on", "text_off",
        "processing", "done", "error"
    ]
    
    for key in required_texts:
        assert key in TEXTS, f"Missing text: {key}"
    print(f"✅ TEXTS содержит все {len(required_texts)} обязательных ключей")
    
    required_buttons = [
        "settings", "quality_low", "quality_medium", "quality_max",
        "text_on", "text_off", "stats", "back"
    ]
    
    for key in required_buttons:
        assert key in BUTTONS, f"Missing button: {key}"
    print(f"✅ BUTTONS содержит все {len(required_buttons)} обязательных ключей")
    
    return True

def main():
    print("\n" + "🔧" * 25)
    print("   VIREX BOT - ПОЛНЫЙ ТЕСТ")
    print("🔧" * 25 + "\n")
    
    tests = [
        ("Импорты", test_imports),
        ("Конфигурация", test_config),
        ("Rate Limiter", test_rate_limiter),
        ("FFmpeg Utils", test_ffmpeg_utils),
        ("Клавиатуры", test_keyboards),
        ("Тексты", test_texts),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ ОШИБКА в тесте '{name}': {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 50)
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print("=" * 50)
    
    if failed == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! 🎉\n")
        return 0
    else:
        print(f"\n⚠️ {failed} тест(ов) провалено\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
