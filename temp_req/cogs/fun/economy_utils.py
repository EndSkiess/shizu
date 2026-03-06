"""
Economy utility functions for managing user balances using MongoDB
"""
import logging
from ..utils.db import db

logger = logging.getLogger('EconomyUtils')

COLLECTION = 'economy'
STARTING_BALANCE = 100
CURRENCY_NAME = "cursed coins"

async def get_balance(user_id: int) -> int:
    """Get user balance, create account if doesn't exist"""
    user_id_str = str(user_id)
    data = await db.find_one(COLLECTION, {'_id': user_id_str})
    
    if not data:
        data = {
            '_id': user_id_str,
            'balance': STARTING_BALANCE,
            'last_daily': None,
            'total_earned': STARTING_BALANCE,
            'total_spent': 0
        }
        await db.insert_one(COLLECTION, data)
        return STARTING_BALANCE
    
    return data.get('balance', STARTING_BALANCE)

async def set_balance(user_id: int, amount: int):
    """Set user balance"""
    user_id_str = str(user_id)
    await db.update_one(
        COLLECTION, 
        {'_id': user_id_str},
        {'$set': {'balance': amount}},
        upsert=True
    )

async def add_balance(user_id: int, amount: int):
    """Add to user balance"""
    user_id_str = str(user_id)
    # Check if user exists first to handle STARTING_BALANCE
    data = await db.find_one(COLLECTION, {'_id': user_id_str})
    
    if not data:
        new_balance = STARTING_BALANCE + amount
        await db.insert_one(COLLECTION, {
            '_id': user_id_str,
            'balance': new_balance,
            'last_daily': None,
            'total_earned': new_balance,
            'total_spent': 0
        })
        return new_balance
    
    await db.update_one(
        COLLECTION,
        {'_id': user_id_str},
        {
            '$inc': {'balance': amount, 'total_earned': amount}
        }
    )
    return data.get('balance', 0) + amount

async def remove_balance(user_id: int, amount: int) -> bool:
    """Remove from user balance, returns True if successful"""
    user_id_str = str(user_id)
    data = await db.find_one(COLLECTION, {'_id': user_id_str})
    
    if not data:
        # Create user with starting balance
        if STARTING_BALANCE < amount:
            return False
        await db.insert_one(COLLECTION, {
            '_id': user_id_str,
            'balance': STARTING_BALANCE - amount,
            'last_daily': None,
            'total_earned': STARTING_BALANCE,
            'total_spent': amount
        })
        return True
    
    if data.get('balance', 0) < amount:
        return False
    
    await db.update_one(
        COLLECTION,
        {'_id': user_id_str},
        {
            '$inc': {'balance': -amount, 'total_spent': amount}
        }
    )
    return True

async def has_balance(user_id: int, amount: int) -> bool:
    """Check if user has enough balance"""
    balance = await get_balance(user_id)
    return balance >= amount

async def get_last_daily(user_id: int) -> str:
    """Get last daily claim timestamp"""
    user_id_str = str(user_id)
    data = await db.find_one(COLLECTION, {'_id': user_id_str})
    if not data:
        return None
    return data.get('last_daily')

async def set_last_daily(user_id: int, timestamp: str):
    """Set last daily claim timestamp"""
    user_id_str = str(user_id)
    await db.update_one(
        COLLECTION,
        {'_id': user_id_str},
        {'$set': {'last_daily': timestamp}},
        upsert=True
    )

async def get_leaderboard(limit: int = 10):
    """Get top users by balance"""
    col = await db.get_collection(COLLECTION)
    if col is None: return []
    cursor = col.find().sort('balance', -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    # Convert to expected format [(id, data), ...]
    return [(doc['_id'], doc) for doc in docs]

async def get_user_stats(user_id: int):
    """Get user statistics"""
    user_id_str = str(user_id)
    data = await db.find_one(COLLECTION, {'_id': user_id_str})
    
    if not data:
        return {
            'balance': STARTING_BALANCE,
            'total_earned': STARTING_BALANCE,
            'total_spent': 0,
            'net_profit': STARTING_BALANCE
        }
    
    return {
        'balance': data.get('balance', 0),
        'total_earned': data.get('total_earned', 0),
        'total_spent': data.get('total_spent', 0),
        'net_profit': data.get('total_earned', 0) - data.get('total_spent', 0)
    }

# Compatibility functions (optional, but keep for safety if used elsewhere)
def load_economy():
    """NOT RECOMMENDED - use async functions. Returning empty dict to avoid crashes."""
    return {}

def save_economy(data):
    """NOT RECOMMENDED - use async functions."""
    pass
