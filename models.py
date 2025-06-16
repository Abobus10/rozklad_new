"""
Модуль з моделями даних для Telegram-бота.

Використовує Pydantic для валідації та типізації даних.
Це забезпечує кращу читабельність коду та запобігає помилкам типів.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserModel(BaseModel):
    """Модель користувача бота."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    group: Optional[str] = None
    reminder_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    reminder_enabled: bool = True
    next_lesson_notification: bool = True
    next_lesson_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    registration_date: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    @field_validator('reminder_time', 'next_lesson_time')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Валідація формату часу."""
        if v is None:
            return v
        try:
            hour, minute = map(int, v.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError('Неправильний формат часу')
            return v
        except (ValueError, AttributeError):
            raise ValueError('Час має бути у форматі HH:MM')


class LessonModel(BaseModel):
    """Модель навчальної пари."""
    
    pair: int = Field(ge=1, le=8, description="Номер пари (1-8)")
    name: str = Field(min_length=1, description="Назва предмету")
    teacher: Optional[str] = Field(None, description="Викладач")
    room: Optional[str] = Field(None, description="Аудиторія")
    weeks: List[Literal[1, 2, 3, 4]] = Field(description="Тижні проведення пари")
    
    @field_validator('weeks')
    @classmethod
    def validate_weeks(cls, v: List[int]) -> List[int]:
        """Валідація списку тижнів."""
        if not v or not all(week in [1, 2, 3, 4] for week in v):
            raise ValueError('Тижні мають бути від 1 до 4')
        return sorted(list(set(v)))  # Прибираємо дублікати та сортуємо


class GroupScheduleModel(BaseModel):
    """Модель розкладу групи."""
    
    schedule: Dict[str, List[LessonModel]] = Field(
        default_factory=dict,
        description="Розклад за днями тижня"
    )
    
    @field_validator('schedule')
    @classmethod
    def validate_schedule_days(cls, v: Dict[str, List[LessonModel]]) -> Dict[str, List[LessonModel]]:
        """Валідація днів тижня в розкладі."""
        valid_days = {'понеділок', 'вівторок', 'середа', 'четвер', 'п\'ятниця', 'субота', 'неділя'}
        for day in v.keys():
            if day not in valid_days:
                raise ValueError(f'Неправильний день тижня: {day}')
        return v


class ScheduleDataModel(BaseModel):
    """Модель даних розкладу."""
    
    startDate: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    groups: Dict[str, GroupScheduleModel] = Field(default_factory=dict)
    
    @field_validator('startDate')
    @classmethod
    def validate_start_date(cls, v: Optional[str]) -> Optional[str]:
        """Валідація дати початку семестру."""
        if v is None:
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Дата має бути у форматі YYYY-MM-DD')


class GroupChatModel(BaseModel):
    """Модель групового чату."""
    
    default_group: Optional[str] = None
    enabled: bool = True
    last_schedule_sent: Optional[datetime] = None


class AppConfigModel(BaseModel):
    """Модель конфігурації додатку."""
    
    telegram_token: str = Field(min_length=1)
    admin_ids: List[int] = Field(default_factory=list)
    kyiv_tz: str = "Europe/Kiev"
    users_file: str = "users.json"
    schedule_file: str = "schedule.json"
    group_chats_file: str = "group_chats.json"
    daily_reminder_time: str = Field("08:00", pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    
    @field_validator('admin_ids')
    @classmethod
    def validate_admin_ids(cls, v: List[int]) -> List[int]:
        """Валідація списку ID адміністраторів."""
        return [admin_id for admin_id in v if admin_id > 0]


class BotStatsModel(BaseModel):
    """Модель статистики бота."""
    
    total_users: int = 0
    active_users_today: int = 0
    total_groups: int = 0
    total_messages_sent: int = 0
    uptime: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now) 