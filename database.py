import aiosqlite
import logging

DB_PATH = "bot_database.db"

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                banned INTEGER DEFAULT 0
            )
        ''')
        # Таблица заказов (order_id теперь текст)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER,
                service TEXT,
                quantity INTEGER,
                price REAL,
                link TEXT,
                status TEXT DEFAULT 'NEW',
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()
    logging.info("Database initialized.")

# Добавление пользователя
async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        await db.commit()

# Проверка бана
async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 1

# Бан пользователя
async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET banned = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

# Разбан пользователя
async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET banned = 0 WHERE user_id = ?', (user_id,))
        await db.commit()

# Создание заказа (order_id — строка)
async def create_order(order_id: str, user_id: int, service: str, quantity: int, price: float, link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO orders (order_id, user_id, service, quantity, price, link, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (order_id, user_id, service, quantity, price, link, 'NEW')
        )
        await db.commit()

# Получение заказа по ID
async def get_order(order_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)) as cursor:
            return await cursor.fetchone()

# Обновление статуса заказа (с возможным комментарием)
async def update_order_status(order_id: str, status: str, comment: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE orders SET status = ?, comment = ? WHERE order_id = ?',
            (status, comment, order_id)
        )
        await db.commit()