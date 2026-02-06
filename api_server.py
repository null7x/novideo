"""
VIREX API Server для Android приложения
Работает параллельно с Telegram ботом
"""

import os
import asyncio
import hashlib
import hmac
import json
import tempfile
import time
import uuid
from datetime import datetime
from typing import Optional

from aiohttp import web
import aiofiles

# Импорты из основного бота
from config import BOT_TOKEN
from rate_limit import RateLimiter

# Инициализация rate limiter для доступа к данным пользователей
rate_limiter = RateLimiter()

# ══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

API_PORT = int(os.getenv("API_PORT", 8080))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB - без ограничений
TEMP_DIR = os.path.join(tempfile.gettempdir(), "virex_api")
os.makedirs(TEMP_DIR, exist_ok=True)

SESSIONS_FILE = "api_sessions.json"

# Активные сессии (user_id -> session_token)
active_sessions = {}

def load_sessions():
    """Загрузка сессий с диска"""
    global active_sessions
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Конвертируем ключи обратно в int
                active_sessions = {int(k): v for k, v in data.items()}
                print(f"[API] Loaded {len(active_sessions)} sessions")
        except Exception as e:
            print(f"[API] Failed to load sessions: {e}")
            active_sessions = {}

def save_sessions():
    """Сохранение сессий на диск"""
    try:
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(active_sessions, f)
    except Exception as e:
        print(f"[API] Failed to save sessions: {e}")

# Загружаем сессии при старте
load_sessions()

# ══════════════════════════════════════════════════════════════════════════════
# АВТОРИЗАЦИЯ ЧЕРЕЗ TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════

def verify_telegram_auth(auth_data: dict) -> bool:
    """Проверка авторизации через Telegram Login Widget"""
    check_hash = auth_data.pop('hash', None)
    if not check_hash:
        return False
    
    # Проверяем время (не старше 1 дня)
    auth_date = int(auth_data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return False
    
    # Формируем строку для проверки
    data_check_string = '\n'.join(
        f"{k}={v}" for k, v in sorted(auth_data.items())
    )
    
    # Создаем секретный ключ из токена бота
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    
    # Вычисляем хеш
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return calculated_hash == check_hash


def create_session(user_id: int) -> str:
    """Создание сессии для пользователя"""
    token = str(uuid.uuid4())
    active_sessions[user_id] = {
        'token': token,
        'created': time.time()
    }
    save_sessions()  # Сохраняем на диск
    return token


def verify_session(user_id: int, token: str) -> bool:
    """Проверка валидности сессии"""
    session = active_sessions.get(user_id)
    if not session:
        return False
    
    # Сессия живёт 7 дней
    if time.time() - session['created'] > 7 * 86400:
        del active_sessions[user_id]
        return False
    
    return session['token'] == token


def get_user_subscription(user_id: int) -> dict:
    """Получение информации о подписке пользователя"""
    user = rate_limiter.get_user(user_id)
    
    is_premium = user.plan in ('vip', 'premium')
    
    # Получаем дату окончания из users_data.json
    expires = 0
    try:
        with open("users_data.json", 'r', encoding='utf-8') as f:
            users_data = json.load(f)
            user_data = users_data.get(str(user_id), {})
            expires = user_data.get('subscription_expires', 0)
    except:
        pass
    
    return {
        'is_premium': is_premium,
        'plan': user.plan if user.plan else 'free',
        'subscription': {
            'type': user.plan if user.plan else 'free',
            'expires': expires
        },
        'videos_today': user.daily_videos,
        'total_videos': user.total_videos,
        'daily_limit': -1 if is_premium else 3,  # -1 = безлимит
        'max_file_size': 500 if is_premium else 100  # MB
    }


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

routes = web.RouteTableDef()


@routes.get('/api/health')
async def health_check(request):
    """Проверка работоспособности API"""
    return web.json_response({
        'status': 'ok',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })


@routes.post('/api/auth/telegram')
async def auth_telegram(request):
    """Авторизация через Telegram"""
    try:
        data = await request.json()
        
        # Проверяем данные от Telegram
        if not verify_telegram_auth(data.copy()):
            return web.json_response({
                'error': 'Invalid Telegram auth data'
            }, status=401)
        
        user_id = int(data['id'])
        username = data.get('username', '')
        first_name = data.get('first_name', '')
        
        # Создаём сессию
        token = create_session(user_id)
        
        # Получаем информацию о подписке
        subscription = get_user_subscription(user_id)
        
        return web.json_response({
            'success': True,
            'token': token,
            'user': {
                'id': user_id,
                'username': username,
                'first_name': first_name
            },
            'subscription': subscription
        })
        
    except Exception as e:
        return web.json_response({
            'error': str(e)
        }, status=500)


@routes.post('/api/auth/deeplink')
async def auth_deeplink(request):
    """Авторизация через deep link (упрощённая)"""
    try:
        data = await request.json()
        
        user_id = data.get('user_id')
        auth_code = data.get('auth_code')
        
        if not user_id or not auth_code:
            return web.json_response({
                'error': 'Missing user_id or auth_code'
            }, status=400)
        
        # Проверяем код авторизации (он генерируется ботом и хранится в users_data.json)
        import json
        users_file = "users_data.json"
        users_data = {}
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
        
        user_data = users_data.get(str(user_id), {})
        stored_code = user_data.get('app_auth_code')
        
        if not stored_code or stored_code != auth_code:
            return web.json_response({
                'error': 'Invalid auth code. Get new code from bot.'
            }, status=401)
        
        # Удаляем использованный код
        user_data.pop('app_auth_code', None)
        users_data[str(user_id)] = user_data
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        
        # Создаём сессию
        token = create_session(int(user_id))
        subscription = get_user_subscription(int(user_id))
        
        return web.json_response({
            'success': True,
            'token': token,
            'user': {
                'id': int(user_id),
                'username': user_data.get('username', ''),
                'first_name': user_data.get('first_name', '')
            },
            'subscription': subscription
        })
        
    except Exception as e:
        return web.json_response({
            'error': str(e)
        }, status=500)


@routes.get('/api/user/subscription')
async def get_subscription(request):
    """Получение информации о подписке"""
    user_id = request.headers.get('X-User-Id')
    token = request.headers.get('X-Auth-Token')
    
    if not user_id or not token:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    if not verify_session(int(user_id), token):
        return web.json_response({'error': 'Session expired'}, status=401)
    
    subscription = get_user_subscription(int(user_id))
    return web.json_response(subscription)


@routes.get('/api/templates')
async def get_templates(request):
    """Список доступных шаблонов"""
    templates = [
        # Бесплатные шаблоны
        {
            'id': 'tiktok', 
            'name': 'TikTok', 
            'description': 'Оптимизация для TikTok: 9:16, высокий битрейт',
            'category': 'social',
            'isPremium': False,
            'effects': ['optimize', 'metadata_clean']
        },
        {
            'id': 'reels', 
            'name': 'Instagram Reels', 
            'description': 'Идеально для Reels и Stories',
            'category': 'social',
            'isPremium': False,
            'effects': ['optimize', 'metadata_clean']
        },
        {
            'id': 'youtube', 
            'name': 'YouTube Shorts', 
            'description': 'Оптимизация для YouTube Shorts',
            'category': 'social',
            'isPremium': False,
            'effects': ['optimize', 'metadata_clean']
        },
        {
            'id': 'clean', 
            'name': 'Чистое видео', 
            'description': 'Минимальная обработка, сохранение качества',
            'category': 'basic',
            'isPremium': False,
            'effects': ['metadata_clean']
        },
        # Premium шаблоны
        {
            'id': 'watermark_trap', 
            'name': '🛡️ Watermark-Trap', 
            'description': 'Защита от детекции + уникализация',
            'category': 'protection',
            'isPremium': True,
            'effects': ['watermark_trap', 'metadata_clean', 'unique']
        },
        {
            'id': 'gaming', 
            'name': '🎮 Gaming', 
            'description': 'Для игровых клипов: яркость, контраст',
            'category': 'effects',
            'isPremium': True,
            'effects': ['gaming_color', 'optimize']
        },
        {
            'id': 'vlog', 
            'name': '📹 Vlog', 
            'description': 'Тёплые тона для влогов',
            'category': 'effects',
            'isPremium': True,
            'effects': ['warm_color', 'optimize']
        },
        {
            'id': 'cinematic', 
            'name': '🎬 Cinematic', 
            'description': 'Кинематографический стиль с letterbox',
            'category': 'effects',
            'isPremium': True,
            'effects': ['cinematic', 'letterbox', 'color_grade']
        },
        {
            'id': 'vintage', 
            'name': '📼 Vintage', 
            'description': 'Ретро VHS стиль',
            'category': 'effects',
            'isPremium': True,
            'effects': ['vintage', 'grain', 'vignette']
        },
        {
            'id': 'neon', 
            'name': '💜 Neon', 
            'description': 'Яркие неоновые цвета',
            'category': 'effects',
            'isPremium': True,
            'effects': ['neon_color', 'glow']
        },
        {
            'id': 'bw', 
            'name': '⚫ Чёрно-белое', 
            'description': 'Классическое чёрно-белое видео',
            'category': 'effects',
            'isPremium': True,
            'effects': ['grayscale', 'contrast']
        },
        {
            'id': 'speed', 
            'name': '⚡ Speed Edit', 
            'description': 'Динамичные переходы и ускорение',
            'category': 'effects',
            'isPremium': True,
            'effects': ['speed_ramp', 'transitions']
        },
        # Высокое разрешение - как у популярных видео
        {
            'id': 'viral_4k', 
            'name': '🔥 Viral 4K', 
            'description': 'Качество как у топовых блогеров 4K',
            'category': 'quality',
            'isPremium': True,
            'effects': ['upscale_4k', 'sharpen', 'denoise']
        },
        {
            'id': 'viral_8k', 
            'name': '💎 Viral 8K', 
            'description': 'Ультра качество 8K для максимального охвата',
            'category': 'quality',
            'isPremium': True,
            'effects': ['upscale_8k', 'sharpen', 'denoise']
        },
        {
            'id': 'viral_10k', 
            'name': '👑 Viral 10K', 
            'description': 'Экстремальное качество 10K',
            'category': 'quality',
            'isPremium': True,
            'effects': ['upscale_10k', 'sharpen', 'denoise']
        },
        {
            'id': 'viral_16k', 
            'name': '🚀 Viral 16K', 
            'description': 'Максимальное качество 16K',
            'category': 'quality',
            'isPremium': True,
            'effects': ['upscale_16k', 'sharpen', 'denoise']
        },
        # Паспорт видео - максимальная уникализация
        {
            'id': 'passport', 
            'name': '🔐 Паспорт', 
            'description': 'Уникальный отпечаток видео - обход любой детекции',
            'category': 'protection',
            'isPremium': True,
            'effects': ['unique_fingerprint', 'metadata_wipe', 'frame_shift', 'audio_shift']
        },
        {
            'id': 'passport_pro', 
            'name': '🛡️ Паспорт PRO', 
            'description': 'Максимальная защита + качество 4K',
            'category': 'protection',
            'isPremium': True,
            'effects': ['unique_fingerprint', 'upscale_4k', 'metadata_wipe', 'invisible_watermark']
        },
        # ═══════════════════════════════════════════════════════════════════
        # VIRAL / AESTHETIC - КАК У ТОПОВЫХ БЛОГЕРОВ
        # ═══════════════════════════════════════════════════════════════════
        {
            'id': 'viral_120fps', 
            'name': '🎬 120FPS Smooth', 
            'description': 'Плавное видео 120fps как у топов',
            'category': 'viral',
            'isPremium': True,
            'effects': ['interpolate_120fps', 'smooth', 'sharpen']
        },
        {
            'id': 'viral_8k_120fps', 
            'name': '💎 8K 120FPS', 
            'description': '8K + 120fps - максимальное качество',
            'category': 'viral',
            'isPremium': True,
            'effects': ['upscale_8k', 'interpolate_120fps', 'hdr']
        },
        {
            'id': 'avatar_style', 
            'name': '🌊 Avatar Style', 
            'description': 'Кинематографический стиль как в Аватаре',
            'category': 'viral',
            'isPremium': True,
            'effects': ['avatar_colors', 'cinematic', '120fps', 'hdr']
        },
        {
            'id': 'aesthetic_hdr', 
            'name': '✨ Aesthetic HDR', 
            'description': 'HDR эффект + насыщенные цвета',
            'category': 'viral',
            'isPremium': True,
            'effects': ['hdr_effect', 'vibrant', 'glow']
        },
        {
            'id': 'movie_quality', 
            'name': '🎥 Movie Quality', 
            'description': 'Качество как в кино - 4K 60fps HDR',
            'category': 'viral',
            'isPremium': True,
            'effects': ['upscale_4k', '60fps', 'film_grain', 'color_grade']
        },
        {
            'id': 'ultra_viral', 
            'name': '🔥 Ultra Viral', 
            'description': 'Максимум качества для вирусного видео',
            'category': 'viral',
            'isPremium': True,
            'effects': ['upscale_4k', 'interpolate_60fps', 'sharpen', 'vibrant', 'unique']
        },
    ]
    return web.json_response({
        'templates': templates,
        'categories': [
            {'id': 'social', 'name': 'Соц. сети'},
            {'id': 'basic', 'name': 'Базовые'},
            {'id': 'protection', 'name': 'Защита'},
            {'id': 'effects', 'name': 'Эффекты'},
            {'id': 'quality', 'name': 'Качество'},
            {'id': 'viral', 'name': '🔥 Viral'}
        ]
    })


@routes.post('/api/video/process')
async def process_video_api(request):
    """Обработка видео"""
    user_id = request.headers.get('X-User-Id')
    token = request.headers.get('X-Auth-Token')
    
    if not user_id or not token:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    if not verify_session(int(user_id), token):
        return web.json_response({'error': 'Session expired'}, status=401)
    
    # Проверяем подписку для некоторых шаблонов
    subscription = get_user_subscription(int(user_id))
    is_premium = subscription['is_premium']
    
    # Премиум шаблоны
    premium_templates = [
        'watermark_trap', 'gaming', 'vlog', 'cinematic', 'vintage', 'neon', 'bw', 'speed',
        'viral_4k', 'viral_8k', 'viral_10k', 'viral_16k', 'passport', 'passport_pro',
        'viral_120fps', 'viral_8k_120fps', 'avatar_style', 'aesthetic_hdr', 'movie_quality', 'ultra_viral'
    ]
    
    try:
        # Читаем multipart данные
        reader = await request.multipart()
        
        video_data = None
        template = 'tiktok'
        text_overlay = None
        
        async for part in reader:
            print(f"[API] Received part: name='{part.name}', filename='{part.filename}'")
            if part.name == 'video':
                # Сохраняем видео во временный файл
                input_path = os.path.join(TEMP_DIR, f"input_{user_id}_{uuid.uuid4().hex}.mp4")
                async with aiofiles.open(input_path, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        await f.write(chunk)
                video_data = input_path
                
            elif part.name == 'template':
                raw_template = await part.read()
                template = raw_template.decode().strip()
                print(f"[API] Raw template bytes: {raw_template}")
                print(f"[API] Parsed template: '{template}'")
                
            elif part.name == 'text':
                text_overlay = (await part.read()).decode().strip()
        
        if not video_data:
            return web.json_response({'error': 'No video provided'}, status=400)
        
        print(f"[API] Received video: {video_data}, size: {os.path.getsize(video_data)} bytes")
        print(f"[API] Requested template: {template}")
        
        # Проверяем премиум шаблоны
        if template in premium_templates and not is_premium:
            os.remove(video_data)
            return web.json_response({
                'error': 'Этот шаблон доступен только для Premium пользователей'
            }, status=403)
        
        # Проверяем размер файла
        file_size = os.path.getsize(video_data)
        max_size = subscription['max_file_size'] * 1024 * 1024
        if file_size > max_size:
            os.remove(video_data)
            return web.json_response({
                'error': f'Файл слишком большой. Максимум: {subscription["max_file_size"]}MB'
            }, status=400)
        
        # Проверяем дневной лимит для бесплатных
        if not is_premium and subscription['daily_limit'] > 0:
            if subscription['videos_today'] >= subscription['daily_limit']:
                os.remove(video_data)
                return web.json_response({
                    'error': f'Достигнут дневной лимит ({subscription["daily_limit"]} видео). Оформите Premium для безлимита.'
                }, status=429)
        
        # Генерируем путь для выходного файла
        output_path = os.path.join(TEMP_DIR, f"output_{user_id}_{uuid.uuid4().hex}.mp4")
        
        # Строим FFmpeg команду в зависимости от шаблона
        from config import FFMPEG_PATH
        
        cmd = build_ffmpeg_command(template, video_data, output_path, text_overlay)
        
        print(f"[API] Template: {template}")
        print(f"[API] Input: {video_data}")
        print(f"[API] Output: {output_path}")
        print(f"[API] FFmpeg command: {' '.join(cmd[:10])}...")
        
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            success = result.returncode == 0 and os.path.exists(output_path)
            print(f"[API] FFmpeg return code: {result.returncode}")
            print(f"[API] Output exists: {os.path.exists(output_path)}")
            if not success:
                print(f"[API] FFmpeg error: {result.stderr.decode()[:500]}")
            else:
                output_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                print(f"[API] Output size: {output_size} bytes")
        except Exception as e:
            print(f"[API] FFmpeg exception: {e}")
            success = False
        
        # Удаляем входной файл
        if os.path.exists(video_data):
            os.remove(video_data)
        
        if not success or not os.path.exists(output_path):
            return web.json_response({
                'error': 'Ошибка обработки видео'
            }, status=500)
        
        # Обновляем статистику пользователя через rate_limiter
        user = rate_limiter.get_user(int(user_id))
        user.total_videos += 1
        user.daily_videos += 1
        rate_limiter.save_data()
        
        # Возвращаем обработанное видео
        return web.FileResponse(
            output_path,
            headers={
                'Content-Disposition': f'attachment; filename="virex_processed.mp4"'
            }
        )
        
    except Exception as e:
        print(f"[API] Error: {e}")
        return web.json_response({
            'error': str(e)
        }, status=500)


def build_ffmpeg_command(template: str, input_path: str, output_path: str, text_overlay: str = None) -> list:
    """Строит FFmpeg команду в зависимости от шаблона"""
    from config import FFMPEG_PATH
    
    base_cmd = [FFMPEG_PATH, '-y', '-i', input_path]
    
    # Базовые фильтры для уникализации
    unique_filters = []
    
    # Добавляем случайные микро-изменения для уникальности
    import random
    hue_shift = random.uniform(-2, 2)
    brightness = random.uniform(-0.02, 0.02)
    saturation = random.uniform(0.98, 1.02)
    
    if template == 'tiktok':
        # TikTok: 9:16, высокий битрейт, уникализация
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}',
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-b:v', '8M']
        
    elif template == 'reels':
        # Instagram Reels
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}',
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-b:v', '6M']
        
    elif template == 'youtube':
        # YouTube Shorts
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}',
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-b:v', '10M']
        
    elif template == 'clean':
        # Минимальная обработка
        unique_filters = [f'hue=h={hue_shift}:s={saturation}']
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
        
    elif template == 'watermark_trap':
        # Watermark-Trap защита
        trap_x = random.randint(5, 15)
        trap_y = random.randint(5, 15)
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.01',
            f'crop=iw-{trap_x}:ih-{trap_y}:{trap_x//2}:{trap_y//2}',
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
            'noise=c0s=3:allf=t'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
        
    elif template == 'gaming':
        # Gaming: яркие цвета
        unique_filters = [
            f'hue=h={hue_shift}:s=1.15',
            'eq=brightness=0.05:contrast=1.1:saturation=1.2',
            'unsharp=5:5:1.0'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
        
    elif template == 'vlog':
        # Vlog: тёплые тона
        unique_filters = [
            f'hue=h={hue_shift + 5}:s=1.05',
            'eq=brightness=0.03:contrast=1.05',
            'colorbalance=rs=0.1:gs=0.05:bs=-0.05'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20']
        
    elif template == 'cinematic':
        # Cinematic: letterbox + color grade
        unique_filters = [
            f'hue=h={hue_shift}:s=0.9',
            'eq=brightness=-0.05:contrast=1.15',
            'colorbalance=rs=-0.1:bs=0.1',
            'crop=iw:ih*0.85:0:ih*0.075',
            'pad=iw:iw*16/9:(ow-iw)/2:(oh-ih)/2:black'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '18']
        
    elif template == 'vintage':
        # Vintage: ретро VHS
        unique_filters = [
            'curves=vintage',
            'noise=c0s=15:allf=t',
            'eq=brightness=-0.05:contrast=0.9:saturation=0.7',
            'vignette=PI/4'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '22']
        
    elif template == 'neon':
        # Neon: яркие неоновые цвета
        unique_filters = [
            f'hue=h={hue_shift}:s=1.5',
            'eq=brightness=0.1:contrast=1.3:saturation=1.8',
            'colorbalance=rs=0.2:gs=-0.1:bs=0.3'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
        
    elif template == 'bw':
        # Black & White
        unique_filters = [
            'hue=s=0',
            'eq=brightness=0.02:contrast=1.2'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20']
        
    elif template == 'speed':
        # Speed Edit: ускорение
        speed_factor = random.uniform(1.1, 1.3)
        unique_filters = [
            f'setpts={1/speed_factor}*PTS',
            f'hue=h={hue_shift}:s={saturation}',
            'eq=contrast=1.1'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
    
    # ═══════════════════════════════════════════════════════════════════
    # ВЫСОКОЕ РАЗРЕШЕНИЕ - КАК У ПОПУЛЯРНЫХ ВИДЕО
    # ═══════════════════════════════════════════════════════════════════
    
    elif template == 'viral_4k':
        # Viral 4K: апскейл до 4K с улучшением
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.05',
            'scale=3840:-2:flags=lanczos',  # 4K с сохранением пропорций
            'unsharp=5:5:0.8:5:5:0.4',  # Резкость
            'hqdn3d=1.5:1.5:6:6'  # Шумоподавление
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-b:v', '35M']
        
    elif template == 'viral_8k':
        # Viral 8K: апскейл до 8K
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.05',
            'scale=7680:-2:flags=lanczos',  # 8K с сохранением пропорций
            'unsharp=5:5:1.0:5:5:0.5',
            'hqdn3d=2:2:8:8'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-b:v', '80M']
        
    elif template == 'viral_10k':
        # Viral 10K: экстремальный апскейл
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.05',
            'scale=10240:-2:flags=lanczos',  # 10K с сохранением пропорций
            'unsharp=5:5:1.2:5:5:0.6',
            'hqdn3d=2:2:8:8'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '10', '-b:v', '120M']
        
    elif template == 'viral_16k':
        # Viral 16K: максимальный апскейл
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.05',
            'scale=15360:-2:flags=lanczos',  # 16K с сохранением пропорций
            'unsharp=5:5:1.5:5:5:0.8',
            'hqdn3d=2.5:2.5:10:10'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '8', '-b:v', '200M']
    
    # ═══════════════════════════════════════════════════════════════════
    # ПАСПОРТ - УНИКАЛЬНЫЙ ОТПЕЧАТОК ВИДЕО
    # ═══════════════════════════════════════════════════════════════════
    
    elif template == 'passport':
        # Паспорт: максимальная уникализация для обхода детекции
        # Случайные параметры для каждого видео
        crop_x = random.randint(2, 8)
        crop_y = random.randint(2, 8)
        noise_level = random.uniform(1, 3)
        speed_shift = random.uniform(0.995, 1.005)  # Микро-изменение скорости
        
        unique_filters = [
            # Сдвиг кадров и скорости
            f'setpts={speed_shift}*PTS',
            # Случайный crop для изменения хеша
            f'crop=iw-{crop_x}:ih-{crop_y}:{crop_x//2}:{crop_y//2}',
            # Цветовые сдвиги
            f'hue=h={random.uniform(-3, 3)}:s={random.uniform(0.97, 1.03)}',
            f'eq=brightness={random.uniform(-0.03, 0.03)}:contrast={random.uniform(0.98, 1.02)}',
            # Невидимый шум
            f'noise=c0s={noise_level}:allf=t',
            # Легкое размытие + резкость для изменения пикселей
            'gblur=sigma=0.3',
            'unsharp=3:3:0.5',
            # Возврат к стандартному размеру
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18']
        
    elif template == 'passport_pro':
        # Паспорт PRO: максимальная защита + качество 4K
        crop_x = random.randint(4, 12)
        crop_y = random.randint(4, 12)
        noise_level = random.uniform(0.5, 2)
        speed_shift = random.uniform(0.998, 1.002)
        
        unique_filters = [
            # Изменение тайминга
            f'setpts={speed_shift}*PTS',
            # Crop для изменения хеша
            f'crop=iw-{crop_x}:ih-{crop_y}:{crop_x//2}:{crop_y//2}',
            # Цветовая коррекция
            f'hue=h={random.uniform(-2, 2)}:s={random.uniform(0.98, 1.02)}',
            f'eq=brightness={random.uniform(-0.02, 0.02)}:contrast=1.03:saturation=1.02',
            # Апскейл до 4K (сохраняя пропорции)
            'scale=3840:-2:flags=lanczos',
            # Улучшение качества
            'unsharp=5:5:0.8',
            'hqdn3d=1:1:5:5',
            # Невидимый шум для уникальности
            f'noise=c0s={noise_level}:allf=t',
            # Виньетка (едва заметная)
            'vignette=PI/6:mode=backward'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-b:v', '35M']
    
    # ═══════════════════════════════════════════════════════════════════
    # VIRAL / AESTHETIC ШАБЛОНЫ - КАК У ТОПОВЫХ БЛОГЕРОВ
    # ═══════════════════════════════════════════════════════════════════
    
    elif template == 'viral_120fps':
        # 120FPS Smooth - интерполяция кадров
        unique_filters = [
            f'hue=h={hue_shift}:s={saturation}',
            f'eq=brightness={brightness}:contrast=1.05',
            # Интерполяция до 120fps через minterpolate
            'minterpolate=fps=120:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
            # Резкость
            'unsharp=5:5:0.8:5:5:0.4'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', '120']
        
    elif template == 'viral_8k_120fps':
        # 8K + 120FPS - максимальное качество
        unique_filters = [
            f'hue=h={hue_shift}:s=1.1',
            'eq=brightness=0.02:contrast=1.1:saturation=1.15',
            # Сначала интерполяция fps (до масштабирования!)
            'minterpolate=fps=120:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
            # Потом апскейл до 8K
            'scale=7680:-2:flags=lanczos',
            # HDR-подобный эффект
            'curves=preset=increase_contrast',
            # Резкость
            'unsharp=5:5:1.0:5:5:0.5',
            # Шумоподавление
            'hqdn3d=2:2:8:8'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '12', '-b:v', '100M', '-r', '120']
        
    elif template == 'avatar_style':
        # Avatar Style - кинематографический стиль как в Аватаре
        unique_filters = [
            f'hue=h={hue_shift}:s=1.2',
            # Цветокоррекция как в Avatar - бирюзово-оранжевые тона
            'colorbalance=rs=-0.15:gs=0.05:bs=0.2:rm=0.1:gm=0.05:bm=-0.1:rh=0.15:gh=-0.05:bh=-0.1',
            # Контраст и насыщенность
            'eq=brightness=0.03:contrast=1.15:saturation=1.25',
            # HDR-подобный эффект
            'curves=preset=lighter',
            # Резкость для четкости
            'unsharp=5:5:1.2:5:5:0.6',
            # Интерполяция до 60fps (до апскейла!)
            'minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
            # Апскейл
            'scale=3840:-2:flags=lanczos'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-b:v', '50M', '-r', '60']
        
    elif template == 'aesthetic_hdr':
        # Aesthetic HDR - HDR эффект + яркие цвета
        unique_filters = [
            f'hue=h={hue_shift}:s=1.3',
            # HDR-подобный тональный маппинг
            'eq=brightness=0.05:contrast=1.2:saturation=1.4',
            # Цветовые кривые для HDR эффекта
            'curves=preset=increase_contrast',
            'colorbalance=rs=0.1:gs=0.05:bs=0.15',
            # Резкость для HDR эффекта
            'unsharp=7:7:1.2',
            # Виньетка
            'vignette=PI/5'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '16', '-b:v', '20M']
        
    elif template == 'movie_quality':
        # Movie Quality - качество как в кино
        unique_filters = [
            f'hue=h={hue_shift}:s=0.95',
            # Кинематографическая цветокоррекция
            'eq=brightness=-0.02:contrast=1.12:saturation=0.9',
            'colorbalance=rs=-0.05:gs=0:bs=0.1',
            # Лёгкое зерно плёнки
            'noise=c0s=5:allf=t',
            # Интерполяция до 60fps (до апскейла!)
            'minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
            # Апскейл до 4K
            'scale=3840:-2:flags=lanczos',
            # Резкость
            'unsharp=5:5:0.6',
            # Лёгкая виньетка
            'vignette=PI/4'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-b:v', '40M', '-r', '60']
        
    elif template == 'ultra_viral':
        # Ultra Viral - максимум качества для вирусного видео
        crop_x = random.randint(2, 6)
        crop_y = random.randint(2, 6)
        unique_filters = [
            # Уникализация
            f'crop=iw-{crop_x}:ih-{crop_y}:{crop_x//2}:{crop_y//2}',
            f'hue=h={random.uniform(-2, 2)}:s=1.15',
            'eq=brightness=0.03:contrast=1.1:saturation=1.2',
            # Интерполяция до 60fps (до апскейла!)
            'minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
            # Апскейл до 4K
            'scale=3840:-2:flags=lanczos',
            # Улучшение качества
            'curves=preset=lighter',
            'unsharp=5:5:1.0',
            'hqdn3d=1:1:4:4',
            # Лёгкий шум для уникальности
            f'noise=c0s={random.uniform(0.5, 1.5)}:allf=t'
        ]
        video_opts = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-b:v', '40M', '-r', '60']
        
    else:
        # Default
        unique_filters = [f'hue=h={hue_shift}:s={saturation}']
        video_opts = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20']
    
    # Добавляем текстовый оверлей если есть
    if text_overlay:
        # Экранируем специальные символы для FFmpeg
        safe_text = text_overlay.replace("'", "'\\''").replace(":", "\\:")
        text_filter = f"drawtext=text='{safe_text}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=h-th-100:shadowcolor=black:shadowx=3:shadowy=3:borderw=2:bordercolor=black"
        unique_filters.append(text_filter)
    
    # Строим финальную команду
    filter_str = ','.join(unique_filters)
    
    cmd = base_cmd + ['-vf', filter_str] + video_opts + [
        '-c:a', 'aac', '-b:a', '192k',
        '-map_metadata', '-1',  # Удаляем метаданные
        '-fflags', '+bitexact',
        '-movflags', '+faststart',
        output_path
    ]
    
    return cmd


@routes.post('/api/video/info')
async def video_info_api(request):
    """Получение информации о видео"""
    user_id = request.headers.get('X-User-Id')
    token = request.headers.get('X-Auth-Token')
    
    if not user_id or not token:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    if not verify_session(int(user_id), token):
        return web.json_response({'error': 'Session expired'}, status=401)
    
    try:
        reader = await request.multipart()
        
        async for part in reader:
            if part.name == 'video':
                input_path = os.path.join(TEMP_DIR, f"info_{user_id}_{uuid.uuid4().hex}.mp4")
                async with aiofiles.open(input_path, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        await f.write(chunk)
                
                # Получаем информацию через ffprobe
                import subprocess
                from config import FFPROBE_PATH
                
                cmd = [
                    FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', input_path
                ]
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    info = json.loads(result.stdout) if result.returncode == 0 else {}
                except Exception as e:
                    info = {'error': str(e)}
                
                # Удаляем файл
                os.remove(input_path)
                
                return web.json_response(info)
        
        return web.json_response({'error': 'No video provided'}, status=400)
        
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# ЗАПУСК СЕРВЕРА
# ══════════════════════════════════════════════════════════════════════════════

async def start_api_server():
    """Запуск API сервера"""
    app = web.Application(client_max_size=MAX_FILE_SIZE)
    app.add_routes(routes)
    
    # CORS middleware
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == 'OPTIONS':
                return web.Response(headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, X-User-Id, X-Auth-Token',
                })
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        return middleware_handler
    
    app.middlewares.append(cors_middleware)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()
    
    print(f"[API] Server started on http://{API_HOST}:{API_PORT}")
    
    # Ожидаем бесконечно (Ctrl+C для остановки)
    try:
        while True:
            await asyncio.sleep(3600)  # Спим по часу
    except KeyboardInterrupt:
        print("[API] Server stopping...")
    finally:
        await runner.cleanup()
        print("[API] Server stopped")


if __name__ == '__main__':
    asyncio.run(start_api_server())
