"""
Economy utility functions for managing user balances
"""
import json
from pathlib import Path
from datetime import datetime
import asyncio

ECONOMY_FILE = Path('data/economy.json')
STARTING_BALANCE = 100
CURRENCY_NAME = "cursed coins"

# Thread lock for file operations
_lock = asyncio.Lock()


def load_economy():
    """Load economy data from JSON file"""
    if not ECONOMY_FILE.exists():
        return {}
    
    try:
        with open(ECONOMY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_economy(data):
    """Save economy data to JSON file"""
    ECONOMY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ECONOMY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def get_balance(user_id: int) -> int:
    """Get user balance, create account if doesn't exist"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = {
                'balance': STARTING_BALANCE,
                'last_daily': None,
                'total_earned': STARTING_BALANCE,
                'total_spent': 0
            }
            save_economy(data)
        
        return data[user_id_str]['balance']


async def set_balance(user_id: int, amount: int):
    """Set user balance"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = {
                'balance': amount,
                'last_daily': None,
                'total_earned': amount,
                'total_spent': 0
            }
        else:
            data[user_id_str]['balance'] = amount
        
        save_economy(data)


async def add_balance(user_id: int, amount: int):
    """Add to user balance"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = {
                'balance': STARTING_BALANCE + amount,
                'last_daily': None,
                'total_earned': STARTING_BALANCE + amount,
                'total_spent': 0
            }
        else:
            data[user_id_str]['balance'] += amount
            data[user_id_str]['total_earned'] = data[user_id_str].get('total_earned', 0) + amount
        
        save_economy(data)
        return data[user_id_str]['balance']


async def remove_balance(user_id: int, amount: int) -> bool:
    """Remove from user balance, returns True if successful"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        # Ensure user exists
        if user_id_str not in data:
            data[user_id_str] = {
                'balance': STARTING_BALANCE,
                'last_daily': None,
                'total_earned': STARTING_BALANCE,
                'total_spent': 0
            }
        
        # Check if user has enough balance
        if data[user_id_str]['balance'] < amount:
            return False
        
        data[user_id_str]['balance'] -= amount
        data[user_id_str]['total_spent'] = data[user_id_str].get('total_spent', 0) + amount
        save_economy(data)
        return True


async def has_balance(user_id: int, amount: int) -> bool:
    """Check if user has enough balance"""
    balance = await get_balance(user_id)
    return balance >= amount


async def get_last_daily(user_id: int) -> str:
    """Get last daily claim timestamp"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            return None
        
        return data[user_id_str].get('last_daily')


async def set_last_daily(user_id: int, timestamp: str):
    """Set last daily claim timestamp"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = {
                'balance': STARTING_BALANCE,
                'last_daily': timestamp,
                'total_earned': STARTING_BALANCE,
                'total_spent': 0
            }
        else:
            data[user_id_str]['last_daily'] = timestamp
        
        save_economy(data)


async def get_leaderboard(limit: int = 10):
    """Get top users by balance"""
    async with _lock:
        data = load_economy()
        
        # Sort by balance
        sorted_users = sorted(
            data.items(),
            key=lambda x: x[1]['balance'],
            reverse=True
        )
        
        return sorted_users[:limit]


async def get_user_stats(user_id: int):
    """Get user statistics"""
    async with _lock:
        data = load_economy()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            return {
                'balance': STARTING_BALANCE,
                'total_earned': STARTING_BALANCE,
                'total_spent': 0,
                'net_profit': STARTING_BALANCE
            }
        
        user_data = data[user_id_str]
        return {
            'balance': user_data['balance'],
            'total_earned': user_data.get('total_earned', 0),
            'total_spent': user_data.get('total_spent', 0),
            'net_profit': user_data.get('total_earned', 0) - user_data.get('total_spent', 0)
        }
