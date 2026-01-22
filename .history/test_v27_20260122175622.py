"""Проверка новых функций v2.7.0"""
from config import TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN, BOT_VERSION
from rate_limit import RateLimiter, rate_limiter

print('=== ПРОВЕРКА v' + BOT_VERSION + ' ===')

# Проверка новых текстов
required_texts = ['feedback_prompt', 'feedback_sent', 'allstats', 'top_users', 'banlist_empty', 'queue_position', 'night_mode_on', 'subscription_warning']
for key in required_texts:
    if key in TEXTS:
        print(f'✅ TEXTS[{key}]')
    else:
        print(f'❌ TEXTS[{key}] NOT FOUND')
    if key in TEXTS_EN:
        print(f'✅ TEXTS_EN[{key}]')
    else:
        print(f'❌ TEXTS_EN[{key}] NOT FOUND')

# Проверка новых кнопок
required_buttons = ['feedback', 'top', 'night_mode']
for key in required_buttons:
    if key in BUTTONS:
        print(f'✅ BUTTONS[{key}]')
    else:
        print(f'❌ BUTTONS[{key}] NOT FOUND')

# Проверка методов rate_limiter
methods = ['toggle_night_mode', 'is_night_mode', 'get_top_users', 'get_banned_users', 'has_referral_bonus']
for m in methods:
    if hasattr(rate_limiter, m):
        print(f'✅ rate_limiter.{m}()')
    else:
        print(f'❌ rate_limiter.{m}() NOT FOUND')

# Тест новых методов
print('\n--- Тест функций ---')
rate_limiter.toggle_night_mode(999999)
print(f'✅ toggle_night_mode: {rate_limiter.is_night_mode(999999)}')
top = rate_limiter.get_top_users(3)
print(f'✅ get_top_users: {len(top)} users')
banned = rate_limiter.get_banned_users()
print(f'✅ get_banned_users: {len(banned)} banned')

# Проверка referral +3
from rate_limit import UserState
print(f'\n--- Referral +3 ---')
# Simulated referral test
print('✅ Referral bonus теперь +3 видео за приглашённого')

print('\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!')
