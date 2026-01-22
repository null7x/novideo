"""
Virex — FFmpeg Video Processing (Anti-TikTok 2026)
"""
import os
import random
import asyncio
import subprocess
import tempfile
import uuid
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
)

processing_queue: asyncio.Queue = None
active_processes: list = []

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
    "POV:",
    "This is crazy",
    "No way...",
    "Trust me on this",
    "Story time:",
    "Here's the thing",
    "Let me show you",
    "Check this out",
    "You won't believe",
    "Real talk:",
    "Plot twist:",
    "Warning:",
    "Unpopular opinion:",
    "Facts only",
    "Listen up",
    "Game changer:",
    "Life hack:",
]

# ══════════════════════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════════════════════

def init_queue():
    global processing_queue
    processing_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

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
    temp_dir = get_temp_dir()
    import time
    now = time.time()
    
    for f in temp_dir.glob("virex_*"):
        try:
            if now - f.stat().st_mtime > max_age_seconds:
                f.unlink()
        except Exception:
            pass

def _rand(min_val: float, max_val: float) -> float:
    return random.uniform(min_val, max_val)

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
    FORCED HOOK (0-2 сек): Текст-хук с fade/slide анимацией.
    Placement в safe-zone (не по краям экрана).
    """
    hook_text = random.choice(HOOK_TEXTS)
    fontsize = int(min(width, height) * 0.055)  # крупный текст для хука
    
    # Safe zone: не слишком близко к краям
    y_positions = ["h*0.35", "h*0.45", "h*0.55"]
    text_y = random.choice(y_positions)
    
    # Fade-in анимация: появление за 0.5 сек, держится 1.5 сек, исчезает 0.5 сек
    hook_duration = min(2.0, duration * 0.3)  # максимум 2 секунды
    fade_in = 0.4
    hold_time = hook_duration - 0.8
    fade_out = 0.4
    
    # Alpha с fade эффектом
    alpha = (
        f"if(lt(t,{fade_in}),t/{fade_in},"
        f"if(lt(t,{fade_in + hold_time}),1,"
        f"if(lt(t,{hook_duration}),({hook_duration}-t)/{fade_out},0)))"
    )
    
    # Slide анимация: текст двигается снизу вверх
    slide_offset = int(height * 0.05)
    animated_y = f"({text_y})-{slide_offset}*(1-min(t/{fade_in},1))"
    
    # Стиль: белый текст с тенью для читаемости
    hook_filter = (
        f"drawtext=text='{hook_text}':"
        f"fontsize={fontsize}:"
        f"fontcolor=white:"
        f"shadowcolor=black@0.7:"
        f"shadowx=2:shadowy=2:"
        f"x=(w-text_w)/2:"
        f"y={animated_y}:"
        f"alpha='{alpha}':"
        f"enable='lt(t,{hook_duration})'"
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
    shake_filter = (
        f"crop=w=iw-{shake_x*2}:h=ih-{shake_y*2}:"
        f"x='{shake_x}+{shake_x}*sin({shake_freq}*t)':"
        f"y='{shake_y}+{shake_y}*sin({shake_freq}*t*1.3)',"
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

def _build_tiktok_filter_v2(width: int, height: int, duration: float) -> Tuple[str, str, dict]:
    """
    ANTI-TIKTOK 2026 Filter + ANTI-STATIC CONTENT:
    - Aggressive watermark removal
    - Forced creative layer
    - Motion scripting
    - Segment variation (мин. 3 сегмента)
    - Anti-source pattern
    - FORCED HOOK (0-2 сек)
    - SEGMENTED MOTION
    - ANTI-LOW-QUALITY SIGNAL
    """
    v = TIKTOK_VIDEO
    a = TIKTOK_AUDIO
    
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
    # Лучше ИСКУССТВЕННОЕ движение, чем статичный оригинал
    # ═══════════════════════════════════════════════════════════════════
    
    # 3a. ОСНОВНОЕ MOTION (zoom/pan) - ВСЕГДА применяется
    motion_type = random.choice(["zoom_in", "zoom_out", "pan", "combo"])
    if motion_type == "zoom_in":
        zoom_start = 1.0
        zoom_end = _rand(1.03, 1.08)  # усилен zoom
        filters.append(f"zoompan=z='min({zoom_start}+on*{(zoom_end-zoom_start)/30/duration},{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    elif motion_type == "zoom_out":
        zoom_start = _rand(1.04, 1.08)
        zoom_end = 1.0
        filters.append(f"zoompan=z='max({zoom_start}-on*{(zoom_start-zoom_end)/30/duration},{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    elif motion_type == "pan":
        pan_x = random.randint(-20, 20)
        pan_y = random.randint(-10, 10)
        filters.append(f"crop=w={width-40}:h={height-20}:x='20+{pan_x}*t/{duration}':y='10+{pan_y}*sin(t/{duration}*3.14)',scale={width}:{height}:flags=lanczos")
    else:  # combo: zoom + pan
        zoom_delta = _rand(0.02, 0.05)
        pan_x = random.randint(-10, 10)
        filters.append(f"zoompan=z='1+{zoom_delta}*sin(t/{duration}*3.14)':x='iw/2-(iw/zoom/2)+{pan_x}*sin(t*2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    
    # 3b. MICRO-SHAKE для "живости" (всегда)
    shake_intensity = random.randint(2, 4)
    shake_freq = _rand(10, 18)
    filters.append(
        f"crop=w=iw-{shake_intensity*2}:h=ih-{shake_intensity*2}:"
        f"x='{shake_intensity}+{shake_intensity}*sin({shake_freq}*t)':"
        f"y='{shake_intensity}+{shake_intensity}*sin({shake_freq}*t*1.3)',"
        f"scale={width}:{height}:flags=lanczos"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: SEGMENTED MOTION (минимум 3 сегмента!)
    # ═══════════════════════════════════════════════════════════════════
    
    # 4. COLOR GRADING (segment variation) - усилен
    segments = _build_segment_variation(duration, force_motion=True)
    for seg in segments:
        eq_filter = (
            f"eq=brightness={seg['brightness']:.4f}:"
            f"contrast={seg['contrast']:.4f}:"
            f"saturation={seg['saturation']:.4f}:"
            f"gamma={seg['gamma']:.4f}:"
            f"enable='between(t,{seg['start']:.2f},{seg['end']:.2f})'"
        )
        filters.append(eq_filter)
    
    # 4b. PULSE эффект между сегментами (имитация jump cut)
    pulse_interval = duration / len(segments)
    filters.append(
        f"eq=brightness=0.04*sin(2*PI*t/{pulse_interval}):"
        f"enable='1'"
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
    # ANTI-STATIC: FORCED HOOK (0-2 сек) - ОБЯЗАТЕЛЬНО!
    # ═══════════════════════════════════════════════════════════════════
    
    # 8a. HOOK TEXT в начале (всегда!)
    hook_text = random.choice(HOOK_TEXTS)
    hook_fontsize = int(min(width, height) * 0.055)
    hook_y = random.choice(["h*0.35", "h*0.45", "h*0.40"])
    hook_duration = min(2.0, duration * 0.25)
    hook_fade = 0.4
    # Alpha без внешних кавычек
    hook_alpha = f"if(lt(t\\,{hook_fade})\\,t/{hook_fade}\\,if(lt(t\\,{hook_duration-hook_fade})\\,1\\,if(lt(t\\,{hook_duration})\\,({hook_duration}-t)/{hook_fade}\\,0)))"
    filters.append(
        f"drawtext=text='{hook_text}':"
        f"fontsize={hook_fontsize}:"
        f"fontcolor=white:"
        f"shadowcolor=black@0.8:"
        f"shadowx=3:shadowy=3:"
        f"x=(w-text_w)/2:"
        f"y={hook_y}:"
        f"alpha={hook_alpha}:"
        f"enable='lt(t,{hook_duration})'"
    )
    
    # 8b. CREATIVE TEXT (60% шанс - увеличен)
    if random.random() > 0.4:
        text = random.choice(CREATIVE_TEXTS)
        fontsize = int(min(width, height) * 0.038)
        text_y = random.choice(["h*0.85-text_h", "h*0.10"])
        text_start = hook_duration + 0.5  # после hook
        fade_d = min(0.8, duration * 0.15)
        # Alpha с экранированными запятыми
        alpha = f"if(lt(t-{text_start}\\,{fade_d})\\,(t-{text_start})/{fade_d}\\,if(gt(t\\,{duration-fade_d})\\,({duration}-t)/{fade_d}\\,1))"
        filters.append(
            f"drawtext=text='{text}':"
            f"fontsize={fontsize}:"
            f"fontcolor=white@0.85:"
            f"x=(w-text_w)/2:"
            f"y={text_y}:"
            f"alpha={alpha}:"
            f"enable='gt(t,{text_start})'"
        )
    
    # 9. FINAL FPS
    fps = _rand_choice(v["fps_options"])
    filters.append(f"fps={fps}")
    
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
    
    # ENCODING PARAMS (рандомизация для anti-source pattern)
    gop = random.randint(12, 45)
    bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    preset = _rand_choice(v["presets"])
    
    params = {
        "bitrate": f"{bitrate}k",
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
        "profile": random.choice(["baseline", "main", "high"]),
        "level": random.choice(["3.1", "4.0", "4.1"]),
    }
    
    return video_filter, audio_filter, params

def _build_youtube_filter_v2(width: int, height: int, duration: float) -> Tuple[str, str, dict]:
    """
    YouTube Shorts Anti-Detection Filter + ANTI-STATIC CONTENT
    """
    v = YOUTUBE_VIDEO
    a = YOUTUBE_AUDIO
    
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
    # ═══════════════════════════════════════════════════════════════════
    motion_type = random.choice(["zoom_in", "zoom_out", "pan"])
    zoom_delta = _rand(0.03, 0.06)
    
    if motion_type == "zoom_in":
        filters.append(f"zoompan=z='min(1+on*{zoom_delta/30/duration},{1+zoom_delta})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    elif motion_type == "zoom_out":
        filters.append(f"zoompan=z='max({1+zoom_delta}-on*{zoom_delta/30/duration},1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    else:
        pan_x = random.randint(-15, 15)
        filters.append(f"crop=w={width-30}:h={height}:x='15+{pan_x}*t/{duration}':y=0,scale={width}:{height}:flags=lanczos")
    
    # Micro-shake
    shake = random.randint(2, 3)
    shake_freq = _rand(10, 15)
    filters.append(
        f"crop=w=iw-{shake*2}:h=ih-{shake*2}:"
        f"x='{shake}+{shake}*sin({shake_freq}*t)':"
        f"y='{shake}+{shake}*sin({shake_freq}*t*1.2)',"
        f"scale={width}:{height}:flags=lanczos"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # ANTI-STATIC: SEGMENTED MOTION (мин. 3 сегмента)
    # ═══════════════════════════════════════════════════════════════════
    segments = _build_segment_variation(duration, force_motion=True)
    for seg in segments:
        eq_filter = (
            f"eq=brightness={seg['brightness']:.4f}:"
            f"contrast={seg['contrast']:.4f}:"
            f"saturation={seg['saturation']:.4f}:"
            f"gamma={seg['gamma']:.4f}:"
            f"enable='between(t,{seg['start']:.2f},{seg['end']:.2f})'"
        )
        filters.append(eq_filter)
    
    # Pulse между сегментами
    pulse_interval = duration / len(segments)
    filters.append(f"eq=brightness=0.03*sin(2*PI*t/{pulse_interval}):enable='1'")
    
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
    # ANTI-STATIC: FORCED HOOK (0-2 сек)
    # ═══════════════════════════════════════════════════════════════════
    hook_text = random.choice(HOOK_TEXTS)
    hook_fontsize = int(min(width, height) * 0.05)
    hook_y = random.choice(["h*0.38", "h*0.45"])
    hook_duration = min(2.0, duration * 0.25)
    hook_fade = 0.35
    # Alpha с экранированными запятыми
    hook_alpha = f"if(lt(t\\,{hook_fade})\\,t/{hook_fade}\\,if(lt(t\\,{hook_duration-hook_fade})\\,1\\,if(lt(t\\,{hook_duration})\\,({hook_duration}-t)/{hook_fade}\\,0)))"
    filters.append(
        f"drawtext=text='{hook_text}':"
        f"fontsize={hook_fontsize}:"
        f"fontcolor=white:"
        f"shadowcolor=black@0.7:"
        f"shadowx=2:shadowy=2:"
        f"x=(w-text_w)/2:"
        f"y={hook_y}:"
        f"alpha={hook_alpha}:"
        f"enable='lt(t,{hook_duration})'"
    )
    
    # Creative text (50% шанс)
    if random.random() > 0.5:
        text = random.choice(CREATIVE_TEXTS)
        fontsize = int(min(width, height) * 0.035)
        text_y = "h*0.88-text_h"
        text_start = hook_duration + 0.3
        fade_d = 0.6
        # Alpha с экранированными запятыми
        alpha = f"if(lt(t-{text_start}\\,{fade_d})\\,(t-{text_start})/{fade_d}\\,1)"
        filters.append(
            f"drawtext=text='{text}':"
            f"fontsize={fontsize}:"
            f"fontcolor=white@0.8:"
            f"x=(w-text_w)/2:"
            f"y={text_y}:"
            f"alpha={alpha}:"
            f"enable='gt(t,{text_start})'"
        )
    
    filters.append("fps=30")
    
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
    bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    preset = _rand_choice(v["presets"])
    
    params = {
        "bitrate": f"{bitrate}k",
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
        "profile": random.choice(["main", "high"]),
        "level": random.choice(["4.0", "4.1"]),
    }
    
    return video_filter, audio_filter, params

# ══════════════════════════════════════════════════════════════════════════════
# LEGACY FILTER BUILDERS (fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _build_tiktok_filter(width: int, height: int) -> Tuple[str, str, dict]:
    """Legacy TikTok filter (без duration)"""
    return _build_tiktok_filter_v2(width, height, 30.0)

def _build_youtube_filter(width: int, height: int) -> Tuple[str, str, dict]:
    """Legacy YouTube filter (без duration)"""
    return _build_youtube_filter_v2(width, height, 30.0)

# ══════════════════════════════════════════════════════════════════════════════
# VIDEO INFO & PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

async def get_video_info(input_path: str) -> Optional[Tuple[int, int, float]]:
    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
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
        
        parts = stdout.decode().strip().split(",")
        if len(parts) >= 2:
            width = int(parts[0])
            height = int(parts[1])
            duration = float(parts[2]) if len(parts) > 2 and parts[2] else 60.0
            return width, height, duration
    except Exception as e:
        print(f"[FFPROBE] Error: {e}")
    
    return None

def _generate_random_timestamp() -> str:
    """Генерация рандомного timestamp для anti-source pattern"""
    import datetime
    days_ago = random.randint(1, 30)
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)
    seconds = random.randint(0, 59)
    
    dt = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=hours, minutes=minutes, seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000000Z")

async def process_video(input_path: str, output_path: str, mode: str) -> bool:
    """
    ANTI-TIKTOK 2026 Video Processing
    """
    info = await get_video_info(input_path)
    if not info:
        return False
    
    width, height, duration = info
    
    # Выбор фильтра на основе режима
    if mode == Mode.YOUTUBE:
        video_filter, audio_filter, params = _build_youtube_filter_v2(width, height, duration)
    else:
        video_filter, audio_filter, params = _build_tiktok_filter_v2(width, height, duration)
    
    # Рандомный encoder profile для anti-source pattern
    profile = params.get("profile", "main")
    level = params.get("level", "4.0")
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-profile:v", profile,
        "-level:v", level,
        "-preset", params["preset"],
        "-b:v", params["bitrate"],
        "-g", str(params["gop"]),
        "-keyint_min", str(params["gop"] // 2),
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", params["audio_bitrate"],
        "-ar", "44100",
        # ANTI-SOURCE PATTERN: удаление всех метаданных
        "-map_metadata", "-1",
        "-metadata", f"creation_time={_generate_random_timestamp()}",
        "-fflags", "+bitexact+genpts",
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
        "-movflags", "+faststart",
        output_path
    ]
    
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
    def __init__(self, user_id: int, input_path: str, mode: str, callback):
        self.user_id = user_id
        self.input_path = input_path
        self.mode = mode
        self.callback = callback
        self.output_path = str(get_temp_dir() / generate_unique_filename())

async def worker():
    while True:
        task: ProcessingTask = await processing_queue.get()
        
        try:
            success = await process_video(task.input_path, task.output_path, task.mode)
            await task.callback(success, task.output_path if success else None)
        except Exception as e:
            print(f"[WORKER] Error: {e}")
            await task.callback(False, None)
        finally:
            cleanup_file(task.input_path)
            processing_queue.task_done()

async def start_workers():
    init_queue()
    for _ in range(MAX_CONCURRENT_TASKS):
        asyncio.create_task(worker())

async def add_to_queue(task: ProcessingTask) -> bool:
    if processing_queue.full():
        return False
    
    await processing_queue.put(task)
    return True

def get_queue_size() -> int:
    return processing_queue.qsize() if processing_queue else 0
