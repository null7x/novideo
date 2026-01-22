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

def _build_segment_variation(duration: float) -> List[dict]:
    """
    Разбивка видео на сегменты с разными параметрами.
    Каждый сегмент получает уникальные настройки.
    """
    num_segments = random.randint(2, 4)
    segment_duration = duration / num_segments
    
    segments = []
    for i in range(num_segments):
        segment = {
            "start": i * segment_duration,
            "end": (i + 1) * segment_duration,
            "brightness": _rand(-0.05, 0.05),
            "contrast": _rand(0.95, 1.05),
            "saturation": _rand(0.95, 1.05),
            "gamma": _rand(0.97, 1.03),
            "speed": _rand(0.98, 1.02),
        }
        segments.append(segment)
    
    return segments

# ══════════════════════════════════════════════════════════════════════════════
# ANTI-TIKTOK 2026: MAIN FILTER BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_tiktok_filter_v2(width: int, height: int, duration: float) -> Tuple[str, str, dict]:
    """
    ANTI-TIKTOK 2026 Filter:
    - Aggressive watermark removal
    - Forced creative layer
    - Motion scripting
    - Segment variation
    - Anti-source pattern
    """
    v = TIKTOK_VIDEO
    a = TIKTOK_AUDIO
    
    filters = []
    
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
    
    # 3. MOTION EFFECT (zoom/pan) - 70% шанс
    use_motion = random.random() > 0.3
    if use_motion and duration > 3:
        motion_type = random.choice(["zoom_in", "zoom_out", "pan"])
        if motion_type == "zoom_in":
            zoom_start = 1.0
            zoom_end = _rand(1.02, 1.06)
            filters.append(f"zoompan=z='min({zoom_start}+on*{(zoom_end-zoom_start)/30/duration},{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
        elif motion_type == "zoom_out":
            zoom_start = _rand(1.03, 1.06)
            zoom_end = 1.0
            filters.append(f"zoompan=z='max({zoom_start}-on*{(zoom_start-zoom_end)/30/duration},{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
        else:  # pan
            pan_x = random.randint(-15, 15)
            filters.append(f"crop=w={width-30}:h={height}:x='15+{pan_x}*t/{duration}':y=0,scale={width}:{height}:flags=lanczos")
    
    # 4. COLOR GRADING (segment variation)
    segments = _build_segment_variation(duration)
    for seg in segments:
        eq_filter = (
            f"eq=brightness={seg['brightness']:.4f}:"
            f"contrast={seg['contrast']:.4f}:"
            f"saturation={seg['saturation']:.4f}:"
            f"gamma={seg['gamma']:.4f}:"
            f"enable='between(t,{seg['start']:.2f},{seg['end']:.2f})'"
        )
        filters.append(eq_filter)
    
    # 5. FILM GRAIN (обязательно!)
    grain = random.randint(4, 10)
    filters.append(f"noise=alls={grain}:allf=t+u")
    
    # 6. VIGNETTE (50% шанс)
    if random.random() > 0.5:
        filters.append(f"vignette=angle={_rand(0.25, 0.4)}:mode=forward")
    
    # 7. BLUR/SHARPEN
    if random.random() > 0.5:
        filters.append("gblur=sigma=0.4")
    else:
        filters.append("unsharp=3:3:0.6:3:3:0.0")
    
    # 8. TEXT OVERLAY (40% шанс для "творческого контента")
    if random.random() > 0.6:
        text = random.choice(CREATIVE_TEXTS)
        fontsize = int(min(width, height) * 0.035)
        text_y = random.choice(["h*0.12", "h*0.88-text_h"])
        fade_d = min(0.8, duration * 0.15)
        alpha = f"if(lt(t,{fade_d}),t/{fade_d},if(gt(t,{duration-fade_d}),({duration}-t)/{fade_d},1))"
        filters.append(f"drawtext=text='{text}':fontsize={fontsize}:fontcolor=white@0.8:x=(w-text_w)/2:y={text_y}:alpha='{alpha}'")
    
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
    YouTube Shorts Anti-Detection Filter
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
    
    # Motion
    if random.random() > 0.4 and duration > 3:
        zoom_delta = _rand(0.02, 0.05)
        if random.random() > 0.5:
            filters.append(f"zoompan=z='min(1+on*{zoom_delta/30/duration},{1+zoom_delta})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
        else:
            filters.append(f"zoompan=z='max({1+zoom_delta}-on*{zoom_delta/30/duration},1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=30")
    
    # Segment color variation
    segments = _build_segment_variation(duration)
    for seg in segments:
        eq_filter = (
            f"eq=brightness={seg['brightness']:.4f}:"
            f"contrast={seg['contrast']:.4f}:"
            f"saturation={seg['saturation']:.4f}:"
            f"gamma={seg['gamma']:.4f}:"
            f"enable='between(t,{seg['start']:.2f},{seg['end']:.2f})'"
        )
        filters.append(eq_filter)
    
    # Grain
    grain = random.randint(3, 7)
    filters.append(f"noise=alls={grain}:allf=t+u")
    
    # Blur/Sharpen
    if random.random() > 0.5:
        filters.append("gblur=sigma=0.35")
    else:
        filters.append("unsharp=3:3:0.5:3:3:0.0")
    
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
