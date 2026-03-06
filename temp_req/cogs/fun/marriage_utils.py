"""
Marriage and Family system utilities - Async data management for marriages and family trees using MongoDB
"""
import logging
from datetime import datetime, UTC
from ..utils.db import db

logger = logging.getLogger('DiscordBot.Marriage')

MARRIAGES_COLLECTION = "marriages"
FAMILY_TREE_COLLECTION = "family_tree"

async def is_married(user_id):
    """Check if user is married"""
    user_id_str = str(user_id)
    data = await db.find_one(MARRIAGES_COLLECTION, {'_id': user_id_str})
    return data is not None

async def get_partner(user_id):
    """Get user's partner ID"""
    user_id_str = str(user_id)
    data = await db.find_one(MARRIAGES_COLLECTION, {'_id': user_id_str})
    if data:
        return data.get("partner_id")
    return None

async def marry_users(user1_id, user2_id):
    """Marry two users"""
    married_at = datetime.now(UTC).isoformat()
    
    await db.update_one(
        MARRIAGES_COLLECTION,
        {'_id': str(user1_id)},
        {'$set': {
            "partner_id": str(user2_id),
            "married_at": married_at,
            "joint_balance": False
        }},
        upsert=True
    )
    
    await db.update_one(
        MARRIAGES_COLLECTION,
        {'_id': str(user2_id)},
        {'$set': {
            "partner_id": str(user1_id),
            "married_at": married_at,
            "joint_balance": False
        }},
        upsert=True
    )

async def divorce_users(user_id):
    """Divorce user and their partner"""
    user_id_str = str(user_id)
    data = await db.find_one(MARRIAGES_COLLECTION, {'_id': user_id_str})
    
    if data:
        partner_id = data["partner_id"]
        
        # Remove both marriage records
        await db.delete_one(MARRIAGES_COLLECTION, {'_id': user_id_str})
        await db.delete_one(MARRIAGES_COLLECTION, {'_id': str(partner_id)})
        
        return partner_id
    
    return None

async def get_marriage_data(user_id):
    """Get marriage data for user"""
    return await db.find_one(MARRIAGES_COLLECTION, {'_id': str(user_id)})

async def toggle_joint_balance(user_id):
    """Toggle joint balance for user's marriage"""
    user_id_str = str(user_id)
    data = await db.find_one(MARRIAGES_COLLECTION, {'_id': user_id_str})
    
    if data:
        partner_id = data["partner_id"]
        current = data.get("joint_balance", False)
        new_value = not current
        
        # Update both users
        await db.update_one(MARRIAGES_COLLECTION, {'_id': user_id_str}, {'$set': {"joint_balance": new_value}})
        await db.update_one(MARRIAGES_COLLECTION, {'_id': str(partner_id)}, {'$set': {"joint_balance": new_value}})
        
        return new_value
    
    return None

async def get_couple_leaderboard(limit=10):
    """Get top couples by marriage duration"""
    col = await db.get_collection(MARRIAGES_COLLECTION)
    if col is None: return []
    
    # Efficiently fetch unique couples by comparing IDs (avoids duplicate partner pairs)
    # Sort by married_at timestamp directly in DB (older = longer duration)
    cursor = col.find({"$expr": {"$lt": ["$_id", "$partner_id"]}}).sort("married_at", 1).limit(limit)
    docs = await cursor.to_list(length=limit)
    
    results = []
    for doc in docs:
        married_at = datetime.fromisoformat(doc["married_at"])
        duration = (datetime.now(UTC) - married_at).total_seconds()
        results.append({
            "user1_id": doc['_id'],
            "user2_id": doc["partner_id"],
            "married_at": doc["married_at"],
            "duration": duration,
            "joint_balance": doc.get("joint_balance", False)
        })
    return results

async def get_family_data(user_id):
    """Get family tree data for user"""
    user_id_str = str(user_id)
    data = await db.find_one(FAMILY_TREE_COLLECTION, {'_id': user_id_str})
    
    if not data:
        data = {
            '_id': user_id_str,
            "parent_ids": [],
            "children_ids": []
        }
        await db.insert_one(FAMILY_TREE_COLLECTION, data)
    
    return data

async def add_child(parent_id, child_id):
    """Add child to parent's family"""
    parent_id_str = str(parent_id)
    child_id_str = str(child_id)
    
    # Add child to parent
    await db.update_one(
        FAMILY_TREE_COLLECTION,
        {'_id': parent_id_str},
        {'$addToSet': {"children_ids": child_id_str}},
        upsert=True
    )
    
    # Add parent to child
    await db.update_one(
        FAMILY_TREE_COLLECTION,
        {'_id': child_id_str},
        {
            '$addToSet': {"parent_ids": parent_id_str},
            '$set': {"adopted_at": datetime.now(UTC).isoformat()}
        },
        upsert=True
    )
    
    # If parent is married, add spouse as parent too
    partner_id = await get_partner(parent_id)
    if partner_id:
        partner_id_str = str(partner_id)
        await db.update_one(
            FAMILY_TREE_COLLECTION,
            {'_id': partner_id_str},
            {'$addToSet': {"children_ids": child_id_str}},
            upsert=True
        )
        await db.update_one(
            FAMILY_TREE_COLLECTION,
            {'_id': child_id_str},
            {'$addToSet': {"parent_ids": partner_id_str}},
            upsert=True
        )

async def can_adopt(parent_id, child_id):
    """Check if parent can adopt child, including circularity checks"""
    child_id_str = str(child_id)
    
    data = await db.find_one(FAMILY_TREE_COLLECTION, {'_id': child_id_str})
    if data:
        if len(data.get("parent_ids", [])) >= 2:
            return False
    
    # Circularity check: parent cannot adopt their own ancestor
    if await is_related(child_id, parent_id):
        return False
        
    return True

async def get_full_family(user_id):
    """Get complete family tree for user"""
    user_id_str = str(user_id)
    
    family = {
        "user_id": user_id_str,
        "parents": [],
        "children": [],
        "grandparents": [],
        "spouse": None
    }
    
    # Get user data
    user_data = await get_family_data(user_id)
    family["parents"] = user_data.get("parent_ids", [])
    family["children"] = user_data.get("children_ids", [])
    
    # Get spouse
    family["spouse"] = await get_partner(user_id)
    
    # Get grandparents
    for parent_id in family["parents"]:
        parent_data = await db.find_one(FAMILY_TREE_COLLECTION, {'_id': parent_id})
        if parent_data:
            family["grandparents"].extend(parent_data.get("parent_ids", []))
    
    return family

async def is_related(user1_id, user2_id):
    """Check if two users are related in any way in the family tree"""
    u1_str = str(user1_id)
    u2_str = str(user2_id)
    
    if u1_str == u2_str:
        return True
        
    # BFS to find any connection
    queue = [u1_str]
    visited = {u1_str}
    
    while queue:
        current = queue.pop(0)
        if current == u2_str:
            return True
            
        data = await db.find_one(FAMILY_TREE_COLLECTION, {'_id': current})
        if not data:
            data = {"parent_ids": [], "children_ids": []}
            
        # Check parents, children, and their connections
        connections = data.get("parent_ids", []) + data.get("children_ids", [])
        
        # Also check spouse (marriage relation)
        spouse = await get_partner(current)
        if spouse:
            connections.append(str(spouse))
            
        for conn in connections:
            if conn not in visited:
                visited.add(conn)
                queue.append(conn)
                
    return False

async def remove_child(parent_id, child_id):
    """Remove a child from parent's family (disown)"""
    parent_id_str = str(parent_id)
    child_id_str = str(child_id)
    
    # Remove child from parent's children list
    await db.update_one(FAMILY_TREE_COLLECTION, {'_id': parent_id_str}, {'$pull': {"children_ids": child_id_str}})
    
    # Remove parent from child's parents list
    await db.update_one(FAMILY_TREE_COLLECTION, {'_id': child_id_str}, {'$pull': {"parent_ids": parent_id_str}})
    
    # Also remove from spouse if married
    partner_id = await get_partner(parent_id)
    if partner_id:
        partner_id_str = str(partner_id)
        await db.update_one(FAMILY_TREE_COLLECTION, {'_id': partner_id_str}, {'$pull': {"children_ids": child_id_str}})
        await db.update_one(FAMILY_TREE_COLLECTION, {'_id': child_id_str}, {'$pull': {"parent_ids": partner_id_str}})
    
    return True

async def remove_from_family(user_id):
    """Remove user from entire family tree (runaway)"""
    user_id_str = str(user_id)
    user_data = await get_family_data(user_id)
    
    if not user_data:
        return False
    
    # Remove user from all parents' children lists
    for parent_id in user_data.get("parent_ids", []):
        await db.update_one(FAMILY_TREE_COLLECTION, {'_id': parent_id}, {'$pull': {"children_ids": user_id_str}})
    
    # Remove user from all children's parent lists
    for child_id in user_data.get("children_ids", []):
        await db.update_one(FAMILY_TREE_COLLECTION, {'_id': child_id}, {'$pull': {"parent_ids": user_id_str}})
    
    # Clear user's family data
    await db.update_one(
        FAMILY_TREE_COLLECTION, 
        {'_id': user_id_str}, 
        {'$set': {"parent_ids": [], "children_ids": []}}
    )
    
    return True

# Compatibility functions (optional, but keep for safety if used elsewhere)
def load_marriages(): return {}
def save_marriages(data): pass
def load_family_tree(): return {}
def save_family_tree(data): pass
