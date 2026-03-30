"""
Модуль работы с администраторами.
"""

from typing import List
from .core import execute, fetchone, fetchall

async def create_admins_table(conn):
    """Создаёт таблицу admins."""
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    logger.info("Table 'admins' ready")

async def add_admin(user_id: int):
    """Добавляет пользователя в список администраторов."""
    await execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))

async def remove_admin(user_id: int):
    """Удаляет пользователя из списка администраторов."""
    await execute('DELETE FROM admins WHERE user_id = ?', (user_id,))

async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    row = await fetchone('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    return row is not None

async def get_all_admins() -> List[int]:
    """Возвращает список ID всех администраторов."""
    rows = await fetchall('SELECT user_id FROM admins')
    return [row[0] for row in rows]