"""
Virex — FFmpeg Video Processing (Anti-TikTok 2026)
"""
import os
import random
import asyncio
import subprocess
import tempfile
import uuid
import time
from pathlib import Path
from typing import Optional, Tuple, List
from config import (
    Mode,
    TIKTOK_VIDEO, TIKTOK_AUDIO,
    YOUTUBE_VIDEO, YOUTUBE_AUDIO,
    FFMPEG_TIMEOUT_SECONDS,
    MAX_CONCURRENT_TASKS,
    MAX_QUEUE_SIZE,
    FFMPEG_PATH,
    FFPROBE_PATH,
    Quality, QUALITY_SETTINGS, DEFAULT_QUALITY,
    # v2.8.0
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    DOWNLOAD_TIMEOUT_SECONDS,
    MEMORY_CLEANUP_INTERVAL_MINUTES,
)

processing_queue: asyncio.Queue = None
active_processes: list = []

# v2.8.0: Переменная для maintenance mode
maintenance_mode: bool = False
last_cleanup_time: float = 0

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-TIKTOK 2026: CREATIVE TEXTS
# ══════════════════════════════════════════════════════════════════════════════

CREATIVE_TEXTS = [
    "Moments like this",
    "On the road",
    "Late night drive",
    "No rush",
    "Just vibes",
    "Living it",
    "That feeling",
    "Main character energy",
    "Everyday magic",
    "Just because",
    "Mood",
    "This is it",
    "Right here",
    "Good times only",
    "Golden hour",
    "Core memory",
    "Real ones know",
    "Trust the process",
    "Different breed",
    "Built different",
]

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-STATIC CONTENT 2026: HOOK TEXTS
# ══════════════════════════════════════════════════════════════════════════════

HOOK_TEXTS = [
    "Wait for it...",
    "You need to see this",
    "Watch till the end",
    "POV",
    "This is crazy",
    "No way...",
    "Trust me on this",
    "Story time",
    "Here is the thing",
    "Let me show you",
    "Check this out",
    "You will not believe",
    "Real talk",
    "Plot twist",
    "Warning",
    "Unpopular opinion",
    "Facts only",
    "Listen up",
    "Game changer",
    "Life hack",
]

# ══════════════════════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════════════════════

def init_queue():
    global processing_queue
    processing_queue = asyncio.PriorityQueue(maxsize=MAX_QUEUE_SIZE)

def get_temp_dir() -> Path:
    temp_dir = Path(tempfile.gettempdir()) / "virex"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def generate_unique_filename(extension: str = ".mp4") -> str:
    return f"virex_{uuid.uuid4().hex[:12]}{extension}"

def cleanup_file(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"[CLEANUP] Failed to remove {filepath}: {e}")

def cleanup_old_files(max_age_seconds: int = 3600):
    """
    Очистка старых временных файлов.
    По умолчанию удаляет файлы старше 1 часа.
    """
    temp_dir = get_temp_dir()
    import time
    now = time.time()
    deleted = 0
    
    # Очистка virex_ файлов
    for f in temp_dir.glob("virex_*"):
        try:
            if now - f.stat().st_mtime > max_age_seconds:
                f.unlink()
                deleted += 1
        except Exception:
            pass
    
    # Очистка любых mp4/webm файлов старше времени
    for ext in ["*.mp4", "*.webm", "*.mkv", "*.avi", "*.mov"]:
        for f in temp_dir.glob(ext):
            try:
                if now - f.stat().st_mtime > max_age_seconds:
                    f.unlink()
                    deleted += 1
            except Exception:
                pass
    
    if deleted > 0:
        print(f"[CLEANUP] Removed {deleted} old files")
    
    return deleted

# v2.8.0: Periodic memory cleanup
async def periodic_cleanup():
    """ Периодическая очистка памяти """
    global last_cleanup_time
    while True:
        await asyncio.sleep(MEMORY_CLEANUP_INTERVAL_MINUTES * 60)
        cleanup_old_files(max_age_seconds=1800)  # 30 минут
        last_cleanup_time = time.time()
        print(f"[CLEANUP] Periodic cleanup completed")

# v2.8.0: Maintenance mode
def set_maintenance_mode(enabled: bool):
    """ Установить режим техобслуживания """
    global maintenance_mode
    maintenance_mode = enabled

def is_maintenance_mode() -> bool:
    """ Проверить режим техобслуживания """
    return maintenance_mode

# v2.8.0: Auto-retry wrapper
async def with_retry(coro_func, *args, max_retries: int = MAX_RETRY_ATTEMPTS, **kwargs):
    """
    Выполнить корутину с автоматическим повтором при ошибке.
    Returns: (success, result, attempts_made)
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = await coro_func(*args, **kwargs)
            return True, result, attempt
        except asyncio.TimeoutError as e:
            last_error = e
            print(f"[RETRY] Attempt {attempt}/{max_retries} timeout")
        except Exception as e:
            last_error = e
            print(f"[RETRY] Attempt {attempt}/{max_retries} failed: {e}")
        
        if attempt < max_retries:
            await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
    
    return False, last_error, max_retries

# v2.8.0: Progress tracking
class ProgressTracker:
    """ Трекер прогресса обработки """
    def __init__(self, total_duration: float):
        self.total_duration = total_duration
        self.current_time = 0
        self.stage = "downloading"  # downloading, processing, uploading
        self.start_time = time.time()
    
    def update(self, current_time: float):
        self.current_time = current_time
    
    def set_stage(self, stage: str):
        self.stage = stage
    
    def get_percent(self) -> int:
        if self.total_duration <= 0:
            return 0
        return min(100, int((self.current_time / self.total_duration) * 100))
    
    def get_eta(self) -> str:
        elapsed = time.time() - self.start_time
        percent = self.get_percent()
        if percent <= 0:
            return "?"
        
        total_time = elapsed / (percent / 100)
        remaining = total_time - elapsed
        
        if remaining < 60:
            return f"{int(remaining)}с"
        elif remaining < 3600:
            return f"{int(remaining // 60)}м"
        else:
            return f"{int(remaining // 3600)}ч"

# v2.8.0: Estimate queue wait time
def estimate_queue_time(position: int) -> str:
    """ Примерное время ожидания в очереди """
    # Среднее время обработки ~30 сек
    avg_process_time = 30
    wait_seconds = (position / MAX_CONCURRENT_TASKS) * avg_process_time
    
    if wait_seconds < 60:
        return f"{int(wait_seconds)}с"
    elif wait_seconds < 3600:
        return f"{int(wait_seconds // 60)}м"
    else:
        return f"{int(wait_seconds // 3600)}ч"

def get_temp_dir_size() -> tuple:
    """
    Получить размер temp папки в МБ и количество файлов.
    """
    temp_dir = get_temp_dir()
    total_size = 0
    file_count = 0
    
    for f in temp_dir.iterdir():
        if f.is_file():
            total_size += f.stat().st_size
            file_count += 1
    
    return round(total_size / (1024 * 1024), 2), file_count

def _rand(min_val: float, max_val: float) -> float:
    return random.uniform(min_val, max_val)

def _escape_ffmpeg_text(text: str) -> str:
    """
    Экранирование текста для FFmpeg drawtext.
    Экранирует: двоеточия, пробелы, апострофы, обратные слэши.
    """
    # Порядок важен! Сначала бэкслэши
    text = text.replace("\\", "\\\\")
    text = text.replace(":", r"\:")
    text = text.replace("'", r"\'")
    text = text.replace(" ", r"\ ")
    return text

def _rand_choice(options: list):
    return random.choice(options)

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-TIKTOK 2026: SEGMENT VARIATION
# ══════════════════════════════════════════════════════════════════════════════

def _build_segment_variation(duration: float, force_motion: bool = False) -> List[dict]:
    """
    ANTI-STATIC 2026: Разбивка видео на сегменты.
    Минимум 3 сегмента для борьбы со статичностью.
    """
    # ANTI-STATIC: минимум 3 сегмента!
    num_segments = random.randint(3, 5) if force_motion else random.randint(3, 4)
    segment_duration = duration / num_segments
    
    segments = []
    for i in range(num_segments):
        # ANTI-STATIC: более агрессивная вариация для каждого сегмента
        segment = {
            "start": i * segment_duration,
            "end": (i + 1) * segment_duration,
            "brightness": _rand(-0.08, 0.08) if force_motion else _rand(-0.05, 0.05),
            "contrast": _rand(0.92, 1.08) if force_motion else _rand(0.95, 1.05),
            "saturation": _rand(0.92, 1.08) if force_motion else _rand(0.95, 1.05),
            "gamma": _rand(0.95, 1.05) if force_motion else _rand(0.97, 1.03),
            "speed": _rand(0.95, 1.05),  # вариация скорости для jump-cut эффекта
            "zoom": _rand(1.0, 1.04) if force_motion else _rand(1.0, 1.02),  # zoom per segment
        }
        segments.append(segment)
    
    return segments

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-STATIC CONTENT 2026: FORCED HOOK & MOTION
# ══════════════════════════════════════════════════════════════════════════════

def _build_forced_hook(width: int, height: int, duration: float) -> str:
    """
    FORCED HOOK (0-2 сек): Текст-хук.
    Placement в safe-zone (не по краям экрана).
    """
    hook_text = random.choice(HOOK_TEXTS)
    fontsize = int(min(width, height) * 0.055)  # крупный текст для хука
    
    # Safe zone: не слишком близко к краям
    y_positions = ["h*0.35", "h*0.45", "h*0.55"]
    text_y = random.choice(y_positions)
    
    hook_duration = min(2.0, duration * 0.3)  # максимум 2 секунды
    
    # Экранируем текст для FFmpeg
    safe_text = _escape_ffmpeg_text(hook_text)
    hook_filter = (
        f"drawtext=text={safe_text}:"
        f"fontsize={fontsize}:"
        f"fontcolor=white:"
        f"shadowcolor=black@0.7:"
        f"shadowx=2:shadowy=2:"
        f"x=(w-text_w)/2:"
        f"y={text_y}:"
        f"enable=lt(t\\,{hook_duration:.2f})"
    )
    
    return hook_filter

def _build_jump_cuts(duration: float, num_cuts: int = 3) -> List[str]:
    """
    ANTI-STATIC: Jump cut эффекты для имитации монтажа.
    Быстрые переходы между сегментами.
    """
    cuts = []
    segment_duration = duration / (num_cuts + 1)
    
    for i in range(1, num_cuts + 1):
        cut_time = i * segment_duration
        # Быстрый flash (белый) на момент cut
        flash_duration = 0.08
        flash = (
            f"fade=t=in:st={cut_time}:d={flash_duration}:alpha=1,"
            f"fade=t=out:st={cut_time + flash_duration}:d={flash_duration}:alpha=1"
        )
        cuts.append(cut_time)
    
    return cuts

def _build_segmented_motion(width: int, height: int, duration: float, segments: List[dict]) -> str:
    """
    SEGMENTED MOTION: каждый сегмент с разными zoom/pan параметрами.
    Создаёт иллюзию динамичного видео даже из статичного контента.
    """
    motion_filters = []
    
    for i, seg in enumerate(segments):
        seg_start = seg["start"]
        seg_end = seg["end"]
        seg_duration = seg_end - seg_start
        zoom = seg.get("zoom", 1.0)
        
        # Чередование типов motion для каждого сегмента
        motion_type = i % 4  # 0: zoom_in, 1: zoom_out, 2: pan_left, 3: pan_right
        
        if motion_type == 0:  # Zoom In
            z_start = 1.0
            z_end = zoom
        elif motion_type == 1:  # Zoom Out
            z_start = zoom
            z_end = 1.0
        elif motion_type == 2:  # Pan Left
            z_start = 1.0
            z_end = 1.0
        else:  # Pan Right
            z_start = 1.0
            z_end = 1.0
    
    return ""

# ══════════════════════════════════════════════════════════════════════════════
# v3.1.0: VIDEO TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def _apply_template_filters(base_filters: List[str], template: str, width: int, height: int) -> List[str]:
    """
    Применяет фильтры шаблона поверх базовых фильтров.
    Шаблоны модифицируют цветокоррекцию, добавляют эффекты и т.д.
    """
    from config import VIDEO_TEMPLATES
    
    if template not in VIDEO_TEMPLATES or template == "none":
        return base_filters
    
    tpl = VIDEO_TEMPLATES[template]
    filters_config = tpl.get("filters", {})
    
    if not filters_config:
        return base_filters
    
    extra_filters = []
    
    # Brightness / Contrast / Saturation / Gamma
    eq_parts = []
    if "brightness" in filters_config:
        eq_parts.append(f"brightness={filters_config['brightness']:.4f}")
    if "contrast" in filters_config:
        eq_parts.append(f"contrast={filters_config['contrast']:.4f}")
    if "saturation" in filters_config:
        eq_parts.append(f"saturation={filters_config['saturation']:.4f}")
    if "gamma" in filters_config:
        eq_parts.append(f"gamma={filters_config['gamma']:.4f}")
    
    if eq_parts:
        extra_filters.append(f"eq={':'.join(eq_parts)}")
    
    # Warmth (цветовой сдвиг к тёплым/холодным тонам)
    if "warmth" in filters_config:
        warmth = filters_config["warmth"]
        if warmth > 0:
            # Тёплый (добавляем жёлтый/оранжевый)
            extra_filters.append(f"colorbalance=rs={warmth}:gs={warmth/2}:bs=-{warmth}")
        else:
            # Холодный (добавляем синий)
            extra_filters.append(f"colorbalance=rs={warmth}:gs={warmth/2}:bs={-warmth}")
    
    # Noise / Grain
    if "noise" in filters_config:
        extra_filters.append(f"noise=alls={int(filters_config['noise'])}:allf=t+u")
    
    # Vignette
    if "vignette" in filters_config:
        extra_filters.append(f"vignette=angle={filters_config['vignette']}:mode=forward")
    
    # Blur
    if "blur" in filters_config:
        extra_filters.append(f"gblur=sigma={filters_config['blur']}")
    
    # Glow effect (яркость + размытие)
    if "glow" in filters_config:
        glow = filters_config["glow"]
        extra_filters.append(f"unsharp=5:5:-{glow}:5:5:-{glow}")
    
    # Sharpness
    if "sharpness" in filters_config:
        sharp = filters_config["sharpness"]
        extra_filters.append(f"unsharp=5:5:{sharp}:5:5:{sharp/2}")
    
    # Letterbox (киношные чёрные полосы)
    if filters_config.get("letterbox"):
        letterbox_height = int(height * 0.12)  # 12% сверху и снизу
        extra_filters.append(
            f"drawbox=x=0:y=0:w={width}:h={letterbox_height}:color=black:t=fill,"
            f"drawbox=x=0:y={height-letterbox_height}:w={width}:h={letterbox_height}:color=black:t=fill"
        )
    
    # Shake effect
    if "shake" in filters_config:
        shake = int(filters_config["shake"])
        extra_filters.append(
            f"crop=w=iw-{shake*2}:h=ih-{shake*2}:x={shake}+{shake}*sin(15*t):y={shake}+{shake}*sin(17*t),"
            f"scale={width}:{height}:flags=lanczos"
        )
    
    # Speed modification будет обрабатываться отдельно
    # (не через фильтры, т.к. влияет на pts и audio)
    
    return base_filters + extra_filters

def _get_template_speed(template: str) -> float:
    """Получить модификатор скорости из шаблона"""
    from config import VIDEO_TEMPLATES
    
    if template not in VIDEO_TEMPLATES or template == "none":
        return 1.0
    
    return VIDEO_TEMPLATES[template].get("filters", {}).get("speed", 1.0)

def _build_anti_static_filters(width: int, height: int, duration: float) -> List[str]:
    """
    ANTI-STATIC CONTENT 2026: Полный набор фильтров против статичности.
    - Forced Hook
    - Segmented Motion
    - Jump Cuts simulation
    - Minimum duration enforcement
    """
    filters = []
    
    # 1. FORCED HOOK в начале (0-2 сек)
    hook_filter = _build_forced_hook(width, height, duration)
    filters.append(hook_filter)
    
    # 2. Постоянное микро-движение (shake/jitter)
    # Небольшая вибрация камеры для "живости"
    shake_x = random.randint(2, 5)
    shake_y = random.randint(2, 5)
    shake_freq = _rand(8, 15)
    shake_x_expr = f"{shake_x}+{shake_x}*sin({shake_freq}*t)"
    shake_y_expr = f"{shake_y}+{shake_y}*sin({shake_freq}*t*1.3)"
    shake_filter = (
        f"crop=w=iw-{shake_x*2}:h=ih-{shake_y*2}:"
        f"x={shake_x_expr}:"
        f"y={shake_y_expr},"
        f"scale={width}:{height}:flags=lanczos"
    )
    filters.append(shake_filter)
    
    # 3. Периодические flash/pulse эффекты
    pulse_interval = _rand(2.5, 4.5)  # каждые 2.5-4.5 сек
    pulse_filter = (
        f"eq=brightness=0.03*sin(2*PI*t/{pulse_interval}):"
        f"saturation=1+0.05*sin(2*PI*t/{pulse_interval}*0.7)"
    )
    filters.append(pulse_filter)
    
    return filters

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-TIKTOK 2026: MAIN FILTER BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_tiktok_filter_v2(width: int, height: int, duration: float, target_fps: float = 30, 
                              quality: str = DEFAULT_QUALITY, text_overlay: bool = True) -> Tuple[str, str, dict]:
    """
    ANTI-TIKTOK 2026 Filter + ANTI-STATIC CONTENT:
    - Поддержка до 8K 120FPS
    - Aggressive watermark removal
    - Forced creative layer
    - Motion scripting
    - Segment variation (мин. 3 сегмента)
    - Anti-source pattern
    - FORCED HOOK (0-2 сек) - опционально
    - SEGMENTED MOTION
    - ANTI-LOW-QUALITY SIGNAL
    - Поддержка пресетов качества
    """
    v = TIKTOK_VIDEO
    a = TIKTOK_AUDIO
    q_settings = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS[Quality.MAX])
    
    filters = []
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: Проверка минимальной длительности
    # ═══════════════════════════════════════════════════════════════════
    min_duration = 8.0  # минимум 8 секунд
    effective_duration = max(duration, min_duration)
    
    # 1. WATERMARK REMOVAL (агрессивный crop)
    crop_factor = _rand(0.94, 0.965)
    crop_w = int(width * crop_factor)
    crop_h = int(height * crop_factor)
    crop_x = (width - crop_w) // 2
    crop_y = (height - crop_h) // 2
    filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
    filters.append(f"scale={width}:{height}:flags=lanczos")
    
    # 2. SPEED VARIATION (рандомная по всему видео)
    speed = _rand(v["speed_min"], v["speed_max"])
    filters.append(f"setpts={1/speed}*PTS")
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: FORCED MOTION (всегда! 100% шанс)
    # Используем быстрые фильтры вместо медленного zoompan
    # ═══════════════════════════════════════════════════════════════════
    
    # 3a. SCALE ZOOM (быстрая альтернатива zoompan)
    zoom_factor = _rand(1.02, 1.05)
    filters.append(f"scale={int(width*zoom_factor)}:{int(height*zoom_factor)}:flags=lanczos")
    filters.append(f"crop={width}:{height}")
    
    # 3b. MICRO-CROP для вариации
    shake_intensity = random.randint(2, 4)
    filters.append(
        f"crop=w=iw-{shake_intensity*2}:h=ih-{shake_intensity*2},"
        f"scale={width}:{height}:flags=lanczos"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: COLOR VARIATION
    # ═══════════════════════════════════════════════════════════════════
    
    # 4. COLOR GRADING (рандомный для всего видео)
    brightness = _rand(-0.06, 0.06)
    contrast = _rand(0.94, 1.06)
    saturation = _rand(0.94, 1.06)
    gamma = _rand(0.96, 1.04)
    filters.append(
        f"eq=brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:"
        f"saturation={saturation:.4f}:"
        f"gamma={gamma:.4f}"
    )
    
    # 5. FILM GRAIN (обязательно!)
    grain = random.randint(5, 12)  # усилен
    filters.append(f"noise=alls={grain}:allf=t+u")
    
    # 6. VIGNETTE (70% шанс - увеличен)
    if random.random() > 0.3:
        filters.append(f"vignette=angle={_rand(0.25, 0.45)}:mode=forward")
    
    # 7. BLUR/SHARPEN
    if random.random() > 0.5:
        filters.append("gblur=sigma=0.4")
    else:
        filters.append("unsharp=3:3:0.7:3:3:0.0")
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: TEXT OVERLAY (упрощённый вариант)
    # ═══════════════════════════════════════════════════════════════════
    
    # 8. TEXT OVERLAY (только если включено)
    if text_overlay:
        hook_text = random.choice(HOOK_TEXTS)
        hook_fontsize = int(min(width, height) * 0.05)
        # Экранируем текст для FFmpeg
        safe_text = _escape_ffmpeg_text(hook_text)
        # Текст постоянно на экране в нижней части (как субтитры)
        filters.append(
            f"drawtext=text={safe_text}:"
            f"fontsize={hook_fontsize}:"
            f"fontcolor=white:"
            f"shadowcolor=black@0.8:"
            f"shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:"
            f"y=h-th-50"
        )
    
    # 9. FINAL FPS (сохраняем оригинальный FPS до 120)
    output_fps = target_fps
    filters.append(f"fps={output_fps}")
    
    video_filter = ",".join(filters)
    
    # AUDIO PROCESSING
    audio_tempo = speed
    volume = _rand(a["volume_min"], a["volume_max"])
    
    audio_filter = f"atempo={audio_tempo:.4f},volume={volume:.4f}"
    
    # Audio EQ variation
    eq_choice = random.randint(0, 3)
    if eq_choice == 1:
        audio_filter += ",lowshelf=g=1.5:f=200"
    elif eq_choice == 2:
        audio_filter += ",highshelf=g=-1.5:f=3500"
    elif eq_choice == 3:
        audio_filter += ",equalizer=f=1000:t=q:w=1:g=2"
    
    # ENCODING PARAMS (рандомизация для anti-source pattern + quality preset)
    gop = random.randint(12, 45)
    base_bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    bitrate = int(base_bitrate * q_settings["bitrate_mult"])
    base_crf = random.randint(v.get("crf_min", 18), v.get("crf_max", 22))
    crf = base_crf + q_settings["crf_offset"]
    preset = q_settings["preset"] if q_settings["preset"] else _rand_choice(v["presets"])
    
    params = {
        "bitrate": f"{bitrate}k",
        "crf": crf,
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
        "profile": random.choice(["main", "high"]),
        "level": random.choice(["4.0", "4.1", "4.2"]),
    }
    
    return video_filter, audio_filter, params

def _build_youtube_filter_v2(width: int, height: int, duration: float, target_fps: float = 30,
                               quality: str = DEFAULT_QUALITY, text_overlay: bool = True) -> Tuple[str, str, dict]:
    """
    YouTube Shorts Anti-Detection Filter + ANTI-STATIC CONTENT
    Поддержка до 8K 120FPS + пресеты качества
    """
    v = YOUTUBE_VIDEO
    a = YOUTUBE_AUDIO
    q_settings = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS[Quality.MAX])
    
    filters = []
    
    # Crop для watermark
    crop_factor = _rand(0.95, 0.975)
    crop_w = int(width * crop_factor)
    crop_h = int(height * crop_factor)
    crop_x = (width - crop_w) // 2
    crop_y = (height - crop_h) // 2
    filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
    filters.append(f"scale={width}:{height}:flags=lanczos")
    
    # Speed
    speed = _rand(v["speed_min"], v["speed_max"])
    filters.append(f"setpts={1/speed}*PTS")
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: FORCED MOTION (100% шанс)
    # Быстрые фильтры вместо медленного zoompan
    # ═══════════════════════════════════════════════════════════════════
    zoom_factor = _rand(1.02, 1.04)
    filters.append(f"scale={int(width*zoom_factor)}:{int(height*zoom_factor)}:flags=lanczos")
    filters.append(f"crop={width}:{height}")
    
    # Micro-crop
    shake = random.randint(2, 3)
    filters.append(
        f"crop=w=iw-{shake*2}:h=ih-{shake*2},"
        f"scale={width}:{height}:flags=lanczos"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: COLOR VARIATION
    # ═══════════════════════════════════════════════════════════════════
    # COLOR GRADING (рандомный для всего видео)
    brightness = _rand(-0.05, 0.05)
    contrast = _rand(0.95, 1.05)
    saturation = _rand(0.95, 1.05)
    gamma = _rand(0.97, 1.03)
    filters.append(
        f"eq=brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:"
        f"saturation={saturation:.4f}:"
        f"gamma={gamma:.4f}"
    )
    
    # Grain
    grain = random.randint(4, 8)
    filters.append(f"noise=alls={grain}:allf=t+u")
    
    # Vignette (60% шанс)
    if random.random() > 0.4:
        filters.append(f"vignette=angle={_rand(0.25, 0.40)}:mode=forward")
    
    # Blur/Sharpen
    if random.random() > 0.5:
        filters.append("gblur=sigma=0.35")
    else:
        filters.append("unsharp=3:3:0.6:3:3:0.0")
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: TEXT OVERLAY
    # ═══════════════════════════════════════════════════════════════════
    if text_overlay:
        hook_text = random.choice(HOOK_TEXTS)
        hook_fontsize = int(min(width, height) * 0.045)
        # Экранируем текст для FFmpeg
        safe_text = _escape_ffmpeg_text(hook_text)
        # Текст постоянно на экране внизу
        filters.append(
            f"drawtext=text={safe_text}:"
            f"fontsize={hook_fontsize}:"
            f"fontcolor=white:"
            f"shadowcolor=black@0.7:"
            f"shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:"
            f"y=h-th-50"
        )
    
    # FPS (сохраняем оригинальный до 120)
    output_fps = target_fps
    filters.append(f"fps={output_fps}")
    
    video_filter = ",".join(filters)
    
    # Audio
    audio_tempo = speed
    volume = _rand(a["volume_min"], a["volume_max"])
    
    audio_filter = (
        f"aresample={a['resample_rate']},"
        f"atempo={audio_tempo:.4f},"
        f"volume={volume:.4f},"
        f"highpass=f=25,lowpass=f=17000,"
        f"lowshelf=g=1.5:f=180"
    )
    
    gop = random.randint(15, 40)
    base_bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    bitrate = int(base_bitrate * q_settings["bitrate_mult"])
    base_crf = random.randint(v.get("crf_min", 17), v.get("crf_max", 20))
    crf = base_crf + q_settings["crf_offset"]
    preset = q_settings["preset"] if q_settings["preset"] else _rand_choice(v["presets"])
    
    params = {
        "bitrate": f"{bitrate}k",
        "crf": crf,
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
        "profile": random.choice(["main", "high"]),
        "level": random.choice(["4.0", "4.1", "4.2"]),
    }
    
    return video_filter, audio_filter, params

# ══════════════════════════════════════════════════════════════════════════════
# LEGACY FILTER BUILDERS (fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _build_tiktok_filter(width: int, height: int) -> Tuple[str, str, dict]:
    """Legacy TikTok filter (без duration)"""
    return _build_tiktok_filter_v2(width, height, 30.0, 30.0)

def _build_youtube_filter(width: int, height: int) -> Tuple[str, str, dict]:
    """Legacy YouTube filter (без duration)"""
    return _build_youtube_filter_v2(width, height, 30.0, 30.0)

# ══════════════════════════════════════════════════════════════════════════════
# VIDEO INFO & PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

async def get_video_info(input_path: str) -> Optional[Tuple[int, int, float, float]]:
    """Получает width, height, duration, fps из видео"""
    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "csv=p=0",
        input_path
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        
        # Формат вывода: width,height,r_frame_rate,duration
        parts = stdout.decode().strip().split(",")
        if len(parts) >= 2:
            width = int(parts[0])
            height = int(parts[1])
            
            # Parse FPS (format: "30/1" or "60000/1001") - parts[2]
            fps = 30.0
            if len(parts) > 2 and parts[2]:
                fps_str = parts[2]
                if "/" in fps_str:
                    fps_parts = fps_str.split("/")
                    if len(fps_parts) == 2 and float(fps_parts[1]) > 0:
                        fps = float(fps_parts[0]) / float(fps_parts[1])
                else:
                    fps = float(fps_str)
            
            # Duration - parts[3]
            duration = 60.0
            if len(parts) > 3 and parts[3]:
                try:
                    duration = float(parts[3])
                except ValueError:
                    duration = 60.0
            
            return width, height, duration, fps
    except Exception as e:
        print(f"[FFPROBE] Error: {e}")
    
    return None


async def get_video_duration(input_path: str) -> float:
    """Получает длительность видео в секундах"""
    info = await get_video_info(input_path)
    if info and len(info) >= 3:
        return info[2]  # duration is the third element
    return 0.0


def _generate_random_timestamp() -> str:
    """Генерация рандомного timestamp для anti-source pattern"""
    import datetime
    days_ago = random.randint(1, 30)
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)
    seconds = random.randint(0, 59)
    
    dt = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=hours, minutes=minutes, seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000000Z")

async def process_video(input_path: str, output_path: str, mode: str, 
                        quality: str = DEFAULT_QUALITY, text_overlay: bool = True,
                        template: str = "none") -> bool:
    """
    ANTI-TIKTOK 2026 Video Processing - поддержка до 8K 120FPS
    + пресеты качества, опциональный текст и шаблоны
    """
    info = await get_video_info(input_path)
    if not info:
        return False
    
    width, height, duration, source_fps = info
    
    # Сохраняем оригинальный FPS (до 120)
    target_fps = min(source_fps, 120)
    
    # Выбор фильтра на основе режима
    if mode == Mode.YOUTUBE:
        video_filter, audio_filter, params = _build_youtube_filter_v2(
            width, height, duration, target_fps, quality, text_overlay
        )
    else:
        video_filter, audio_filter, params = _build_tiktok_filter_v2(
            width, height, duration, target_fps, quality, text_overlay
        )
    
    # v3.1.0: Применяем шаблон поверх базовых фильтров
    if template and template != "none":
        base_filters = video_filter.split(",")
        modified_filters = _apply_template_filters(base_filters, template, width, height)
        video_filter = ",".join(modified_filters)
        
        # Применяем модификатор скорости из шаблона
        template_speed = _get_template_speed(template)
        if template_speed != 1.0:
            # Добавляем setpts для изменения скорости
            video_filter = f"setpts={1/template_speed}*PTS," + video_filter
            # Модифицируем аудио темп
            audio_filter = f"atempo={template_speed}," + audio_filter
    
    # Рандомный encoder profile для anti-source pattern
    profile = params.get("profile", "main")
    # Уровень зависит от разрешения
    if width > 3840 or height > 2160:
        level = "6.2"  # 8K
    elif width > 1920 or height > 1080:
        level = "5.2"  # 4K
    else:
        level = params.get("level", "4.2")
    crf = params.get("crf", 18)
    
    # Добавляем pix_fmt конвертацию в конец video_filter для совместимости
    video_filter_final = video_filter + ",format=yuv420p"
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", video_filter_final,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", level,
        "-preset", params["preset"],
        # CRF для качества + maxrate для контроля размера
        "-crf", str(crf),
        "-maxrate", params["bitrate"],
        "-bufsize", f"{int(params['bitrate'].replace('k', '')) * 2}k",
        "-g", str(params["gop"]),
        "-keyint_min", str(params["gop"] // 2),
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", params["audio_bitrate"],
        "-ar", "48000",
        # ANTI-SOURCE PATTERN: удаление всех метаданных
        "-map_metadata", "-1",
        "-metadata", f"creation_time={_generate_random_timestamp()}",
        "-fflags", "+bitexact+genpts",
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
        "-movflags", "+faststart",
        output_path
    ]
    
    # DEBUG: выводим команду
    print(f"[FFMPEG] CMD: {' '.join(cmd[:6])} ... {output_path}")
    print(f"[FFMPEG] VF length: {len(video_filter)}")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        active_processes.append(proc)
        
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=FFMPEG_TIMEOUT_SECONDS
            )
            
            if proc.returncode != 0:
                print(f"[FFMPEG] Error: {stderr.decode()[-500:]}")
                return False
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
        except asyncio.TimeoutError:
            print(f"[FFMPEG] Timeout after {FFMPEG_TIMEOUT_SECONDS}s")
            proc.kill()
            await proc.wait()
            return False
        finally:
            if proc in active_processes:
                active_processes.remove(proc)
                
    except Exception as e:
        print(f"[FFMPEG] Exception: {e}")
        return False

def kill_all_ffmpeg():
    for proc in active_processes[:]:
        try:
            proc.kill()
        except Exception:
            pass
    active_processes.clear()

# ══════════════════════════════════════════════════════════════════════════════
# QUEUE & WORKERS
# ══════════════════════════════════════════════════════════════════════════════

class ProcessingTask:
    def __init__(self, user_id: int, input_path: str, mode: str, callback, 
                 quality: str = DEFAULT_QUALITY, text_overlay: bool = True,
                 priority: int = 0):
        self.user_id = user_id
        self.input_path = input_path
        self.mode = mode
        self.callback = callback
        self.quality = quality
        self.text_overlay = text_overlay
        self.output_path = str(get_temp_dir() / generate_unique_filename())
        self.priority = priority  # 0=free, 1=vip, 2=premium
        self.cancelled = False
        self.task_id = f"{user_id}_{int(time.time()*1000)}"
    
    def __lt__(self, other):
        # Для PriorityQueue — больший приоритет = раньше в очереди
        return self.priority > other.priority

# Словарь активных задач для возможности отмены
active_tasks: dict = {}

async def worker():
    while True:
        # Получаем задачу с учётом приоритета
        priority, task = await processing_queue.get()
        task: ProcessingTask
        
        # Проверяем отмену
        if task.cancelled:
            cleanup_file(task.input_path)
            processing_queue.task_done()
            active_tasks.pop(task.task_id, None)
            continue
        
        try:
            success = await process_video(
                task.input_path, task.output_path, task.mode,
                task.quality, task.text_overlay
            )
            
            # Ещё раз проверяем отмену после обработки
            if not task.cancelled:
                await task.callback(success, task.output_path if success else None)
            else:
                cleanup_file(task.output_path)
        except Exception as e:
            print(f"[WORKER] Error: {e}")
            if not task.cancelled:
                await task.callback(False, None)
        finally:
            cleanup_file(task.input_path)
            processing_queue.task_done()
            active_tasks.pop(task.task_id, None)

async def start_workers():
    init_queue()
    for _ in range(MAX_CONCURRENT_TASKS):
        asyncio.create_task(worker())
    # v2.8.0: Запуск периодической очистки
    asyncio.create_task(periodic_cleanup())

async def add_to_queue(task: ProcessingTask) -> Tuple[bool, int]:
    """
    Добавить задачу в очередь.
    Returns: (success, position)
    """
    if processing_queue.full():
        return False, 0
    
    # Сохраняем задачу для возможности отмены
    active_tasks[task.task_id] = task
    
    # Добавляем с приоритетом (отрицательный для правильной сортировки)
    await processing_queue.put((-task.priority, task))
    
    # Позиция в очереди
    position = processing_queue.qsize()
    return True, position

def cancel_task(user_id: int) -> bool:
    """ Отменить задачу пользователя в очереди """
    for task_id, task in list(active_tasks.items()):
        if task.user_id == user_id and not task.cancelled:
            task.cancelled = True
            return True
    return False

def get_user_task(user_id: int) -> ProcessingTask:
    """ Получить активную задачу пользователя """
    for task in active_tasks.values():
        if task.user_id == user_id:
            return task
    return None

def get_user_queue_count(user_id: int) -> int:
    """ Посчитать сколько задач пользователя в очереди """
    count = 0
    for task in active_tasks.values():
        if task.user_id == user_id and not task.cancelled:
            count += 1
    return count

def get_queue_size() -> int:
    return processing_queue.qsize() if processing_queue else 0

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: TRIM VIDEO
# ══════════════════════════════════════════════════════════════════════════════

async def trim_video(
    input_path: str,
    output_path: str,
    start_time: str,
    end_time: str,
) -> Tuple[bool, Optional[str]]:
    """
    Обрезать видео по времени.
    start_time, end_time в формате HH:MM:SS или SS
    """
    try:
        cmd = [
            FFMPEG_PATH, "-y",
            "-ss", start_time,
            "-i", input_path,
            "-to", end_time,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except asyncio.TimeoutError:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: ADD MUSIC OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

async def add_music_overlay(
    video_path: str,
    audio_path: str,
    output_path: str,
    volume: float = 0.3,
    keep_original: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Добавить музыку к видео.
    volume: громкость музыки (0.0-1.0)
    keep_original: сохранить оригинальный звук
    """
    try:
        if keep_original:
            # Микшируем оригинальный звук с музыкой
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex",
                f"[0:a]volume=1.0[a1];[1:a]volume={volume}[a2];[a1][a2]amix=inputs=2:duration=first[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path
            ]
        else:
            # Заменяем звук на музыку
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                f"-af", f"volume={volume}",
                "-shortest",
                output_path
            ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except asyncio.TimeoutError:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: FORMAT CONVERTER
# ══════════════════════════════════════════════════════════════════════════════

async def convert_to_gif(
    input_path: str,
    output_path: str,
    fps: int = 10,
    scale: int = 480,
) -> Tuple[bool, Optional[str]]:
    """Конвертировать видео в GIF"""
    try:
        # Сначала генерируем палитру для лучшего качества
        palette_path = output_path + ".palette.png"
        
        # Генерация палитры
        cmd1 = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", f"fps={fps},scale={scale}:-1:flags=lanczos,palettegen",
            palette_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd1,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=FFMPEG_TIMEOUT_SECONDS // 2)
        
        # Создание GIF с палитрой
        cmd2 = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-i", palette_path,
            "-filter_complex", f"fps={fps},scale={scale}:-1:flags=lanczos[x];[x][1:v]paletteuse",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd2,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        # Очистка палитры
        if os.path.exists(palette_path):
            os.remove(palette_path)
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)

async def convert_to_mp3(
    input_path: str,
    output_path: str,
    bitrate: str = "192k",
) -> Tuple[bool, Optional[str]]:
    """Извлечь аудио из видео в MP3"""
    try:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", bitrate,
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)

async def convert_to_webm(
    input_path: str,
    output_path: str,
) -> Tuple[bool, Optional[str]]:
    """Конвертировать в WebM"""
    try:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-c:a", "libopus",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: CUSTOM WATERMARK
# ══════════════════════════════════════════════════════════════════════════════

async def apply_custom_watermark(
    input_path: str,
    watermark_path: str,
    output_path: str,
    position: str = "br",
    opacity: float = 0.7,
    scale: float = 0.15,
) -> Tuple[bool, Optional[str]]:
    """
    Добавить пользовательский водяной знак.
    position: tl, tr, bl, br (top/bottom left/right)
    """
    try:
        # Позиции
        positions = {
            "tl": "10:10",
            "tr": "W-w-10:10",
            "bl": "10:H-h-10",
            "br": "W-w-10:H-h-10",
            "center": "(W-w)/2:(H-h)/2",
        }
        overlay_pos = positions.get(position, positions["br"])
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-i", watermark_path,
            "-filter_complex",
            f"[1:v]scale=iw*{scale}:-1,format=rgba,colorchannelmixer=aa={opacity}[wm];[0:v][wm]overlay={overlay_pos}",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: RESOLUTION CHANGE
# ══════════════════════════════════════════════════════════════════════════════

async def change_resolution(
    input_path: str,
    output_path: str,
    resolution: str,
) -> Tuple[bool, Optional[str]]:
    """
    Изменить разрешение видео.
    resolution: 1080p, 720p, 480p, 360p
    """
    try:
        resolutions = {
            "1080p": "1920:1080",
            "720p": "1280:720",
            "480p": "854:480",
            "360p": "640:360",
        }
        
        if resolution not in resolutions:
            return False, f"Unknown resolution: {resolution}"
        
        scale = resolutions[resolution]
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", f"scale={scale}:force_original_aspect_ratio=decrease,pad={scale}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════════════════════════
# v2.9.0: EFFECT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

async def apply_effect_template(
    input_path: str,
    output_path: str,
    template_id: str,
) -> Tuple[bool, Optional[str]]:
    """
    Применить шаблон эффектов.
    """
    from config import EFFECT_TEMPLATES
    
    try:
        if template_id not in EFFECT_TEMPLATES:
            return False, f"Unknown template: {template_id}"
        
        template = EFFECT_TEMPLATES[template_id]
        filter_str = template["filter"]
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: MERGE VIDEOS
# ══════════════════════════════════════════════════════════════════════════════

async def merge_videos(
    input_paths: List[str],
    output_path: str,
) -> Tuple[bool, Optional[str]]:
    """
    Склеить несколько видео в одно.
    """
    try:
        if len(input_paths) < 2:
            return False, "Need at least 2 videos to merge"
        
        # Создаём файл со списком видео
        temp_dir = get_temp_dir()
        list_file = temp_dir / f"merge_list_{uuid.uuid4().hex[:8]}.txt"
        
        with open(list_file, 'w', encoding='utf-8') as f:
            for path in input_paths:
                # Экранируем путь
                escaped_path = path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS * 2  # Больше времени для склейки
        )
        
        # Удаляем временный файл
        try:
            os.remove(list_file)
        except:
            pass
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: SPEED CONTROL
# ══════════════════════════════════════════════════════════════════════════════

async def change_speed(
    input_path: str,
    output_path: str,
    speed: float,
) -> Tuple[bool, Optional[str]]:
    """
    Изменить скорость видео.
    speed: 0.5 (замедление) - 2.0 (ускорение)
    """
    try:
        if speed <= 0 or speed > 4:
            return False, "Speed must be between 0.1 and 4.0"
        
        # Фильтр для видео и аудио
        video_filter = f"setpts={1/speed}*PTS"
        audio_filter = f"atempo={speed}" if 0.5 <= speed <= 2.0 else f"atempo={min(2.0, speed)},atempo={speed/2.0}"
        
        # Для скоростей вне 0.5-2.0 нужно каскадировать atempo
        if speed < 0.5:
            audio_filter = f"atempo=0.5,atempo={speed/0.5}"
        elif speed > 2.0:
            audio_filter = f"atempo=2.0,atempo={speed/2.0}"
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-filter:v", video_filter,
            "-filter:a", audio_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: ROTATE/FLIP VIDEO
# ══════════════════════════════════════════════════════════════════════════════

async def rotate_flip_video(
    input_path: str,
    output_path: str,
    action: str,
) -> Tuple[bool, Optional[str]]:
    """
    Повернуть или отразить видео.
    action: 90_cw, 90_ccw, 180, flip_h, flip_v
    """
    try:
        filter_map = {
            "90_cw": "transpose=1",       # 90° по часовой
            "90_ccw": "transpose=2",      # 90° против часовой
            "180": "transpose=1,transpose=1",  # 180°
            "flip_h": "hflip",            # Горизонтальное отражение
            "flip_v": "vflip",            # Вертикальное отражение
        }
        
        if action not in filter_map:
            return False, f"Unknown action: {action}"
        
        video_filter = filter_map[action]
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", video_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: CHANGE ASPECT RATIO
# ══════════════════════════════════════════════════════════════════════════════

async def change_aspect_ratio(
    input_path: str,
    output_path: str,
    aspect: str,
) -> Tuple[bool, Optional[str]]:
    """
    Изменить соотношение сторон.
    aspect: 9:16, 16:9, 1:1, 4:3, 4:5
    """
    from config import ASPECT_RATIOS
    
    try:
        if aspect not in ASPECT_RATIOS:
            return False, f"Unknown aspect ratio: {aspect}"
        
        ratio = ASPECT_RATIOS[aspect]
        w, h = ratio["width"], ratio["height"]
        
        # Crop + pad для нужного соотношения
        filter_str = f"crop=ih*{w}/{h}:ih:(iw-ih*{w}/{h})/2:0,scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        
        if aspect == "16:9":
            filter_str = "crop=iw:iw*9/16:0:(ih-iw*9/16)/2,scale=1920:1080"
        elif aspect == "1:1":
            filter_str = "crop=min(iw\\,ih):min(iw\\,ih),scale=1080:1080"
        elif aspect == "4:3":
            filter_str = "crop=ih*4/3:ih:(iw-ih*4/3)/2:0,scale=1440:1080"
        elif aspect == "4:5":
            filter_str = "crop=ih*4/5:ih:(iw-ih*4/5)/2:0,scale=864:1080"
        elif aspect == "9:16":
            filter_str = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: APPLY VIDEO FILTER
# ══════════════════════════════════════════════════════════════════════════════

async def apply_video_filter(
    input_path: str,
    output_path: str,
    filter_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Применить видео-фильтр.
    filter_name: bw, sepia, negative, blur, sharpen, vintage, warm, cold, vignette, bright
    """
    from config import VIDEO_FILTERS
    
    try:
        if filter_name not in VIDEO_FILTERS:
            return False, f"Unknown filter: {filter_name}"
        
        filter_data = VIDEO_FILTERS[filter_name]
        video_filter = filter_data["filter"]
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", video_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: ADD CUSTOM TEXT OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

async def add_custom_text(
    input_path: str,
    output_path: str,
    text: str,
    style: str = "default",
    position: str = "bottom",
) -> Tuple[bool, Optional[str]]:
    """
    Добавить свой текст на видео.
    position: top, bottom, center
    """
    from config import CAPTION_STYLES
    
    try:
        style_data = CAPTION_STYLES.get(style, CAPTION_STYLES["default"])
        
        # Позиция текста
        positions = {
            "top": "x=(w-text_w)/2:y=50",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
            "bottom": "x=(w-text_w)/2:y=h-text_h-50",
        }
        pos = positions.get(position, positions["bottom"])
        
        # Экранируем текст
        escaped_text = text.replace("'", "'\\''").replace(":", "\\:")
        
        # Формируем фильтр drawtext
        fontfile = ""  # Используем системные шрифты
        
        filter_parts = [
            f"text='{escaped_text}'",
            f"fontsize={style_data['fontsize']}",
            f"fontcolor={style_data['fontcolor']}",
            f"borderw={style_data['borderw']}",
            f"bordercolor={style_data['bordercolor']}",
            f"shadowx={style_data.get('shadowx', 0)}",
            f"shadowy={style_data.get('shadowy', 0)}",
            pos,
        ]
        
        # Добавляем box если есть
        if style_data.get('box'):
            filter_parts.append(f"box=1")
            filter_parts.append(f"boxcolor={style_data.get('boxcolor', 'black@0.5')}")
            filter_parts.append(f"boxborderw=5")
        
        drawtext_filter = f"drawtext={':'.join(filter_parts)}"
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", drawtext_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: COMPRESS VIDEO
# ══════════════════════════════════════════════════════════════════════════════

async def compress_video(
    input_path: str,
    output_path: str,
    preset: str,
) -> Tuple[bool, Optional[str], dict]:
    """
    Сжать видео под конкретную платформу.
    preset: telegram, whatsapp, discord, email, max_quality
    Возвращает: (success, error, info_dict)
    """
    from config import COMPRESSION_PRESETS
    
    try:
        if preset not in COMPRESSION_PRESETS:
            return False, f"Unknown preset: {preset}", {}
        
        preset_data = COMPRESSION_PRESETS[preset]
        target_size_mb = preset_data["target_size_mb"]
        max_bitrate = preset_data["max_bitrate"]
        audio_bitrate = preset_data["audio_bitrate"]
        
        # Получаем длительность видео
        duration = await get_video_duration(input_path)
        if duration <= 0:
            duration = 60  # fallback
        
        # Рассчитываем оптимальный битрейт
        # target_size_bits = target_size_mb * 8 * 1024 * 1024
        # video_bitrate = (target_size_bits / duration) - audio_bitrate_int
        audio_bitrate_int = int(audio_bitrate.replace('k', '')) * 1000
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        calculated_bitrate = int((target_size_bits / duration - audio_bitrate_int) / 1000)
        
        # Используем минимум из рассчитанного и максимального
        video_bitrate = min(calculated_bitrate, max_bitrate)
        
        # Получаем размер исходного файла
        original_size = os.path.getsize(input_path)
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-b:v", f"{video_bitrate}k",
            "-maxrate", f"{video_bitrate}k",
            "-bufsize", f"{video_bitrate * 2}k",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200], {}
        
        # Получаем размер выходного файла
        new_size = os.path.getsize(output_path)
        saved_percent = round((1 - new_size / original_size) * 100, 1)
        
        info = {
            "original_size": format_file_size(original_size),
            "new_size": format_file_size(new_size),
            "saved_percent": saved_percent,
        }
        
        return True, None, info
    except Exception as e:
        return False, str(e), {}


def format_file_size(size_bytes: int) -> str:
    """Форматировать размер файла"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: EXTRACT THUMBNAIL
# ══════════════════════════════════════════════════════════════════════════════

async def extract_thumbnail(
    input_path: str,
    output_path: str,
    time_position: str = "middle",
) -> Tuple[bool, Optional[str]]:
    """
    Извлечь превью из видео.
    time_position: start, 25%, middle, 75%, end, или MM:SS
    """
    try:
        duration = await get_video_duration(input_path)
        if duration <= 0:
            duration = 10
        
        # Определяем позицию
        if time_position == "start":
            seek_time = 0
        elif time_position == "25%":
            seek_time = duration * 0.25
        elif time_position == "middle":
            seek_time = duration * 0.5
        elif time_position == "75%":
            seek_time = duration * 0.75
        elif time_position == "end":
            seek_time = duration * 0.95
        elif time_position == "best":
            # Выбираем случайную "красивую" точку
            seek_time = duration * random.uniform(0.2, 0.8)
        elif ":" in time_position:
            # Формат MM:SS
            parts = time_position.split(":")
            seek_time = int(parts[0]) * 60 + int(parts[1])
        else:
            seek_time = duration * 0.5
        
        seek_time = min(seek_time, duration - 0.1)
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-ss", str(seek_time),
            "-i", input_path,
            "-vframes", "1",
            "-q:v", "2",  # Высокое качество JPEG
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: GET DETAILED VIDEO INFO
# ══════════════════════════════════════════════════════════════════════════════

async def get_detailed_video_info(input_path: str) -> dict:
    """
    Получить подробную информацию о видео.
    """
    try:
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )
        
        import json
        data = json.loads(stdout.decode())
        
        # Парсим информацию
        video_stream = None
        audio_stream = None
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not video_stream:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and not audio_stream:
                audio_stream = stream
        
        format_info = data.get("format", {})
        
        # Формируем результат
        duration = float(format_info.get("duration", 0))
        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
        
        file_size = int(format_info.get("size", 0))
        
        info = {
            "duration": duration_str,
            "duration_seconds": duration,
            "file_size": format_file_size(file_size),
            "file_size_bytes": file_size,
            "format": format_info.get("format_name", "unknown"),
            "video_codec": video_stream.get("codec_name", "N/A") if video_stream else "N/A",
            "width": video_stream.get("width", 0) if video_stream else 0,
            "height": video_stream.get("height", 0) if video_stream else 0,
            "fps": "N/A",
            "video_bitrate": "N/A",
            "audio_codec": audio_stream.get("codec_name", "N/A") if audio_stream else "N/A",
            "audio_bitrate": "N/A",
            "channels": audio_stream.get("channels", 0) if audio_stream else 0,
            "sample_rate": f"{audio_stream.get('sample_rate', 0)} Hz" if audio_stream else "N/A",
        }
        
        # Рассчитываем FPS
        if video_stream:
            fps_str = video_stream.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(num) / int(den) if int(den) != 0 else 0
                info["fps"] = f"{fps:.1f}"
            
            # Битрейт видео
            vbr = video_stream.get("bit_rate")
            if vbr:
                info["video_bitrate"] = f"{int(vbr) // 1000} kbps"
        
        # Битрейт аудио
        if audio_stream:
            abr = audio_stream.get("bit_rate")
            if abr:
                info["audio_bitrate"] = f"{int(abr) // 1000} kbps"
        
        return info
    except Exception as e:
        return {
            "error": str(e),
            "duration": "N/A",
            "file_size": "N/A",
            "format": "N/A",
            "video_codec": "N/A",
            "width": 0,
            "height": 0,
            "fps": "N/A",
            "video_bitrate": "N/A",
            "audio_codec": "N/A",
            "audio_bitrate": "N/A",
            "channels": 0,
            "sample_rate": "N/A",
        }


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: ADJUST VOLUME
# ══════════════════════════════════════════════════════════════════════════════

async def adjust_volume(
    input_path: str,
    output_path: str,
    volume_setting: str,
) -> Tuple[bool, Optional[str]]:
    """
    Изменить громкость видео.
    volume_setting: mute, 50%, 100%, 150%, 200%, normalize
    """
    from config import VOLUME_OPTIONS
    
    try:
        if volume_setting not in VOLUME_OPTIONS:
            return False, f"Unknown volume setting: {volume_setting}"
        
        value = VOLUME_OPTIONS[volume_setting]["value"]
        
        if value == "normalize":
            # Нормализация громкости
            audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"
        elif value == 0:
            # Без звука
            audio_filter = "volume=0"
        else:
            audio_filter = f"volume={value}"
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "copy",
            "-af", audio_filter,
            "-c:a", "aac",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=FFMPEG_TIMEOUT_SECONDS
        )
        
        if process.returncode != 0:
            return False, stderr.decode()[:200]
        
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# v3.0.0: AUTO-PROCESS WITH TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════

async def auto_process_video(
    input_path: str,
    output_path: str,
    template_id: str,
) -> Tuple[bool, Optional[str]]:
    """
    Автоматическая обработка видео по шаблону.
    """
    from config import AUTO_PROCESS_TEMPLATES
    
    try:
        if template_id not in AUTO_PROCESS_TEMPLATES:
            return False, f"Unknown template: {template_id}"
        
        template = AUTO_PROCESS_TEMPLATES[template_id]
        
        # Временные файлы для промежуточных результатов
        temp_dir = get_temp_dir()
        current_input = input_path
        step = 0
        
        # Применяем настройки по очереди
        
        # 1. Aspect ratio
        if "aspect" in template:
            step += 1
            temp_output = str(temp_dir / f"auto_{step}_{uuid.uuid4().hex[:8]}.mp4")
            success, error = await change_aspect_ratio(current_input, temp_output, template["aspect"])
            if not success:
                return False, f"Aspect ratio error: {error}"
            if current_input != input_path:
                try:
                    os.remove(current_input)
                except:
                    pass
            current_input = temp_output
        
        # 2. Speed
        if "speed" in template and template["speed"] != "1x":
            step += 1
            temp_output = str(temp_dir / f"auto_{step}_{uuid.uuid4().hex[:8]}.mp4")
            speed_val = float(template["speed"].replace("x", ""))
            success, error = await change_speed(current_input, temp_output, speed_val)
            if not success:
                return False, f"Speed error: {error}"
            if current_input != input_path:
                try:
                    os.remove(current_input)
                except:
                    pass
            current_input = temp_output
        
        # 3. Filter
        if "filter" in template:
            step += 1
            temp_output = str(temp_dir / f"auto_{step}_{uuid.uuid4().hex[:8]}.mp4")
            success, error = await apply_video_filter(current_input, temp_output, template["filter"])
            if not success:
                return False, f"Filter error: {error}"
            if current_input != input_path:
                try:
                    os.remove(current_input)
                except:
                    pass
            current_input = temp_output
        
        # 4. Volume
        if "volume" in template:
            step += 1
            temp_output = str(temp_dir / f"auto_{step}_{uuid.uuid4().hex[:8]}.mp4")
            success, error = await adjust_volume(current_input, temp_output, template["volume"])
            if not success:
                return False, f"Volume error: {error}"
            if current_input != input_path:
                try:
                    os.remove(current_input)
                except:
                    pass
            current_input = temp_output
        
        # 5. Compression (последний шаг)
        if "compression" in template:
            success, error, _ = await compress_video(current_input, output_path, template["compression"])
            if not success:
                return False, f"Compression error: {error}"
            if current_input != input_path:
                try:
                    os.remove(current_input)
                except:
                    pass
        else:
            # Просто копируем если нет сжатия
            import shutil
            if current_input != input_path:
                shutil.move(current_input, output_path)
            else:
                shutil.copy(current_input, output_path)
        
        return True, None
    except Exception as e:
        return False, str(e)

