import aiohttp
import logging
from config import VEXBOOST_API_KEY, VEXBOOST_API_URL

logger = logging.getLogger(__name__)

class VexBoostError(Exception):
    pass

async def _call_api(params: dict):
    """Базовый метод для запросов к VexBoost API."""
    params['key'] = VEXBOOST_API_KEY
    async with aiohttp.ClientSession() as session:
        async with session.get(VEXBOOST_API_URL, params=params) as resp:
            if resp.status != 200:
                raise VexBoostError(f"HTTP {resp.status}: {await resp.text()}")
            return await resp.json()

async def get_services():
    """Возвращает список всех услуг VexBoost."""
    return await _call_api({'action': 'services'})

async def create_order(service_id: int, link: str, quantity: int) -> dict:
    """Создаёт заказ в VexBoost. Возвращает {'order': order_id}."""
    params = {
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    return await _call_api(params)

async def get_order_status(order_id: int) -> dict:
    """Возвращает статус заказа (одного)."""
    params = {'action': 'status', 'order': order_id}
    return await _call_api(params)

async def get_orders_status(orders_ids: list) -> dict:
    """Возвращает статус нескольких заказов."""
    params = {'action': 'status', 'orders': ','.join(map(str, orders_ids))}
    return await _call_api(params)

async def refill_order(order_id: int) -> dict:
    """Запрашивает рефилл заказа."""
    params = {'action': 'refill', 'order': order_id}
    return await _call_api(params)

async def cancel_order(order_id: int) -> dict:
    """Отменяет заказ."""
    params = {'action': 'cancel', 'order': order_id}
    return await _call_api(params)

async def get_balance() -> dict:
    """Возвращает баланс аккаунта VexBoost."""
    params = {'action': 'balance'}
    return await _call_api(params)