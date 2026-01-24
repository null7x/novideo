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
    # Дневные и недельные лимиты
    daily_videos: int = 0
    daily_date: str = ""   # ISO дата для дневного лимита
    weekly_videos: int = 0
    week_start: str = ""   # ISO дата начала недели
    # Сохраняем для совместимости
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
    # Бан
    banned: bool = False
    ban_reason: str = ""
    # Язык
    language: str = "ru"
    language_set: bool = False  # Был ли выбран язык пользователем
    # Реферальная система
    referrer_id: int = 0  # Кто пригласил
    referral_count: int = 0  # Сколько пригласил
    referral_bonus: int = 0  # Бонусные видео
    # Дата окончания VIP/Premium
    plan_expires: str = ""  # ISO дата окончания
    # Уведомление об истечении
    expiry_notified: str = ""  # Дата последнего уведомления
    # Ночной режим
    night_mode: bool = False
    # История загрузок (последние 20)
    history: list = field(default_factory=list)
    # v2.8.0: Trial VIP
    trial_used: bool = False
    # v2.8.0: Streak bonus
    streak_count: int = 0
    streak_last_date: str = ""
    # v2.8.0: Favorites
    favorites: list = field(default_factory=list)
    # v2.8.0: Operation logs
    operation_logs: list = field(default_factory=list)
    # v2.9.0: Gamification
    points: int = 0
    level: int = 1
    achievements: list = field(default_factory=list)
    # v2.9.0: Trim settings
    trim_start: str = ""
    trim_end: str = ""
    # v2.9.0: Custom watermark
    watermark_file_id: str = ""
    watermark_position: str = "br"  # br=bottom-right
    # v2.9.0: Resolution setting
    resolution: str = "original"
    # v2.9.0: Current template
    current_template: str = ""
    # v2.9.0: Reminders
    reminders: list = field(default_factory=list)
    # v2.9.0: Weekly stats for analytics
    weekly_stats: dict = field(default_factory=dict)
    # v2.9.0: Pending audio for music overlay
    pending_audio_file_id: str = ""
    # v2.9.0: Batch processing state
    batch_videos: list = field(default_factory=list)
    # v3.0.0: Merge videos queue
    merge_videos: list = field(default_factory=list)
    # v3.0.0: Speed setting (0.5x - 2x)
    speed_setting: str = "1x"
    # v3.0.0: Rotation setting
    rotation_setting: str = ""
    # v3.0.0: Aspect ratio setting
    aspect_setting: str = ""
    # v3.0.0: Filter setting
    filter_setting: str = ""
    # v3.0.0: Custom text overlay
    custom_text: str = ""
    # v3.0.0: Caption style
    caption_style: str = "default"
    # v3.0.0: Compression preset
    compression_preset: str = ""
    # v3.0.0: Volume setting
    volume_setting: str = "100%"
    # v3.0.0: Scheduled tasks
    scheduled_tasks: list = field(default_factory=list)
    # v3.0.0: Auto-process template
    auto_process_template: str = ""
    # v3.0.0: Pending video for processing
    pending_video_file_id: str = ""
    # v3.0.0: Dynamic admin flag
    is_admin: bool = False

class RateLimiter:
    def __init__(self):
        self.users: Dict[int, UserState] = {}
        self.data_file = "users_data.json"
        self._load_data()
    
    def _load_data(self):
        """ Загрузить данные из файла """
        import json
        import os
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for uid, udata in data.items():
                        user = UserState(user_id=int(uid))
                        for key, value in udata.items():
                            if hasattr(user, key):
                                setattr(user, key, value)
                        self.users[int(uid)] = user
                print(f"[DATA] Loaded {len(self.users)} users")
        except Exception as e:
            print(f"[DATA] Error loading: {e}")
    
    def save_data(self):
        """ Сохранить данные в файл """
        import json
        try:
            data = {}
            for uid, user in self.users.items():
                data[str(uid)] = {
                    "plan": user.plan,
                    "mode": user.mode,
                    "total_videos": user.total_videos,
                    "monthly_videos": user.monthly_videos,
                    "period_start": user.period_start,
                    "daily_videos": user.daily_videos,
                    "daily_date": user.daily_date,
                    "weekly_videos": user.weekly_videos,
                    "week_start": user.week_start,
                    "username": user.username,
                    "total_downloads": user.total_downloads,
                    "monthly_downloads": user.monthly_downloads,
                    "first_seen": user.first_seen,
                    "quality": user.quality,
                    "text_overlay": user.text_overlay,
                    "banned": user.banned,
                    "ban_reason": user.ban_reason,
                    "language": user.language,
                    "referrer_id": user.referrer_id,
                    "referral_count": user.referral_count,
                    "referral_bonus": user.referral_bonus,
                    "plan_expires": user.plan_expires,
                    "night_mode": user.night_mode,
                    "history": getattr(user, 'history', [])[:20],
                    # v2.8.0
                    "trial_used": getattr(user, 'trial_used', False),
                    "streak_count": getattr(user, 'streak_count', 0),
                    "streak_last_date": getattr(user, 'streak_last_date', ''),
                    "favorites": getattr(user, 'favorites', [])[:5],
                    # v2.9.0
                    "points": getattr(user, 'points', 0),
                    "level": getattr(user, 'level', 1),
                    "achievements": getattr(user, 'achievements', []),
                    "watermark_file_id": getattr(user, 'watermark_file_id', ''),
                    "watermark_position": getattr(user, 'watermark_position', 'br'),
                    "resolution": getattr(user, 'resolution', 'original'),
                    "current_template": getattr(user, 'current_template', ''),
                    "reminders": getattr(user, 'reminders', []),
                    "weekly_stats": getattr(user, 'weekly_stats', {}),
                    # v3.0.0
                    "merge_videos": getattr(user, 'merge_videos', []),
                    "speed_setting": getattr(user, 'speed_setting', '1x'),
                    "rotation_setting": getattr(user, 'rotation_setting', ''),
                    "aspect_setting": getattr(user, 'aspect_setting', ''),
                    "filter_setting": getattr(user, 'filter_setting', ''),
                    "custom_text": getattr(user, 'custom_text', ''),
                    "caption_style": getattr(user, 'caption_style', 'default'),
                    "compression_preset": getattr(user, 'compression_preset', ''),
                    "volume_setting": getattr(user, 'volume_setting', '100%'),
                    "scheduled_tasks": getattr(user, 'scheduled_tasks', []),
                    "auto_process_template": getattr(user, 'auto_process_template', ''),
                    "is_admin": getattr(user, 'is_admin', False),
                }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[DATA] Error saving: {e}")
    
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
        
        # Сбрасываем счётчики если нужно
        self._reset_daily_if_needed(user_id)
        self._reset_weekly_if_needed(user_id)
        
        # Проверка дневного лимита
        if user.daily_videos >= limits.videos_per_day:
            return False, "daily_limit"
        
        # Проверка недельного лимита
        if user.weekly_videos >= limits.videos_per_week:
            return False, "weekly_limit"
        
        # Проверка cooldown
        if user.last_request_time > 0:
            elapsed = now - user.last_request_time
            if elapsed < limits.cooldown_seconds:
                remaining = int(limits.cooldown_seconds - elapsed)
                return False, f"cooldown:{remaining}"
        
        return True, None
    
    def _reset_daily_if_needed(self, user_id: int):
        """ Сброс дневного счётчика """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today().isoformat()
        
        if user.daily_date != today:
            user.daily_date = today
            user.daily_videos = 0
    
    def _reset_weekly_if_needed(self, user_id: int):
        """ Сброс недельного счётчика (каждые 7 дней) """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today()
        
        if not user.week_start:
            user.week_start = today.isoformat()
            user.weekly_videos = 0
            return
        
        try:
            week_start_date = datetime.date.fromisoformat(user.week_start)
            days_passed = (today - week_start_date).days
            
            if days_passed >= 7:
                user.week_start = today.isoformat()
                user.weekly_videos = 0
        except:
            user.week_start = today.isoformat()
            user.weekly_videos = 0
    
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
    
    def get_daily_remaining(self, user_id: int) -> int:
        """ Осталось видео сегодня """
        self._reset_daily_if_needed(user_id)
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        return max(0, limits.videos_per_day - user.daily_videos)
    
    def get_weekly_remaining(self, user_id: int) -> int:
        """ Осталось видео на эту неделю """
        self._reset_weekly_if_needed(user_id)
        user = self.get_user(user_id)
        limits = self.get_limits(user_id)
        return max(0, limits.videos_per_week - user.weekly_videos)
    
    def get_monthly_remaining(self, user_id: int) -> int:
        """ Осталось видео на 30 дней (для совместимости) """
        return self.get_weekly_remaining(user_id)
    
    def get_time_until_daily_reset(self, user_id: int) -> str:
        """ Время до сброса дневного лимита """
        import datetime
        now = datetime.datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        delta = tomorrow - now
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{hours}ч {minutes}м"
    
    def get_time_until_weekly_reset(self, user_id: int) -> str:
        """ Время до сброса недельного лимита """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today()
        
        if not user.week_start:
            return "сейчас"
        
        try:
            week_start = datetime.date.fromisoformat(user.week_start)
            week_end = week_start + datetime.timedelta(days=7)
            days_left = (week_end - today).days
            
            if days_left <= 0:
                return "сейчас"
            return f"{days_left} дн"
        except:
            return "скоро"
    
    def get_plan_expiry_info(self, user_id: int) -> dict:
        """ Информация об истечении плана """
        import datetime
        user = self.get_user(user_id)
        
        if user.plan == "free" or not user.plan_expires:
            return {"has_expiry": False, "days_left": None, "expires": None}
        
        try:
            expires = datetime.date.fromisoformat(user.plan_expires)
            today = datetime.date.today()
            days_left = (expires - today).days
            return {
                "has_expiry": True,
                "days_left": max(0, days_left),
                "expires": user.plan_expires
            }
        except:
            return {"has_expiry": False, "days_left": None, "expires": None}
    
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
        
        # Дневной и недельный счётчики
        self._reset_daily_if_needed(user_id)
        self._reset_weekly_if_needed(user_id)
        user.daily_videos += 1
        user.weekly_videos += 1
        
        # Месячный счётчик (для совместимости)
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
        
        # Сброс счётчиков
        self._reset_daily_if_needed(user_id)
        self._reset_weekly_if_needed(user_id)
        
        return {
            "total_videos": user.total_videos,
            "today_videos": user.today_videos,
            "daily_videos": user.daily_videos,
            "daily_limit": limits.videos_per_day,
            "daily_remaining": max(0, limits.videos_per_day - user.daily_videos),
            "weekly_videos": user.weekly_videos,
            "weekly_limit": limits.videos_per_week,
            "weekly_remaining": max(0, limits.videos_per_week - user.weekly_videos),
            "monthly_videos": user.monthly_videos,
            "monthly_limit": limits.videos_per_week,  # Используем недельный для совместимости
            "monthly_remaining": max(0, limits.videos_per_week - user.weekly_videos),
            "last_process_time": user.last_process_time,
            "mode": user.mode,
            "quality": user.quality,
            "text_overlay": user.text_overlay,
            "plan": user.plan,
            "username": user.username,
            "total_downloads": user.total_downloads,
            "monthly_downloads": user.monthly_downloads,
            "first_seen": user.first_seen,
        }
    
    def increment_download_count(self, user_id: int):
        """ Увеличить счётчик скачиваний (только скачать) """
        import datetime
        user = self.get_user(user_id)
        
        # Сбрасываем месячный счётчик если нужно
        self._reset_monthly_if_needed(user_id)
        
        user.total_downloads += 1
        user.monthly_downloads += 1
    
    def is_new_user(self, user_id: int) -> bool:
        """ Проверка, новый ли пользователь (ещё не уведомляли админа) """
        import datetime
        user = self.get_user(user_id)
        
        if not user.first_seen:
            user.first_seen = datetime.datetime.now().isoformat()
        
        if not user.admin_notified:
            user.admin_notified = True
            return True
        return False
    
    def get_total_users(self) -> int:
        """ Общее количество пользователей """
        return len(self.users)
    
    def get_global_stats(self) -> dict:
        """ Глобальная статистика """
        import datetime
        total_users = len(self.users)
        total_videos = sum(u.total_videos for u in self.users.values())
        total_downloads = sum(u.total_downloads for u in self.users.values())
        vip_users = sum(1 for u in self.users.values() if u.plan == "vip")
        premium_users = sum(1 for u in self.users.values() if u.plan == "premium")
        free_users = sum(1 for u in self.users.values() if u.plan == "free")
        
        # Активные сегодня
        today = datetime.date.today().isoformat()
        active_today = sum(1 for u in self.users.values() if u.today_date == today)
        
        # Языки
        languages = {}
        for u in self.users.values():
            lang = u.language or "ru"
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            "total_users": total_users,
            "total_videos": total_videos,
            "total_downloads": total_downloads,
            "vip_users": vip_users,
            "premium_users": premium_users,
            "active_today": active_today,
            "plans": {
                "free": free_users,
                "vip": vip_users,
                "premium": premium_users,
            },
            "languages": languages,
        }
    
    def get_daily_stats(self) -> dict:
        """ Получить статистику за сегодня """
        import datetime
        today = datetime.date.today().isoformat()
        
        # Считаем новых пользователей (first_seen = сегодня)
        new_users = sum(1 for u in self.users.values() 
                       if u.first_seen and u.first_seen.startswith(today))
        
        # Видео за сегодня
        videos_today = sum(u.today_videos for u in self.users.values() 
                          if u.today_date == today)
        
        # Скачиваний (используем today_downloads если есть)
        downloads_today = sum(getattr(u, 'today_downloads', 0) for u in self.users.values())
        
        return {
            "new_users": new_users,
            "videos_today": videos_today,
            "downloads_today": downloads_today,
        }
    
    def reset_daily_stats(self):
        """ Сброс ежедневных счетчиков """
        for user in self.users.values():
            user.today_videos = 0
            if hasattr(user, 'today_downloads'):
                user.today_downloads = 0
        self.save_data()
    
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
    
    # ═════════════════════════════════════════════════════════════
    # BAN SYSTEM
    # ═════════════════════════════════════════════════════════════
    
    def ban_user(self, user_id: int, reason: str = ""):
        user = self.get_user(user_id)
        user.banned = True
        user.ban_reason = reason
        self.save_data()
    
    def unban_user(self, user_id: int):
        user = self.get_user(user_id)
        user.banned = False
        user.ban_reason = ""
        self.save_data()
    
    def is_banned(self, user_id: int) -> bool:
        return self.get_user(user_id).banned
    
    def get_ban_reason(self, user_id: int) -> str:
        return self.get_user(user_id).ban_reason
    
    # ═════════════════════════════════════════════════════════════
    # LANGUAGE
    # ═════════════════════════════════════════════════════════════
    
    def set_language(self, user_id: int, lang: str):
        user = self.get_user(user_id)
        user.language = lang
        user.language_set = True
        self.save_data()
    
    def is_language_set(self, user_id: int) -> bool:
        """ Проверка, был ли выбран язык пользователем """
        return self.get_user(user_id).language_set
    
    def get_language(self, user_id: int) -> str:
        return self.get_user(user_id).language
    
    # ═════════════════════════════════════════════════════════════
    # REFERRAL SYSTEM
    # ═════════════════════════════════════════════════════════════
    
    def get_referral_stats(self, user_id: int) -> dict:
        user = self.get_user(user_id)
        return {
            "referrer_id": user.referrer_id,
            "referral_count": user.referral_count,
            "referral_bonus": user.referral_bonus,
        }
    
    def use_referral_bonus(self, user_id: int) -> bool:
        """ Использовать бонусное видео """
        user = self.get_user(user_id)
        if user.referral_bonus > 0:
            user.referral_bonus -= 1
            self.save_data()
            return True
        return False
    
    def get_referral_link(self, user_id: int) -> str:
        return f"https://t.me/Virexprobot?start=ref{user_id}"
    
    # ═════════════════════════════════════════════════════════════
    # PLAN EXPIRATION
    # ═════════════════════════════════════════════════════════════
    
    def set_plan_with_expiry(self, user_id: int, plan: str, days: int = 30):
        """ Установить план с датой истечения """
        import datetime
        user = self.get_user(user_id)
        user.plan = plan
        expiry = datetime.date.today() + datetime.timedelta(days=days)
        user.plan_expires = expiry.isoformat()
        # Сброс месячного счётчика
        user.monthly_videos = 0
        user.period_start = datetime.date.today().isoformat()
        self.save_data()
    
    def check_plan_expiry(self, user_id: int) -> bool:
        """ Проверить, не истёк ли план. Возвращает True если истёк """
        import datetime
        user = self.get_user(user_id)
        if user.plan == "free" or not user.plan_expires:
            return False
        
        try:
            expiry = datetime.date.fromisoformat(user.plan_expires)
            if datetime.date.today() > expiry:
                user.plan = "free"
                user.plan_expires = ""
                self.save_data()
                return True
        except:
            pass
        return False
    
    def get_plan_expiry_days(self, user_id: int) -> int:
        """ Дней до истечения плана """
        import datetime
        user = self.get_user(user_id)
        if user.plan == "free" or not user.plan_expires:
            return 0
        
        try:
            expiry = datetime.date.fromisoformat(user.plan_expires)
            days = (expiry - datetime.date.today()).days
            return max(0, days)
        except:
            return 0
    
    def get_expiring_users(self, days_before: int = 3) -> list:
        """ Получить список пользователей с истекающим планом """
        import datetime
        result = []
        today = datetime.date.today()
        
        for uid, user in self.users.items():
            if user.plan != "free" and user.plan_expires:
                try:
                    expiry = datetime.date.fromisoformat(user.plan_expires)
                    days_left = (expiry - today).days
                    if 0 < days_left <= days_before:
                        result.append({
                            "user_id": uid,
                            "username": user.username,
                            "plan": user.plan,
                            "days_left": days_left,
                        })
                except:
                    pass
        return result
    
    def should_notify_expiry(self, user_id: int) -> bool:
        """ Проверить, нужно ли уведомлять об истечении """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today().isoformat()
        
        # Уведомляем только раз в день
        if user.expiry_notified == today:
            return False
        return True
    
    def mark_expiry_notified(self, user_id: int):
        """ Отметить, что уведомление отправлено """
        import datetime
        user = self.get_user(user_id)
        user.expiry_notified = datetime.date.today().isoformat()
        self.save_data()
    
    # ═════════════════════════════════════════════════════════════
    # NIGHT MODE
    # ═════════════════════════════════════════════════════════════
    
    def toggle_night_mode(self, user_id: int) -> bool:
        """ Переключить ночной режим, вернуть новое значение """
        user = self.get_user(user_id)
        user.night_mode = not user.night_mode
        self.save_data()
        return user.night_mode
    
    def is_night_mode(self, user_id: int) -> bool:
        return self.get_user(user_id).night_mode
    
    # ═════════════════════════════════════════════════════════════
    # TOP USERS
    # ═════════════════════════════════════════════════════════════
    
    def get_top_users(self, limit: int = 10) -> list:
        """ Получить топ пользователей по количеству обработок """
        sorted_users = sorted(
            self.users.values(),
            key=lambda u: u.total_videos,
            reverse=True
        )[:limit]
        
        result = []
        for i, user in enumerate(sorted_users, 1):
            result.append({
                "position": i,
                "user_id": user.user_id,
                "username": user.username,
                "total_videos": user.total_videos,
                "plan": user.plan,
            })
        return result
    
    # ═════════════════════════════════════════════════════════════
    # BAN LIST
    # ═════════════════════════════════════════════════════════════
    
    def get_banned_users(self) -> list:
        """ Получить список забаненных пользователей """
        result = []
        for user in self.users.values():
            if user.banned:
                result.append({
                    "user_id": user.user_id,
                    "username": user.username,
                    "reason": user.ban_reason,
                })
        return result
    
    # ═════════════════════════════════════════════════════════════
    # REFERRAL BONUS +3 VIDEOS
    # ═════════════════════════════════════════════════════════════
    
    def set_referrer(self, user_id: int, referrer_id: int):
        """ Установить реферера (кто пригласил) - даёт +3 видео """
        print(f"[REFERRAL] set_referrer called: user={user_id}, referrer={referrer_id}")
        if user_id == referrer_id:
            print(f"[REFERRAL] REJECTED: user == referrer")
            return False
        user = self.get_user(user_id)
        print(f"[REFERRAL] user.referrer_id = {user.referrer_id}")
        if user.referrer_id == 0:  # Только если ещё не установлен
            user.referrer_id = referrer_id
            # Увеличиваем счётчик рефералов у пригласившего
            referrer = self.get_user(referrer_id)
            referrer.referral_count += 1
            referrer.referral_bonus += 3  # +3 бонусных видео
            self.save_data()
            print(f"[REFERRAL] SUCCESS! referrer {referrer_id} now has {referrer.referral_bonus} bonus videos")
            return True
        print(f"[REFERRAL] REJECTED: user already has referrer_id={user.referrer_id}")
        return False
    
    def has_referral_bonus(self, user_id: int) -> bool:
        """ Есть ли бонусные видео """
        user = self.get_user(user_id)
        return user.referral_bonus > 0
    
    def get_all_users(self) -> list:
        """ Получить список всех ID пользователей """
        return list(self.users.keys())
    
    # ═════════════════════════════════════════════════════════════
    # PROMO CODES
    # ═════════════════════════════════════════════════════════════
    
    def get_promo_codes(self) -> dict:
        """ Получить все промо-коды """
        if not hasattr(self, '_promo_codes'):
            self._promo_codes = {}
            self._load_promo_codes()
        return self._promo_codes
    
    def _load_promo_codes(self):
        """ Загрузить промо-коды из файла """
        import json
        import os
        try:
            if os.path.exists("promo_codes.json"):
                with open("promo_codes.json", 'r', encoding='utf-8') as f:
                    self._promo_codes = json.load(f)
        except:
            self._promo_codes = {}
    
    def _save_promo_codes(self):
        """ Сохранить промо-коды в файл """
        import json
        try:
            with open("promo_codes.json", 'w', encoding='utf-8') as f:
                json.dump(self._promo_codes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[PROMO] Save error: {e}")
    
    def create_promo_code(self, code: str, bonus_type: str, bonus_value: int, max_uses: int = 100) -> bool:
        """
        Создать промо-код
        bonus_type: "videos" (бонусные видео), "days_vip", "days_premium"
        """
        codes = self.get_promo_codes()
        code = code.upper()
        
        if code in codes:
            return False
        
        codes[code] = {
            "bonus_type": bonus_type,
            "bonus_value": bonus_value,
            "max_uses": max_uses,
            "used_count": 0,
            "used_by": [],  # список user_id кто использовал
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "active": True,
        }
        self._save_promo_codes()
        return True
    
    def activate_promo_code(self, user_id: int, code: str) -> Tuple[bool, str]:
        """
        Активировать промо-код
        Returns: (success, message)
        """
        codes = self.get_promo_codes()
        code = code.upper()
        
        if code not in codes:
            return False, "invalid"
        
        promo = codes[code]
        
        if not promo.get("active", True):
            return False, "inactive"
        
        if promo["used_count"] >= promo["max_uses"]:
            return False, "expired"
        
        if user_id in promo.get("used_by", []):
            return False, "already_used"
        
        # Применяем бонус
        user = self.get_user(user_id)
        bonus_type = promo["bonus_type"]
        bonus_value = promo["bonus_value"]
        
        if bonus_type == "videos":
            user.referral_bonus += bonus_value
            result_msg = f"+{bonus_value} videos"
        elif bonus_type == "days_vip":
            self.set_plan_with_expiry(user_id, "vip", bonus_value)
            result_msg = f"VIP {bonus_value} days"
        elif bonus_type == "days_premium":
            self.set_plan_with_expiry(user_id, "premium", bonus_value)
            result_msg = f"Premium {bonus_value} days"
        else:
            return False, "unknown_type"
        
        # Обновляем счётчик
        promo["used_count"] += 1
        promo["used_by"].append(user_id)
        self._save_promo_codes()
        self.save_data()
        
        return True, result_msg
    
    def delete_promo_code(self, code: str) -> bool:
        """ Удалить промо-код """
        codes = self.get_promo_codes()
        code = code.upper()
        if code in codes:
            del codes[code]
            self._save_promo_codes()
            return True
        return False
    
    def list_promo_codes(self) -> list:
        """ Список всех промо-кодов """
        codes = self.get_promo_codes()
        result = []
        for code, data in codes.items():
            result.append({
                "code": code,
                "bonus_type": data["bonus_type"],
                "bonus_value": data["bonus_value"],
                "used": data["used_count"],
                "max": data["max_uses"],
                "active": data.get("active", True),
            })
        return result
    
    # ═════════════════════════════════════════════════════════════
    # PROCESSING HISTORY
    # ═════════════════════════════════════════════════════════════
    
    def add_to_history(self, user_id: int, video_type: str, source: str = "file"):
        """ Добавить запись в историю обработок """
        user = self.get_user(user_id)
        if not hasattr(user, 'history'):
            user.history = []
        
        import datetime
        entry = {
            "time": datetime.datetime.now().isoformat(),
            "type": video_type,  # "tiktok" / "youtube"
            "source": source,  # "file" / "url"
        }
        user.history.append(entry)
        
        # Храним только последние 20 записей
        if len(user.history) > 20:
            user.history = user.history[-20:]
    
    def get_history(self, user_id: int, limit: int = 10) -> list:
        """ Получить историю обработок """
        user = self.get_user(user_id)
        history = getattr(user, 'history', [])
        return history[-limit:][::-1]  # последние N в обратном порядке
    
    # ═════════════════════════════════════════════════════════════
    # ADMIN STATS
    # ═════════════════════════════════════════════════════════════
    
    def get_global_stats(self) -> dict:
        """ Глобальная статистика для админа """
        import datetime
        today = datetime.date.today().isoformat()
        
        total_users = len(self.users)
        active_today = 0
        total_videos = 0
        total_downloads = 0
        plans = {"free": 0, "vip": 0, "premium": 0}
        languages = {"ru": 0, "en": 0}
        
        for user in self.users.values():
            total_videos += user.total_videos
            total_downloads += user.total_downloads
            plans[user.plan] = plans.get(user.plan, 0) + 1
            languages[user.language] = languages.get(user.language, 0) + 1
            
            if user.today_date == today and user.today_videos > 0:
                active_today += 1
        
        return {
            "total_users": total_users,
            "active_today": active_today,
            "total_videos": total_videos,
            "total_downloads": total_downloads,
            "plans": plans,
            "languages": languages,
            "promo_codes": len(self.get_promo_codes()),
        }
    
    # ═════════════════════════════════════════════════════════════
    # BACKUP / RESTORE
    # ═════════════════════════════════════════════════════════════
    
    def export_backup(self) -> str:
        """ Экспортировать все данные в JSON строку """
        import json
        import datetime
        
        backup = {
            "version": "1.0",
            "created": datetime.datetime.now().isoformat(),
            "users": {},
            "promo_codes": self._promo_codes
        }
        
        for uid, user in self.users.items():
            backup["users"][str(uid)] = {
                "plan": user.plan,
                "mode": user.mode,
                "total_videos": user.total_videos,
                "monthly_videos": user.monthly_videos,
                "period_start": user.period_start,
                "username": user.username,
                "total_downloads": user.total_downloads,
                "monthly_downloads": user.monthly_downloads,
                "first_seen": user.first_seen,
                "quality": user.quality,
                "text_overlay": user.text_overlay,
                "banned": user.banned,
                "ban_reason": user.ban_reason,
                "language": user.language,
                "referrer_id": user.referrer_id,
                "referral_count": user.referral_count,
                "referral_bonus": user.referral_bonus,
                "plan_expires": user.plan_expires,
                "history": getattr(user, 'history', []),
            }
        
        return json.dumps(backup, ensure_ascii=False, indent=2)
    
    def import_backup(self, json_data: str) -> tuple:
        """ 
        Импортировать данные из JSON. 
        Возвращает (success, message)
        """
        import json
        
        try:
            backup = json.loads(json_data)
            
            if "users" not in backup:
                return False, "Invalid backup format"
            
            users_imported = 0
            for uid, udata in backup["users"].items():
                user = self.get_user(int(uid))
                for key, value in udata.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                users_imported += 1
            
            # Импортируем промо-коды если есть
            if "promo_codes" in backup:
                self._promo_codes.update(backup["promo_codes"])
                self._save_promo_codes()
            
            self.save_data()
            return True, f"Imported {users_imported} users"
        except json.JSONDecodeError:
            return False, "Invalid JSON"
        except Exception as e:
            return False, str(e)
    
    # ═════════════════════════════════════════════════════════════
    # SOURCE STATS
    # ═════════════════════════════════════════════════════════════
    
    def get_source_stats(self) -> dict:
        """ Статистика по источникам видео """
        sources = {
            "file": 0,
            "tiktok": 0,
            "youtube": 0,
            "instagram": 0,
            "chinese": 0,
            "url": 0,
        }
        
        for user in self.users.values():
            history = getattr(user, 'history', [])
            for entry in history:
                source = entry.get("source", "unknown")
                if source in sources:
                    sources[source] += 1
                else:
                    sources["url"] += 1
        
        return sources
    
    # ═════════════════════════════════════════════════════════════
    # NEW USER CHECK
    # ═════════════════════════════════════════════════════════════
    
    def is_new_user(self, user_id: int) -> bool:
        """ Проверить, новый ли это пользователь """
        user = self.get_user(user_id)
        if not user.admin_notified:
            user.admin_notified = True
            return True
        return False
    
    def get_user_count_for_queue(self, user_id: int) -> int:
        """ Посчитать сколько задач юзера в очереди """
        # Используется в связке с active_tasks из ffmpeg_utils
        count = 0
        from ffmpeg_utils import active_tasks
        for task_id, task in active_tasks.items():
            if task.user_id == user_id:
                count += 1
        return count
    
    # ═════════════════════════════════════════════════════════════
    # v2.8.0: TRIAL VIP
    # ═════════════════════════════════════════════════════════════
    
    def can_use_trial(self, user_id: int) -> bool:
        """ Может ли пользователь использовать trial VIP """
        user = self.get_user(user_id)
        return user.plan == "free" and not getattr(user, 'trial_used', False)
    
    def activate_trial(self, user_id: int) -> bool:
        """ Активировать trial VIP на 24 часа """
        user = self.get_user(user_id)
        if not self.can_use_trial(user_id):
            return False
        
        user.trial_used = True
        self.set_plan_with_expiry(user_id, "vip", 1)  # 1 день
        self.save_data()
        return True
    
    def is_trial_used(self, user_id: int) -> bool:
        """ Был ли использован trial """
        user = self.get_user(user_id)
        return getattr(user, 'trial_used', False)
    
    # ═════════════════════════════════════════════════════════════
    # v2.8.0: STREAK BONUS
    # ═════════════════════════════════════════════════════════════
    
    def update_streak(self, user_id: int) -> Tuple[int, bool]:
        """ 
        Обновить streak пользователя при обработке видео.
        Возвращает (новый streak, получен ли бонус)
        """
        import datetime
        user = self.get_user(user_id)
        today = datetime.date.today().isoformat()
        
        streak_count = getattr(user, 'streak_count', 0)
        streak_last = getattr(user, 'streak_last_date', '')
        
        if streak_last == today:
            # Уже учтено сегодня
            return streak_count, False
        
        if streak_last:
            try:
                last_date = datetime.date.fromisoformat(streak_last)
                yesterday = datetime.date.today() - datetime.timedelta(days=1)
                
                if last_date == yesterday:
                    # Продолжаем streak
                    streak_count += 1
                else:
                    # Streak сброшен
                    streak_count = 1
            except:
                streak_count = 1
        else:
            streak_count = 1
        
        user.streak_count = streak_count
        user.streak_last_date = today
        
        # Бонус за 7-дневный streak: +1 к дневному лимиту
        bonus_earned = streak_count >= 7 and streak_count % 7 == 0
        
        self.save_data()
        return streak_count, bonus_earned
    
    def get_streak(self, user_id: int) -> dict:
        """ Получить информацию о streak """
        import datetime
        user = self.get_user(user_id)
        streak_count = getattr(user, 'streak_count', 0)
        streak_last = getattr(user, 'streak_last_date', '')
        
        # Проверяем актуальность streak
        is_active = False
        if streak_last:
            try:
                last_date = datetime.date.fromisoformat(streak_last)
                yesterday = datetime.date.today() - datetime.timedelta(days=1)
                today = datetime.date.today()
                is_active = last_date >= yesterday
            except:
                pass
        
        return {
            "streak": streak_count if is_active else 0,
            "last_date": streak_last,
            "is_active": is_active,
            "has_bonus": streak_count >= 7,
        }
    
    def get_streak_bonus_videos(self, user_id: int) -> int:
        """ Получить бонусные видео за streak (1 за каждые 7 дней) """
        streak = self.get_streak(user_id)
        if streak["has_bonus"]:
            return streak["streak"] // 7
        return 0
    
    # ═════════════════════════════════════════════════════════════
    # v2.8.0: FAVORITES
    # ═════════════════════════════════════════════════════════════
    
    def save_favorite(self, user_id: int, name: str) -> bool:
        """ Сохранить текущие настройки как избранное """
        user = self.get_user(user_id)
        favorites = getattr(user, 'favorites', [])
        
        # Максимум 5 избранных
        if len(favorites) >= 5:
            favorites.pop(0)
        
        favorite = {
            "name": name,
            "quality": user.quality,
            "text_overlay": user.text_overlay,
            "mode": user.mode,
        }
        favorites.append(favorite)
        user.favorites = favorites
        self.save_data()
        return True
    
    def load_favorite(self, user_id: int, name: str) -> bool:
        """ Загрузить избранные настройки """
        user = self.get_user(user_id)
        favorites = getattr(user, 'favorites', [])
        
        for fav in favorites:
            if fav.get("name") == name:
                user.quality = fav.get("quality", user.quality)
                user.text_overlay = fav.get("text_overlay", user.text_overlay)
                user.mode = fav.get("mode", user.mode)
                self.save_data()
                return True
        return False
    
    def delete_favorite(self, user_id: int, name: str) -> bool:
        """ Удалить избранные настройки """
        user = self.get_user(user_id)
        favorites = getattr(user, 'favorites', [])
        
        for i, fav in enumerate(favorites):
            if fav.get("name") == name:
                favorites.pop(i)
                user.favorites = favorites
                self.save_data()
                return True
        return False
    
    def get_favorites(self, user_id: int) -> list:
        """ Получить список избранных настроек """
        user = self.get_user(user_id)
        return getattr(user, 'favorites', [])
    
    # ═════════════════════════════════════════════════════════════
    # v2.8.0: OPERATION LOGS
    # ═════════════════════════════════════════════════════════════
    
    def add_log(self, user_id: int, operation: str, details: str = ""):
        """ Добавить запись в лог операций """
        import datetime
        user = self.get_user(user_id)
        logs = getattr(user, 'operation_logs', [])
        
        entry = {
            "time": datetime.datetime.now().strftime("%m-%d %H:%M"),
            "op": operation,
            "details": details[:50],
        }
        logs.append(entry)
        
        # Храним только последние 20
        if len(logs) > 20:
            logs = logs[-20:]
        
        user.operation_logs = logs
    
    def get_logs(self, user_id: int, limit: int = 20) -> list:
        """ Получить логи операций """
        user = self.get_user(user_id)
        logs = getattr(user, 'operation_logs', [])
        return logs[-limit:][::-1]
    
    # ═════════════════════════════════════════════════════════════
    # v2.8.0: ENHANCED STATS
    # ═════════════════════════════════════════════════════════════
    
    def get_extended_daily_stats(self) -> dict:
        """ Расширенная статистика за день """
        import datetime
        today = datetime.date.today().isoformat()
        
        stats = {
            "new_users": 0,
            "active_users": 0,
            "videos_processed": 0,
            "downloads": 0,
            "by_plan": {"free": 0, "vip": 0, "premium": 0},
            "errors": 0,
        }
        
        for user in self.users.values():
            if user.first_seen and user.first_seen.startswith(today):
                stats["new_users"] += 1
            
            if user.today_date == today:
                if user.today_videos > 0:
                    stats["active_users"] += 1
                stats["videos_processed"] += user.today_videos
                stats["by_plan"][user.plan] = stats["by_plan"].get(user.plan, 0) + user.today_videos
        
        return stats
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: GAMIFICATION
    # ═════════════════════════════════════════════════════════════
    
    def add_points(self, user_id: int, points: int, reason: str = "") -> Tuple[int, bool]:
        """Добавить очки и проверить повышение уровня"""
        from config import USER_LEVELS
        user = self.get_user(user_id)
        
        old_level = getattr(user, 'level', 1)
        user.points = getattr(user, 'points', 0) + points
        
        # Проверяем новый уровень
        new_level = 1
        for lvl in USER_LEVELS:
            if user.points >= lvl["points"]:
                new_level = lvl["level"]
        
        user.level = new_level
        level_up = new_level > old_level
        
        self.save_data()
        return new_level, level_up
    
    def get_user_level(self, user_id: int) -> dict:
        """Получить информацию об уровне пользователя"""
        from config import USER_LEVELS
        user = self.get_user(user_id)
        
        points = getattr(user, 'points', 0)
        level = getattr(user, 'level', 1)
        
        # Найти текущий и следующий уровень
        current_level = USER_LEVELS[0]
        next_level = USER_LEVELS[1] if len(USER_LEVELS) > 1 else None
        
        for i, lvl in enumerate(USER_LEVELS):
            if lvl["level"] == level:
                current_level = lvl
                next_level = USER_LEVELS[i + 1] if i + 1 < len(USER_LEVELS) else None
                break
        
        return {
            "level": level,
            "name": current_level["name"],
            "emoji": current_level["emoji"],
            "points": points,
            "next_level_points": next_level["points"] if next_level else None,
            "next_level_name": next_level["name"] if next_level else None,
        }
    
    def unlock_achievement(self, user_id: int, achievement_id: str) -> dict:
        """Разблокировать достижение"""
        from config import ACHIEVEMENTS
        user = self.get_user(user_id)
        
        achievements = getattr(user, 'achievements', [])
        
        if achievement_id in achievements:
            return None  # Уже разблокировано
        
        if achievement_id not in ACHIEVEMENTS:
            return None  # Не существует
        
        achievement = ACHIEVEMENTS[achievement_id]
        achievements.append(achievement_id)
        user.achievements = achievements
        
        # Добавляем очки
        self.add_points(user_id, achievement["points"], achievement_id)
        
        self.save_data()
        return achievement
    
    def check_achievements(self, user_id: int) -> list:
        """Проверить и разблокировать достижения"""
        import datetime
        user = self.get_user(user_id)
        unlocked = []
        
        total = user.total_videos
        streak = getattr(user, 'streak_count', 0)
        referrals = user.referral_count
        hour = datetime.datetime.now().hour
        
        # Проверяем условия
        checks = [
            ("first_video", total >= 1),
            ("videos_10", total >= 10),
            ("videos_50", total >= 50),
            ("videos_100", total >= 100),
            ("videos_500", total >= 500),
            ("streak_7", streak >= 7),
            ("streak_30", streak >= 30),
            ("referral_1", referrals >= 1),
            ("referral_10", referrals >= 10),
            ("night_owl", hour >= 0 and hour < 5),
            ("early_bird", hour >= 5 and hour < 7),
        ]
        
        for ach_id, condition in checks:
            if condition:
                result = self.unlock_achievement(user_id, ach_id)
                if result:
                    unlocked.append(result)
        
        return unlocked
    
    def get_achievements(self, user_id: int) -> dict:
        """Получить список достижений пользователя"""
        from config import ACHIEVEMENTS
        user = self.get_user(user_id)
        
        user_achievements = getattr(user, 'achievements', [])
        total_points = sum(ACHIEVEMENTS[a]["points"] for a in user_achievements if a in ACHIEVEMENTS)
        
        return {
            "unlocked": user_achievements,
            "total": len(ACHIEVEMENTS),
            "total_points": total_points,
        }
    
    def get_leaderboard(self, limit: int = 10) -> list:
        """Получить таблицу лидеров по очкам"""
        users_with_points = []
        
        for uid, user in self.users.items():
            points = getattr(user, 'points', 0)
            level = getattr(user, 'level', 1)
            if points > 0:
                users_with_points.append({
                    "user_id": uid,
                    "username": user.username,
                    "points": points,
                    "level": level,
                })
        
        # Сортируем по очкам
        users_with_points.sort(key=lambda x: x["points"], reverse=True)
        return users_with_points[:limit]
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: TRIM SETTINGS
    # ═════════════════════════════════════════════════════════════
    
    def set_trim(self, user_id: int, start: str, end: str):
        """Установить параметры обрезки"""
        user = self.get_user(user_id)
        user.trim_start = start
        user.trim_end = end
    
    def get_trim(self, user_id: int) -> Tuple[str, str]:
        """Получить параметры обрезки"""
        user = self.get_user(user_id)
        return getattr(user, 'trim_start', ''), getattr(user, 'trim_end', '')
    
    def clear_trim(self, user_id: int):
        """Очистить параметры обрезки"""
        user = self.get_user(user_id)
        user.trim_start = ""
        user.trim_end = ""
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: CUSTOM WATERMARK
    # ═════════════════════════════════════════════════════════════
    
    def set_watermark(self, user_id: int, file_id: str, position: str = "br"):
        """Установить водяной знак"""
        user = self.get_user(user_id)
        user.watermark_file_id = file_id
        user.watermark_position = position
        self.save_data()
    
    def get_watermark(self, user_id: int) -> Tuple[str, str]:
        """Получить водяной знак"""
        user = self.get_user(user_id)
        return getattr(user, 'watermark_file_id', ''), getattr(user, 'watermark_position', 'br')
    
    def remove_watermark(self, user_id: int):
        """Удалить водяной знак"""
        user = self.get_user(user_id)
        user.watermark_file_id = ""
        self.save_data()
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: RESOLUTION SETTINGS
    # ═════════════════════════════════════════════════════════════
    
    def set_resolution(self, user_id: int, resolution: str):
        """Установить разрешение"""
        user = self.get_user(user_id)
        user.resolution = resolution
        self.save_data()
    
    def get_resolution(self, user_id: int) -> str:
        """Получить разрешение"""
        user = self.get_user(user_id)
        return getattr(user, 'resolution', 'original')
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: EFFECT TEMPLATES
    # ═════════════════════════════════════════════════════════════
    
    def set_template(self, user_id: int, template_id: str):
        """Установить шаблон эффектов"""
        user = self.get_user(user_id)
        user.current_template = template_id
        self.save_data()
    
    def get_template(self, user_id: int) -> str:
        """Получить текущий шаблон"""
        user = self.get_user(user_id)
        return getattr(user, 'current_template', '')
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: POSTING REMINDERS
    # ═════════════════════════════════════════════════════════════
    
    def add_reminder(self, user_id: int, platform: str, time_str: str):
        """Добавить напоминание о публикации"""
        user = self.get_user(user_id)
        reminders = getattr(user, 'reminders', [])
        
        reminders.append({
            "platform": platform,
            "time": time_str,
            "enabled": True,
        })
        
        user.reminders = reminders
        self.save_data()
    
    def get_reminders(self, user_id: int) -> list:
        """Получить напоминания"""
        user = self.get_user(user_id)
        return getattr(user, 'reminders', [])
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: WEEKLY ANALYTICS
    # ═════════════════════════════════════════════════════════════
    
    def update_weekly_stats(self, user_id: int):
        """Обновить недельную статистику"""
        import datetime
        user = self.get_user(user_id)
        
        today = datetime.date.today().isoformat()
        weekly_stats = getattr(user, 'weekly_stats', {})
        
        if not isinstance(weekly_stats, dict):
            weekly_stats = {}
        
        weekly_stats[today] = weekly_stats.get(today, 0) + 1
        
        # Храним только последние 7 дней
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        weekly_stats = {k: v for k, v in weekly_stats.items() if k >= week_ago}
        
        user.weekly_stats = weekly_stats
    
    def get_weekly_analytics(self, user_id: int) -> dict:
        """Получить аналитику за неделю"""
        import datetime
        user = self.get_user(user_id)
        
        weekly_stats = getattr(user, 'weekly_stats', {})
        if not isinstance(weekly_stats, dict):
            weekly_stats = {}
        
        # Генерируем данные за 7 дней
        days = []
        total = 0
        for i in range(6, -1, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            count = weekly_stats.get(day, 0)
            days.append({
                "day": day,
                "short": datetime.date.fromisoformat(day).strftime("%a"),
                "count": count,
            })
            total += count
        
        return {
            "days": days,
            "total": total,
            "average": round(total / 7, 1),
        }
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: MUSIC OVERLAY
    # ═════════════════════════════════════════════════════════════
    
    def set_pending_audio(self, user_id: int, file_id: str):
        """Установить ожидающее аудио"""
        user = self.get_user(user_id)
        user.pending_audio_file_id = file_id
    
    def get_pending_audio(self, user_id: int) -> str:
        """Получить ожидающее аудио"""
        user = self.get_user(user_id)
        return getattr(user, 'pending_audio_file_id', '')
    
    def clear_pending_audio(self, user_id: int):
        """Очистить ожидающее аудио"""
        user = self.get_user(user_id)
        user.pending_audio_file_id = ""
    
    # ═════════════════════════════════════════════════════════════
    # v2.9.0: BATCH PROCESSING
    # ═════════════════════════════════════════════════════════════
    
    def add_to_batch(self, user_id: int, file_id: str) -> int:
        """Добавить видео в пакет"""
        from config import MAX_BATCH_SIZE
        user = self.get_user(user_id)
        
        batch = getattr(user, 'batch_videos', [])
        if not isinstance(batch, list):
            batch = []
        
        if len(batch) >= MAX_BATCH_SIZE:
            return -1  # Лимит
        
        batch.append(file_id)
        user.batch_videos = batch
        return len(batch)
    
    def get_batch(self, user_id: int) -> list:
        """Получить пакет видео"""
        user = self.get_user(user_id)
        return getattr(user, 'batch_videos', [])
    
    def clear_batch(self, user_id: int):
        """Очистить пакет"""
        user = self.get_user(user_id)
        user.batch_videos = []
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: MERGE VIDEOS
    # ═════════════════════════════════════════════════════════════
    
    def add_to_merge(self, user_id: int, file_id: str) -> int:
        """Добавить видео в очередь склейки"""
        from config import MAX_MERGE_VIDEOS
        user = self.get_user(user_id)
        
        merge = getattr(user, 'merge_videos', [])
        if not isinstance(merge, list):
            merge = []
        
        if len(merge) >= MAX_MERGE_VIDEOS:
            return -1  # Лимит
        
        merge.append(file_id)
        user.merge_videos = merge
        return len(merge)
    
    def get_merge_queue(self, user_id: int) -> list:
        """Получить очередь склейки"""
        user = self.get_user(user_id)
        return getattr(user, 'merge_videos', [])
    
    def clear_merge_queue(self, user_id: int):
        """Очистить очередь склейки"""
        user = self.get_user(user_id)
        user.merge_videos = []
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: SPEED CONTROL
    # ═════════════════════════════════════════════════════════════
    
    def set_speed(self, user_id: int, speed: str):
        """Установить скорость видео"""
        user = self.get_user(user_id)
        user.speed_setting = speed
    
    def get_speed(self, user_id: int) -> str:
        """Получить скорость видео"""
        user = self.get_user(user_id)
        return getattr(user, 'speed_setting', '1x')
    
    def clear_speed(self, user_id: int):
        """Сбросить скорость"""
        user = self.get_user(user_id)
        user.speed_setting = "1x"
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: ROTATION/FLIP
    # ═════════════════════════════════════════════════════════════
    
    def set_rotation(self, user_id: int, rotation: str):
        """Установить поворот/отражение"""
        user = self.get_user(user_id)
        user.rotation_setting = rotation
    
    def get_rotation(self, user_id: int) -> str:
        """Получить поворот"""
        user = self.get_user(user_id)
        return getattr(user, 'rotation_setting', '')
    
    def clear_rotation(self, user_id: int):
        """Сбросить поворот"""
        user = self.get_user(user_id)
        user.rotation_setting = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: ASPECT RATIO
    # ═════════════════════════════════════════════════════════════
    
    def set_aspect(self, user_id: int, aspect: str):
        """Установить соотношение сторон"""
        user = self.get_user(user_id)
        user.aspect_setting = aspect
    
    def get_aspect(self, user_id: int) -> str:
        """Получить соотношение сторон"""
        user = self.get_user(user_id)
        return getattr(user, 'aspect_setting', '')
    
    def clear_aspect(self, user_id: int):
        """Сбросить соотношение"""
        user = self.get_user(user_id)
        user.aspect_setting = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: VIDEO FILTERS
    # ═════════════════════════════════════════════════════════════
    
    def set_filter(self, user_id: int, filter_name: str):
        """Установить фильтр"""
        user = self.get_user(user_id)
        user.filter_setting = filter_name
    
    def get_filter(self, user_id: int) -> str:
        """Получить фильтр"""
        user = self.get_user(user_id)
        return getattr(user, 'filter_setting', '')
    
    def clear_filter(self, user_id: int):
        """Удалить фильтр"""
        user = self.get_user(user_id)
        user.filter_setting = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: CUSTOM TEXT OVERLAY
    # ═════════════════════════════════════════════════════════════
    
    def set_custom_text(self, user_id: int, text: str):
        """Установить свой текст"""
        user = self.get_user(user_id)
        user.custom_text = text
    
    def get_custom_text(self, user_id: int) -> str:
        """Получить свой текст"""
        user = self.get_user(user_id)
        return getattr(user, 'custom_text', '')
    
    def clear_custom_text(self, user_id: int):
        """Удалить свой текст"""
        user = self.get_user(user_id)
        user.custom_text = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: CAPTION STYLES
    # ═════════════════════════════════════════════════════════════
    
    def set_caption_style(self, user_id: int, style: str):
        """Установить стиль текста"""
        user = self.get_user(user_id)
        user.caption_style = style
    
    def get_caption_style(self, user_id: int) -> str:
        """Получить стиль текста"""
        user = self.get_user(user_id)
        return getattr(user, 'caption_style', 'default')
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: COMPRESSION
    # ═════════════════════════════════════════════════════════════
    
    def set_compression(self, user_id: int, preset: str):
        """Установить пресет сжатия"""
        user = self.get_user(user_id)
        user.compression_preset = preset
    
    def get_compression(self, user_id: int) -> str:
        """Получить пресет сжатия"""
        user = self.get_user(user_id)
        return getattr(user, 'compression_preset', '')
    
    def clear_compression(self, user_id: int):
        """Сбросить сжатие"""
        user = self.get_user(user_id)
        user.compression_preset = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: VOLUME CONTROL
    # ═════════════════════════════════════════════════════════════
    
    def set_volume(self, user_id: int, volume: str):
        """Установить громкость"""
        user = self.get_user(user_id)
        user.volume_setting = volume
    
    def get_volume(self, user_id: int) -> str:
        """Получить громкость"""
        user = self.get_user(user_id)
        return getattr(user, 'volume_setting', '100%')
    
    def clear_volume(self, user_id: int):
        """Сбросить громкость"""
        user = self.get_user(user_id)
        user.volume_setting = "100%"
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: SCHEDULER
    # ═════════════════════════════════════════════════════════════
    
    def add_scheduled_task(self, user_id: int, time_str: str, action: str, params: dict = None):
        """Добавить запланированную задачу"""
        import datetime
        user = self.get_user(user_id)
        
        tasks = getattr(user, 'scheduled_tasks', [])
        if not isinstance(tasks, list):
            tasks = []
        
        tasks.append({
            "id": len(tasks) + 1,
            "time": time_str,
            "action": action,
            "params": params or {},
            "created": datetime.datetime.now().isoformat(),
            "executed": False,
        })
        
        user.scheduled_tasks = tasks
        self.save_data()
        return len(tasks)
    
    def get_scheduled_tasks(self, user_id: int) -> list:
        """Получить запланированные задачи"""
        user = self.get_user(user_id)
        tasks = getattr(user, 'scheduled_tasks', [])
        # Только невыполненные
        return [t for t in tasks if not t.get('executed', False)]
    
    def mark_task_executed(self, user_id: int, task_id: int):
        """Отметить задачу выполненной"""
        user = self.get_user(user_id)
        tasks = getattr(user, 'scheduled_tasks', [])
        
        for task in tasks:
            if task.get('id') == task_id:
                task['executed'] = True
                break
        
        user.scheduled_tasks = tasks
        self.save_data()
    
    def remove_scheduled_task(self, user_id: int, task_id: int):
        """Удалить задачу"""
        user = self.get_user(user_id)
        tasks = getattr(user, 'scheduled_tasks', [])
        
        tasks = [t for t in tasks if t.get('id') != task_id]
        user.scheduled_tasks = tasks
        self.save_data()
    
    def clear_scheduled_tasks(self, user_id: int):
        """Очистить все задачи"""
        user = self.get_user(user_id)
        user.scheduled_tasks = []
        self.save_data()
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: AUTO-PROCESS
    # ═════════════════════════════════════════════════════════════
    
    def set_auto_process(self, user_id: int, template: str):
        """Установить шаблон автообработки"""
        user = self.get_user(user_id)
        user.auto_process_template = template
    
    def get_auto_process(self, user_id: int) -> str:
        """Получить шаблон автообработки"""
        user = self.get_user(user_id)
        return getattr(user, 'auto_process_template', '')
    
    def clear_auto_process(self, user_id: int):
        """Выключить автообработку"""
        user = self.get_user(user_id)
        user.auto_process_template = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: PENDING VIDEO
    # ═════════════════════════════════════════════════════════════
    
    def set_pending_video(self, user_id: int, file_id: str):
        """Установить ожидающее видео"""
        user = self.get_user(user_id)
        user.pending_video_file_id = file_id
    
    def get_pending_video(self, user_id: int) -> str:
        """Получить ожидающее видео"""
        user = self.get_user(user_id)
        return getattr(user, 'pending_video_file_id', '')
    
    def clear_pending_video(self, user_id: int):
        """Очистить ожидающее видео"""
        user = self.get_user(user_id)
        user.pending_video_file_id = ""
    
    # ═════════════════════════════════════════════════════════════
    # v3.0.0: CLEAR ALL V3 SETTINGS
    # ═════════════════════════════════════════════════════════════
    
    def clear_v3_settings(self, user_id: int):
        """Сбросить все настройки v3.0.0"""
        user = self.get_user(user_id)
        user.speed_setting = "1x"
        user.rotation_setting = ""
        user.aspect_setting = ""
        user.filter_setting = ""
        user.custom_text = ""
        user.caption_style = "default"
        user.compression_preset = ""
        user.volume_setting = "100%"
    
    def has_v3_settings(self, user_id: int) -> bool:
        """Проверить есть ли активные настройки v3.0.0"""
        user = self.get_user(user_id)
        return any([
            getattr(user, 'speed_setting', '1x') != '1x',
            getattr(user, 'rotation_setting', ''),
            getattr(user, 'aspect_setting', ''),
            getattr(user, 'filter_setting', ''),
            getattr(user, 'custom_text', ''),
            getattr(user, 'compression_preset', ''),
            getattr(user, 'volume_setting', '100%') != '100%',
        ])
    
    def get_v3_settings_summary(self, user_id: int) -> str:
        """Получить сводку активных настроек v3.0.0"""
        user = self.get_user(user_id)
        settings = []
        
        speed = getattr(user, 'speed_setting', '1x')
        if speed != '1x':
            settings.append(f"⚡ Скорость: {speed}")
        
        rotation = getattr(user, 'rotation_setting', '')
        if rotation:
            settings.append(f"🔄 Поворот: {rotation}")
        
        aspect = getattr(user, 'aspect_setting', '')
        if aspect:
            settings.append(f"📏 Формат: {aspect}")
        
        filter_s = getattr(user, 'filter_setting', '')
        if filter_s:
            settings.append(f"🎨 Фильтр: {filter_s}")
        
        text = getattr(user, 'custom_text', '')
        if text:
            settings.append(f"✍️ Текст: {text[:20]}...")
        
        compress = getattr(user, 'compression_preset', '')
        if compress:
            settings.append(f"📦 Сжатие: {compress}")
        
        volume = getattr(user, 'volume_setting', '100%')
        if volume != '100%':
            settings.append(f"🔊 Громкость: {volume}")
        
        return "\n".join(settings) if settings else "Нет активных настроек"

rate_limiter = RateLimiter()
