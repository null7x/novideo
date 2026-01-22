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
    # Реферальная система
    referrer_id: int = 0  # Кто пригласил
    referral_count: int = 0  # Сколько пригласил
    referral_bonus: int = 0  # Бонусные видео
    # Дата окончания VIP/Premium
    plan_expires: str = ""  # ISO дата окончания
    # Уведомление об истечении
    expiry_notified: str = ""  # Дата последнего уведомления

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
        self.save_data()
    
    def get_language(self, user_id: int) -> str:
        return self.get_user(user_id).language
    
    # ═════════════════════════════════════════════════════════════
    # REFERRAL SYSTEM
    # ═════════════════════════════════════════════════════════════
    
    def set_referrer(self, user_id: int, referrer_id: int):
        """ Установить реферера (кто пригласил) """
        if user_id == referrer_id:
            return False
        user = self.get_user(user_id)
        if user.referrer_id == 0:  # Только если ещё не установлен
            user.referrer_id = referrer_id
            # Увеличиваем счётчик рефералов у пригласившего
            referrer = self.get_user(referrer_id)
            referrer.referral_count += 1
            referrer.referral_bonus += 1  # +1 бонусное видео
            self.save_data()
            return True
        return False
    
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
        return f"https://t.me/Arion_1bot?start=ref{user_id}"
    
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

rate_limiter = RateLimiter()
