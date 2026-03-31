import logging
from typing import Optional, List, Tuple
from .core import execute, fetchone, fetchall

logger = logging.getLogger(__name__)

async def create_services_table(conn):
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,
            category TEXT,
            subcategory TEXT,
            name TEXT,
            price REAL DEFAULT 1.0,
            speed INTEGER DEFAULT 2,
            description TEXT,
            min_quantity INTEGER,
            max_quantity INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    logger.info("Table 'services' ready")

async def add_service(platform: str, category: str, subcategory: str, name: str, price: float, min_q: int, max_q: int, speed: int = 2, description: str = ""):
    cursor = await execute(
        'INSERT INTO services (platform, category, subcategory, name, price, min_quantity, max_quantity, speed, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (platform, category, subcategory, name, price, min_q, max_q, speed, description)
    )
    return cursor.lastrowid

async def get_service(service_id: int) -> Optional[Tuple]:
    return await fetchone('SELECT * FROM services WHERE id = ?', (service_id,))

async def get_services_by_platform(platform: str) -> List[Tuple]:
    return await fetchall('SELECT * FROM services WHERE platform = ?', (platform,))

async def get_services_by_category(platform: str, category: str) -> List[Tuple]:
    return await fetchall('SELECT * FROM services WHERE platform = ? AND category = ?', (platform, category))

async def get_services_by_subcategory(platform: str, category: str, subcategory: str) -> List[Tuple]:
    return await fetchall('SELECT * FROM services WHERE platform = ? AND category = ? AND subcategory = ?', (platform, category, subcategory))

async def update_service_price(service_id: int, price: float):
    await execute('UPDATE services SET price = ? WHERE id = ?', (price, service_id))

async def update_service_speed(service_id: int, speed: int):
    await execute('UPDATE services SET speed = ? WHERE id = ?', (speed, service_id))

async def update_service_description(service_id: int, description: str):
    await execute('UPDATE services SET description = ? WHERE id = ?', (description, service_id))

async def update_all_prices(discount_percent: int):
    await execute('UPDATE services SET price = price * (1 - ?/100.0)', (discount_percent,))