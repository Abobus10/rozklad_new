"""
Модуль с моделями данных для Telegram бота.

Использует Pydantic для валидации и типизации данных.
Это обеспечивает лучшую читаемость кода и предотвращает ошибки типов.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserModel(BaseModel):
    """Модель пользователя бота."""
    
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
        """Валидация формата времени."""
        if v is None:
            return v
        try:
            hour, minute = map(int, v.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError('Неверный формат времени')
            return v
        except (ValueError, AttributeError):
            raise ValueError('Время должно быть в формате HH:MM')


class LessonModel(BaseModel):
    """Модель учебной пары."""
    
    pair: int = Field(ge=1, le=8, description="Номер пары (1-8)")
    name: str = Field(min_length=1, description="Название предмета")
    teacher: Optional[str] = Field(None, description="Преподаватель")
    room: Optional[str] = Field(None, description="Аудитория")
    weeks: List[Literal[1, 2, 3, 4]] = Field(description="Недели проведения пары")
    
    @field_validator('weeks')
    @classmethod
    def validate_weeks(cls, v: List[int]) -> List[int]:
        """Валидация списка недель."""
        if not v or not all(week in [1, 2, 3, 4] for week in v):
            raise ValueError('Недели должны быть от 1 до 4')
        return sorted(list(set(v)))  # Убираем дубликаты и сортируем


class GroupScheduleModel(BaseModel):
    """Модель расписания группы."""
    
    schedule: Dict[str, List[LessonModel]] = Field(
        default_factory=dict,
        description="Расписание по дням недели"
    )
    
    @field_validator('schedule')
    @classmethod
    def validate_schedule_days(cls, v: Dict[str, List[LessonModel]]) -> Dict[str, List[LessonModel]]:
        """Валидация дней недели в расписании."""
        valid_days = {'понеділок', 'вівторок', 'середа', 'четвер', 'п\'ятниця', 'субота', 'неділя'}
        for day in v.keys():
            if day not in valid_days:
                raise ValueError(f'Неверный день недели: {day}')
        return v


class ScheduleDataModel(BaseModel):
    """Модель данных расписания."""
    
    startDate: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    groups: Dict[str, GroupScheduleModel] = Field(default_factory=dict)
    
    @field_validator('startDate')
    @classmethod
    def validate_start_date(cls, v: Optional[str]) -> Optional[str]:
        """Валидация даты начала семестра."""
        if v is None:
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Дата должна быть в формате YYYY-MM-DD')


class GroupChatModel(BaseModel):
    """Модель группового чата."""
    
    default_group: Optional[str] = None
    enabled: bool = True
    last_schedule_sent: Optional[datetime] = None


class AppConfigModel(BaseModel):
    """Модель конфигурации приложения."""
    
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
        """Валидация списка ID администраторов."""
        return [admin_id for admin_id in v if admin_id > 0]


class BotStatsModel(BaseModel):
    """Модель статистики бота."""
    
    total_users: int = 0
    active_users_today: int = 0
    total_groups: int = 0
    total_messages_sent: int = 0
    uptime: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now) 