import aiosqlite
import logging

DB_PATH = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                banned INTEGER DEFAULT 0,
                accepted_terms INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                banned_by INTEGER,
                banned_at TIMESTAMP,
                ban_reason TEXT
            )
        ''')
        for col in ['banned_by', 'banned_at', 'ban_reason']:
            try:
                await db.execute(f'SELECT {col} FROM users LIMIT 1')
            except aiosqlite.OperationalError:
                await db.execute(f'ALTER TABLE users ADD COLUMN {col} TEXT')
                logging.info(f"Column '{col}' added to users table.")
        try:
            await db.execute('SELECT balance FROM users LIMIT 1')
        except aiosqlite.OperationalError:
            await db.execute('ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0')
            logging.info("Column 'balance' added to users table.")
        try:
            await db.execute('SELECT accepted_terms FROM users LIMIT 1')
        except aiosqlite.OperationalError:
            await db.execute('ALTER TABLE users ADD COLUMN accepted_terms INTEGER DEFAULT 0')
            logging.info("Column 'accepted_terms' added to users table.")

        # Таблица заказов (добавляем поле status WAITING_CONFIRM)
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
                payment_id TEXT,
                payment_charge_id TEXT,
                payment_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        for col in ['payment_id', 'payment_charge_id', 'payment_method', 'comment']:
            try:
                await db.execute(f'SELECT {col} FROM orders LIMIT 1')
            except aiosqlite.OperationalError:
                await db.execute(f'ALTER TABLE orders ADD COLUMN {col} TEXT')
                logging.info(f"Column '{col}' added to orders table.")

        # Таблица транзакций
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                status TEXT,
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица администраторов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')

        # Таблица состояния бота
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('INSERT OR IGNORE INTO bot_state (key, value) VALUES ("active", "1")')
        await db.execute('INSERT OR IGNORE INTO bot_state (key, value) VALUES ("reason", "")')
        await db.commit()
    logging.info("Database initialized.")

# ====== Состояние бота ======
async def is_bot_active() -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT value FROM bot_state WHERE key = "active"') as cursor:
            row = await cursor.fetchone()
            return row and row[0] == "1"

async def get_bot_status() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT key, value FROM bot_state') as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

async def set_bot_active(active: bool, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE bot_state SET value = ? WHERE key = "active"', ("1" if active else "0",))
        if reason:
            await db.execute('UPDATE bot_state SET value = ? WHERE key = "reason"', (reason,))
        else:
            await db.execute('UPDATE bot_state SET value = ? WHERE key = "reason"', ("",))
        await db.commit()

# ====== Пользователи ======
async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def get_balance(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0

async def update_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def set_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 1

async def get_ban_info(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT banned, banned_by, banned_at, ban_reason FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def ban_user(user_id: int, admin_id: int, reason: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET banned = 1, banned_by = ?, banned_at = datetime("now"), ban_reason = ? WHERE user_id = ?',
            (admin_id, reason, user_id)
        )
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET banned = 0, banned_by = NULL, banned_at = NULL, ban_reason = NULL WHERE user_id = ?', (user_id,))
        await db.commit()

async def has_accepted_terms(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT accepted_terms FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 1

async def accept_terms(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET accepted_terms = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM users') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# ====== Заказы ======
async def create_order(order_id: str, user_id: int, service: str, quantity: int, price: float, link: str, status: str = "NEW", comment: str = None, payment_method: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO orders (order_id, user_id, service, quantity, price, link, status, comment, payment_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (order_id, user_id, service, quantity, price, link, status, comment, payment_method)
        )
        await db.commit()

async def get_order(order_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)) as cursor:
            return await cursor.fetchone()

async def update_order_status(order_id: str, status: str, comment: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE orders SET status = ?, comment = ? WHERE order_id = ?',
            (status, comment, order_id)
        )
        await db.commit()

async def update_order_payment_id(order_id: str, payment_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE orders SET payment_id = ? WHERE order_id = ?',
            (payment_id, order_id)
        )
        await db.commit()

async def update_order_payment_method(order_id: str, method: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE orders SET payment_method = ? WHERE order_id = ?',
            (method, order_id)
        )
        await db.commit()

async def get_pending_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM orders WHERE status = ?', ("PENDING",)) as cursor:
            return await cursor.fetchall()

async def get_orders_by_status(status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM orders WHERE status = ?', (status,)) as cursor:
            return await cursor.fetchall()

# ====== Транзакции ======
async def add_transaction(user_id: int, amount: float, method: str, status: str, payment_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO transactions (user_id, amount, method, status, payment_id) VALUES (?, ?, ?, ?, ?)',
            (user_id, amount, method, status, payment_id)
        )
        await db.commit()

async def get_transactions(user_id: int, limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            return await cursor.fetchall()

async def get_all_transactions(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?',
            (limit,)
        ) as cursor:
            return await cursor.fetchall()

# ====== Администраторы ======
async def add_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def remove_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        await db.commit()

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM admins') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]