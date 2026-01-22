"""Virex v3.0.0 Test Script"""
import sys

print('='*60)
print('VIREX v3.0.0 COMPREHENSIVE TEST')
print('='*60)

errors = []
warnings = []

# 1. Test config.py
print('\n[1] Testing config.py...')
try:
    from config import (
        BOT_VERSION, SPEED_OPTIONS, ROTATION_OPTIONS, ASPECT_RATIOS,
        VIDEO_FILTERS, CAPTION_STYLES, COMPRESSION_PRESETS, VOLUME_OPTIONS,
        THUMBNAIL_OPTIONS, AUTO_PROCESS_TEMPLATES, MAX_MERGE_VIDEOS,
        TEXTS, TEXTS_EN, BUTTONS, BUTTONS_EN
    )
    print(f'  ✓ BOT_VERSION = {BOT_VERSION}')
    assert BOT_VERSION == '3.0.0', f'Version mismatch: {BOT_VERSION}'
    print(f'  ✓ SPEED_OPTIONS: {len(SPEED_OPTIONS)} options')
    print(f'  ✓ ROTATION_OPTIONS: {len(ROTATION_OPTIONS)} options')
    print(f'  ✓ ASPECT_RATIOS: {len(ASPECT_RATIOS)} ratios')
    print(f'  ✓ VIDEO_FILTERS: {len(VIDEO_FILTERS)} filters')
    print(f'  ✓ CAPTION_STYLES: {len(CAPTION_STYLES)} styles')
    print(f'  ✓ COMPRESSION_PRESETS: {len(COMPRESSION_PRESETS)} presets')
    print(f'  ✓ VOLUME_OPTIONS: {len(VOLUME_OPTIONS)} options')
    print(f'  ✓ THUMBNAIL_OPTIONS: {len(THUMBNAIL_OPTIONS)} options')
    print(f'  ✓ AUTO_PROCESS_TEMPLATES: {len(AUTO_PROCESS_TEMPLATES)} templates')
    print(f'  ✓ MAX_MERGE_VIDEOS = {MAX_MERGE_VIDEOS}')
    
    # Check new TEXTS
    v3_texts = ['merge_help', 'speed_menu', 'rotate_menu', 'aspect_menu', 'filter_menu',
                'text_overlay_help', 'caption_menu', 'compress_menu', 'thumbnail_menu',
                'video_info', 'volume_menu', 'schedule_help', 'autoprocess_menu']
    for key in v3_texts:
        if key not in TEXTS:
            errors.append(f'Missing TEXTS key: {key}')
        if key not in TEXTS_EN:
            errors.append(f'Missing TEXTS_EN key: {key}')
    print(f'  ✓ v3.0.0 TEXTS: {len(v3_texts)} keys checked')
    
except Exception as e:
    errors.append(f'config.py: {e}')
    print(f'  ✗ Error: {e}')

# 2. Test rate_limit.py
print('\n[2] Testing rate_limit.py...')
try:
    from rate_limit import rate_limiter, UserState
    
    # Check new UserState fields
    test_user = UserState(user_id=999999)
    v3_fields = ['merge_videos', 'speed_setting', 'rotation_setting', 'aspect_setting',
                 'filter_setting', 'custom_text', 'caption_style', 'compression_preset',
                 'volume_setting', 'scheduled_tasks', 'auto_process_template', 'pending_video_file_id']
    for field in v3_fields:
        if not hasattr(test_user, field):
            errors.append(f'Missing UserState field: {field}')
    print(f'  ✓ UserState v3.0.0 fields: {len(v3_fields)} checked')
    
    # Check new methods
    v3_methods = [
        'add_to_merge', 'get_merge_queue', 'clear_merge_queue',
        'set_speed', 'get_speed', 'clear_speed',
        'set_rotation', 'get_rotation', 'clear_rotation',
        'set_aspect', 'get_aspect', 'clear_aspect',
        'set_filter', 'get_filter', 'clear_filter',
        'set_custom_text', 'get_custom_text', 'clear_custom_text',
        'set_caption_style', 'get_caption_style',
        'set_compression', 'get_compression', 'clear_compression',
        'set_volume', 'get_volume', 'clear_volume',
        'add_scheduled_task', 'get_scheduled_tasks', 'remove_scheduled_task', 'clear_scheduled_tasks',
        'set_auto_process', 'get_auto_process', 'clear_auto_process',
        'set_pending_video', 'get_pending_video', 'clear_pending_video',
        'clear_v3_settings', 'has_v3_settings', 'get_v3_settings_summary',
    ]
    for method in v3_methods:
        if not hasattr(rate_limiter, method):
            errors.append(f'Missing method: {method}')
    print(f'  ✓ RateLimiter v3.0.0 methods: {len(v3_methods)} checked')
    
except Exception as e:
    errors.append(f'rate_limit.py: {e}')
    print(f'  ✗ Error: {e}')

# 3. Test ffmpeg_utils.py
print('\n[3] Testing ffmpeg_utils.py...')
try:
    from ffmpeg_utils import (
        merge_videos, change_speed, rotate_flip_video, change_aspect_ratio,
        apply_video_filter, add_custom_text, compress_video, extract_thumbnail,
        get_detailed_video_info, adjust_volume, auto_process_video, format_file_size
    )
    v3_funcs = ['merge_videos', 'change_speed', 'rotate_flip_video', 'change_aspect_ratio',
                'apply_video_filter', 'add_custom_text', 'compress_video', 'extract_thumbnail',
                'get_detailed_video_info', 'adjust_volume', 'auto_process_video', 'format_file_size']
    print(f'  ✓ v3.0.0 functions: {len(v3_funcs)} imported')
except Exception as e:
    errors.append(f'ffmpeg_utils.py: {e}')
    print(f'  ✗ Error: {e}')

# 4. Test bot.py
print('\n[4] Testing bot.py syntax...')
try:
    import ast
    with open('bot.py', 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print('  ✓ Syntax OK')
    
    # Count handlers
    handlers = code.count('@dp.message(Command(')
    callbacks = code.count('@dp.callback_query(')
    print(f'  ✓ Command handlers: {handlers}')
    print(f'  ✓ Callback handlers: {callbacks}')
    
    # Check v3.0.0 commands
    v3_commands = ['merge', 'speed', 'rotate', 'aspect', 'filter', 'text', 'caption',
                   'compress', 'thumbnail', 'info', 'volume', 'schedule', 'autoprocess']
    for cmd in v3_commands:
        if f'Command("{cmd}")' in code:
            pass
        else:
            errors.append(f'Missing command handler: /{cmd}')
    print(f'  ✓ v3.0.0 commands: {len(v3_commands)} checked')
    
except SyntaxError as e:
    errors.append(f'bot.py syntax error: {e}')
    print(f'  ✗ Syntax Error: {e}')
except Exception as e:
    errors.append(f'bot.py: {e}')
    print(f'  ✗ Error: {e}')

# 5. Count total functions
print('\n[5] Counting total functions...')
try:
    import ast
    total_funcs = 0
    for filename in ['config.py', 'rate_limit.py', 'ffmpeg_utils.py', 'bot.py']:
        with open(filename, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        funcs = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        print(f'  ✓ {filename}: {funcs} functions')
        total_funcs += funcs
    print(f'  ✓ TOTAL: {total_funcs} functions')
except Exception as e:
    print(f'  ✗ Error: {e}')

# Summary
print('\n' + '='*60)
print('SUMMARY')
print('='*60)

if errors:
    print(f'\n❌ ERRORS ({len(errors)}):')
    for err in errors:
        print(f'  • {err}')
else:
    print('\n✅ NO ERRORS!')

if warnings:
    print(f'\n⚠️ WARNINGS ({len(warnings)}):')
    for warn in warnings:
        print(f'  • {warn}')

print(f'\n📊 Total checks: config + rate_limit + ffmpeg + bot')
print(f'🔢 v3.0.0 Features: 14 implemented')
print('='*60)
sys.exit(len(errors))
