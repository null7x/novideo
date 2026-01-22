"""
Virex — Rate Limiting & Anti-Abuse
"""
import time
import hashlib
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from config import (
    PLAN_LIMITS,
    RATE_LIMIT_WINDOW_SECONDS,
    ABUSE_THRESHOLD_HITS,
    SOFT_BLOCK_DURATION_SECONDS,
    BUTTON_COOLDOWN_SECONDS,
    DUPLICATE_FILE_BLOCK_SECONDS,
    Quality, DEFAULT_QUALITY,
)

@dataclass
class UserState:
    user_id: int
    plan: str = "free"
    mode: str = "tiktok"
    request_timestamps: list = field(default_factory=list)
    last_request_time: float = 0
    last_button_time: float = 0
    last_file_hash: str = ""
    last_file_time: float = 0
    abuse_hits: int = 0
    soft_block_until: float = 0
    current_file_id: Optional[str] = None
    processing: bool = False
    # Статистика и настройки
    total_videos: int = 0
    today_videos: int = 0
    today_date: str = ""
    last_process_time: float = 0
    quality: str = field(default_factory=lambda: DEFAULT_QUALITY)
    text_overlay: bool = True
    # Месячные лимиты (30 дней)
    monthly_videos: int = 0
    period_start: str = ""  # ISO дата начала периода
    # Сохраняем username для админ-команд
    username: str = ""
    # Статистика скачиваний
    total_downloads: int = 0
    monthly_downloads: int = 0
    # Дата первого использования
    first_seen: str = ""
    # Уведомлен ли админ о новом пользователе
    admin_notified: bool = False

class RateLimiter:
    def __init__(self):
        self.users: Dict[int, UserState] = {}
    
    def get_user(self, user_id: int) -> UserState:
        if user_id not in self.users:
            self.users[user_id] = UserState(user_id=user_id)
        return self.users[user_id]
    
    def get_limits(self, user_id: int):
        user = self.get_user(user_id)
        return PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    
    def is_soft_blocked(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if user.soft_block_until > time.time():
            return True
        return False
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        now = time.time()
        
        if self.is_soft_blocked(user_id):
            return False, "soft_block"
        
        # Проверка месячного лимита (30 дней)
        self._reset_monthly_if_needed(user_id)
        if user.monthly_videos >= limits.videos_per_month:
            return False, "monthly_limit"
        
        # Проверка cooldown
        if user.last_request_time > 0:
            elapsed = now - user.last_request_time
            if elapsed < limits.cooldown_seconds:
                remaining = int(limits.cooldown_seconds - elapsed)
                return False, f"cooldown:{remaining}"
        
        return True, None
    
    def _reset_monthly_if_needed(self, user_id: int):
        """ Сброс счётчика если прошло 30 дней """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today()
        
        if not user.period_start:
            user.period_start = today.isoformat()
            user.monthly_videos = 0
            return
        
        try:
            period_start_date = datetime.date.fromisoformat(user.period_start)
            days_passed = (today - period_start_date).days
            
            if days_passed >= 30:
                user.period_start = today.isoformat()
                user.monthly_videos = 0
        except:
            user.period_start = today.isoformat()
            user.monthly_videos = 0
    
    def get_monthly_remaining(self, user_id: int) -> int:
        """ Осталось видео на 30 дней """
        self._reset_monthly_if_needed(user_id)
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        return max(0, limits.videos_per_month - user.monthly_videos)
    
    def check_duplicate_file(self, user_id: int, file_unique_id: str) -> bool:
        user = self.get_user(user_id)
        now = time.time()
        
        file_hash = hashlib.md5(file_unique_id.encode()).hexdigest()
        
        if (user.last_file_hash == file_hash and 
            now - user.last_file_time < DUPLICATE_FILE_BLOCK_SECONDS):
            return True
        
        return False
    
    def check_button_spam(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        now = time.time()
        
        if now - user.last_button_time < BUTTON_COOLDOWN_SECONDS:
            return True
        
        user.last_button_time = now
        return False
    
    def register_request(self, user_id: int, file_unique_id: str):
        user = self.get_user(user_id)
        now = time.time()
        
        user.request_timestamps.append(now)
        user.last_request_time = now
        user.last_file_hash = hashlib.md5(file_unique_id.encode()).hexdigest()
        user.last_file_time = now
    
    def _check_abuse(self, user_id: int):
        user = self.get_user(user_id)
        
        if user.abuse_hits >= ABUSE_THRESHOLD_HITS:
            user.soft_block_until = time.time() + SOFT_BLOCK_DURATION_SECONDS
            user.abuse_hits = 0
            print(f"[ABUSE] User {user_id} soft-blocked for {SOFT_BLOCK_DURATION_SECONDS}s")
    
    def get_remaining_videos(self, user_id: int) -> int:
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        now = time.time()
        
        user.request_timestamps = [
            ts for ts in user.request_timestamps
            if now - ts < RATE_LIMIT_WINDOW_SECONDS
        ]
        
        return max(0, limits.videos_per_hour - len(user.request_timestamps))
    
    def set_mode(self, user_id: int, mode: str):
        user = self.get_user(user_id)
        user.mode = mode
    
    def get_mode(self, user_id: int) -> str:
        return self.get_user(user_id).mode
    
    def set_username(self, user_id: int, username: str):
        """ Сохранить username пользователя """
        user = self.get_user(user_id)
        user.username = username or ""
    
    def get_username(self, user_id: int) -> str:
        return self.get_user(user_id).username
    
    def find_user_by_username(self, username: str) -> Optional[int]:
        """ Найти user_id по username """
        username = username.lstrip("@").lower()
        for user_id, user in self.users.items():
            if user.username.lower() == username:
                return user_id
        return None
    
    def set_processing(self, user_id: int, processing: bool, file_id: str = None):
        user = self.get_user(user_id)
        user.processing = processing
        user.current_file_id = file_id if processing else None
    
    def is_processing(self, user_id: int) -> bool:
        return self.get_user(user_id).processing
    
    def set_plan(self, user_id: int, plan: str):
        user = self.get_user(user_id)
        if plan in PLAN_LIMITS:
            user.plan = plan
    
    def get_plan(self, user_id: int) -> str:
        return self.get_user(user_id).plan
    
    # ═════════════════════════════════════════════════════════════
    # STATISTICS
    # ═════════════════════════════════════════════════════════════
    
    def increment_video_count(self, user_id: int):
        """ Увеличить счётчик обработанных видео """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today().isoformat()
        
        if user.today_date != today:
            user.today_date = today
            user.today_videos = 0
        
        # Обновляем все счётчики
        user.total_videos += 1
        user.today_videos += 1
        user.last_process_time = time.time()
        
        # Месячный счётчик
        self._reset_monthly_if_needed(user_id)
        user.monthly_videos += 1
    
    def get_stats(self, user_id: int) -> dict:
        """ Получить статистику пользователя """
        import datetime
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        today = datetime.date.today().isoformat()
        
        # Сброс ежедневного счётчика
        if user.today_date != today:
            user.today_date = today
            user.today_videos = 0
        
        # Сброс месячного счётчика
        self._reset_monthly_if_needed(user_id)
        
        return {
            "total_videos": user.total_videos,
            "today_videos": user.today_videos,
            "monthly_videos": user.monthly_videos,
            "monthly_limit": limits.videos_per_month,
            "monthly_remaining": max(0, limits.videos_per_month - user.monthly_videos),
            "last_process_time": user.last_process_time,
            "mode": user.mode,
            "quality": user.quality,
            "text_overlay": user.text_overlay,
            "plan": user.plan,
            "username": user.username,
        }
    
    # ═════════════════════════════════════════════════════════════
    # QUALITY SETTINGS
    # ═════════════════════════════════════════════════════════════
    
    def set_quality(self, user_id: int, quality: str):
        user = self.get_user(user_id)
        if quality in [Quality.LOW, Quality.MEDIUM, Quality.MAX]:
            user.quality = quality
    
    def get_quality(self, user_id: int) -> str:
        return self.get_user(user_id).quality
    
    # ═════════════════════════════════════════════════════════════
    # TEXT OVERLAY SETTINGS
    # ═════════════════════════════════════════════════════════════
    
    def toggle_text_overlay(self, user_id: int) -> bool:
        """ Переключить текст на видео, вернуть новое значение """
        user = self.get_user(user_id)
        user.text_overlay = not user.text_overlay
        return user.text_overlay
    
    def get_text_overlay(self, user_id: int) -> bool:
        return self.get_user(user_id).text_overlay
    
    # ═════════════════════════════════════════════════════════════
    # PLAN FEATURE CHECKS
    # ═════════════════════════════════════════════════════════════
    
    def can_disable_text(self, user_id: int) -> bool:
        """ Может ли пользователь отключать текст """
        limits = self.get_limits(user_id)
        return limits.can_disable_text
    
    def can_use_quality(self, user_id: int, quality: str) -> bool:
        """ Может ли пользователь использовать это качество """
        limits = self.get_limits(user_id)
        if limits.quality_options is None:
            return True
        return quality in limits.quality_options
    
    def get_available_qualities(self, user_id: int) -> list:
        """ Получить доступные качества """
        limits = self.get_limits(user_id)
        return limits.quality_options or [Quality.LOW, Quality.MEDIUM, Quality.MAX]

rate_limiter = RateLimiter()
