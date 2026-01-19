"""
Virex — FFmpeg Video Processing
"""
import os
import random
import asyncio
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple
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

def _build_tiktok_filter(width: int, height: int) -> Tuple[str, dict]:
    v = TIKTOK_VIDEO
    a = TIKTOK_AUDIO
    
    crop_factor = _rand(v["crop_min"], v["crop_max"])
    crop_w = int(width * crop_factor)
    crop_h = int(height * crop_factor)
    crop_x = (width - crop_w) // 2
    crop_y = (height - crop_h) // 2
    
    speed = _rand(v["speed_min"], v["speed_max"])
    gamma = _rand(v["gamma_min"], v["gamma_max"])
    brightness = _rand(v["brightness_min"], v["brightness_max"])
    contrast = _rand(v["contrast_min"], v["contrast_max"])
    saturation = _rand(v["saturation_min"], v["saturation_max"])
    noise = random.randint(v["noise_min"], v["noise_max"])
    fps = _rand_choice(v["fps_options"])
    gop = random.randint(v["gop_min"], v["gop_max"])
    bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    preset = _rand_choice(v["presets"])
    scaler = _rand_choice(v["scalers"])
    
    do_blur = random.choice([True, False])
    blur_or_sharpen = "gblur=sigma=0.3" if do_blur else "unsharp=3:3:0.5:3:3:0.0"
    
    zoom_x = random.randint(-2, 2)
    zoom_y = random.randint(-2, 2)
    
    video_filter = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={width}:{height}:flags={scaler},"
        f"setpts={1/speed}*PTS,"
        f"eq=gamma={gamma:.4f}:brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:saturation={saturation:.4f},"
        f"noise=alls={noise}:allf=t,"
        f"{blur_or_sharpen},"
        f"crop={width-abs(zoom_x)*2}:{height-abs(zoom_y)*2}:{abs(zoom_x)}:{abs(zoom_y)},"
        f"scale={width}:{height}:flags={scaler},"
        f"fps={fps}"
    )
    
    audio_tempo = speed
    volume = _rand(a["volume_min"], a["volume_max"])
    
    audio_filter = f"atempo={audio_tempo:.4f},volume={volume:.4f}"
    
    eq_choice = random.randint(0, 2)
    if eq_choice == 1:
        audio_filter += ",lowshelf=g=1:f=200"
    elif eq_choice == 2:
        audio_filter += ",highshelf=g=-1:f=3000"
    
    params = {
        "bitrate": f"{bitrate}k",
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
    }
    
    return video_filter, audio_filter, params

def _build_youtube_filter(width: int, height: int) -> Tuple[str, dict]:
    v = YOUTUBE_VIDEO
    a = YOUTUBE_AUDIO
    
    crop_factor = _rand(v["crop_min"], v["crop_max"])
    crop_w = int(width * crop_factor)
    crop_h = int(height * crop_factor)
    crop_x = (width - crop_w) // 2
    crop_y = (height - crop_h) // 2
    
    speed = _rand(v["speed_min"], v["speed_max"])
    gamma = _rand(v["gamma_min"], v["gamma_max"])
    brightness = _rand(v["brightness_min"], v["brightness_max"])
    contrast = _rand(v["contrast_min"], v["contrast_max"])
    saturation = _rand(v["saturation_min"], v["saturation_max"])
    noise = random.randint(v["noise_min"], v["noise_max"])
    gop = random.randint(v["gop_min"], v["gop_max"])
    bitrate = random.randint(v["bitrate_min"], v["bitrate_max"])
    preset = _rand_choice(v["presets"])
    scaler = _rand_choice(v["scalers"])
    
    do_blur = random.choice([True, False])
    blur_or_sharpen = "gblur=sigma=0.4" if do_blur else "unsharp=3:3:0.6:3:3:0.0"
    
    zoom_x = random.randint(-3, 3)
    zoom_y = random.randint(-3, 3)
    
    timing_shift = _rand(-0.02, 0.02)
    
    video_filter = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={width}:{height}:flags={scaler},"
        f"setpts={1/speed + timing_shift}*PTS,"
        f"eq=gamma={gamma:.4f}:brightness={brightness:.4f}:"
        f"contrast={contrast:.4f}:saturation={saturation:.4f},"
        f"noise=alls={noise}:allf=t,"
        f"{blur_or_sharpen},"
        f"crop={width-abs(zoom_x)*2}:{height-abs(zoom_y)*2}:{abs(zoom_x)}:{abs(zoom_y)},"
        f"scale={width}:{height}:flags={scaler},"
        f"fps=30"
    )
    
    audio_tempo = speed
    volume = _rand(a["volume_min"], a["volume_max"])
    noise_vol = 10 ** (a["background_noise_db"] / 20)
    
    audio_filter = (
        f"aresample={a['resample_rate']},"
        f"atempo={audio_tempo:.4f},"
        f"volume={volume:.4f},"
        f"highpass=f=20,lowpass=f=18000,"
        f"anoisesrc=d=0.5:c=pink:a={noise_vol:.6f}[noise];"
        f"[0:a]aresample={a['resample_rate']},atempo={audio_tempo:.4f},volume={volume:.4f},"
        f"highpass=f=20,lowpass=f=18000[main];"
        f"[main][noise]amix=inputs=2:duration=first:weights=1 0.02"
    )
    
    simple_audio_filter = (
        f"aresample={a['resample_rate']},"
        f"atempo={audio_tempo:.4f},"
        f"volume={volume:.4f},"
        f"highpass=f=20,lowpass=f=18000,"
        f"lowshelf=g=2:f=150,highshelf=g=-1:f=4000"
    )
    
    params = {
        "bitrate": f"{bitrate}k",
        "preset": preset,
        "gop": gop,
        "audio_bitrate": a["audio_bitrate"],
    }
    
    return video_filter, simple_audio_filter, params

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

async def process_video(input_path: str, output_path: str, mode: str) -> bool:
    info = await get_video_info(input_path)
    if not info:
        return False
    
    width, height, duration = info
    
    if mode == Mode.YOUTUBE:
        video_filter, audio_filter, params = _build_youtube_filter(width, height)
    else:
        video_filter, audio_filter, params = _build_tiktok_filter(width, height)
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-preset", params["preset"],
        "-b:v", params["bitrate"],
        "-g", str(params["gop"]),
        "-c:a", "aac",
        "-b:a", params["audio_bitrate"],
        "-map_metadata", "-1",
        "-fflags", "+bitexact",
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
