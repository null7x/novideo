"""
ДЕТАЛЬНАЯ ПРОВЕРКА КАЖДОЙ ФУНКЦИИ VIREX BOT v2.8.0
"""
import asyncio
import sys

print("=" * 70)
print("🔬 ДЕТАЛЬНАЯ ПРОВЕРКА ВСЕХ ФУНКЦИЙ")
print("=" * 70)

errors = []
test_user = 123456789

# ═══════════════════════════════════════════════════════════════════════════════
# ИМПОРТЫ
# ═══════════════════════════════════════════════════════════════════════════════
from config import (
    BOT_VERSION, TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN,
    PLAN_LIMITS, Quality, Mode, QUALITY_SETTINGS,
    MAX_RETRY_ATTEMPTS, MAINTENANCE_MODE
)
from rate_limit import rate_limiter
from ffmpeg_utils import (
    get_temp_dir, generate_unique_filename, cleanup_file,
    get_queue_size, is_maintenance_mode, set_maintenance_mode,
    estimate_queue_time, ProgressTracker, get_temp_dir_size
)

print(f"\n📦 Версия: {BOT_VERSION}")
print(f"👥 Пользователей в базе: {len(rate_limiter.users)}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONFIG FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("1️⃣ CONFIG.PY")
print("─" * 70)

def test_config():
    tests = []
    
    # Test PLAN_LIMITS
    try:
        assert "free" in PLAN_LIMITS
        assert "vip" in PLAN_LIMITS
        assert "premium" in PLAN_LIMITS
        assert PLAN_LIMITS["free"].videos_per_day == 2
        assert PLAN_LIMITS["vip"].videos_per_day == 15
        assert PLAN_LIMITS["premium"].videos_per_day == 999999
        tests.append(("PLAN_LIMITS", True, "free=2/day, vip=15/day, premium=∞"))
    except Exception as e:
        tests.append(("PLAN_LIMITS", False, str(e)))
    
    # Test QUALITY_SETTINGS
    try:
        assert Quality.LOW in QUALITY_SETTINGS
        assert Quality.MEDIUM in QUALITY_SETTINGS
        assert Quality.MAX in QUALITY_SETTINGS
        assert "crf_offset" in QUALITY_SETTINGS[Quality.LOW]
        tests.append(("QUALITY_SETTINGS", True, "low, medium, max"))
    except Exception as e:
        tests.append(("QUALITY_SETTINGS", False, str(e)))
    
    # Test Mode
    try:
        assert Mode.TIKTOK == "tiktok"
        assert Mode.YOUTUBE == "youtube"
        tests.append(("Mode", True, "tiktok, youtube"))
    except Exception as e:
        tests.append(("Mode", False, str(e)))
    
    # Test TEXTS count
    try:
        ru_count = len(TEXTS)
        en_count = len(TEXTS_EN)
        btn_count = len(BUTTONS)
        tests.append(("TEXTS", True, f"RU={ru_count}, EN={en_count}, BTN={btn_count}"))
    except Exception as e:
        tests.append(("TEXTS", False, str(e)))
    
    return tests

for name, ok, info in test_config():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"CONFIG {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. RATE_LIMITER - USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("2️⃣ RATE_LIMITER - Управление пользователями")
print("─" * 70)

def test_user_management():
    tests = []
    
    # get_user
    try:
        user = rate_limiter.get_user(test_user)
        assert user.user_id == test_user
        tests.append(("get_user()", True, f"user_id={user.user_id}"))
    except Exception as e:
        tests.append(("get_user()", False, str(e)))
    
    # set_username / get_username
    try:
        rate_limiter.set_username(test_user, "test_user_123")
        username = rate_limiter.get_username(test_user)
        assert username == "test_user_123"
        tests.append(("set/get_username()", True, f"username={username}"))
    except Exception as e:
        tests.append(("set/get_username()", False, str(e)))
    
    # find_user_by_username
    try:
        found_id = rate_limiter.find_user_by_username("test_user_123")
        assert found_id == test_user
        tests.append(("find_user_by_username()", True, f"found={found_id}"))
    except Exception as e:
        tests.append(("find_user_by_username()", False, str(e)))
    
    # set_language / get_language
    try:
        rate_limiter.set_language(test_user, "en")
        lang = rate_limiter.get_language(test_user)
        assert lang == "en"
        rate_limiter.set_language(test_user, "ru")
        tests.append(("set/get_language()", True, f"lang=en→ru"))
    except Exception as e:
        tests.append(("set/get_language()", False, str(e)))
    
    # is_new_user
    try:
        is_new = rate_limiter.is_new_user(test_user + 999)
        tests.append(("is_new_user()", True, f"new_user={is_new}"))
    except Exception as e:
        tests.append(("is_new_user()", False, str(e)))
    
    # get_total_users
    try:
        total = rate_limiter.get_total_users()
        assert isinstance(total, int)
        tests.append(("get_total_users()", True, f"total={total}"))
    except Exception as e:
        tests.append(("get_total_users()", False, str(e)))
    
    # get_all_users
    try:
        all_users = rate_limiter.get_all_users()
        assert isinstance(all_users, list)
        tests.append(("get_all_users()", True, f"count={len(all_users)}"))
    except Exception as e:
        tests.append(("get_all_users()", False, str(e)))
    
    return tests

for name, ok, info in test_user_management():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"USER_MGMT {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. RATE_LIMITER - PLANS & LIMITS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("3️⃣ RATE_LIMITER - Планы и лимиты")
print("─" * 70)

def test_plans_limits():
    tests = []
    
    # set_plan / get_plan
    try:
        rate_limiter.set_plan(test_user, "vip")
        plan = rate_limiter.get_plan(test_user)
        assert plan == "vip"
        rate_limiter.set_plan(test_user, "free")
        tests.append(("set/get_plan()", True, f"vip→free"))
    except Exception as e:
        tests.append(("set/get_plan()", False, str(e)))
    
    # get_limits
    try:
        limits = rate_limiter.get_limits(test_user)
        assert hasattr(limits, 'videos_per_day')
        tests.append(("get_limits()", True, f"day={limits.videos_per_day}"))
    except Exception as e:
        tests.append(("get_limits()", False, str(e)))
    
    # get_daily_remaining
    try:
        remaining = rate_limiter.get_daily_remaining(test_user)
        assert isinstance(remaining, int)
        tests.append(("get_daily_remaining()", True, f"remaining={remaining}"))
    except Exception as e:
        tests.append(("get_daily_remaining()", False, str(e)))
    
    # get_weekly_remaining
    try:
        remaining = rate_limiter.get_weekly_remaining(test_user)
        assert isinstance(remaining, int)
        tests.append(("get_weekly_remaining()", True, f"remaining={remaining}"))
    except Exception as e:
        tests.append(("get_weekly_remaining()", False, str(e)))
    
    # check_rate_limit
    try:
        allowed, reason = rate_limiter.check_rate_limit(test_user)
        assert isinstance(allowed, bool)
        tests.append(("check_rate_limit()", True, f"allowed={allowed}"))
    except Exception as e:
        tests.append(("check_rate_limit()", False, str(e)))
    
    # set_plan_with_expiry
    try:
        rate_limiter.set_plan_with_expiry(test_user, "vip", 7)
        info = rate_limiter.get_plan_expiry_info(test_user)
        assert info["has_expiry"] == True
        rate_limiter.set_plan(test_user, "free")
        tests.append(("set_plan_with_expiry()", True, f"days_left={info['days_left']}"))
    except Exception as e:
        tests.append(("set_plan_with_expiry()", False, str(e)))
    
    # get_plan_expiry_info
    try:
        info = rate_limiter.get_plan_expiry_info(test_user)
        assert "has_expiry" in info
        assert "days_left" in info
        tests.append(("get_plan_expiry_info()", True, f"has_expiry={info['has_expiry']}"))
    except Exception as e:
        tests.append(("get_plan_expiry_info()", False, str(e)))
    
    # check_plan_expiry
    try:
        expired = rate_limiter.check_plan_expiry(test_user)
        assert isinstance(expired, bool)
        tests.append(("check_plan_expiry()", True, f"expired={expired}"))
    except Exception as e:
        tests.append(("check_plan_expiry()", False, str(e)))
    
    # get_time_until_daily_reset
    try:
        time_str = rate_limiter.get_time_until_daily_reset(test_user)
        assert isinstance(time_str, str)
        tests.append(("get_time_until_daily_reset()", True, f"reset={time_str}"))
    except Exception as e:
        tests.append(("get_time_until_daily_reset()", False, str(e)))
    
    # get_time_until_weekly_reset
    try:
        time_str = rate_limiter.get_time_until_weekly_reset(test_user)
        assert isinstance(time_str, str)
        tests.append(("get_time_until_weekly_reset()", True, f"reset={time_str}"))
    except Exception as e:
        tests.append(("get_time_until_weekly_reset()", False, str(e)))
    
    return tests

for name, ok, info in test_plans_limits():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"PLANS {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. RATE_LIMITER - SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("4️⃣ RATE_LIMITER - Настройки пользователя")
print("─" * 70)

def test_settings():
    tests = []
    
    # set_mode / get_mode
    try:
        rate_limiter.set_mode(test_user, "youtube")
        mode = rate_limiter.get_mode(test_user)
        assert mode == "youtube"
        rate_limiter.set_mode(test_user, "tiktok")
        tests.append(("set/get_mode()", True, f"youtube→tiktok"))
    except Exception as e:
        tests.append(("set/get_mode()", False, str(e)))
    
    # set_quality / get_quality
    try:
        rate_limiter.set_quality(test_user, Quality.MAX)
        quality = rate_limiter.get_quality(test_user)
        assert quality == Quality.MAX
        tests.append(("set/get_quality()", True, f"quality={quality}"))
    except Exception as e:
        tests.append(("set/get_quality()", False, str(e)))
    
    # toggle_text_overlay / get_text_overlay
    try:
        original = rate_limiter.get_text_overlay(test_user)
        new_val = rate_limiter.toggle_text_overlay(test_user)
        assert new_val != original
        rate_limiter.toggle_text_overlay(test_user)  # restore
        tests.append(("toggle/get_text_overlay()", True, f"toggled OK"))
    except Exception as e:
        tests.append(("toggle/get_text_overlay()", False, str(e)))
    
    # toggle_night_mode / is_night_mode
    try:
        original = rate_limiter.is_night_mode(test_user)
        new_val = rate_limiter.toggle_night_mode(test_user)
        assert new_val != original
        rate_limiter.toggle_night_mode(test_user)  # restore
        tests.append(("toggle/is_night_mode()", True, f"toggled OK"))
    except Exception as e:
        tests.append(("toggle/is_night_mode()", False, str(e)))
    
    # can_disable_text
    try:
        can = rate_limiter.can_disable_text(test_user)
        assert isinstance(can, bool)
        tests.append(("can_disable_text()", True, f"can={can}"))
    except Exception as e:
        tests.append(("can_disable_text()", False, str(e)))
    
    # can_use_quality
    try:
        can = rate_limiter.can_use_quality(test_user, Quality.MAX)
        assert isinstance(can, bool)
        tests.append(("can_use_quality()", True, f"MAX={can}"))
    except Exception as e:
        tests.append(("can_use_quality()", False, str(e)))
    
    # get_available_qualities
    try:
        qualities = rate_limiter.get_available_qualities(test_user)
        assert isinstance(qualities, list)
        tests.append(("get_available_qualities()", True, f"count={len(qualities)}"))
    except Exception as e:
        tests.append(("get_available_qualities()", False, str(e)))
    
    return tests

for name, ok, info in test_settings():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"SETTINGS {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. RATE_LIMITER - STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("5️⃣ RATE_LIMITER - Статистика")
print("─" * 70)

def test_statistics():
    tests = []
    
    # get_stats
    try:
        stats = rate_limiter.get_stats(test_user)
        assert "total_videos" in stats
        assert "daily_videos" in stats
        assert "plan" in stats
        tests.append(("get_stats()", True, f"total={stats['total_videos']}"))
    except Exception as e:
        tests.append(("get_stats()", False, str(e)))
    
    # increment_video_count
    try:
        before = rate_limiter.get_stats(test_user)["total_videos"]
        rate_limiter.increment_video_count(test_user)
        after = rate_limiter.get_stats(test_user)["total_videos"]
        assert after == before + 1
        tests.append(("increment_video_count()", True, f"{before}→{after}"))
    except Exception as e:
        tests.append(("increment_video_count()", False, str(e)))
    
    # increment_download_count
    try:
        before = rate_limiter.get_stats(test_user).get("total_downloads", 0)
        rate_limiter.increment_download_count(test_user)
        after = rate_limiter.get_stats(test_user).get("total_downloads", 0)
        assert after == before + 1
        tests.append(("increment_download_count()", True, f"{before}→{after}"))
    except Exception as e:
        tests.append(("increment_download_count()", False, str(e)))
    
    # get_global_stats
    try:
        stats = rate_limiter.get_global_stats()
        assert "total_users" in stats
        assert "total_videos" in stats
        tests.append(("get_global_stats()", True, f"users={stats['total_users']}"))
    except Exception as e:
        tests.append(("get_global_stats()", False, str(e)))
    
    # get_daily_stats
    try:
        stats = rate_limiter.get_daily_stats()
        assert "new_users" in stats
        assert "videos_today" in stats
        tests.append(("get_daily_stats()", True, f"new={stats['new_users']}"))
    except Exception as e:
        tests.append(("get_daily_stats()", False, str(e)))
    
    # get_extended_daily_stats
    try:
        stats = rate_limiter.get_extended_daily_stats()
        assert "active_users" in stats
        assert "by_plan" in stats
        tests.append(("get_extended_daily_stats()", True, f"active={stats['active_users']}"))
    except Exception as e:
        tests.append(("get_extended_daily_stats()", False, str(e)))
    
    # get_top_users
    try:
        top = rate_limiter.get_top_users(5)
        assert isinstance(top, list)
        tests.append(("get_top_users()", True, f"count={len(top)}"))
    except Exception as e:
        tests.append(("get_top_users()", False, str(e)))
    
    # get_source_stats
    try:
        sources = rate_limiter.get_source_stats()
        assert isinstance(sources, dict)
        tests.append(("get_source_stats()", True, f"sources={len(sources)}"))
    except Exception as e:
        tests.append(("get_source_stats()", False, str(e)))
    
    return tests

for name, ok, info in test_statistics():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"STATS {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. RATE_LIMITER - REFERRAL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("6️⃣ RATE_LIMITER - Реферальная система")
print("─" * 70)

def test_referral():
    tests = []
    ref_user = test_user + 1000
    
    # get_referral_link
    try:
        link = rate_limiter.get_referral_link(test_user)
        assert "t.me" in link
        assert str(test_user) in link
        tests.append(("get_referral_link()", True, f"link OK"))
    except Exception as e:
        tests.append(("get_referral_link()", False, str(e)))
    
    # get_referral_stats
    try:
        stats = rate_limiter.get_referral_stats(test_user)
        assert "referral_count" in stats
        assert "referral_bonus" in stats
        tests.append(("get_referral_stats()", True, f"count={stats['referral_count']}"))
    except Exception as e:
        tests.append(("get_referral_stats()", False, str(e)))
    
    # set_referrer
    try:
        # Создаём нового пользователя для теста
        new_user = rate_limiter.get_user(ref_user)
        new_user.referrer_id = 0  # Сбрасываем
        result = rate_limiter.set_referrer(ref_user, test_user)
        tests.append(("set_referrer()", True, f"set={result}"))
    except Exception as e:
        tests.append(("set_referrer()", False, str(e)))
    
    # has_referral_bonus
    try:
        has_bonus = rate_limiter.has_referral_bonus(test_user)
        assert isinstance(has_bonus, bool)
        tests.append(("has_referral_bonus()", True, f"has={has_bonus}"))
    except Exception as e:
        tests.append(("has_referral_bonus()", False, str(e)))
    
    # use_referral_bonus (если есть бонусы)
    try:
        user = rate_limiter.get_user(test_user)
        user.referral_bonus = 1  # Даём 1 бонус для теста
        used = rate_limiter.use_referral_bonus(test_user)
        assert used == True
        tests.append(("use_referral_bonus()", True, f"used={used}"))
    except Exception as e:
        tests.append(("use_referral_bonus()", False, str(e)))
    
    return tests

for name, ok, info in test_referral():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"REFERRAL {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. RATE_LIMITER - BAN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("7️⃣ RATE_LIMITER - Система банов")
print("─" * 70)

def test_ban_system():
    tests = []
    ban_user = test_user + 2000
    
    # ban_user
    try:
        rate_limiter.ban_user(ban_user, "test reason")
        is_banned = rate_limiter.is_banned(ban_user)
        assert is_banned == True
        tests.append(("ban_user()", True, f"banned=True"))
    except Exception as e:
        tests.append(("ban_user()", False, str(e)))
    
    # get_ban_reason
    try:
        reason = rate_limiter.get_ban_reason(ban_user)
        assert reason == "test reason"
        tests.append(("get_ban_reason()", True, f"reason={reason}"))
    except Exception as e:
        tests.append(("get_ban_reason()", False, str(e)))
    
    # get_banned_users
    try:
        banned = rate_limiter.get_banned_users()
        assert isinstance(banned, list)
        tests.append(("get_banned_users()", True, f"count={len(banned)}"))
    except Exception as e:
        tests.append(("get_banned_users()", False, str(e)))
    
    # unban_user
    try:
        rate_limiter.unban_user(ban_user)
        is_banned = rate_limiter.is_banned(ban_user)
        assert is_banned == False
        tests.append(("unban_user()", True, f"banned=False"))
    except Exception as e:
        tests.append(("unban_user()", False, str(e)))
    
    return tests

for name, ok, info in test_ban_system():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"BAN {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. RATE_LIMITER - v2.8.0 FEATURES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("8️⃣ RATE_LIMITER - v2.8.0 Новые функции")
print("─" * 70)

def test_v28_features():
    tests = []
    
    # TRIAL VIP
    try:
        can = rate_limiter.can_use_trial(test_user)
        used = rate_limiter.is_trial_used(test_user)
        tests.append(("can_use_trial()", True, f"can={can}, used={used}"))
    except Exception as e:
        tests.append(("can_use_trial()", False, str(e)))
    
    # STREAK
    try:
        streak, bonus = rate_limiter.update_streak(test_user)
        assert isinstance(streak, int)
        tests.append(("update_streak()", True, f"streak={streak}, bonus={bonus}"))
    except Exception as e:
        tests.append(("update_streak()", False, str(e)))
    
    try:
        info = rate_limiter.get_streak(test_user)
        assert "streak" in info
        assert "has_bonus" in info
        tests.append(("get_streak()", True, f"streak={info['streak']}"))
    except Exception as e:
        tests.append(("get_streak()", False, str(e)))
    
    try:
        bonus = rate_limiter.get_streak_bonus_videos(test_user)
        assert isinstance(bonus, int)
        tests.append(("get_streak_bonus_videos()", True, f"bonus={bonus}"))
    except Exception as e:
        tests.append(("get_streak_bonus_videos()", False, str(e)))
    
    # FAVORITES
    try:
        rate_limiter.save_favorite(test_user, "test_preset")
        tests.append(("save_favorite()", True, "saved"))
    except Exception as e:
        tests.append(("save_favorite()", False, str(e)))
    
    try:
        favs = rate_limiter.get_favorites(test_user)
        assert isinstance(favs, list)
        tests.append(("get_favorites()", True, f"count={len(favs)}"))
    except Exception as e:
        tests.append(("get_favorites()", False, str(e)))
    
    try:
        loaded = rate_limiter.load_favorite(test_user, "test_preset")
        tests.append(("load_favorite()", True, f"loaded={loaded}"))
    except Exception as e:
        tests.append(("load_favorite()", False, str(e)))
    
    try:
        deleted = rate_limiter.delete_favorite(test_user, "test_preset")
        tests.append(("delete_favorite()", True, f"deleted={deleted}"))
    except Exception as e:
        tests.append(("delete_favorite()", False, str(e)))
    
    # LOGS
    try:
        rate_limiter.add_log(test_user, "test_operation", "test_details")
        tests.append(("add_log()", True, "added"))
    except Exception as e:
        tests.append(("add_log()", False, str(e)))
    
    try:
        logs = rate_limiter.get_logs(test_user, 10)
        assert isinstance(logs, list)
        tests.append(("get_logs()", True, f"count={len(logs)}"))
    except Exception as e:
        tests.append(("get_logs()", False, str(e)))
    
    return tests

for name, ok, info in test_v28_features():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"v2.8 {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. RATE_LIMITER - PROMO CODES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("9️⃣ RATE_LIMITER - Промо-коды")
print("─" * 70)

def test_promo_codes():
    tests = []
    
    # create_promo_code
    try:
        created = rate_limiter.create_promo_code("TESTCODE123", "videos", 5, 10)
        tests.append(("create_promo_code()", True, f"created={created}"))
    except Exception as e:
        tests.append(("create_promo_code()", False, str(e)))
    
    # list_promo_codes
    try:
        codes = rate_limiter.list_promo_codes()
        assert isinstance(codes, list)
        tests.append(("list_promo_codes()", True, f"count={len(codes)}"))
    except Exception as e:
        tests.append(("list_promo_codes()", False, str(e)))
    
    # activate_promo_code
    try:
        promo_user = test_user + 5000
        success, msg = rate_limiter.activate_promo_code(promo_user, "TESTCODE123")
        tests.append(("activate_promo_code()", True, f"success={success}, msg={msg}"))
    except Exception as e:
        tests.append(("activate_promo_code()", False, str(e)))
    
    # delete_promo_code
    try:
        deleted = rate_limiter.delete_promo_code("TESTCODE123")
        tests.append(("delete_promo_code()", True, f"deleted={deleted}"))
    except Exception as e:
        tests.append(("delete_promo_code()", False, str(e)))
    
    return tests

for name, ok, info in test_promo_codes():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"PROMO {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. RATE_LIMITER - HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("🔟 RATE_LIMITER - История")
print("─" * 70)

def test_history():
    tests = []
    
    # add_to_history
    try:
        rate_limiter.add_to_history(test_user, "tiktok", "file")
        tests.append(("add_to_history()", True, "added"))
    except Exception as e:
        tests.append(("add_to_history()", False, str(e)))
    
    # get_history
    try:
        history = rate_limiter.get_history(test_user, 10)
        assert isinstance(history, list)
        tests.append(("get_history()", True, f"count={len(history)}"))
    except Exception as e:
        tests.append(("get_history()", False, str(e)))
    
    return tests

for name, ok, info in test_history():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"HISTORY {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 11. RATE_LIMITER - DATA PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("1️⃣1️⃣ RATE_LIMITER - Сохранение данных")
print("─" * 70)

def test_persistence():
    tests = []
    
    # save_data
    try:
        rate_limiter.save_data()
        tests.append(("save_data()", True, "saved"))
    except Exception as e:
        tests.append(("save_data()", False, str(e)))
    
    # export_backup
    try:
        backup = rate_limiter.export_backup()
        assert isinstance(backup, str)
        assert len(backup) > 0
        tests.append(("export_backup()", True, f"size={len(backup)} bytes"))
    except Exception as e:
        tests.append(("export_backup()", False, str(e)))
    
    return tests

for name, ok, info in test_persistence():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"PERSIST {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# 12. FFMPEG_UTILS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("1️⃣2️⃣ FFMPEG_UTILS")
print("─" * 70)

def test_ffmpeg_utils():
    tests = []
    
    # get_temp_dir
    try:
        temp = get_temp_dir()
        assert temp.exists()
        tests.append(("get_temp_dir()", True, f"path={temp}"))
    except Exception as e:
        tests.append(("get_temp_dir()", False, str(e)))
    
    # generate_unique_filename
    try:
        fn = generate_unique_filename()
        assert fn.startswith("virex_")
        assert fn.endswith(".mp4")
        tests.append(("generate_unique_filename()", True, f"fn={fn[:20]}..."))
    except Exception as e:
        tests.append(("generate_unique_filename()", False, str(e)))
    
    # get_queue_size
    try:
        size = get_queue_size()
        assert isinstance(size, int)
        tests.append(("get_queue_size()", True, f"size={size}"))
    except Exception as e:
        tests.append(("get_queue_size()", False, str(e)))
    
    # get_temp_dir_size
    try:
        size_mb, count = get_temp_dir_size()
        tests.append(("get_temp_dir_size()", True, f"{size_mb}MB, {count} files"))
    except Exception as e:
        tests.append(("get_temp_dir_size()", False, str(e)))
    
    # is_maintenance_mode / set_maintenance_mode
    try:
        initial = is_maintenance_mode()
        set_maintenance_mode(True)
        assert is_maintenance_mode() == True
        set_maintenance_mode(False)
        assert is_maintenance_mode() == False
        tests.append(("maintenance_mode", True, "toggle OK"))
    except Exception as e:
        tests.append(("maintenance_mode", False, str(e)))
    
    # estimate_queue_time
    try:
        eta = estimate_queue_time(5)
        assert isinstance(eta, str)
        tests.append(("estimate_queue_time()", True, f"eta={eta}"))
    except Exception as e:
        tests.append(("estimate_queue_time()", False, str(e)))
    
    # ProgressTracker
    try:
        tracker = ProgressTracker(100.0)
        tracker.update(50.0)
        tracker.set_stage("processing")
        percent = tracker.get_percent()
        eta = tracker.get_eta()
        assert percent == 50
        tests.append(("ProgressTracker", True, f"percent={percent}%, eta={eta}"))
    except Exception as e:
        tests.append(("ProgressTracker", False, str(e)))
    
    return tests

for name, ok, info in test_ffmpeg_utils():
    status = "✅" if ok else "❌"
    print(f"   {status} {name}: {info}")
    if not ok:
        errors.append(f"FFMPEG {name}: {info}")

# ═══════════════════════════════════════════════════════════════════════════════
# ИТОГ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("📋 ИТОГОВЫЙ ОТЧЁТ")
print("=" * 70)

# Подсчёт
total_tests = 0
for section in [test_config, test_user_management, test_plans_limits, test_settings,
                test_statistics, test_referral, test_ban_system, test_v28_features,
                test_promo_codes, test_history, test_persistence, test_ffmpeg_utils]:
    total_tests += len(section())

if errors:
    print(f"\n❌ ОШИБКИ ({len(errors)}):")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print(f"\n✅ ВСЕ {total_tests} ФУНКЦИЙ ПРОВЕРЕНЫ УСПЕШНО!")
    print("=" * 70)
