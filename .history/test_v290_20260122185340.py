"""
Virex v2.9.0 — Test Suite
Tests all new v2.9.0 functions
"""
import sys
import asyncio

def test_v290():
    print("=" * 60)
    print("VIREX v2.9.0 COMPREHENSIVE TEST")
    print("=" * 60)
    
    errors = []
    passed = 0
    
    # ═══════════════════════════════════════════════════════════════════
    # CONFIG.PY v2.9.0 TESTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n[1/4] Testing config.py v2.9.0...")
    
    from config import (
        BOT_VERSION,
        MAX_BATCH_SIZE,
        EFFECT_TEMPLATES,
        RESOLUTION_OPTIONS,
        BEST_POSTING_TIMES,
        ACHIEVEMENTS,
        USER_LEVELS,
        TEXTS,
        TEXTS_EN,
        BUTTONS,
        BUTTONS_EN,
    )
    
    # Test version
    if BOT_VERSION == "2.9.0":
        print("  ✅ BOT_VERSION = 2.9.0")
        passed += 1
    else:
        errors.append(f"BOT_VERSION != 2.9.0: {BOT_VERSION}")
    
    # Test MAX_BATCH_SIZE
    if MAX_BATCH_SIZE == 5:
        print("  ✅ MAX_BATCH_SIZE = 5")
        passed += 1
    else:
        errors.append(f"MAX_BATCH_SIZE wrong: {MAX_BATCH_SIZE}")
    
    # Test EFFECT_TEMPLATES
    if len(EFFECT_TEMPLATES) >= 4:
        print(f"  ✅ EFFECT_TEMPLATES: {len(EFFECT_TEMPLATES)} templates")
        passed += 1
        for tid in ["vintage", "neon", "cinematic", "bright"]:
            if tid in EFFECT_TEMPLATES:
                passed += 1
            else:
                errors.append(f"Missing template: {tid}")
    else:
        errors.append("EFFECT_TEMPLATES incomplete")
    
    # Test RESOLUTION_OPTIONS
    if len(RESOLUTION_OPTIONS) >= 4:
        print(f"  ✅ RESOLUTION_OPTIONS: {RESOLUTION_OPTIONS}")
        passed += 1
    else:
        errors.append("RESOLUTION_OPTIONS incomplete")
    
    # Test BEST_POSTING_TIMES
    if "TikTok" in BEST_POSTING_TIMES and "YouTube" in BEST_POSTING_TIMES:
        print(f"  ✅ BEST_POSTING_TIMES: {len(BEST_POSTING_TIMES)} platforms")
        passed += 1
    else:
        errors.append("BEST_POSTING_TIMES missing platforms")
    
    # Test ACHIEVEMENTS
    if len(ACHIEVEMENTS) >= 10:
        print(f"  ✅ ACHIEVEMENTS: {len(ACHIEVEMENTS)} achievements")
        passed += 1
    else:
        errors.append("ACHIEVEMENTS too few")
    
    # Test USER_LEVELS
    if len(USER_LEVELS) >= 8:
        print(f"  ✅ USER_LEVELS: {len(USER_LEVELS)} levels")
        passed += 1
    else:
        errors.append("USER_LEVELS too few")
    
    # Test new texts
    new_text_keys = [
        "profile_info", "achievements_title", "leaderboard_title",
        "analytics_weekly", "trim_help", "watermark_help",
        "resolution_select", "templates_select", "convert_help",
        "music_help", "reminder_help", "batch_ready",
    ]
    for key in new_text_keys:
        if key in TEXTS:
            passed += 1
        else:
            errors.append(f"Missing TEXTS['{key}']")
        if key in TEXTS_EN:
            passed += 1
        else:
            errors.append(f"Missing TEXTS_EN['{key}']")
    
    print(f"  ✅ New texts: {len(new_text_keys)} keys in both RU/EN")
    
    # Test new buttons
    new_btn_keys = [
        "achievements", "leaderboard", "convert_gif", "convert_mp3",
        "watermark_set", "apply_template", "add_reminder",
    ]
    for key in new_btn_keys:
        if key in BUTTONS:
            passed += 1
        else:
            errors.append(f"Missing BUTTONS['{key}']")
        if key in BUTTONS_EN:
            passed += 1
        else:
            errors.append(f"Missing BUTTONS_EN['{key}']")
    
    print(f"  ✅ New buttons: {len(new_btn_keys)} keys in both RU/EN")
    
    # ═══════════════════════════════════════════════════════════════════
    # RATE_LIMIT.PY v2.9.0 TESTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n[2/4] Testing rate_limit.py v2.9.0...")
    
    from rate_limit import rate_limiter, UserState
    
    # Test new UserState fields
    test_user = UserState(user_id=99999999)
    new_fields = [
        ("points", 0),
        ("level", 1),
        ("achievements", []),
        ("trim_start", ""),
        ("trim_end", ""),
        ("watermark_file_id", ""),
        ("watermark_position", "br"),
        ("resolution", "original"),
        ("current_template", ""),
        ("reminders", []),
        ("weekly_stats", {}),
        ("pending_audio_file_id", ""),
        ("batch_videos", []),
    ]
    
    for field, default in new_fields:
        if hasattr(test_user, field):
            passed += 1
        else:
            errors.append(f"UserState missing field: {field}")
    
    print(f"  ✅ UserState: {len(new_fields)} new fields")
    
    # Test new RateLimiter methods
    new_methods = [
        # Gamification
        "add_points",
        "get_user_level",
        "unlock_achievement",
        "check_achievements",
        "get_achievements",
        "get_leaderboard",
        # Trim
        "set_trim",
        "get_trim",
        "clear_trim",
        # Watermark
        "set_watermark",
        "get_watermark",
        "remove_watermark",
        # Resolution
        "set_resolution",
        "get_resolution",
        # Templates
        "set_template",
        "get_template",
        # Reminders
        "add_reminder",
        "get_reminders",
        # Analytics
        "update_weekly_stats",
        "get_weekly_analytics",
        # Music
        "set_pending_audio",
        "get_pending_audio",
        "clear_pending_audio",
        # Batch
        "add_to_batch",
        "get_batch",
        "clear_batch",
    ]
    
    for method in new_methods:
        if hasattr(rate_limiter, method):
            passed += 1
        else:
            errors.append(f"RateLimiter missing method: {method}")
    
    print(f"  ✅ RateLimiter: {len(new_methods)} new methods")
    
    # Test gamification
    print("\n  Testing gamification...")
    test_uid = 11111111
    
    # Add points and check level up
    new_level, level_up = rate_limiter.add_points(test_uid, 50, "test")
    print(f"    Points added: level={new_level}, level_up={level_up}")
    passed += 1
    
    # Get user level
    level_info = rate_limiter.get_user_level(test_uid)
    if "level" in level_info and "points" in level_info:
        print(f"    Level info: {level_info}")
        passed += 1
    else:
        errors.append("get_user_level incomplete")
    
    # Check achievements
    achievements = rate_limiter.check_achievements(test_uid)
    print(f"    Achievements checked: {len(achievements)} new")
    passed += 1
    
    # Get achievements
    ach_info = rate_limiter.get_achievements(test_uid)
    if "unlocked" in ach_info and "total" in ach_info:
        print(f"    Achievements info: {ach_info['unlocked']}/{ach_info['total']}")
        passed += 1
    else:
        errors.append("get_achievements incomplete")
    
    # Get leaderboard
    leaders = rate_limiter.get_leaderboard(5)
    print(f"    Leaderboard: {len(leaders)} users")
    passed += 1
    
    # Test trim
    print("\n  Testing trim...")
    rate_limiter.set_trim(test_uid, "00:10", "00:30")
    start, end = rate_limiter.get_trim(test_uid)
    if start == "00:10" and end == "00:30":
        print(f"    Trim set: {start} - {end}")
        passed += 1
    else:
        errors.append("Trim not working")
    rate_limiter.clear_trim(test_uid)
    passed += 1
    
    # Test watermark
    print("\n  Testing watermark...")
    rate_limiter.set_watermark(test_uid, "test_file_id", "tl")
    wm_file, wm_pos = rate_limiter.get_watermark(test_uid)
    if wm_file == "test_file_id" and wm_pos == "tl":
        print(f"    Watermark: file={wm_file[:20]}..., pos={wm_pos}")
        passed += 1
    else:
        errors.append("Watermark not working")
    rate_limiter.remove_watermark(test_uid)
    passed += 1
    
    # Test resolution
    print("\n  Testing resolution...")
    rate_limiter.set_resolution(test_uid, "720p")
    res = rate_limiter.get_resolution(test_uid)
    if res == "720p":
        print(f"    Resolution: {res}")
        passed += 1
    else:
        errors.append("Resolution not working")
    
    # Test template
    print("\n  Testing templates...")
    rate_limiter.set_template(test_uid, "vintage")
    tmpl = rate_limiter.get_template(test_uid)
    if tmpl == "vintage":
        print(f"    Template: {tmpl}")
        passed += 1
    else:
        errors.append("Template not working")
    
    # Test reminders
    print("\n  Testing reminders...")
    rate_limiter.add_reminder(test_uid, "TikTok", "18:00")
    reminders = rate_limiter.get_reminders(test_uid)
    if len(reminders) > 0:
        print(f"    Reminders: {len(reminders)}")
        passed += 1
    else:
        errors.append("Reminders not working")
    
    # Test analytics
    print("\n  Testing analytics...")
    rate_limiter.update_weekly_stats(test_uid)
    analytics = rate_limiter.get_weekly_analytics(test_uid)
    if "days" in analytics and "total" in analytics:
        print(f"    Analytics: {analytics['total']} videos this week")
        passed += 1
    else:
        errors.append("Analytics not working")
    
    # Test music
    print("\n  Testing music overlay...")
    rate_limiter.set_pending_audio(test_uid, "audio_file_id")
    audio = rate_limiter.get_pending_audio(test_uid)
    if audio == "audio_file_id":
        print(f"    Pending audio: {audio}")
        passed += 1
    else:
        errors.append("Music overlay not working")
    rate_limiter.clear_pending_audio(test_uid)
    passed += 1
    
    # Test batch
    print("\n  Testing batch processing...")
    rate_limiter.clear_batch(test_uid)
    count = rate_limiter.add_to_batch(test_uid, "video1")
    count = rate_limiter.add_to_batch(test_uid, "video2")
    batch = rate_limiter.get_batch(test_uid)
    if len(batch) == 2:
        print(f"    Batch: {len(batch)} videos")
        passed += 1
    else:
        errors.append("Batch not working")
    rate_limiter.clear_batch(test_uid)
    passed += 1
    
    # ═══════════════════════════════════════════════════════════════════
    # FFMPEG_UTILS.PY v2.9.0 TESTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n[3/4] Testing ffmpeg_utils.py v2.9.0...")
    
    import ffmpeg_utils
    
    new_ffmpeg_functions = [
        "trim_video",
        "add_music_overlay",
        "convert_to_gif",
        "convert_to_mp3",
        "convert_to_webm",
        "apply_custom_watermark",
        "change_resolution",
        "apply_effect_template",
    ]
    
    for func in new_ffmpeg_functions:
        if hasattr(ffmpeg_utils, func):
            passed += 1
        else:
            errors.append(f"ffmpeg_utils missing: {func}")
    
    print(f"  ✅ ffmpeg_utils: {len(new_ffmpeg_functions)} new functions")
    
    # ═══════════════════════════════════════════════════════════════════
    # BOT.PY v2.9.0 TESTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n[4/4] Testing bot.py v2.9.0...")
    
    import bot
    
    new_commands = [
        "cmd_profile",
        "cmd_achievements",
        "cmd_leaderboard",
        "cmd_analytics",
        "cmd_trim",
        "cmd_watermark",
        "cmd_resolution",
        "cmd_templates",
        "cmd_convert",
        "cmd_music",
        "cmd_reminder",
        "handle_photo",
        "handle_audio",
    ]
    
    for cmd in new_commands:
        if hasattr(bot, cmd):
            passed += 1
        else:
            errors.append(f"bot.py missing: {cmd}")
    
    print(f"  ✅ bot.py: {len(new_commands)} new handlers")
    
    # Check callback handlers
    new_callbacks = [
        "cb_show_achievements",
        "cb_back_to_profile",
        "cb_show_leaderboard",
        "cb_watermark_position",
        "cb_watermark_remove",
        "cb_resolution_change",
        "cb_template_select",
        "cb_convert_format",
        "cb_music_clear",
        "cb_reminder_add",
        "show_achievements_menu",
        "show_leaderboard",
    ]
    
    for cb in new_callbacks:
        if hasattr(bot, cb):
            passed += 1
        else:
            errors.append(f"bot.py missing callback: {cb}")
    
    print(f"  ✅ bot.py: {len(new_callbacks)} new callbacks")
    
    # ═══════════════════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  • {err}")
    else:
        print(f"\n✅ ALL TESTS PASSED!")
    
    print(f"\nTotal checks: {passed}")
    print(f"Errors: {len(errors)}")
    
    return len(errors) == 0

if __name__ == "__main__":
    success = test_v290()
    sys.exit(0 if success else 1)
