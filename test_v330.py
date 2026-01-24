"""
Полная проверка ВСЕХ функций проекта VIREX v3.3.0
"""
import asyncio
import os
import sys
import time

# Счётчики
passed = 0
failed = 0
errors = []

def test(name, condition, details=""):
    global passed, failed, errors
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name} {details}")
        failed += 1
        errors.append(f"{name}: {details}")

async def run_tests():
    global passed, failed
    
    print("=" * 60)
    print("🧪 VIREX v3.3.0 — ПОЛНАЯ ПРОВЕРКА ФУНКЦИЙ")
    print("=" * 60)
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 1. CONFIG.PY")
    # ══════════════════════════════════════════════════════════════
    try:
        import config
        test("BOT_VERSION", config.BOT_VERSION == "3.3.0", f"got {config.BOT_VERSION}")
        test("BOT_TOKEN exists", hasattr(config, 'BOT_TOKEN'))
        test("Mode enum", hasattr(config, 'Mode'))
        test("Quality enum", hasattr(config, 'Quality'))
        test("TEXTS dict", isinstance(config.TEXTS, dict) and len(config.TEXTS) > 0)
        test("TEXTS_EN dict", isinstance(config.TEXTS_EN, dict) and len(config.TEXTS_EN) > 0)
        test("BUTTONS dict", isinstance(config.BUTTONS, dict))
        test("PLAN_LIMITS dict", isinstance(config.PLAN_LIMITS, dict))
        test("ADMIN_IDS", hasattr(config, 'ADMIN_IDS'))
        test("FFMPEG_PATH", hasattr(config, 'FFMPEG_PATH'))
        test("FFPROBE_PATH", hasattr(config, 'FFPROBE_PATH'))
        test("MAX_FILE_SIZE_MB", config.MAX_FILE_SIZE_MB > 0)
        test("MAX_VIDEO_DURATION_SECONDS", config.MAX_VIDEO_DURATION_SECONDS > 0)
        test("WATERMARK_TRAP_ENABLED", hasattr(config, 'WATERMARK_TRAP_ENABLED'))
    except Exception as e:
        test("config.py import", False, str(e))
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 2. RATE_LIMIT.PY")
    # ══════════════════════════════════════════════════════════════
    try:
        import rate_limit
        rl = rate_limit.rate_limiter
        
        test("RateLimiter instance", rl is not None)
        test("get_plan()", callable(getattr(rl, 'get_plan', None)))
        test("check_rate_limit()", callable(getattr(rl, 'check_rate_limit', None)))
        test("is_processing()", callable(getattr(rl, 'is_processing', None)))
        test("set_processing()", callable(getattr(rl, 'set_processing', None)))
        test("increment_video_count()", callable(getattr(rl, 'increment_video_count', None)))
        test("get_language()", callable(getattr(rl, 'get_language', None)))
        test("set_language()", callable(getattr(rl, 'set_language', None)))
        test("get_username()", callable(getattr(rl, 'get_username', None)))
        test("find_user_by_username()", callable(getattr(rl, 'find_user_by_username', None)))
        test("set_plan_with_expiry()", callable(getattr(rl, 'set_plan_with_expiry', None)))
        test("add_to_history()", callable(getattr(rl, 'add_to_history', None)))
        test("add_log()", callable(getattr(rl, 'add_log', None)))
        test("update_streak()", callable(getattr(rl, 'update_streak', None)))
        test("add_points()", callable(getattr(rl, 'add_points', None)))
        test("check_achievements()", callable(getattr(rl, 'check_achievements', None)))
        test("can_use_watermark_trap()", callable(getattr(rl, 'can_use_watermark_trap', None)))
        
        # Функциональные тесты
        test_user = 999999999
        plan = rl.get_plan(test_user)
        test("get_plan returns string", isinstance(plan, str))
        
        lang = rl.get_language(test_user)
        test("get_language returns ru/en", lang in ["ru", "en"])
        
    except Exception as e:
        test("rate_limit.py import", False, str(e))
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 3. FFMPEG_UTILS.PY")
    # ══════════════════════════════════════════════════════════════
    try:
        import ffmpeg_utils
        
        test("start_workers()", callable(ffmpeg_utils.start_workers))
        test("add_to_queue()", callable(ffmpeg_utils.add_to_queue))
        test("ProcessingTask class", hasattr(ffmpeg_utils, 'ProcessingTask'))
        test("get_temp_dir()", callable(ffmpeg_utils.get_temp_dir))
        test("generate_unique_filename()", callable(ffmpeg_utils.generate_unique_filename))
        test("cleanup_file()", callable(ffmpeg_utils.cleanup_file))
        test("cleanup_old_files()", callable(ffmpeg_utils.cleanup_old_files))
        test("get_queue_size()", callable(ffmpeg_utils.get_queue_size))
        test("cancel_task()", callable(ffmpeg_utils.cancel_task))
        test("get_user_task()", callable(ffmpeg_utils.get_user_task))
        test("is_maintenance_mode()", callable(ffmpeg_utils.is_maintenance_mode))
        test("set_maintenance_mode()", callable(ffmpeg_utils.set_maintenance_mode))
        test("estimate_queue_time()", callable(ffmpeg_utils.estimate_queue_time))
        test("with_retry()", callable(ffmpeg_utils.with_retry))
        test("ProgressTracker class", hasattr(ffmpeg_utils, 'ProgressTracker'))
        
        # Функциональные тесты
        temp_dir = ffmpeg_utils.get_temp_dir()
        test("get_temp_dir() returns path", os.path.exists(temp_dir))
        
        filename = ffmpeg_utils.generate_unique_filename(".mp4")
        test("generate_unique_filename()", filename.endswith(".mp4"))
        
        queue_size = ffmpeg_utils.get_queue_size()
        test("get_queue_size() returns int", isinstance(queue_size, int))
        
    except Exception as e:
        test("ffmpeg_utils.py import", False, str(e))
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 4. WATERMARK_TRAP.PY")
    # ══════════════════════════════════════════════════════════════
    try:
        import watermark_trap
        
        test("TrapSignature class", hasattr(watermark_trap, 'TrapSignature'))
        test("WatermarkTrapProcessor class", hasattr(watermark_trap, 'WatermarkTrapProcessor'))
        test("WatermarkTrapDetector class", hasattr(watermark_trap, 'WatermarkTrapDetector'))
        test("DetectionResult class", hasattr(watermark_trap, 'DetectionResult'))
        test("get_trap_processor()", callable(watermark_trap.get_trap_processor))
        test("get_trap_detector()", callable(watermark_trap.get_trap_detector))
        test("apply_watermark_trap()", callable(watermark_trap.apply_watermark_trap))
        
        # Получаем процессор
        processor = watermark_trap.get_trap_processor()
        test("TrapProcessor instance", processor is not None)
        test("generate_trap_signature() module func", callable(watermark_trap.generate_trap_signature))
        
        # Генерируем сигнатуру через модульную функцию
        sig = watermark_trap.generate_trap_signature(12345, "test.mp4")
        test("TrapSignature.user_id", sig.user_id == 12345)
        test("TrapSignature.timestamp", sig.timestamp > 0)
        test("TrapSignature.master_key", len(sig.master_key) > 0)
        test("TrapSignature.pixel_key", len(sig.pixel_key) > 0)
        test("TrapSignature.temporal_key", len(sig.temporal_key) > 0)
        test("TrapSignature.audio_key", len(sig.audio_key) > 0)
        
        # Получаем детектор
        detector = watermark_trap.get_trap_detector()
        test("TrapDetector instance", detector is not None)
        test("detect() async", callable(getattr(detector, 'detect', None)))
        
    except Exception as e:
        test("watermark_trap.py import", False, str(e))
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 5. CONTENT_PROTECTION.PY")
    # ══════════════════════════════════════════════════════════════
    try:
        import content_protection as cp
        
        # Enums
        test("RiskLevel enum", hasattr(cp, 'RiskLevel'))
        test("RiskLevel.SAFE", hasattr(cp.RiskLevel, 'SAFE'))
        test("RiskLevel.CRITICAL", hasattr(cp.RiskLevel, 'CRITICAL'))
        
        # Dataclasses
        test("DigitalPassport class", hasattr(cp, 'DigitalPassport'))
        test("MatchResult class", hasattr(cp, 'MatchResult'))
        test("SafeCheckResult class", hasattr(cp, 'SafeCheckResult'))
        test("UserAnalytics class", hasattr(cp, 'UserAnalytics'))
        test("SmartPreset class", hasattr(cp, 'SmartPreset'))
        test("TheftReport class", hasattr(cp, 'TheftReport'))
        test("ScanResult class", hasattr(cp, 'ScanResult'))
        
        # Classes
        test("VideoFingerprinter class", hasattr(cp, 'VideoFingerprinter'))
        test("SimilarityDetector class", hasattr(cp, 'SimilarityDetector'))
        test("SafeChecker class", hasattr(cp, 'SafeChecker'))
        test("AnalyticsManager class", hasattr(cp, 'AnalyticsManager'))
        test("AntiStealSystem class", hasattr(cp, 'AntiStealSystem'))
        test("ContentScanner class", hasattr(cp, 'ContentScanner'))
        test("VirexShield class", hasattr(cp, 'VirexShield'))
        
        # Presets
        test("SMART_PRESETS dict", hasattr(cp, 'SMART_PRESETS'))
        test("SMART_PRESETS count", len(cp.SMART_PRESETS) == 11)
        test("get_preset()", callable(cp.get_preset))
        test("list_presets()", callable(cp.list_presets))
        test("get_preset_message()", callable(cp.get_preset_message))
        
        # Singletons
        test("get_similarity_detector()", callable(cp.get_similarity_detector))
        test("get_safe_checker()", callable(cp.get_safe_checker))
        test("get_analytics_manager()", callable(cp.get_analytics_manager))
        test("get_virex_shield()", callable(cp.get_virex_shield))
        
        # VideoFingerprinter
        vf = cp.VideoFingerprinter
        test("VF.calculate_file_hash()", callable(vf.calculate_file_hash))
        test("VF.calculate_perceptual_hash()", callable(vf.calculate_perceptual_hash))
        test("VF.calculate_temporal_signature()", callable(vf.calculate_temporal_signature))
        test("VF.compare_hashes()", callable(vf.compare_hashes))
        
        # Compare hashes test
        sim = vf.compare_hashes("abcd1234", "abcd1234")
        test("compare_hashes identical = 1.0", sim == 1.0)
        sim2 = vf.compare_hashes("abcd1234", "00000000")
        test("compare_hashes different < 1.0", sim2 < 1.0)
        
        # VirexShield
        shield = cp.get_virex_shield()
        test("VirexShield VERSION", shield.VERSION == "1.0.0")
        test("shield.detector", shield.detector is not None)
        test("shield.anti_steal", shield.anti_steal is not None)
        test("shield.scanner", shield.scanner is not None)
        test("shield.safe_checker", shield.safe_checker is not None)
        test("shield.analytics", shield.analytics is not None)
        
        # Shield methods
        test("shield.register_for_protection()", callable(shield.register_for_protection))
        test("shield.check_if_stolen()", callable(shield.check_if_stolen))
        test("shield.scan_for_matches()", callable(shield.scan_for_matches))
        test("shield.scan_url()", callable(shield.scan_url))
        test("shield.safe_check()", callable(shield.safe_check))
        test("shield.get_smart_preset()", callable(shield.get_smart_preset))
        test("shield.list_smart_presets()", callable(shield.list_smart_presets))
        test("shield.get_preset_for_platform()", callable(shield.get_preset_for_platform))
        test("shield.get_user_analytics()", callable(shield.get_user_analytics))
        test("shield.record_processing()", callable(shield.record_processing))
        test("shield.get_passport()", callable(shield.get_passport))
        test("shield.get_user_passports()", callable(shield.get_user_passports))
        test("shield.verify_passport()", callable(shield.verify_passport))
        test("shield.get_shield_info()", callable(shield.get_shield_info))
        
        # Smart Presets
        presets = shield.list_smart_presets()
        test("list_smart_presets() returns 11", len(presets) == 11)
        
        preset = shield.get_smart_preset("tiktok_usa")
        test("get_smart_preset('tiktok_usa')", preset is not None)
        test("preset.name", preset.name == "tiktok_usa")
        test("preset.display_name", "TikTok USA" in preset.display_name)
        test("preset.aggressive_uniqueness", preset.aggressive_uniqueness == True)
        
        preset2 = shield.get_preset_for_platform("tiktok")
        test("get_preset_for_platform('tiktok')", preset2 is not None)
        
        preset3 = shield.get_preset_for_platform("instagram")
        test("get_preset_for_platform('instagram')", preset3 is not None)
        test("instagram -> reels_2025", preset3.name == "reels_2025")
        
        # Analytics
        analytics = shield.get_user_analytics(12345)
        test("UserAnalytics.user_id", analytics.user_id == 12345)
        test("UserAnalytics.total_processed", hasattr(analytics, 'total_processed'))
        test("UserAnalytics.to_message()", callable(analytics.to_message))
        
        # Shield info
        info_ru = shield.get_shield_info("ru")
        test("get_shield_info('ru')", "VIREX SHIELD" in info_ru)
        info_en = shield.get_shield_info("en")
        test("get_shield_info('en')", "VIREX SHIELD" in info_en)
        
        # MatchResult
        mr = cp.MatchResult(found=False, similarity=0.0, risk_level=cp.RiskLevel.SAFE)
        test("MatchResult.to_message()", callable(mr.to_message))
        msg = mr.to_message("ru")
        test("MatchResult message", "Совпадений не найдено" in msg)
        
        # SafeCheckResult
        scr = cp.SafeCheckResult(
            overall_risk=cp.RiskLevel.SAFE,
            overall_score=90.0,
            originality_score=95.0,
            ban_probability=5.0,
            strike_probability=3.0,
            shadow_ban_risk=10.0
        )
        test("SafeCheckResult.to_message()", callable(scr.to_message))
        msg2 = scr.to_message("ru")
        test("SafeCheckResult message", "SAFE-CHECK" in msg2)
        
        # ContentScanner
        scanner = shield.scanner
        platform, vid = scanner.detect_platform("https://tiktok.com/@user/video/123456")
        test("detect_platform tiktok", platform == "tiktok")
        
        platform2, vid2 = scanner.detect_platform("https://instagram.com/reel/ABC123")
        test("detect_platform instagram", platform2 == "instagram")
        
        platform3, vid3 = scanner.detect_platform("https://youtube.com/shorts/XYZ789")
        test("detect_platform youtube", platform3 == "youtube")
        
    except Exception as e:
        import traceback
        test("content_protection.py import", False, str(e))
        traceback.print_exc()
    
    # ══════════════════════════════════════════════════════════════
    print("\n📦 6. BOT.PY (imports only)")
    # ══════════════════════════════════════════════════════════════
    try:
        from bot import dp, bot, get_text, get_button
        
        test("Dispatcher (dp)", dp is not None)
        test("Bot instance", bot is not None)
        test("get_text()", callable(get_text))
        test("get_button()", callable(get_button))
        
        # Проверяем наличие хендлеров
        from bot import (
            pending_detection,
            pending_safecheck, 
            pending_scan,
            VIREX_SHIELD_AVAILABLE,
            WATERMARK_TRAP_DETECTION_AVAILABLE
        )
        test("pending_detection dict", isinstance(pending_detection, dict))
        test("pending_safecheck dict", isinstance(pending_safecheck, dict))
        test("pending_scan dict", isinstance(pending_scan, dict))
        test("VIREX_SHIELD_AVAILABLE", VIREX_SHIELD_AVAILABLE == True)
        test("WATERMARK_TRAP_DETECTION_AVAILABLE", WATERMARK_TRAP_DETECTION_AVAILABLE == True)
        
    except Exception as e:
        test("bot.py import", False, str(e))
    
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"📊 ИТОГО: {passed} ✅ passed, {failed} ❌ failed")
    print("=" * 60)
    
    if errors:
        print("\n❌ ОШИБКИ:")
        for e in errors:
            print(f"   • {e}")
    else:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
