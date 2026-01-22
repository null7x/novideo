"""
Тест новых функций Virex
"""
import sys

def run_tests():
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ НОВЫХ ФУНКЦИЙ VIREX")
    print("=" * 50)
    
    # 1. Test config imports
    try:
        from config import BOT_TOKEN, TEXTS, BUTTONS, Quality, QUALITY_SETTINGS, SHORT_ID_TTL_SECONDS
        print("✅ 1. Config imports OK")
        print(f"   Quality presets: {list(QUALITY_SETTINGS.keys())}")
        print(f"   Buttons: {len(BUTTONS)} buttons")
        print(f"   SHORT_ID_TTL: {SHORT_ID_TTL_SECONDS}s")
    except Exception as e:
        print(f"❌ 1. Config ERROR: {e}")
        return False
    
    # 2. Test rate_limiter
    try:
        from rate_limit import rate_limiter
        user_id = 12345
        
        # Test quality
        rate_limiter.set_quality(user_id, Quality.LOW)
        assert rate_limiter.get_quality(user_id) == Quality.LOW
        rate_limiter.set_quality(user_id, Quality.MAX)
        assert rate_limiter.get_quality(user_id) == Quality.MAX
        print("✅ 2. Quality settings OK")
    except Exception as e:
        print(f"❌ 2. Quality ERROR: {e}")
        return False
    
    # 3. Test text overlay
    try:
        assert rate_limiter.get_text_overlay(user_id) == True
        rate_limiter.toggle_text_overlay(user_id)
        assert rate_limiter.get_text_overlay(user_id) == False
        rate_limiter.toggle_text_overlay(user_id)
        assert rate_limiter.get_text_overlay(user_id) == True
        print("✅ 3. Text overlay toggle OK")
    except Exception as e:
        print(f"❌ 3. Text overlay ERROR: {e}")
        return False
    
    # 4. Test statistics
    try:
        rate_limiter.increment_video_count(user_id)
        rate_limiter.increment_video_count(user_id)
        stats = rate_limiter.get_stats(user_id)
        assert stats['total_videos'] == 2
        assert stats['today_videos'] == 2
        print("✅ 4. Statistics OK")
        print(f"   Total: {stats['total_videos']}, Today: {stats['today_videos']}")
    except Exception as e:
        print(f"❌ 4. Statistics ERROR: {e}")
        return False
    
    # 5. Test ProcessingTask
    try:
        from ffmpeg_utils import ProcessingTask, get_temp_dir
        
        def dummy_callback(s, p): pass
        task = ProcessingTask(
            user_id=user_id,
            input_path='test.mp4',
            mode='tiktok',
            callback=dummy_callback,
            quality=Quality.MEDIUM,
            text_overlay=False
        )
        assert task.quality == Quality.MEDIUM
        assert task.text_overlay == False
        print("✅ 5. ProcessingTask OK")
    except Exception as e:
        print(f"❌ 5. ProcessingTask ERROR: {e}")
        return False
    
    # 6. Test bot imports
    try:
        from bot import (
            get_start_keyboard, get_settings_keyboard, get_stats_keyboard,
            store_short_id, cleanup_short_id_map, generate_short_id
        )
        
        # Test short_id functions
        sid = generate_short_id()
        store_short_id(sid, "test_file_id")
        print("✅ 6. Bot keyboards & short_id OK")
    except Exception as e:
        print(f"❌ 6. Bot imports ERROR: {e}")
        return False
    
    # 7. Test ffmpeg filter builders
    try:
        from ffmpeg_utils import _build_tiktok_filter_v2, _build_youtube_filter_v2
        
        # TikTok filter with quality
        vf, af, params = _build_tiktok_filter_v2(1080, 1920, 30.0, 30.0, Quality.LOW, True)
        assert "crop=" in vf
        print("✅ 7. FFmpeg TikTok filter OK")
        
        # YouTube filter without text
        vf, af, params = _build_youtube_filter_v2(1080, 1920, 30.0, 30.0, Quality.MAX, False)
        assert "drawtext" not in vf  # text_overlay=False
        print("✅ 8. FFmpeg YouTube filter (no text) OK")
        
    except Exception as e:
        print(f"❌ 7-8. FFmpeg filters ERROR: {e}")
        return False
    
    print()
    print("=" * 50)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
