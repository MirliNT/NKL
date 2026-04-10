import logging
from typing import Optional, Tuple, List
from datetime import datetime
from .core import execute, fetchone, fetchall, get_connection

logger = logging.getLogger(__name__)

async def create_users_table(conn):
    """Создаёт таблицу users, если её нет."""
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            banned INTEGER DEFAULT 0,
            accepted_terms INTEGER DEFAULT 0,
            balance REAL DEFAULT 0,
            banned_by INTEGER,
            banned_at TIMESTAMP,
            ban_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Добавляем недостающие колонки для старых БД
    for col, col_type in [
        ('balance', 'REAL DEFAULT 0'),
        ('accepted_terms', 'INTEGER DEFAULT 0'),
        ('banned_by', 'INTEGER'),
        ('banned_at', 'TIMESTAMP'),
        ('ban_reason', 'TEXT'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ]:
        try:
            await conn.execute(f'SELECT {col} FROM users LIMIT 1')
        except:
            await conn.execute(f'ALTER TABLE users ADD COLUMN {col} {col_type}')
    logger.info("Table 'users' ready")

async def add_user(user_id: int):
    """Добавляет пользователя, если его нет, и устанавливает created_at."""
    await execute('INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, datetime("now"))', (user_id,))

async def get_balance(user_id: int) -> float:
    row = await fetchone('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    return row[0] if row else 0.0

async def update_balance(user_id: int, amount: float):
    await execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))

async def set_balance(user_id: int, amount: float):
    await execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))

async def is_banned(user_id: int) -> bool:
    row = await fetchone('SELECT banned FROM users WHERE user_id = ?', (user_id,))
    return row and row[0] == 1

async def get_ban_info(user_id: int) -> Optional[Tuple]:
    return await fetchone('SELECT banned, banned_by, banned_at, ban_reason FROM users WHERE user_id = ?', (user_id,))

async def ban_user(user_id: int, admin_id: int, reason: str = None):
    await execute(
        'UPDATE users SET banned = 1, banned_by = ?, banned_at = datetime("now"), ban_reason = ? WHERE user_id = ?',
        (admin_id, reason, user_id)
    )

async def unban_user(user_id: int):
    await execute('UPDATE users SET banned = 0, banned_by = NULL, banned_at = NULL, ban_reason = NULL WHERE user_id = ?', (user_id,))

async def has_accepted_terms(user_id: int) -> bool:
    row = await fetchone('SELECT accepted_terms FROM users WHERE user_id = ?', (user_id,))
    return row and row[0] == 1

async def accept_terms(user_id: int):
    await execute('UPDATE users SET accepted_terms = 1 WHERE user_id = ?', (user_id,))

async def get_all_users() -> List[int]:
    rows = await fetchall('SELECT user_id FROM users')
    return [row[0] for row in rows]

# ====== Функции для профиля ======
async def get_user_reg_date(user_id: int) -> Optional[datetime]:
    """Возвращает дату регистрации пользователя."""
    row = await fetchone('SELECT created_at FROM users WHERE user_id = ?', (user_id,))
    if row and row[0]:
        if isinstance(row[0], str):
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return row[0]
    return None

async def get_user_spent(user_id: int) -> float:
    """Сумма всех успешных заказов пользователя (статусы PAID или ACCEPTED)."""
    rows = await fetchall(
        'SELECT SUM(price) FROM orders WHERE user_id = ? AND status IN ("PAID", "ACCEPTED")',
        (user_id,)
    )
    return rows[0][0] if rows and rows[0][0] else 0.0

async def get_user_orders_count(user_id: int) -> int:
    """Количество выполненных заказов (PAID или ACCEPTED)."""
    row = await fetchone(
        'SELECT COUNT(*) FROM orders WHERE user_id = ? AND status IN ("PAID", "ACCEPTED")',
        (user_id,)
    )
    return row[0] if row else 0

async def get_user_orders(user_id: int, limit: int = 20):
    """Возвращает последние заказы пользователя (все статусы)."""
    return await fetchall(
        'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    )