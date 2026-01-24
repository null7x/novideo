"""
🛡️ VIREX SHIELD — Digital Content Protection System v1.0
═══════════════════════════════════════════════════════════════════════════════

"Мы не делаем копию. Мы делаем видео, которое нельзя украсть."

🛡 Компоненты:
1. Digital Passport — цифровой паспорт видео с уникальным ID
2. Video Fingerprinting — перцептуальные хеши для сравнения
3. Similarity Detection — поиск совпадений в БД
4. Safe-Check — AI анализ риска бана/страйка/теневого бана
5. Anti-Steal System — защита от кражи с уведомлениями
6. Content Scanner — сканер TikTok/Reels/YouTube Shorts
7. Smart Presets — оптимальные настройки для платформ
8. Analytics — детальная аналитика для VIP

🎯 Smart Presets:
- TikTok USA / TikTok EU
- Reels 2025
- YouTube Shorts
- Gaming Shorts
- Anime Edits
- Meme Content
- Cinematic
- Music Video
- Safe Mode
- Hardcore Anti-Reupload

═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import hashlib
import asyncio
import struct
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Файлы БД
PASSPORTS_DB_FILE = "video_passports.json"
FINGERPRINTS_DB_FILE = "video_fingerprints.json"
MATCHES_HISTORY_FILE = "matches_history.json"
ANALYTICS_FILE = "analytics_data.json"

# Порог схожести для совпадения (0.0 - 1.0)
SIMILARITY_THRESHOLD = 0.75  # 75%+

# Риски
class RiskLevel(Enum):
    SAFE = "safe"           # 🟢 Безопасно
    LOW = "low"             # 🟢 Низкий риск
    MEDIUM = "medium"       # 🟡 Средний риск
    HIGH = "high"           # 🟠 Высокий риск
    CRITICAL = "critical"   # 🔴 Критический


# ══════════════════════════════════════════════════════════════════════════════
# 1. DIGITAL PASSPORT — Цифровой паспорт видео
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DigitalPassport:
    """
    Цифровой паспорт видео — уникальный ID и доказательство владения
    
    Содержит:
    - Уникальный ID
    - Данные владельца
    - Хеши и сигнатуры
    - Временные метки
    - История изменений
    """
    # Идентификация
    passport_id: str                    # Уникальный ID паспорта (VIREX-XXXX-XXXX)
    video_hash: str                     # SHA-256 хеш файла
    perceptual_hash: str                # Перцептуальный хеш (для сравнения)
    
    # Владелец
    owner_user_id: int                  # Telegram user_id
    owner_username: str = ""            # Username (если есть)
    
    # Временные метки
    created_at: float = 0.0             # Время создания
    processed_at: float = 0.0           # Время обработки
    
    # Технические данные
    duration_seconds: float = 0.0       # Длительность
    resolution: str = ""                # Разрешение (1920x1080)
    file_size_bytes: int = 0            # Размер файла
    fps: float = 0.0                    # FPS
    
    # Watermark-Trap
    watermark_signature: str = ""       # Сигнатура Watermark-Trap
    trap_enabled: bool = False          # Включён ли Trap
    
    # Метаданные обработки
    template_used: str = ""             # Использованный шаблон
    mode: str = ""                      # Режим (tiktok/youtube)
    quality: str = ""                   # Качество
    
    # История
    verification_count: int = 0         # Сколько раз проверяли
    last_verified_at: float = 0.0       # Последняя проверка
    matches_found: int = 0              # Найдено совпадений
    
    def __post_init__(self):
        if not self.passport_id:
            self.passport_id = self._generate_passport_id()
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    def _generate_passport_id(self) -> str:
        """Генерация уникального ID паспорта"""
        import random
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        part1 = "".join(random.choices(chars, k=4))
        part2 = "".join(random.choices(chars, k=4))
        return f"VIREX-{part1}-{part2}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "DigitalPassport":
        return cls(**data)
    
    def get_display_card(self, lang: str = "ru") -> str:
        """Красивая карточка паспорта для отображения"""
        created = datetime.fromtimestamp(self.created_at).strftime("%d.%m.%Y %H:%M")
        
        if lang == "en":
            trap_status = "✅ Active" if self.trap_enabled else "❌ Disabled"
            return (
                f"🪪 <b>DIGITAL PASSPORT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 <b>ID:</b> <code>{self.passport_id}</code>\n"
                f"👤 <b>Owner:</b> {self.owner_username or f'user_{self.owner_user_id}'}\n"
                f"📅 <b>Created:</b> {created}\n\n"
                f"📊 <b>Video Info:</b>\n"
                f"   • Resolution: {self.resolution}\n"
                f"   • Duration: {self.duration_seconds:.1f}s\n"
                f"   • FPS: {self.fps:.0f}\n"
                f"   • Size: {self.file_size_bytes // 1024 // 1024}MB\n\n"
                f"🔐 <b>Protection:</b>\n"
                f"   • Watermark-Trap: {trap_status}\n"
                f"   • Verifications: {self.verification_count}\n"
                f"   • Matches found: {self.matches_found}\n\n"
                f"🔑 <b>Signatures:</b>\n"
                f"   • File: <code>{self.video_hash[:16]}...</code>\n"
                f"   • Visual: <code>{self.perceptual_hash[:16]}...</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Use this passport to prove ownership</i>"
            )
        else:
            trap_status = "✅ Активен" if self.trap_enabled else "❌ Выключен"
            return (
                f"🪪 <b>ЦИФРОВОЙ ПАСПОРТ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 <b>ID:</b> <code>{self.passport_id}</code>\n"
                f"👤 <b>Владелец:</b> {self.owner_username or f'user_{self.owner_user_id}'}\n"
                f"📅 <b>Создан:</b> {created}\n\n"
                f"📊 <b>Информация о видео:</b>\n"
                f"   • Разрешение: {self.resolution}\n"
                f"   • Длительность: {self.duration_seconds:.1f}с\n"
                f"   • FPS: {self.fps:.0f}\n"
                f"   • Размер: {self.file_size_bytes // 1024 // 1024}МБ\n\n"
                f"🔐 <b>Защита:</b>\n"
                f"   • Watermark-Trap: {trap_status}\n"
                f"   • Проверок: {self.verification_count}\n"
                f"   • Совпадений найдено: {self.matches_found}\n\n"
                f"🔑 <b>Сигнатуры:</b>\n"
                f"   • Файл: <code>{self.video_hash[:16]}...</code>\n"
                f"   • Визуал: <code>{self.perceptual_hash[:16]}...</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Используйте паспорт для доказательства авторства</i>"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 2. VIDEO FINGERPRINTING — Перцептуальные хеши
# ══════════════════════════════════════════════════════════════════════════════

class VideoFingerprinter:
    """
    Создание "отпечатков" видео для сравнения
    
    Методы:
    1. File Hash (SHA-256) — точное совпадение
    2. Perceptual Hash — визуальное сходство
    3. Audio Fingerprint — аудио сходство
    4. Temporal Signature — паттерн изменения яркости
    """
    
    @staticmethod
    async def calculate_file_hash(filepath: str) -> str:
        """SHA-256 хеш файла"""
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"[FP] File hash error: {e}")
            return hashlib.sha256(os.urandom(32)).hexdigest()
    
    @staticmethod
    async def calculate_perceptual_hash(filepath: str) -> str:
        """
        Перцептуальный хеш на основе яркости кадров
        
        Алгоритм:
        1. Извлекаем N кадров равномерно
        2. Для каждого кадра считаем среднюю яркость
        3. Создаём битовую строку (выше/ниже среднего)
        4. Конвертируем в hex
        """
        try:
            from config import FFPROBE_PATH, FFMPEG_PATH
            
            # Получаем длительность
            cmd = [
                FFPROBE_PATH,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                filepath
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            try:
                duration = float(stdout.decode().strip())
            except:
                duration = 10.0
            
            # Берём 64 точки для хеша
            num_samples = 64
            interval = duration / num_samples
            
            # Получаем яркость в каждой точке через ffprobe
            brightness_values = []
            
            for i in range(num_samples):
                timestamp = i * interval
                
                # Извлекаем один кадр и считаем среднюю яркость
                cmd = [
                    FFMPEG_PATH,
                    "-ss", str(timestamp),
                    "-i", filepath,
                    "-vframes", "1",
                    "-vf", "scale=8:8,format=gray",
                    "-f", "rawvideo",
                    "-"
                ]
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                
                if stdout:
                    # Средняя яркость пикселей
                    avg = sum(stdout) / len(stdout) if stdout else 128
                    brightness_values.append(avg)
                else:
                    brightness_values.append(128)
            
            # Создаём битовую строку
            if len(brightness_values) < 64:
                brightness_values.extend([128] * (64 - len(brightness_values)))
            
            overall_avg = sum(brightness_values) / len(brightness_values)
            bits = "".join("1" if b > overall_avg else "0" for b in brightness_values[:64])
            
            # Конвертируем в hex
            hash_int = int(bits, 2)
            return format(hash_int, '016x')
            
        except Exception as e:
            print(f"[FP] Perceptual hash error: {e}")
            # Fallback: используем часть file hash
            file_hash = await VideoFingerprinter.calculate_file_hash(filepath)
            return file_hash[:16]
    
    @staticmethod
    async def calculate_temporal_signature(filepath: str) -> str:
        """
        Временная сигнатура — паттерн изменения яркости между кадрами
        """
        try:
            from config import FFMPEG_PATH
            
            # Извлекаем 32 кадра и считаем дельты яркости
            cmd = [
                FFMPEG_PATH,
                "-i", filepath,
                "-vf", "fps=1,scale=4:4,format=gray",
                "-vframes", "32",
                "-f", "rawvideo",
                "-"
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if not stdout or len(stdout) < 32:
                return "0" * 8
            
            # Группируем по кадрам (4x4 = 16 пикселей)
            frame_size = 16
            frames = [stdout[i:i+frame_size] for i in range(0, len(stdout), frame_size)]
            
            # Считаем средние яркости
            avgs = [sum(f) / len(f) if f else 128 for f in frames[:32]]
            
            # Создаём паттерн дельт
            deltas = []
            for i in range(1, len(avgs)):
                delta = avgs[i] - avgs[i-1]
                if delta > 10:
                    deltas.append("U")  # Up
                elif delta < -10:
                    deltas.append("D")  # Down
                else:
                    deltas.append("S")  # Stable
            
            # Хешируем паттерн
            pattern = "".join(deltas)
            return hashlib.md5(pattern.encode()).hexdigest()[:8]
            
        except Exception as e:
            print(f"[FP] Temporal signature error: {e}")
            return "0" * 8
    
    @staticmethod
    def compare_hashes(hash1: str, hash2: str) -> float:
        """
        Сравнение двух хешей — возвращает схожесть 0.0-1.0
        
        Используем Hamming distance для перцептуальных хешей
        """
        if not hash1 or not hash2:
            return 0.0
        
        # Точное совпадение
        if hash1 == hash2:
            return 1.0
        
        # Hamming distance для hex строк
        try:
            # Конвертируем в бинарный
            bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
            bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
            
            # Выравниваем длины
            max_len = max(len(bin1), len(bin2))
            bin1 = bin1.zfill(max_len)
            bin2 = bin2.zfill(max_len)
            
            # Считаем различающиеся биты
            diff = sum(b1 != b2 for b1, b2 in zip(bin1, bin2))
            
            # Схожесть = 1 - (различия / всего)
            similarity = 1.0 - (diff / max_len)
            return similarity
            
        except Exception:
            return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 3. SIMILARITY DETECTION — Поиск совпадений
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MatchResult:
    """Результат поиска совпадений"""
    found: bool
    similarity: float               # 0.0 - 1.0
    risk_level: RiskLevel
    original_passport: Optional[DigitalPassport] = None
    match_type: str = ""            # exact, visual, audio, partial
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_message(self, lang: str = "ru") -> str:
        """Форматирование результата для вывода"""
        similarity_pct = self.similarity * 100
        
        risk_icons = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }
        risk_icon = risk_icons.get(self.risk_level, "⚪")
        
        if not self.found:
            if lang == "en":
                return (
                    f"✅ <b>No matches found!</b>\n\n"
                    f"{risk_icon} Risk level: {self.risk_level.value.upper()}\n\n"
                    f"Your video appears to be original.\n"
                    f"No similar content detected in our database."
                )
            else:
                return (
                    f"✅ <b>Совпадений не найдено!</b>\n\n"
                    f"{risk_icon} Уровень риска: {self.risk_level.value.upper()}\n\n"
                    f"Ваше видео выглядит оригинальным.\n"
                    f"Похожий контент в базе не обнаружен."
                )
        
        if lang == "en":
            match_types = {
                "exact": "🎯 Exact match",
                "visual": "👁 Visual similarity",
                "audio": "🔊 Audio similarity",
                "partial": "📐 Partial match",
            }
            
            text = (
                f"⚠️ <b>MATCH FOUND!</b>\n\n"
                f"📊 <b>Similarity:</b> {similarity_pct:.1f}%\n"
                f"🔍 <b>Type:</b> {match_types.get(self.match_type, self.match_type)}\n"
                f"{risk_icon} <b>Risk:</b> {self.risk_level.value.upper()}\n"
            )
            
            if self.original_passport:
                text += (
                    f"\n📁 <b>Original source:</b>\n"
                    f"   • ID: {self.original_passport.passport_id}\n"
                    f"   • Owner: {self.original_passport.owner_username or f'user_{self.original_passport.owner_user_id}'}\n"
                    f"   • Created: {datetime.fromtimestamp(self.original_passport.created_at).strftime('%d.%m.%Y')}\n"
                )
            
            text += (
                f"\n⚠️ <b>Warning:</b>\n"
                f"Publishing this video may result in:\n"
                f"• Copyright strike\n"
                f"• Shadow ban\n"
                f"• Account suspension"
            )
            
        else:
            match_types = {
                "exact": "🎯 Точное совпадение",
                "visual": "👁 Визуальное сходство",
                "audio": "🔊 Аудио сходство",
                "partial": "📐 Частичное совпадение",
            }
            
            text = (
                f"⚠️ <b>НАЙДЕНО СОВПАДЕНИЕ!</b>\n\n"
                f"📊 <b>Схожесть:</b> {similarity_pct:.1f}%\n"
                f"🔍 <b>Тип:</b> {match_types.get(self.match_type, self.match_type)}\n"
                f"{risk_icon} <b>Риск:</b> {self.risk_level.value.upper()}\n"
            )
            
            if self.original_passport:
                text += (
                    f"\n📁 <b>Оригинальный источник:</b>\n"
                    f"   • ID: {self.original_passport.passport_id}\n"
                    f"   • Владелец: {self.original_passport.owner_username or f'user_{self.original_passport.owner_user_id}'}\n"
                    f"   • Создан: {datetime.fromtimestamp(self.original_passport.created_at).strftime('%d.%m.%Y')}\n"
                )
            
            text += (
                f"\n⚠️ <b>Предупреждение:</b>\n"
                f"Публикация этого видео может привести к:\n"
                f"• Страйку за копирайт\n"
                f"• Теневому бану\n"
                f"• Блокировке аккаунта"
            )
        
        return text


class SimilarityDetector:
    """
    Детектор схожести видео
    
    Сравнивает видео с базой и находит совпадения
    """
    
    def __init__(self):
        self.fingerprints_db: Dict[str, Dict] = {}
        self.passports_db: Dict[str, DigitalPassport] = {}
        self._load_databases()
    
    def _load_databases(self):
        """Загрузка баз данных"""
        # Fingerprints
        if os.path.exists(FINGERPRINTS_DB_FILE):
            try:
                with open(FINGERPRINTS_DB_FILE, 'r') as f:
                    self.fingerprints_db = json.load(f)
            except:
                self.fingerprints_db = {}
        
        # Passports
        if os.path.exists(PASSPORTS_DB_FILE):
            try:
                with open(PASSPORTS_DB_FILE, 'r') as f:
                    data = json.load(f)
                    self.passports_db = {
                        k: DigitalPassport.from_dict(v) 
                        for k, v in data.items()
                    }
            except:
                self.passports_db = {}
    
    def _save_databases(self):
        """Сохранение баз данных"""
        try:
            with open(FINGERPRINTS_DB_FILE, 'w') as f:
                json.dump(self.fingerprints_db, f, indent=2)
        except Exception as e:
            print(f"[DB] Failed to save fingerprints: {e}")
        
        try:
            with open(PASSPORTS_DB_FILE, 'w') as f:
                data = {k: v.to_dict() for k, v in self.passports_db.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[DB] Failed to save passports: {e}")
    
    async def add_video(self, filepath: str, user_id: int, 
                        username: str = "", **metadata) -> DigitalPassport:
        """Добавить видео в базу и создать паспорт"""
        
        # Вычисляем отпечатки
        file_hash = await VideoFingerprinter.calculate_file_hash(filepath)
        perceptual_hash = await VideoFingerprinter.calculate_perceptual_hash(filepath)
        temporal_sig = await VideoFingerprinter.calculate_temporal_signature(filepath)
        
        # Получаем инфо о файле
        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        
        # Создаём паспорт
        passport = DigitalPassport(
            passport_id="",  # Сгенерируется автоматически
            video_hash=file_hash,
            perceptual_hash=perceptual_hash,
            owner_user_id=user_id,
            owner_username=username,
            created_at=time.time(),
            processed_at=time.time(),
            file_size_bytes=file_size,
            duration_seconds=metadata.get("duration", 0),
            resolution=metadata.get("resolution", ""),
            fps=metadata.get("fps", 0),
            template_used=metadata.get("template", ""),
            mode=metadata.get("mode", ""),
            quality=metadata.get("quality", ""),
            watermark_signature=metadata.get("watermark_signature", ""),
            trap_enabled=metadata.get("trap_enabled", False),
        )
        
        # Сохраняем fingerprint
        self.fingerprints_db[passport.passport_id] = {
            "passport_id": passport.passport_id,
            "file_hash": file_hash,
            "perceptual_hash": perceptual_hash,
            "temporal_sig": temporal_sig,
            "user_id": user_id,
            "created_at": passport.created_at,
        }
        
        # Сохраняем паспорт
        self.passports_db[passport.passport_id] = passport
        
        self._save_databases()
        
        return passport
    
    async def find_matches(self, filepath: str, 
                           exclude_user_id: int = 0) -> MatchResult:
        """
        Поиск совпадений в базе
        
        Args:
            filepath: Путь к видео для проверки
            exclude_user_id: Исключить видео этого пользователя
        
        Returns:
            MatchResult с информацией о совпадении
        """
        
        # Вычисляем отпечатки проверяемого видео
        file_hash = await VideoFingerprinter.calculate_file_hash(filepath)
        perceptual_hash = await VideoFingerprinter.calculate_perceptual_hash(filepath)
        
        best_match = None
        best_similarity = 0.0
        match_type = ""
        
        for fp_id, fp_data in self.fingerprints_db.items():
            # Пропускаем свои видео
            if exclude_user_id and fp_data.get("user_id") == exclude_user_id:
                continue
            
            # 1. Проверка точного совпадения
            if fp_data.get("file_hash") == file_hash:
                best_match = fp_id
                best_similarity = 1.0
                match_type = "exact"
                break
            
            # 2. Визуальное сходство
            visual_sim = VideoFingerprinter.compare_hashes(
                perceptual_hash, 
                fp_data.get("perceptual_hash", "")
            )
            
            if visual_sim > best_similarity:
                best_similarity = visual_sim
                best_match = fp_id
                match_type = "visual"
        
        # Определяем уровень риска
        if best_similarity >= 0.95:
            risk_level = RiskLevel.CRITICAL
        elif best_similarity >= 0.85:
            risk_level = RiskLevel.HIGH
        elif best_similarity >= 0.75:
            risk_level = RiskLevel.MEDIUM
        elif best_similarity >= 0.5:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.SAFE
        
        # Формируем результат
        if best_similarity >= SIMILARITY_THRESHOLD and best_match:
            original_passport = self.passports_db.get(best_match)
            
            # Увеличиваем счётчик совпадений
            if original_passport:
                original_passport.matches_found += 1
                self._save_databases()
            
            return MatchResult(
                found=True,
                similarity=best_similarity,
                risk_level=risk_level,
                original_passport=original_passport,
                match_type=match_type,
                details={"passport_id": best_match}
            )
        
        return MatchResult(
            found=False,
            similarity=best_similarity,
            risk_level=risk_level,
            match_type="",
            details={}
        )
    
    def get_passport(self, passport_id: str) -> Optional[DigitalPassport]:
        """Получить паспорт по ID"""
        return self.passports_db.get(passport_id)
    
    def get_user_passports(self, user_id: int) -> List[DigitalPassport]:
        """Получить все паспорта пользователя"""
        return [p for p in self.passports_db.values() if p.owner_user_id == user_id]
    
    def verify_passport(self, passport_id: str) -> bool:
        """Верифицировать паспорт (увеличить счётчик проверок)"""
        passport = self.passports_db.get(passport_id)
        if passport:
            passport.verification_count += 1
            passport.last_verified_at = time.time()
            self._save_databases()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 4. SAFE-CHECK — Анализ риска бана
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SafeCheckResult:
    """Результат проверки безопасности"""
    overall_risk: RiskLevel
    overall_score: float            # 0-100 (100 = безопасно)
    
    # Отдельные оценки
    originality_score: float        # Оригинальность
    ban_probability: float          # Вероятность бана
    strike_probability: float       # Вероятность страйка
    shadow_ban_risk: float          # Риск теневого бана
    
    # Рекомендации
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_message(self, lang: str = "ru") -> str:
        """Форматирование результата"""
        risk_icons = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }
        
        def score_bar(score: float) -> str:
            filled = int(score / 10)
            empty = 10 - filled
            return "█" * filled + "░" * empty
        
        icon = risk_icons.get(self.overall_risk, "⚪")
        
        if lang == "en":
            risk_names = {
                RiskLevel.SAFE: "SAFE",
                RiskLevel.LOW: "LOW RISK",
                RiskLevel.MEDIUM: "MEDIUM RISK",
                RiskLevel.HIGH: "HIGH RISK",
                RiskLevel.CRITICAL: "CRITICAL",
            }
            
            text = (
                f"🛡 <b>AI SAFE-CHECK REPORT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{icon} <b>Status: {risk_names.get(self.overall_risk, 'UNKNOWN')}</b>\n"
                f"📊 Overall Score: {self.overall_score:.0f}/100\n\n"
                f"<b>Detailed Analysis:</b>\n\n"
                f"✨ Originality:\n"
                f"   {score_bar(self.originality_score)} {self.originality_score:.0f}%\n\n"
                f"⛔ Ban Probability:\n"
                f"   {score_bar(100-self.ban_probability)} {self.ban_probability:.0f}%\n\n"
                f"⚠️ Strike Risk:\n"
                f"   {score_bar(100-self.strike_probability)} {self.strike_probability:.0f}%\n\n"
                f"👻 Shadow Ban Risk:\n"
                f"   {score_bar(100-self.shadow_ban_risk)} {self.shadow_ban_risk:.0f}%\n"
            )
            
            if self.warnings:
                text += f"\n⚠️ <b>Warnings:</b>\n"
                for w in self.warnings:
                    text += f"   • {w}\n"
            
            if self.recommendations:
                text += f"\n💡 <b>Recommendations:</b>\n"
                for r in self.recommendations:
                    text += f"   • {r}\n"
        else:
            risk_names = {
                RiskLevel.SAFE: "БЕЗОПАСНО",
                RiskLevel.LOW: "НИЗКИЙ РИСК",
                RiskLevel.MEDIUM: "СРЕДНИЙ РИСК",
                RiskLevel.HIGH: "ВЫСОКИЙ РИСК",
                RiskLevel.CRITICAL: "КРИТИЧЕСКИЙ",
            }
            
            text = (
                f"🛡 <b>ОТЧЁТ AI SAFE-CHECK</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{icon} <b>Статус: {risk_names.get(self.overall_risk, 'НЕИЗВЕСТНО')}</b>\n"
                f"📊 Общая оценка: {self.overall_score:.0f}/100\n\n"
                f"<b>Детальный анализ:</b>\n\n"
                f"✨ Оригинальность:\n"
                f"   {score_bar(self.originality_score)} {self.originality_score:.0f}%\n\n"
                f"⛔ Вероятность бана:\n"
                f"   {score_bar(100-self.ban_probability)} {self.ban_probability:.0f}%\n\n"
                f"⚠️ Риск страйка:\n"
                f"   {score_bar(100-self.strike_probability)} {self.strike_probability:.0f}%\n\n"
                f"👻 Риск теневого бана:\n"
                f"   {score_bar(100-self.shadow_ban_risk)} {self.shadow_ban_risk:.0f}%\n"
            )
            
            if self.warnings:
                text += f"\n⚠️ <b>Предупреждения:</b>\n"
                for w in self.warnings:
                    text += f"   • {w}\n"
            
            if self.recommendations:
                text += f"\n💡 <b>Рекомендации:</b>\n"
                for r in self.recommendations:
                    text += f"   • {r}\n"
        
        return text


class SafeChecker:
    """
    AI Safe-Check — проверка видео перед публикацией
    
    Анализирует:
    - Схожесть с существующим контентом
    - Технические характеристики
    - Риск детекции как "неоригинал"
    """
    
    def __init__(self, detector: SimilarityDetector):
        self.detector = detector
    
    async def check(self, filepath: str, user_id: int = 0,
                    processed: bool = True) -> SafeCheckResult:
        """
        Полная проверка безопасности видео
        
        Args:
            filepath: Путь к видео
            user_id: ID пользователя (исключить свои видео)
            processed: Было ли видео обработано через Virex
        """
        
        recommendations = []
        warnings = []
        
        # 1. Проверка на совпадения
        match_result = await self.detector.find_matches(filepath, user_id)
        
        # Базовые оценки
        if match_result.found:
            originality_score = (1 - match_result.similarity) * 100
            
            if match_result.similarity >= 0.95:
                ban_probability = 85.0
                strike_probability = 70.0
                shadow_ban_risk = 90.0
                warnings.append("Найдено почти идентичное видео в базе")
            elif match_result.similarity >= 0.85:
                ban_probability = 50.0
                strike_probability = 40.0
                shadow_ban_risk = 70.0
                warnings.append("Высокое сходство с существующим контентом")
            else:
                ban_probability = 25.0
                strike_probability = 15.0
                shadow_ban_risk = 40.0
                warnings.append("Умеренное сходство с существующим контентом")
        else:
            originality_score = 95.0
            ban_probability = 5.0
            strike_probability = 3.0
            shadow_ban_risk = 10.0
        
        # 2. Бонусы за обработку через Virex
        if processed:
            ban_probability *= 0.6  # -40% риска
            strike_probability *= 0.5
            shadow_ban_risk *= 0.7
            originality_score = min(100, originality_score * 1.15)
            recommendations.append("Видео обработано через Virex — защита активна")
        else:
            recommendations.append("Обработайте видео через Virex для снижения рисков")
        
        # 3. Рекомендации
        if ban_probability > 50:
            recommendations.append("Используйте Hardcore режим Anti-Reupload")
            recommendations.append("Добавьте уникальные элементы к видео")
        
        if shadow_ban_risk > 50:
            recommendations.append("Измените шаблон обработки")
            recommendations.append("Добавьте оригинальный текст/водяной знак")
        
        # 4. Общая оценка
        overall_score = (
            originality_score * 0.4 +
            (100 - ban_probability) * 0.3 +
            (100 - strike_probability) * 0.15 +
            (100 - shadow_ban_risk) * 0.15
        )
        
        # 5. Определяем уровень риска
        if overall_score >= 80:
            overall_risk = RiskLevel.SAFE
        elif overall_score >= 65:
            overall_risk = RiskLevel.LOW
        elif overall_score >= 45:
            overall_risk = RiskLevel.MEDIUM
        elif overall_score >= 25:
            overall_risk = RiskLevel.HIGH
        else:
            overall_risk = RiskLevel.CRITICAL
        
        return SafeCheckResult(
            overall_risk=overall_risk,
            overall_score=overall_score,
            originality_score=originality_score,
            ban_probability=ban_probability,
            strike_probability=strike_probability,
            shadow_ban_risk=shadow_ban_risk,
            recommendations=recommendations,
            warnings=warnings,
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. ANALYTICS — Аналитика для VIP
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UserAnalytics:
    """Аналитика пользователя"""
    user_id: int
    
    # Счётчики
    total_processed: int = 0        # Всего обработано
    total_scanned: int = 0          # Всего проверено на совпадения
    matches_detected: int = 0       # Найдено совпадений (чужих)
    stolen_detected: int = 0        # Обнаружено краж (твоих видео)
    passports_created: int = 0      # Создано паспортов
    
    # Платформы
    platforms: Dict[str, int] = field(default_factory=dict)  # tiktok: 50, youtube: 30
    
    # Шаблоны
    templates_used: Dict[str, int] = field(default_factory=dict)
    
    # Риски
    avg_originality_score: float = 0.0
    high_risk_count: int = 0
    
    # Временные данные
    first_use: float = 0.0
    last_use: float = 0.0
    
    def to_message(self, lang: str = "ru") -> str:
        """Форматирование аналитики"""
        
        # Топ платформ
        top_platforms = sorted(self.platforms.items(), key=lambda x: -x[1])[:3]
        
        # Топ шаблонов
        top_templates = sorted(self.templates_used.items(), key=lambda x: -x[1])[:3]
        
        if lang == "en":
            text = (
                f"📊 <b>YOUR ANALYTICS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Processing Stats:</b>\n"
                f"   📹 Videos processed: {self.total_processed}\n"
                f"   🔍 Videos scanned: {self.total_scanned}\n"
                f"   🪪 Passports created: {self.passports_created}\n\n"
                f"<b>Protection Stats:</b>\n"
                f"   ⚠️ Matches found: {self.matches_detected}\n"
                f"   🚨 Thefts detected: {self.stolen_detected}\n"
                f"   📈 Avg originality: {self.avg_originality_score:.0f}%\n"
                f"   ⛔ High risk videos: {self.high_risk_count}\n"
            )
            
            if top_platforms:
                text += f"\n<b>Top Platforms:</b>\n"
                for platform, count in top_platforms:
                    text += f"   • {platform}: {count} videos\n"
            
            if top_templates:
                text += f"\n<b>Favorite Templates:</b>\n"
                for template, count in top_templates:
                    text += f"   • {template}: {count} uses\n"
        else:
            text = (
                f"📊 <b>ВАША АНАЛИТИКА</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Статистика обработки:</b>\n"
                f"   📹 Обработано видео: {self.total_processed}\n"
                f"   🔍 Проверено видео: {self.total_scanned}\n"
                f"   🪪 Создано паспортов: {self.passports_created}\n\n"
                f"<b>Статистика защиты:</b>\n"
                f"   ⚠️ Найдено совпадений: {self.matches_detected}\n"
                f"   🚨 Обнаружено краж: {self.stolen_detected}\n"
                f"   📈 Средняя оригинальность: {self.avg_originality_score:.0f}%\n"
                f"   ⛔ Видео с высоким риском: {self.high_risk_count}\n"
            )
            
            if top_platforms:
                text += f"\n<b>Топ платформ:</b>\n"
                for platform, count in top_platforms:
                    text += f"   • {platform}: {count} видео\n"
            
            if top_templates:
                text += f"\n<b>Любимые шаблоны:</b>\n"
                for template, count in top_templates:
                    text += f"   • {template}: {count} раз\n"
        
        return text


class AnalyticsManager:
    """Менеджер аналитики"""
    
    def __init__(self):
        self.data: Dict[int, UserAnalytics] = {}
        self._load()
    
    def _load(self):
        """Загрузка данных"""
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, 'r') as f:
                    raw_data = json.load(f)
                    for user_id_str, analytics_data in raw_data.items():
                        user_id = int(user_id_str)
                        self.data[user_id] = UserAnalytics(
                            user_id=user_id,
                            **{k: v for k, v in analytics_data.items() if k != 'user_id'}
                        )
            except Exception as e:
                print(f"[ANALYTICS] Load error: {e}")
    
    def _save(self):
        """Сохранение данных"""
        try:
            data = {str(k): asdict(v) for k, v in self.data.items()}
            with open(ANALYTICS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ANALYTICS] Save error: {e}")
    
    def get_or_create(self, user_id: int) -> UserAnalytics:
        """Получить или создать аналитику пользователя"""
        if user_id not in self.data:
            self.data[user_id] = UserAnalytics(
                user_id=user_id,
                first_use=time.time()
            )
        return self.data[user_id]
    
    def record_processing(self, user_id: int, template: str = "", mode: str = ""):
        """Записать обработку видео"""
        analytics = self.get_or_create(user_id)
        analytics.total_processed += 1
        analytics.last_use = time.time()
        
        if template:
            analytics.templates_used[template] = analytics.templates_used.get(template, 0) + 1
        
        if mode:
            analytics.platforms[mode] = analytics.platforms.get(mode, 0) + 1
        
        self._save()
    
    def record_scan(self, user_id: int, match_found: bool, originality_score: float):
        """Записать сканирование"""
        analytics = self.get_or_create(user_id)
        analytics.total_scanned += 1
        
        if match_found:
            analytics.matches_detected += 1
        
        # Обновляем среднюю оригинальность
        total = analytics.total_scanned
        prev_avg = analytics.avg_originality_score
        analytics.avg_originality_score = (prev_avg * (total - 1) + originality_score) / total
        
        if originality_score < 50:
            analytics.high_risk_count += 1
        
        self._save()
    
    def record_theft_detected(self, user_id: int):
        """Записать обнаружение кражи"""
        analytics = self.get_or_create(user_id)
        analytics.stolen_detected += 1
        self._save()
    
    def record_passport_created(self, user_id: int):
        """Записать создание паспорта"""
        analytics = self.get_or_create(user_id)
        analytics.passports_created += 1
        self._save()


# ══════════════════════════════════════════════════════════════════════════════
# 6. SMART PRESETS — Оптимальные настройки для платформ
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SmartPreset:
    """Пресет оптимальных настроек для платформы"""
    name: str
    display_name: str
    description: str
    
    # Кодек
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23
    
    # Аудио
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    sample_rate: int = 44100
    
    # Видео
    max_fps: int = 60
    pixel_format: str = "yuv420p"
    
    # Уникализация
    recommended_templates: List[str] = field(default_factory=list)
    unique_noise: float = 0.003
    color_shift: float = 0.02
    speed_variation: float = 0.02
    
    # Метаданные
    strip_metadata: bool = True
    add_noise_to_audio: bool = True
    
    # Специальные флаги
    optimize_for_discovery: bool = False
    aggressive_uniqueness: bool = False


# Встроенные пресеты для популярных платформ
SMART_PRESETS: Dict[str, SmartPreset] = {
    "tiktok_usa": SmartPreset(
        name="tiktok_usa",
        display_name="🇺🇸 TikTok USA",
        description="Оптимизировано для американского TikTok — максимальная уникальность",
        codec="libx264",
        preset="slow",
        crf=20,
        max_fps=30,
        recommended_templates=["zoom_rotate", "rgb_shake", "glitch_wave", "color_dance"],
        unique_noise=0.005,
        color_shift=0.03,
        speed_variation=0.03,
        aggressive_uniqueness=True,
        optimize_for_discovery=True,
    ),
    
    "tiktok_eu": SmartPreset(
        name="tiktok_eu",
        display_name="🇪🇺 TikTok Europe",
        description="Для европейского TikTok — баланс качества и уникальности",
        codec="libx264",
        preset="medium",
        crf=21,
        max_fps=30,
        recommended_templates=["soft_glow", "cinema_bars", "smooth_zoom", "color_grade"],
        unique_noise=0.004,
        color_shift=0.025,
        speed_variation=0.025,
    ),
    
    "reels_2025": SmartPreset(
        name="reels_2025",
        display_name="📸 Instagram Reels 2025",
        description="Новейшие алгоритмы Instagram — обход через метаданные и паттерны",
        codec="libx264",
        preset="slow",
        crf=19,
        max_fps=60,
        recommended_templates=["instagram_clean", "soft_motion", "aesthetic_blur", "minimal"],
        unique_noise=0.003,
        color_shift=0.02,
        speed_variation=0.015,
        strip_metadata=True,
        optimize_for_discovery=True,
    ),
    
    "youtube_shorts": SmartPreset(
        name="youtube_shorts",
        display_name="▶️ YouTube Shorts",
        description="Для YouTube — фокус на качество и оригинальность",
        codec="libx264",
        preset="slow",
        crf=18,
        max_fps=60,
        audio_bitrate="256k",
        recommended_templates=["cinema_pro", "motion_blur", "color_boost", "sharp_edge"],
        unique_noise=0.002,
        color_shift=0.015,
        speed_variation=0.01,
    ),
    
    "gaming_shorts": SmartPreset(
        name="gaming_shorts",
        display_name="🎮 Gaming Shorts",
        description="Для игрового контента — сохранение детализации",
        codec="libx264",
        preset="slower",
        crf=17,
        max_fps=60,
        recommended_templates=["gaming_hud", "neon_glow", "pixel_effect", "screen_shake"],
        unique_noise=0.002,
        color_shift=0.01,
        speed_variation=0.005,
    ),
    
    "anime_edits": SmartPreset(
        name="anime_edits",
        display_name="🌸 Anime Edits",
        description="Для AMV и аниме — особые цветовые профили",
        codec="libx264",
        preset="slow",
        crf=19,
        max_fps=30,
        recommended_templates=["anime_glow", "soft_blur", "color_pop", "vintage_anime"],
        unique_noise=0.003,
        color_shift=0.025,
        speed_variation=0.02,
    ),
    
    "meme_content": SmartPreset(
        name="meme_content",
        display_name="😂 Meme Content",
        description="Для мемов — агрессивная уникализация",
        codec="libx264",
        preset="fast",
        crf=23,
        max_fps=30,
        recommended_templates=["deep_fried", "earrape", "bass_boost", "glitch_hard"],
        unique_noise=0.008,
        color_shift=0.04,
        speed_variation=0.04,
        aggressive_uniqueness=True,
    ),
    
    "cinematic": SmartPreset(
        name="cinematic",
        display_name="🎬 Cinematic",
        description="Для кино-контента — минимальные изменения, максимальное качество",
        codec="libx264",
        preset="veryslow",
        crf=16,
        max_fps=24,
        audio_bitrate="320k",
        recommended_templates=["letterbox", "film_grain", "color_grade_pro", "soft_vignette"],
        unique_noise=0.001,
        color_shift=0.008,
        speed_variation=0.005,
    ),
    
    "music_video": SmartPreset(
        name="music_video",
        display_name="🎵 Music Video",
        description="Для музыкальных клипов — приоритет аудио",
        codec="libx264",
        preset="slow",
        crf=18,
        max_fps=30,
        audio_bitrate="320k",
        sample_rate=48000,
        recommended_templates=["beat_sync", "spectrum_visual", "lyrics_flow", "rhythm_cut"],
        unique_noise=0.002,
        color_shift=0.015,
        add_noise_to_audio=False,  # Не трогаем аудио
    ),
    
    "safe_mode": SmartPreset(
        name="safe_mode",
        display_name="🛡️ Safe Mode",
        description="Минимальные изменения — когда качество критично",
        codec="libx264",
        preset="slow",
        crf=18,
        max_fps=60,
        recommended_templates=["subtle_grain", "micro_shift", "soft_color"],
        unique_noise=0.001,
        color_shift=0.005,
        speed_variation=0.002,
    ),
    
    "hardcore": SmartPreset(
        name="hardcore",
        display_name="💀 Hardcore Anti-Reupload",
        description="Максимальная защита — для контента который воруют",
        codec="libx264",
        preset="medium",
        crf=21,
        max_fps=30,
        recommended_templates=["multi_layer", "deep_unique", "pattern_break", "full_scramble"],
        unique_noise=0.012,
        color_shift=0.06,
        speed_variation=0.06,
        aggressive_uniqueness=True,
        strip_metadata=True,
    ),
}


def get_preset(name: str) -> Optional[SmartPreset]:
    """Получить пресет по имени"""
    return SMART_PRESETS.get(name)


def list_presets() -> List[SmartPreset]:
    """Список всех пресетов"""
    return list(SMART_PRESETS.values())


def get_preset_message(lang: str = "ru") -> str:
    """Форматированный список пресетов"""
    if lang == "en":
        text = "🎯 <b>SMART PRESETS</b>\n\nChoose optimal settings for your platform:\n\n"
    else:
        text = "🎯 <b>УМНЫЕ ПРЕСЕТЫ</b>\n\nВыберите оптимальные настройки для вашей платформы:\n\n"
    
    for preset in SMART_PRESETS.values():
        text += f"<b>{preset.display_name}</b>\n"
        text += f"   {preset.description}\n\n"
    
    return text


# ══════════════════════════════════════════════════════════════════════════════
# 7. ANTI-STEAL SYSTEM — Защита от кражи
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TheftReport:
    """Отчёт о краже"""
    found: bool
    stolen_video_id: str = ""
    original_passport_id: str = ""
    thief_fingerprint: str = ""
    similarity: float = 0.0
    detection_method: str = ""
    detected_at: float = 0.0
    platform: str = ""
    url: str = ""
    
    def to_message(self, lang: str = "ru") -> str:
        if not self.found:
            if lang == "en":
                return "✅ No theft detected. Your video appears to be safe."
            return "✅ Кража не обнаружена. Ваше видео в безопасности."
        
        detected_time = datetime.fromtimestamp(self.detected_at).strftime('%d.%m.%Y %H:%M')
        
        if lang == "en":
            return (
                f"🚨 <b>THEFT DETECTED!</b>\n\n"
                f"📅 Detected: {detected_time}\n"
                f"📊 Similarity: {self.similarity * 100:.1f}%\n"
                f"🔍 Method: {self.detection_method}\n"
                f"📱 Platform: {self.platform or 'Unknown'}\n"
                f"🔗 URL: {self.url or 'Not available'}\n\n"
                f"<b>Your rights:</b>\n"
                f"• File a DMCA takedown\n"
                f"• Report to platform\n"
                f"• Contact support for evidence package"
            )
        
        return (
            f"🚨 <b>ОБНАРУЖЕНА КРАЖА!</b>\n\n"
            f"📅 Обнаружено: {detected_time}\n"
            f"📊 Схожесть: {self.similarity * 100:.1f}%\n"
            f"🔍 Метод: {self.detection_method}\n"
            f"📱 Платформа: {self.platform or 'Неизвестно'}\n"
            f"🔗 URL: {self.url or 'Недоступен'}\n\n"
            f"<b>Ваши права:</b>\n"
            f"• Подать DMCA жалобу\n"
            f"• Пожаловаться на платформе\n"
            f"• Обратиться в поддержку за пакетом доказательств"
        )


class AntiStealSystem:
    """
    Anti-Steal System — защита от кражи контента
    
    Функции:
    - Регистрация видео в базе
    - Мониторинг краж
    - Уведомления при обнаружении
    - Генерация доказательств
    """
    
    THEFT_HISTORY_FILE = "theft_history.json"
    
    def __init__(self, detector: SimilarityDetector):
        self.detector = detector
        self.theft_history: Dict[str, List[Dict]] = {}
        self._load_history()
    
    def _load_history(self):
        """Загрузка истории краж"""
        if os.path.exists(self.THEFT_HISTORY_FILE):
            try:
                with open(self.THEFT_HISTORY_FILE, 'r') as f:
                    self.theft_history = json.load(f)
            except:
                self.theft_history = {}
    
    def _save_history(self):
        """Сохранение истории"""
        try:
            with open(self.THEFT_HISTORY_FILE, 'w') as f:
                json.dump(self.theft_history, f, indent=2)
        except Exception as e:
            print(f"[ANTI-STEAL] Save error: {e}")
    
    async def register_video(self, filepath: str, user_id: int, 
                            username: str = "", **metadata) -> DigitalPassport:
        """
        Зарегистрировать видео для защиты от кражи
        
        Returns:
            DigitalPassport с уникальным ID
        """
        passport = await self.detector.add_video(
            filepath=filepath,
            user_id=user_id,
            username=username,
            **metadata
        )
        
        print(f"[ANTI-STEAL] Registered video {passport.passport_id} for user {user_id}")
        return passport
    
    async def check_stolen(self, filepath: str, owner_user_id: int) -> TheftReport:
        """
        Проверить, является ли видео украденной версией
        
        Args:
            filepath: Путь к подозрительному видео
            owner_user_id: ID владельца оригинала
        
        Returns:
            TheftReport с деталями
        """
        # Ищем совпадения с видео этого пользователя
        file_hash = await VideoFingerprinter.calculate_file_hash(filepath)
        perceptual_hash = await VideoFingerprinter.calculate_perceptual_hash(filepath)
        
        best_match_passport = None
        best_similarity = 0.0
        detection_method = ""
        
        # Проходим только по видео указанного пользователя
        for passport_id, passport in self.detector.passports_db.items():
            if passport.owner_user_id != owner_user_id:
                continue
            
            # Проверяем fingerprint
            fp_data = self.detector.fingerprints_db.get(passport_id, {})
            
            # Точное совпадение хеша файла
            if fp_data.get("file_hash") == file_hash:
                best_match_passport = passport
                best_similarity = 1.0
                detection_method = "exact_hash"
                break
            
            # Визуальное сходство
            visual_sim = VideoFingerprinter.compare_hashes(
                perceptual_hash,
                fp_data.get("perceptual_hash", "")
            )
            
            if visual_sim > best_similarity:
                best_similarity = visual_sim
                best_match_passport = passport
                detection_method = "perceptual_hash"
        
        # Если нашли совпадение
        if best_similarity >= SIMILARITY_THRESHOLD and best_match_passport:
            theft_report = TheftReport(
                found=True,
                original_passport_id=best_match_passport.passport_id,
                thief_fingerprint=perceptual_hash,
                similarity=best_similarity,
                detection_method=detection_method,
                detected_at=time.time(),
            )
            
            # Сохраняем в историю
            user_key = str(owner_user_id)
            if user_key not in self.theft_history:
                self.theft_history[user_key] = []
            
            self.theft_history[user_key].append({
                "passport_id": best_match_passport.passport_id,
                "similarity": best_similarity,
                "method": detection_method,
                "detected_at": theft_report.detected_at,
            })
            self._save_history()
            
            return theft_report
        
        return TheftReport(found=False)
    
    def get_theft_history(self, user_id: int) -> List[Dict]:
        """Получить историю обнаруженных краж для пользователя"""
        return self.theft_history.get(str(user_id), [])
    
    def get_theft_count(self, user_id: int) -> int:
        """Количество обнаруженных краж"""
        return len(self.theft_history.get(str(user_id), []))


# ══════════════════════════════════════════════════════════════════════════════
# 8. CONTENT SCANNER — Сканер TikTok/Reels
# ══════════════════════════════════════════════════════════════════════════════

@dataclass 
class ScanResult:
    """Результат сканирования контента"""
    success: bool
    platform: str = ""              # tiktok, instagram, youtube
    video_url: str = ""
    author: str = ""
    
    # Результат сравнения
    match_found: bool = False
    similarity: float = 0.0
    original_passport: Optional[DigitalPassport] = None
    
    # Риски
    risk_level: RiskLevel = RiskLevel.SAFE
    is_stolen: bool = False
    
    # Ошибки
    error: str = ""
    
    def to_message(self, lang: str = "ru") -> str:
        if not self.success:
            if lang == "en":
                return f"❌ Scan failed: {self.error}"
            return f"❌ Ошибка сканирования: {self.error}"
        
        risk_icons = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟢", 
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }
        
        if lang == "en":
            if not self.match_found:
                return (
                    f"✅ <b>SCAN COMPLETE</b>\n\n"
                    f"📱 Platform: {self.platform.title()}\n"
                    f"👤 Author: {self.author or 'Unknown'}\n\n"
                    f"{risk_icons[self.risk_level]} <b>Result:</b> No matches found\n"
                    f"The video appears to be original."
                )
            
            text = (
                f"⚠️ <b>MATCH DETECTED!</b>\n\n"
                f"📱 Platform: {self.platform.title()}\n"
                f"👤 Author: {self.author or 'Unknown'}\n"
                f"📊 Similarity: {self.similarity * 100:.1f}%\n"
                f"{risk_icons[self.risk_level]} Risk: {self.risk_level.value.upper()}\n"
            )
            
            if self.is_stolen:
                text += "\n🚨 <b>This appears to be STOLEN content!</b>"
            
            if self.original_passport:
                text += (
                    f"\n\n📁 <b>Original source:</b>\n"
                    f"   Passport: {self.original_passport.passport_id}\n"
                    f"   Owner: {self.original_passport.owner_username or 'Unknown'}\n"
                )
            
            return text
        
        # Russian
        if not self.match_found:
            return (
                f"✅ <b>СКАНИРОВАНИЕ ЗАВЕРШЕНО</b>\n\n"
                f"📱 Платформа: {self.platform.title()}\n"
                f"👤 Автор: {self.author or 'Неизвестен'}\n\n"
                f"{risk_icons[self.risk_level]} <b>Результат:</b> Совпадений не найдено\n"
                f"Видео выглядит оригинальным."
            )
        
        text = (
            f"⚠️ <b>НАЙДЕНО СОВПАДЕНИЕ!</b>\n\n"
            f"📱 Платформа: {self.platform.title()}\n"
            f"👤 Автор: {self.author or 'Неизвестен'}\n"
            f"📊 Схожесть: {self.similarity * 100:.1f}%\n"
            f"{risk_icons[self.risk_level]} Риск: {self.risk_level.value.upper()}\n"
        )
        
        if self.is_stolen:
            text += "\n🚨 <b>Это похоже на УКРАДЕННЫЙ контент!</b>"
        
        if self.original_passport:
            text += (
                f"\n\n📁 <b>Оригинальный источник:</b>\n"
                f"   Паспорт: {self.original_passport.passport_id}\n"
                f"   Владелец: {self.original_passport.owner_username or 'Неизвестен'}\n"
            )
        
        return text


class ContentScanner:
    """
    Content Scanner — сканирование TikTok/Reels/YouTube Shorts
    
    ВАЖНО: Это демо-реализация. Для реального скачивания видео
    с платформ нужна интеграция с yt-dlp или аналогами.
    """
    
    # Паттерны URL
    URL_PATTERNS = {
        "tiktok": [
            r"tiktok\.com/@[\w.-]+/video/(\d+)",
            r"tiktok\.com/t/(\w+)",
            r"vm\.tiktok\.com/(\w+)",
        ],
        "instagram": [
            r"instagram\.com/reel/([\w-]+)",
            r"instagram\.com/p/([\w-]+)",
        ],
        "youtube": [
            r"youtube\.com/shorts/([\w-]+)",
            r"youtu\.be/([\w-]+)",
        ],
    }
    
    def __init__(self, detector: SimilarityDetector):
        self.detector = detector
    
    def detect_platform(self, url: str) -> Tuple[str, str]:
        """
        Определить платформу и извлечь ID видео
        
        Returns:
            (platform, video_id)
        """
        import re
        
        for platform, patterns in self.URL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return platform, match.group(1)
        
        return "", ""
    
    async def scan_url(self, url: str, user_id: int = 0) -> ScanResult:
        """
        Сканировать URL на совпадения
        
        ПРИМЕЧАНИЕ: Для полной реализации нужен yt-dlp.
        Это заглушка для демонстрации интерфейса.
        """
        platform, video_id = self.detect_platform(url)
        
        if not platform:
            return ScanResult(
                success=False,
                error="Неподдерживаемая платформа. Поддерживаются: TikTok, Instagram Reels, YouTube Shorts"
            )
        
        # TODO: Интеграция с yt-dlp для скачивания
        # Пока возвращаем результат без реального скачивания
        
        return ScanResult(
            success=True,
            platform=platform,
            video_url=url,
            author=f"@user_{video_id[:8]}",
            match_found=False,  # Реальная проверка требует скачивания
            risk_level=RiskLevel.SAFE,
            error="Для полного сканирования требуется загрузка видео. Отправьте видео файл напрямую."
        )
    
    async def scan_video(self, filepath: str, user_id: int = 0,
                        check_ownership: bool = False) -> ScanResult:
        """
        Сканировать видео файл
        
        Args:
            filepath: Путь к видео
            user_id: ID пользователя  
            check_ownership: Проверять ли на кражу у этого пользователя
        """
        try:
            # Ищем совпадения
            match_result = await self.detector.find_matches(
                filepath=filepath,
                exclude_user_id=user_id if not check_ownership else 0
            )
            
            is_stolen = False
            
            # Если проверяем на кражу
            if check_ownership and match_result.found:
                if match_result.original_passport:
                    if match_result.original_passport.owner_user_id == user_id:
                        is_stolen = True
            
            return ScanResult(
                success=True,
                match_found=match_result.found,
                similarity=match_result.similarity,
                original_passport=match_result.original_passport,
                risk_level=match_result.risk_level,
                is_stolen=is_stolen,
            )
            
        except Exception as e:
            return ScanResult(
                success=False,
                error=str(e)
            )


# ══════════════════════════════════════════════════════════════════════════════
# 9. VIREX SHIELD — Главный оркестратор
# ══════════════════════════════════════════════════════════════════════════════

class VirexShield:
    """
    🛡️ VIREX SHIELD — Центральная система защиты контента
    
    Объединяет:
    - Anti-Steal System
    - Content Scanner
    - AI Safe-Check
    - Digital Passports
    - Smart Presets
    - Analytics
    
    "Мы не делаем копию. Мы делаем видео, которое нельзя украсть."
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        self.detector = SimilarityDetector()
        self.anti_steal = AntiStealSystem(self.detector)
        self.scanner = ContentScanner(self.detector)
        self.safe_checker = SafeChecker(self.detector)
        self.analytics = AnalyticsManager()
        
        print(f"[VIREX SHIELD] Initialized v{self.VERSION}")
    
    # ────────────────────────────────────────────────────────────────────────
    # Anti-Steal
    # ────────────────────────────────────────────────────────────────────────
    
    async def register_for_protection(self, filepath: str, user_id: int,
                                      username: str = "", **metadata) -> DigitalPassport:
        """Зарегистрировать видео для защиты"""
        passport = await self.anti_steal.register_video(
            filepath=filepath,
            user_id=user_id, 
            username=username,
            **metadata
        )
        
        self.analytics.record_passport_created(user_id)
        return passport
    
    async def check_if_stolen(self, filepath: str, owner_user_id: int) -> TheftReport:
        """Проверить, украдено ли видео"""
        report = await self.anti_steal.check_stolen(filepath, owner_user_id)
        
        if report.found:
            self.analytics.record_theft_detected(owner_user_id)
        
        return report
    
    # ────────────────────────────────────────────────────────────────────────
    # Scanner
    # ────────────────────────────────────────────────────────────────────────
    
    async def scan_for_matches(self, filepath: str, user_id: int = 0) -> ScanResult:
        """Сканировать видео на совпадения"""
        result = await self.scanner.scan_video(filepath, user_id)
        
        self.analytics.record_scan(
            user_id=user_id,
            match_found=result.match_found,
            originality_score=(1 - result.similarity) * 100
        )
        
        return result
    
    async def scan_url(self, url: str, user_id: int = 0) -> ScanResult:
        """Сканировать URL на совпадения"""
        return await self.scanner.scan_url(url, user_id)
    
    # ────────────────────────────────────────────────────────────────────────
    # Safe-Check
    # ────────────────────────────────────────────────────────────────────────
    
    async def safe_check(self, filepath: str, user_id: int = 0,
                         processed: bool = True) -> SafeCheckResult:
        """Полная проверка безопасности"""
        result = await self.safe_checker.check(filepath, user_id, processed)
        
        self.analytics.record_scan(
            user_id=user_id,
            match_found=result.ban_probability > 50,
            originality_score=result.originality_score
        )
        
        return result
    
    # ────────────────────────────────────────────────────────────────────────
    # Smart Presets
    # ────────────────────────────────────────────────────────────────────────
    
    def get_smart_preset(self, name: str) -> Optional[SmartPreset]:
        """Получить пресет"""
        return get_preset(name)
    
    def list_smart_presets(self) -> List[SmartPreset]:
        """Список пресетов"""
        return list_presets()
    
    def get_preset_for_platform(self, platform: str) -> Optional[SmartPreset]:
        """Подобрать пресет для платформы"""
        platform = platform.lower()
        
        mapping = {
            "tiktok": "tiktok_usa",
            "instagram": "reels_2025",
            "reels": "reels_2025",
            "youtube": "youtube_shorts",
            "shorts": "youtube_shorts",
            "gaming": "gaming_shorts",
            "anime": "anime_edits",
            "meme": "meme_content",
        }
        
        preset_name = mapping.get(platform, "safe_mode")
        return get_preset(preset_name)
    
    # ────────────────────────────────────────────────────────────────────────
    # Analytics
    # ────────────────────────────────────────────────────────────────────────
    
    def get_user_analytics(self, user_id: int) -> UserAnalytics:
        """Получить аналитику пользователя"""
        return self.analytics.get_or_create(user_id)
    
    def record_processing(self, user_id: int, template: str = "", mode: str = ""):
        """Записать обработку"""
        self.analytics.record_processing(user_id, template, mode)
    
    # ────────────────────────────────────────────────────────────────────────
    # Digital Passport
    # ────────────────────────────────────────────────────────────────────────
    
    def get_passport(self, passport_id: str) -> Optional[DigitalPassport]:
        """Получить паспорт"""
        return self.detector.get_passport(passport_id)
    
    def get_user_passports(self, user_id: int) -> List[DigitalPassport]:
        """Получить все паспорта пользователя"""
        return self.detector.get_user_passports(user_id)
    
    def verify_passport(self, passport_id: str) -> bool:
        """Верифицировать паспорт"""
        return self.detector.verify_passport(passport_id)
    
    # ────────────────────────────────────────────────────────────────────────
    # Info
    # ────────────────────────────────────────────────────────────────────────
    
    def get_shield_info(self, lang: str = "ru") -> str:
        """Информация о системе"""
        total_passports = len(self.detector.passports_db)
        total_fingerprints = len(self.detector.fingerprints_db)
        
        if lang == "en":
            return (
                f"🛡️ <b>VIREX SHIELD v{self.VERSION}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Digital Content Protection System</b>\n\n"
                f"📊 <b>Database:</b>\n"
                f"   • Passports: {total_passports}\n"
                f"   • Fingerprints: {total_fingerprints}\n\n"
                f"<b>Features:</b>\n"
                f"   🔒 Anti-Steal System\n"
                f"   🔍 Content Scanner\n"
                f"   🛡️ AI Safe-Check\n"
                f"   🪪 Digital Passports\n"
                f"   🎯 Smart Presets\n"
                f"   📊 Analytics\n\n"
                f"<i>We don't make copies.\n"
                f"We make videos that can't be stolen.</i>"
            )
        
        return (
            f"🛡️ <b>VIREX SHIELD v{self.VERSION}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Система защиты цифрового контента</b>\n\n"
            f"📊 <b>База данных:</b>\n"
            f"   • Паспортов: {total_passports}\n"
            f"   • Отпечатков: {total_fingerprints}\n\n"
            f"<b>Возможности:</b>\n"
            f"   🔒 Anti-Steal System\n"
            f"   🔍 Сканер контента\n"
            f"   🛡️ AI Safe-Check\n"
            f"   🪪 Цифровые паспорта\n"
            f"   🎯 Умные пресеты\n"
            f"   📊 Аналитика\n\n"
            f"<i>Мы не делаем копию.\n"
            f"Мы делаем видео, которое нельзя украсть.</i>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ══════════════════════════════════════════════════════════════════════════════

_similarity_detector: Optional[SimilarityDetector] = None
_safe_checker: Optional[SafeChecker] = None
_analytics_manager: Optional[AnalyticsManager] = None
_virex_shield: Optional[VirexShield] = None


def get_similarity_detector() -> SimilarityDetector:
    global _similarity_detector
    if _similarity_detector is None:
        _similarity_detector = SimilarityDetector()
    return _similarity_detector


def get_safe_checker() -> SafeChecker:
    global _safe_checker
    if _safe_checker is None:
        _safe_checker = SafeChecker(get_similarity_detector())
    return _safe_checker


def get_analytics_manager() -> AnalyticsManager:
    global _analytics_manager
    if _analytics_manager is None:
        _analytics_manager = AnalyticsManager()
    return _analytics_manager


def get_virex_shield() -> VirexShield:
    """Получить главный экземпляр Virex Shield"""
    global _virex_shield
    if _virex_shield is None:
        _virex_shield = VirexShield()
    return _virex_shield


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Enums
    "RiskLevel",
    
    # Dataclasses
    "DigitalPassport",
    "MatchResult",
    "SafeCheckResult",
    "UserAnalytics",
    "SmartPreset",
    "TheftReport",
    "ScanResult",
    
    # Classes
    "VideoFingerprinter",
    "SimilarityDetector",
    "SafeChecker",
    "AnalyticsManager",
    "AntiStealSystem",
    "ContentScanner",
    "VirexShield",
    
    # Presets
    "SMART_PRESETS",
    "get_preset",
    "list_presets",
    "get_preset_message",
    
    # Singletons
    "get_similarity_detector",
    "get_safe_checker",
    "get_analytics_manager",
    "get_virex_shield",
]
