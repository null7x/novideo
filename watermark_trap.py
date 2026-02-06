"""
Virex — Watermark-Trap System v1.0
═══════════════════════════════════════════════════════════════════════════════
Невидимый цифровой отпечаток нового поколения

🎯 Цель:
- Невидим для глаза
- Не убивается обычной уникализацией  
- Позволяет доказать источник видео
- Может "палить" вора при повторной загрузке

🧩 УРОВНИ:
1. Pixel Drift Trap (микросмещение пикселей)
2. Temporal Noise Signature (временной отпечаток)
3. Audio Phase Trap (фазовый сдвиг звука)
4. Compression Fingerprint (контроль артефактов кодека)
5. Ghost Metadata (ловушка в метаданных)
6. Neural Pattern Trap (паттерн для нейросети)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import hashlib
import json
import time
import struct
import random
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WatermarkTrapConfig:
    """Конфигурация Watermark-Trap"""
    # Мастер-ключ для генерации сигнатур
    master_secret: str = "VIREX_TRAP_2026_SECRET_KEY"
    
    # Уровни защиты (все включены по умолчанию)
    pixel_drift_enabled: bool = True
    temporal_noise_enabled: bool = True
    audio_phase_enabled: bool = True
    compression_fp_enabled: bool = True
    ghost_metadata_enabled: bool = True
    neural_pattern_enabled: bool = True
    
    # Параметры Pixel Drift
    pixel_drift_strength: float = 0.015  # ±1.5% RGB
    pixel_drift_density: float = 0.02    # 2% пикселей
    
    # Параметры Temporal Noise
    temporal_interval: int = 17          # каждые N кадров
    temporal_strength: float = 0.007     # ±0.7% яркость/контраст
    
    # Параметры Audio Phase
    audio_phase_shift_ms: float = 0.5    # сдвиг фазы в мс
    audio_freq_shift_hz: float = 0.3     # микросдвиг частоты
    
    # Параметры Compression Fingerprint
    custom_gop_pattern: bool = True
    custom_qp_offset: int = 1            # смещение QP
    
    # Параметры Ghost Metadata
    ghost_fields: List[str] = field(default_factory=lambda: [
        "virex_trap_id", "x_render_engine", "creation_tool_id",
        "content_hash", "processing_session", "encoder_signature"
    ])
    
    # Параметры Neural Pattern
    neural_pattern_strength: float = 0.008
    neural_pattern_layers: int = 3

# Глобальный конфиг
TRAP_CONFIG = WatermarkTrapConfig()

# ══════════════════════════════════════════════════════════════════════════════
# WATERMARK KEY GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrapSignature:
    """Сигнатура Watermark-Trap для конкретного видео"""
    user_id: int
    video_hash: str
    timestamp: float
    random_salt: str
    master_key: str
    
    # Производные ключи для каждого уровня
    pixel_key: str = ""
    temporal_key: str = ""
    audio_key: str = ""
    compression_key: str = ""
    metadata_key: str = ""
    neural_key: str = ""
    
    def __post_init__(self):
        """Генерация производных ключей"""
        base = f"{self.master_key}:{self.user_id}:{self.video_hash}:{self.timestamp}:{self.random_salt}"
        
        self.pixel_key = hashlib.sha256(f"{base}:pixel".encode()).hexdigest()[:32]
        self.temporal_key = hashlib.sha256(f"{base}:temporal".encode()).hexdigest()[:32]
        self.audio_key = hashlib.sha256(f"{base}:audio".encode()).hexdigest()[:32]
        self.compression_key = hashlib.sha256(f"{base}:compression".encode()).hexdigest()[:32]
        self.metadata_key = hashlib.sha256(f"{base}:metadata".encode()).hexdigest()[:32]
        self.neural_key = hashlib.sha256(f"{base}:neural".encode()).hexdigest()[:32]
    
    @property
    def full_signature(self) -> str:
        """Полная сигнатура для хранения"""
        data = {
            "user_id": self.user_id,
            "video_hash": self.video_hash,
            "timestamp": self.timestamp,
            "salt": self.random_salt,
            "keys": {
                "pixel": self.pixel_key[:8],
                "temporal": self.temporal_key[:8],
                "audio": self.audio_key[:8],
                "compression": self.compression_key[:8],
                "metadata": self.metadata_key[:8],
                "neural": self.neural_key[:8],
            }
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "video_hash": self.video_hash,
            "timestamp": self.timestamp,
            "salt": self.random_salt,
            "signature": self.full_signature,
            "created_at": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


def generate_trap_signature(user_id: int, video_path: str) -> TrapSignature:
    """Генерация уникальной сигнатуры для видео"""
    
    # Хеш видео файла
    video_hash = _calculate_file_hash(video_path)
    
    # Временная метка
    timestamp = time.time()
    
    # Случайная соль
    random_salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    
    return TrapSignature(
        user_id=user_id,
        video_hash=video_hash,
        timestamp=timestamp,
        random_salt=random_salt,
        master_key=TRAP_CONFIG.master_secret
    )


def _calculate_file_hash(filepath: str) -> str:
    """Быстрый хеш файла (первые и последние 1MB)"""
    try:
        file_size = os.path.getsize(filepath)
        chunk_size = 1024 * 1024  # 1MB
        
        hasher = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            # Первый чанк
            hasher.update(f.read(chunk_size))
            
            # Последний чанк (если файл достаточно большой)
            if file_size > chunk_size * 2:
                f.seek(-chunk_size, 2)
                hasher.update(f.read(chunk_size))
            
            # Размер файла
            hasher.update(struct.pack('>Q', file_size))
        
        return hasher.hexdigest()[:32]
    except Exception:
        return hashlib.sha256(os.urandom(16)).hexdigest()[:32]


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 1: PIXEL DRIFT TRAP
# ══════════════════════════════════════════════════════════════════════════════

class PixelDriftTrap:
    """
    Невидимое микросмещение RGB/яркости
    
    - Случайные пиксели: ±1-2 значения RGB
    - По псевдослучайному ключу
    - Меняется по кадрам
    - После сжатия TikTok/YouTube — частично сохраняется
    """
    
    @staticmethod
    def generate_filter(signature: TrapSignature, width: int, height: int) -> str:
        """
        Генерация FFmpeg фильтра для Pixel Drift
        
        Используем geq (generic equation) для попиксельного изменения
        """
        # Сид из ключа
        seed = int(signature.pixel_key[:8], 16) % 1000000
        
        # Параметры drift
        strength = TRAP_CONFIG.pixel_drift_strength
        
        # Генерируем паттерн смещения на основе позиции и сида
        # Используем sin/cos для создания волнообразного паттерна
        
        # Формула: добавляем микро-вариацию зависящую от X, Y и номера кадра
        # geq фильтр позволяет модифицировать каждый пиксель
        
        # Яркость: микро-сдвиг на основе позиции
        lum_offset = strength * 255  # ~3-4 уровня
        
        # Паттерн на основе сида
        phase_x = (seed % 100) / 100.0 * 3.14159
        phase_y = ((seed // 100) % 100) / 100.0 * 3.14159
        freq = 0.01 + (seed % 50) / 5000.0
        
        # Создаём невидимый drift паттерн
        # lum = исходная яркость + микро-синусоида
        geq_filter = (
            f"geq="
            f"lum='clip(lum(X,Y) + {lum_offset:.3f}*sin({freq:.6f}*X + {phase_x:.4f})*sin({freq:.6f}*Y + {phase_y:.4f})*sin(N*0.1), 0, 255)':"
            f"cb='cb(X,Y)':"
            f"cr='cr(X,Y)'"
        )
        
        return geq_filter
    
    @staticmethod
    def generate_subtle_filter(signature: TrapSignature) -> str:
        """Облегчённый вариант через eq + noise"""
        seed = int(signature.pixel_key[:8], 16)
        
        # Микро-сдвиг яркости уникальный для пользователя
        brightness_offset = ((seed % 200) - 100) / 10000.0  # ±0.01
        
        # Микро-шум с уникальным паттерном (c0s max = 100)
        noise_seed = (seed % 50) + 1  # 1-50, безопасный диапазон
        
        return f"eq=brightness={brightness_offset:.6f},noise=c0s={noise_seed}:c0f=t+u:alls=3:allf=t+u"


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 2: TEMPORAL NOISE SIGNATURE
# ══════════════════════════════════════════════════════════════════════════════

class TemporalNoiseTrap:
    """
    Шум, завязанный на время (номер кадра)
    
    Каждые N кадров:
    - микроконтраст
    - микрояркость
    
    Паттерн:
    - кадр 17 → +0.7%
    - кадр 43 → −0.5%
    - кадр 91 → +0.9%
    
    Уникален для каждого пользователя
    """
    
    @staticmethod
    def generate_keyframes(signature: TrapSignature, total_frames: int) -> List[Dict]:
        """Генерация временных точек с изменениями"""
        seed = int(signature.temporal_key[:8], 16)
        random.seed(seed)
        
        keyframes = []
        interval = TRAP_CONFIG.temporal_interval
        strength = TRAP_CONFIG.temporal_strength
        
        for frame in range(interval, total_frames, interval):
            # Уникальное изменение для каждого keyframe
            brightness_delta = (random.random() - 0.5) * 2 * strength
            contrast_delta = (random.random() - 0.5) * 2 * strength * 0.5
            
            keyframes.append({
                "frame": frame,
                "brightness": brightness_delta,
                "contrast": contrast_delta,
            })
        
        return keyframes
    
    @staticmethod
    def generate_filter(signature: TrapSignature, fps: float = 30.0) -> str:
        """
        Генерация FFmpeg фильтра для временной сигнатуры
        
        Используем sendcmd для изменения параметров в определённые моменты
        """
        seed = int(signature.temporal_key[:8], 16)
        
        # Создаём уникальный паттерн на основе сида
        # Используем sin с уникальной частотой и фазой
        freq = 0.05 + (seed % 100) / 2000.0
        phase = (seed % 1000) / 1000.0 * 6.28
        amplitude = TRAP_CONFIG.temporal_strength
        
        # eq фильтр с временной модуляцией через выражение
        # n = номер кадра, t = время
        temporal_filter = (
            f"eq=brightness='{amplitude:.5f}*sin({freq:.5f}*n + {phase:.4f})':"
            f"contrast='1 + {amplitude * 0.3:.5f}*cos({freq * 1.3:.5f}*n + {phase:.4f})'"
        )
        
        return temporal_filter


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 3: AUDIO PHASE TRAP
# ══════════════════════════════════════════════════════════════════════════════

class AudioPhaseTrap:
    """
    Фазовый сдвиг звука (НЕ громкость)
    
    - Человек не слышит
    - Shazam / AI видит
    - Можно связать с ID пользователя
    - Почти никто это не чистит
    """
    
    @staticmethod
    def generate_filter(signature: TrapSignature) -> str:
        """
        Генерация audio фильтра для фазового сдвига
        
        Используем:
        - aphaser: фазовый сдвиг
        - aecho: микро-эхо (< 1ms, не слышно)
        - highpass/lowpass для микро-модуляции спектра
        """
        seed = int(signature.audio_key[:8], 16)
        
        # Параметры на основе сида
        phase_delay = TRAP_CONFIG.audio_phase_shift_ms + (seed % 100) / 1000.0  # 0.5-0.6ms
        
        # Микро-частотные сдвиги
        freq_shift = TRAP_CONFIG.audio_freq_shift_hz + (seed % 50) / 100.0  # 0.3-0.8 Hz
        
        # Ультра-тихое эхо (не слышимое человеком)
        echo_delay = 0.5 + (seed % 10) / 100.0  # 0.5-0.6ms
        echo_decay = 0.01 + (seed % 5) / 1000.0  # 0.01-0.015
        
        # Генерируем комплексный audio fingerprint
        # 1. Микро фазовый сдвиг
        # 2. Ультра-тихое эхо
        # 3. Микросдвиг EQ (не слышимый)
        
        audio_filter = (
            f"aecho=0.6:0.3:{echo_delay:.3f}:{echo_decay:.4f},"
            f"aphaser=type=t:speed={freq_shift:.2f}:decay=0.1,"
            f"equalizer=f={(seed % 1000) + 50}:t=q:w=0.1:g=0.01"
        )
        
        return audio_filter
    
    @staticmethod
    def generate_subtle_filter(signature: TrapSignature) -> str:
        """Минимальный фильтр (только фаза)"""
        seed = int(signature.audio_key[:8], 16)
        
        # Инвертируем часть спектра (не слышно, но уникально)
        freq = 18000 + (seed % 2000)  # 18-20kHz (за пределами слышимости для большинства)
        
        return f"highpass=f={freq}:poles=1"


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 4: COMPRESSION FINGERPRINT
# ══════════════════════════════════════════════════════════════════════════════

class CompressionFingerprint:
    """
    Контроль артефактов кодека
    
    - Нестандартный профиль кодирования
    - Нестандартный GOP
    - Нестандартный QP-паттерн
    
    Даже после перекодирования остаётся статистический след
    """
    
    @staticmethod
    def generate_encoding_params(signature: TrapSignature) -> Dict[str, Any]:
        """
        Генерация уникальных параметров кодирования
        """
        seed = int(signature.compression_key[:8], 16)
        
        # Уникальные параметры GOP
        keyint = 30 + (seed % 20)  # 30-50 вместо стандартных 30
        min_keyint = 1 + (seed % 5)  # 1-5
        
        # Уникальный QP offset
        qp_offset = TRAP_CONFIG.custom_qp_offset + (seed % 3)  # 1-3
        
        # Уникальные параметры B-frames
        bframes = 2 + (seed % 4)  # 2-5
        
        # Уникальный ref frames
        ref_frames = 3 + (seed % 3)  # 3-5
        
        # Уникальные параметры rate control
        qcomp = 0.6 + (seed % 20) / 100.0  # 0.60-0.80
        
        return {
            "keyint": keyint,
            "min_keyint": min_keyint,
            "qp_offset": qp_offset,
            "bframes": bframes,
            "ref_frames": ref_frames,
            "qcomp": qcomp,
            # x264/x265 специфичные
            "x264_params": (
                f"keyint={keyint}:min-keyint={min_keyint}:"
                f"bframes={bframes}:ref={ref_frames}:"
                f"qcomp={qcomp:.2f}:aq-mode=2:aq-strength=1.{seed % 10}"
            ),
        }
    
    @staticmethod
    def get_ffmpeg_params(signature: TrapSignature) -> List[str]:
        """Получить FFmpeg параметры для кодирования"""
        params = CompressionFingerprint.generate_encoding_params(signature)
        
        return [
            "-x264-params", params["x264_params"],
            "-g", str(params["keyint"]),
            "-bf", str(params["bframes"]),
            "-refs", str(params["ref_frames"]),
        ]


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 5: GHOST METADATA
# ══════════════════════════════════════════════════════════════════════════════

class GhostMetadata:
    """
    Ловушка в метаданных
    
    - Фейковые поля
    - Нестандартный порядок
    - Мусорные поля
    
    TikTok/YouTube часть чистят,
    НО при повторной загрузке иногда всплывает остаток
    """
    
    @staticmethod
    def generate_metadata(signature: TrapSignature) -> Dict[str, str]:
        """Генерация ghost-метаданных"""
        
        # Основные поля-ловушки
        metadata = {
            # Закодированный ID пользователя
            "encoder": f"Virex Pro v3.2 (id:{signature.user_id})",
            
            # Хеш сигнатуры
            "comment": f"VTrap:{signature.full_signature[:16]}",
            
            # Fake поля которые могут пережить обработку
            "software": f"VideoProcessor-{signature.metadata_key[:8]}",
            "handler_name": f"Virex-{signature.user_id % 10000}",
            "creation_time": datetime.fromtimestamp(signature.timestamp).isoformat(),
            
            # Скрытые поля
            "author": f"u{signature.user_id}",
            "copyright": f"VTRAP-{signature.full_signature[:8]}",
            
            # Мусорные поля (некоторые платформы не чистят)
            "artist": f"x{signature.random_salt[:6]}",
            "album": f"VIREX_{int(signature.timestamp) % 100000}",
            
            # Техническая информация
            "description": f"Processed by Virex Watermark-Trap System. ID: {signature.full_signature[:12]}",
        }
        
        return metadata
    
    @staticmethod
    def get_ffmpeg_metadata_args(signature: TrapSignature) -> List[str]:
        """FFmpeg аргументы для вставки метаданных"""
        metadata = GhostMetadata.generate_metadata(signature)
        
        args = []
        for key, value in metadata.items():
            args.extend(["-metadata", f"{key}={value}"])
        
        return args


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 6: NEURAL PATTERN TRAP
# ══════════════════════════════════════════════════════════════════════════════

class NeuralPatternTrap:
    """
    Паттерн, который "видит" только нейросеть
    
    - Микро-структуры
    - Неравномерность текстур
    - Повторяющиеся паттерны на разных сценах
    
    Позволяет распознать видео через AI-анализ
    """
    
    @staticmethod
    def generate_filter(signature: TrapSignature, width: int, height: int) -> str:
        """
        Генерация фильтра для neural pattern
        
        Создаём микро-паттерн который не виден глазу,
        но распознаётся нейросетями
        """
        seed = int(signature.neural_key[:8], 16)
        
        # Параметры паттерна
        strength = TRAP_CONFIG.neural_pattern_strength
        
        # Частоты паттерна (уникальные для пользователя)
        freq_x = 0.001 + (seed % 100) / 100000.0
        freq_y = 0.001 + ((seed // 100) % 100) / 100000.0
        phase = (seed % 1000) / 1000.0 * 6.28
        
        # Создаём текстурный паттерн через geq
        # Добавляем периодическую структуру, невидимую глазу
        neural_filter = (
            f"geq="
            f"lum='lum(X,Y) + {strength * 255:.3f}*sin({freq_x:.7f}*X*X + {freq_y:.7f}*Y*Y + {phase:.4f})':"
            f"cb='cb(X,Y)':"
            f"cr='cr(X,Y)'"
        )
        
        return neural_filter
    
    @staticmethod
    def generate_texture_overlay(signature: TrapSignature) -> str:
        """Генерация текстурного оверлея"""
        seed = int(signature.neural_key[:8], 16)
        
        # Создаём уникальный "отпечаток" через noise + blur
        # Noise создаёт паттерн, blur делает его незаметным
        noise_amount = 1 + (seed % 2)  # 1-2 (очень слабый)
        
        return f"noise=alls={noise_amount}:allf=t+u,gblur=sigma=0.3"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WATERMARK-TRAP PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

class WatermarkTrapProcessor:
    """
    Главный процессор Watermark-Trap
    
    Объединяет все 6 уровней защиты
    """
    
    def __init__(self, config: WatermarkTrapConfig = None):
        self.config = config or TRAP_CONFIG
        self.signatures_db: Dict[str, TrapSignature] = {}
    
    def create_signature(self, user_id: int, video_path: str) -> TrapSignature:
        """Создать сигнатуру для видео"""
        signature = generate_trap_signature(user_id, video_path)
        
        # Сохраняем в "БД"
        self.signatures_db[signature.full_signature] = signature
        
        return signature
    
    def get_video_filters(self, signature: TrapSignature, 
                          width: int = 1920, height: int = 1080,
                          has_audio: bool = True) -> Tuple[str, str]:
        """
        Получить video и audio фильтры для FFmpeg
        
        Returns:
            (video_filter, audio_filter)
        """
        video_filters = []
        audio_filters = []
        
        # Level 1: Pixel Drift (всегда используем subtle версию для скорости)
        if self.config.pixel_drift_enabled:
            video_filters.append(
                PixelDriftTrap.generate_subtle_filter(signature)
            )
        
        # Level 2: Temporal Noise
        if self.config.temporal_noise_enabled:
            video_filters.append(
                TemporalNoiseTrap.generate_filter(signature)
            )
        
        # Level 3: Audio Phase
        if self.config.audio_phase_enabled and has_audio:
            audio_filters.append(
                AudioPhaseTrap.generate_subtle_filter(signature)
            )
        
        # Level 6: Neural Pattern (subtle версия)
        if self.config.neural_pattern_enabled:
            video_filters.append(
                NeuralPatternTrap.generate_texture_overlay(signature)
            )
        
        # Объединяем фильтры
        video_filter = ",".join(video_filters) if video_filters else ""
        audio_filter = ",".join(audio_filters) if audio_filters else ""
        
        return video_filter, audio_filter
    
    def get_encoding_params(self, signature: TrapSignature) -> List[str]:
        """Получить параметры кодирования (Level 4)"""
        if self.config.compression_fp_enabled:
            return CompressionFingerprint.get_ffmpeg_params(signature)
        return []
    
    def get_metadata_params(self, signature: TrapSignature) -> List[str]:
        """Получить параметры метаданных (Level 5)"""
        if self.config.ghost_metadata_enabled:
            return GhostMetadata.get_ffmpeg_metadata_args(signature)
        return []
    
    def get_all_ffmpeg_additions(self, signature: TrapSignature,
                                  width: int = 1920, height: int = 1080,
                                  has_audio: bool = True) -> Dict[str, Any]:
        """
        Получить все дополнения для FFmpeg команды
        
        Returns:
            {
                "video_filter": str,
                "audio_filter": str,
                "encoding_params": List[str],
                "metadata_params": List[str],
                "signature": TrapSignature
            }
        """
        video_filter, audio_filter = self.get_video_filters(
            signature, width, height, has_audio
        )
        
        return {
            "video_filter": video_filter,
            "audio_filter": audio_filter,
            "encoding_params": self.get_encoding_params(signature),
            "metadata_params": self.get_metadata_params(signature),
            "signature": signature,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DETECTION MODE (Режим проверки)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DetectionResult:
    """Результат проверки видео на Watermark-Trap"""
    found: bool
    confidence: float  # 0.0 - 1.0
    user_id: Optional[int] = None
    timestamp: Optional[float] = None
    signature_match: Optional[str] = None
    detection_method: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_message(self, lang: str = "ru") -> str:
        """Форматирование результата для вывода"""
        if not self.found:
            if lang == "ru":
                return "❌ Watermark-Trap не найден\n\nВидео не обрабатывалось через Virex или метки были удалены."
            return "❌ Watermark-Trap not found\n\nVideo was not processed through Virex or marks were removed."
        
        if lang == "ru":
            return (
                f"✅ Найден Watermark-Trap!\n\n"
                f"👤 Источник: user_{self.user_id}\n"
                f"📅 Дата: {datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M')}\n"
                f"🎯 Уверенность: {self.confidence * 100:.1f}%\n"
                f"🔍 Метод: {self.detection_method}\n"
                f"🔐 Сигнатура: {self.signature_match[:16]}..."
            )
        else:
            return (
                f"✅ Watermark-Trap Found!\n\n"
                f"👤 Source: user_{self.user_id}\n"
                f"📅 Date: {datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M')}\n"
                f"🎯 Confidence: {self.confidence * 100:.1f}%\n"
                f"🔍 Method: {self.detection_method}\n"
                f"🔐 Signature: {self.signature_match[:16]}..."
            )


class WatermarkTrapDetector:
    """
    Детектор Watermark-Trap в видео
    
    Режим проверки:
    1. Загружаешь подозрительное видео
    2. Система извлекает сигнатуры
    3. Сравнивает с БД
    4. Выдаёт результат
    """
    
    def __init__(self, signatures_db: Dict[str, TrapSignature] = None):
        self.signatures_db = signatures_db or {}
    
    def add_signature(self, signature: TrapSignature):
        """Добавить сигнатуру в БД"""
        self.signatures_db[signature.full_signature] = signature
    
    def load_signatures_from_file(self, filepath: str):
        """Загрузить сигнатуры из файла"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                for sig_data in data:
                    sig = TrapSignature(
                        user_id=sig_data["user_id"],
                        video_hash=sig_data["video_hash"],
                        timestamp=sig_data["timestamp"],
                        random_salt=sig_data["salt"],
                        master_key=TRAP_CONFIG.master_secret
                    )
                    self.signatures_db[sig.full_signature] = sig
        except Exception as e:
            print(f"[TRAP] Failed to load signatures: {e}")
    
    def save_signatures_to_file(self, filepath: str):
        """Сохранить сигнатуры в файл"""
        try:
            data = [sig.to_dict() for sig in self.signatures_db.values()]
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[TRAP] Failed to save signatures: {e}")
    
    async def detect(self, video_path: str) -> DetectionResult:
        """
        Попытка обнаружить Watermark-Trap в видео
        
        Проверяем:
        1. Метаданные (быстро)
        2. Хеш видео (если совпадает с оригиналом)
        3. TODO: Анализ пикселей (медленно, требует ML)
        """
        result = DetectionResult(found=False, confidence=0.0)
        
        # Метод 1: Проверка метаданных
        metadata_result = await self._check_metadata(video_path)
        if metadata_result.found:
            return metadata_result
        
        # Метод 2: Проверка хеша (для неизменённых видео)
        hash_result = self._check_hash(video_path)
        if hash_result.found:
            return hash_result
        
        # Метод 3: Статистический анализ (базовый)
        # TODO: Полноценный ML анализ
        
        return result
    
    async def _check_metadata(self, video_path: str) -> DetectionResult:
        """Проверка ghost-метаданных"""
        try:
            from config import FFPROBE_PATH
            
            cmd = [
                FFPROBE_PATH,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode != 0:
                return DetectionResult(found=False, confidence=0.0)
            
            data = json.loads(stdout.decode())
            tags = data.get("format", {}).get("tags", {})
            
            # Ищем наши маркеры
            for key, value in tags.items():
                # Проверяем comment с VTrap
                if key.lower() == "comment" and value.startswith("VTrap:"):
                    sig_fragment = value[6:22]  # Первые 16 символов сигнатуры
                    
                    # Ищем в БД
                    for full_sig, signature in self.signatures_db.items():
                        if full_sig.startswith(sig_fragment):
                            return DetectionResult(
                                found=True,
                                confidence=0.95,
                                user_id=signature.user_id,
                                timestamp=signature.timestamp,
                                signature_match=full_sig,
                                detection_method="Ghost Metadata (comment)",
                                details={"tag": key, "value": value}
                            )
                
                # Проверяем encoder с id:
                if key.lower() == "encoder" and "id:" in value:
                    try:
                        user_id = int(value.split("id:")[1].split(")")[0])
                        return DetectionResult(
                            found=True,
                            confidence=0.85,
                            user_id=user_id,
                            timestamp=time.time(),
                            signature_match="partial_encoder",
                            detection_method="Ghost Metadata (encoder)",
                            details={"tag": key, "value": value}
                        )
                    except:
                        pass
            
            return DetectionResult(found=False, confidence=0.0)
            
        except Exception as e:
            print(f"[TRAP] Metadata check failed: {e}")
            return DetectionResult(found=False, confidence=0.0)
    
    def _check_hash(self, video_path: str) -> DetectionResult:
        """Проверка по хешу файла"""
        video_hash = _calculate_file_hash(video_path)
        
        for full_sig, signature in self.signatures_db.items():
            if signature.video_hash == video_hash:
                return DetectionResult(
                    found=True,
                    confidence=0.99,
                    user_id=signature.user_id,
                    timestamp=signature.timestamp,
                    signature_match=full_sig,
                    detection_method="Video Hash Match",
                    details={"hash": video_hash}
                )
        
        return DetectionResult(found=False, confidence=0.0)


# ══════════════════════════════════════════════════════════════════════════════
# STORAGE: Persistent signatures database
# ══════════════════════════════════════════════════════════════════════════════

SIGNATURES_FILE = "watermark_signatures.json"

# Глобальные инстансы
_trap_processor: Optional[WatermarkTrapProcessor] = None
_trap_detector: Optional[WatermarkTrapDetector] = None


def get_trap_processor() -> WatermarkTrapProcessor:
    """Получить глобальный процессор"""
    global _trap_processor
    if _trap_processor is None:
        _trap_processor = WatermarkTrapProcessor()
    return _trap_processor


def get_trap_detector() -> WatermarkTrapDetector:
    """Получить глобальный детектор"""
    global _trap_detector
    if _trap_detector is None:
        _trap_detector = WatermarkTrapDetector()
        # Загружаем сигнатуры
        if os.path.exists(SIGNATURES_FILE):
            _trap_detector.load_signatures_from_file(SIGNATURES_FILE)
    return _trap_detector


def save_signature(signature: TrapSignature):
    """Сохранить сигнатуру в файл"""
    detector = get_trap_detector()
    detector.add_signature(signature)
    detector.save_signatures_to_file(SIGNATURES_FILE)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR FFmpeg INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def apply_watermark_trap(
    user_id: int,
    input_path: str,
    existing_video_filter: str = "",
    existing_audio_filter: str = "",
    width: int = 1920,
    height: int = 1080,
    has_audio: bool = True
) -> Tuple[str, str, List[str], TrapSignature]:
    """
    Применить Watermark-Trap к FFmpeg фильтрам
    
    Args:
        user_id: ID пользователя
        input_path: Путь к входному видео
        existing_video_filter: Существующий video filter
        existing_audio_filter: Существующий audio filter
        width: Ширина видео
        height: Высота видео
        has_audio: Есть ли аудио
    
    Returns:
        (new_video_filter, new_audio_filter, extra_params, signature)
    """
    processor = get_trap_processor()
    
    # Создаём сигнатуру
    signature = processor.create_signature(user_id, input_path)
    
    # Получаем дополнения
    additions = processor.get_all_ffmpeg_additions(
        signature, width, height, has_audio
    )
    
    # Объединяем с существующими фильтрами
    video_filter = existing_video_filter
    if additions["video_filter"]:
        if video_filter:
            video_filter = f"{video_filter},{additions['video_filter']}"
        else:
            video_filter = additions["video_filter"]
    
    audio_filter = existing_audio_filter
    if additions["audio_filter"]:
        if audio_filter:
            audio_filter = f"{audio_filter},{additions['audio_filter']}"
        else:
            audio_filter = additions["audio_filter"]
    
    # Объединяем extra params
    extra_params = additions["encoding_params"] + additions["metadata_params"]
    
    # Сохраняем сигнатуру
    save_signature(signature)
    
    return video_filter, audio_filter, extra_params, signature


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Config
    "WatermarkTrapConfig",
    "TRAP_CONFIG",
    
    # Core classes
    "TrapSignature",
    "WatermarkTrapProcessor",
    "WatermarkTrapDetector",
    "DetectionResult",
    
    # Level classes
    "PixelDriftTrap",
    "TemporalNoiseTrap",
    "AudioPhaseTrap",
    "CompressionFingerprint",
    "GhostMetadata",
    "NeuralPatternTrap",
    
    # Functions
    "generate_trap_signature",
    "get_trap_processor",
    "get_trap_detector",
    "save_signature",
    "apply_watermark_trap",
]
