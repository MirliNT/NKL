"""
Модуль управления настройками бота.
Настройки хранятся в БД и кэшируются для ускорения доступа.
"""

import logging
from typing import Any, Optional
from database.settings_db import get_setting as db_get_setting, set_setting as db_set_setting, get_all_settings as db_get_all
from utils.cache import invalidate_settings as invalidate_cache
from config import DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

# Кэш настроек (будет заполнен при первом обращении)
_settings_cache = None

async def _load_cache():
    """Загружает все настройки в кэш из БД."""
    global _settings_cache
    _settings_cache = await db_get_all()
    logger.debug("Settings cache loaded")

async def get_setting(key: str, default: Any = None) -> Any:
    """
    Получить значение настройки.
    Если в БД нет, возвращает default или значение из DEFAULT_SETTINGS.
    """
    global _settings_cache
    if _settings_cache is None:
        await _load_cache()
    if key in _settings_cache:
        return _settings_cache[key]
    # Если нет в кэше, пробуем получить из БД напрямую (на случай, если кэш не обновлён)
    value = await db_get_setting(key)
    if value is not None:
        return value
    # Иначе возвращаем значение по умолчанию
    return default if default is not None else DEFAULT_SETTINGS.get(key)

async def set_setting(key: str, value: str):
    """
    Установить значение настройки и сбросить кэш.
    """
    await db_set_setting(key, value)
    await invalidate_cache()
    global _settings_cache
    _settings_cache = None  # принудительно сбросить кэш

async def get_all_settings() -> dict:
    """
    Получить все настройки (с учётом кэша).
    """
    global _settings_cache
    if _settings_cache is None:
        await _load_cache()
    return _settings_cache.copy()

async def reload_settings():
    """Принудительно перезагрузить кэш настроек."""
    global _settings_cache
    _settings_cache = None
    await _load_cache()

# Удобные функции для конкретных настроек
async def get_min_topup_yookassa() -> float:
    return float(await get_setting("min_topup_yookassa", "1.0"))

async def get_min_topup_heleket() -> float:
    return float(await get_setting("min_topup_heleket", "5.0"))

async def get_default_price() -> float:
    return float(await get_setting("default_price", "1.0"))