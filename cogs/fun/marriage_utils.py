"""
Marriage and Family system utilities - Data management for marriages and family trees
"""
import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger('DiscordBot.Marriage')

# Data paths
MARRIAGES_PATH = Path("data/marriages.json")
FAMILY_TREE_PATH = Path("data/family_tree.json")

def load_marriages():
    """Load marriages from JSON file"""
    if not MARRIAGES_PATH.exists():
        return {}
    
    try:
        with open(MARRIAGES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load marriages: {e}")
        return {}

def save_marriages(data):
    """Save marriages to JSON file"""
    try:
        MARRIAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MARRIAGES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save marriages: {e}")

def load_family_tree():
    """Load family tree from JSON file"""
    if not FAMILY_TREE_PATH.exists():
        return {}
    
    try:
        with open(FAMILY_TREE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load family tree: {e}")
        return {}

def save_family_tree(data):
    """Save family tree to JSON file"""
    try:
        FAMILY_TREE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(FAMILY_TREE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save family tree: {e}")

def is_married(user_id):
    """Check if user is married"""
    marriages = load_marriages()
    return str(user_id) in marriages

def get_partner(user_id):
    """Get user's partner ID"""
    marriages = load_marriages()
    user_data = marriages.get(str(user_id))
    if user_data:
        return user_data.get("partner_id")
    return None

def marry_users(user1_id, user2_id):
    """Marry two users"""
    marriages = load_marriages()
    married_at = datetime.utcnow().isoformat()
    
    marriages[str(user1_id)] = {
        "partner_id": str(user2_id),
        "married_at": married_at,
        "joint_balance": False
    }
    
    marriages[str(user2_id)] = {
        "partner_id": str(user1_id),
        "married_at": married_at,
        "joint_balance": False
    }
    
    save_marriages(marriages)

def divorce_users(user_id):
    """Divorce user and their partner"""
    marriages = load_marriages()
    user_id_str = str(user_id)
    
    if user_id_str in marriages:
        partner_id = marriages[user_id_str]["partner_id"]
        
        # Remove both marriage records
        del marriages[user_id_str]
        if partner_id in marriages:
            del marriages[partner_id]
        
        save_marriages(marriages)
        return partner_id
    
    return None

def get_marriage_data(user_id):
    """Get marriage data for user"""
    marriages = load_marriages()
    return marriages.get(str(user_id))

def toggle_joint_balance(user_id):
    """Toggle joint balance for user's marriage"""
    marriages = load_marriages()
    user_id_str = str(user_id)
    
    if user_id_str in marriages:
        partner_id = marriages[user_id_str]["partner_id"]
        current = marriages[user_id_str].get("joint_balance", False)
        new_value = not current
        
        # Update both users
        marriages[user_id_str]["joint_balance"] = new_value
        marriages[partner_id]["joint_balance"] = new_value
        
        save_marriages(marriages)
        return new_value
    
    return None

def get_couple_leaderboard(limit=10):
    """Get top couples by marriage duration"""
    marriages = load_marriages()
    couples = []
    seen = set()
    
    for user_id, data in marriages.items():
        partner_id = data["partner_id"]
        
        # Avoid duplicates
        couple_key = tuple(sorted([user_id, partner_id]))
        if couple_key in seen:
            continue
        seen.add(couple_key)
        
        married_at = datetime.fromisoformat(data["married_at"])
        duration = (datetime.utcnow() - married_at).total_seconds()
        
        couples.append({
            "user1_id": user_id,
            "user2_id": partner_id,
            "married_at": data["married_at"],
            "duration": duration,
            "joint_balance": data.get("joint_balance", False)
        })
    
    # Sort by duration
    couples.sort(key=lambda x: x["duration"], reverse=True)
    return couples[:limit]

def get_family_data(user_id):
    """Get family tree data for user"""
    tree = load_family_tree()
    user_id_str = str(user_id)
    
    if user_id_str not in tree:
        tree[user_id_str] = {
            "parent_ids": [],
            "children_ids": []
        }
        save_family_tree(tree)
    
    return tree[user_id_str]

def add_child(parent_id, child_id):
    """Add child to parent's family"""
    tree = load_family_tree()
    parent_id_str = str(parent_id)
    child_id_str = str(child_id)
    
    # Initialize if needed
    if parent_id_str not in tree:
        tree[parent_id_str] = {"parent_ids": [], "children_ids": []}
    if child_id_str not in tree:
        tree[child_id_str] = {"parent_ids": [], "children_ids": []}
    
    # Add child to parent
    if child_id_str not in tree[parent_id_str]["children_ids"]:
        tree[parent_id_str]["children_ids"].append(child_id_str)
    
    # Add parent to child
    if parent_id_str not in tree[child_id_str]["parent_ids"]:
        tree[child_id_str]["parent_ids"].append(parent_id_str)
        tree[child_id_str]["adopted_at"] = datetime.utcnow().isoformat()
    
    # If parent is married, add spouse as parent too
    partner_id = get_partner(parent_id)
    if partner_id:
        partner_id_str = str(partner_id)
        if partner_id_str not in tree:
            tree[partner_id_str] = {"parent_ids": [], "children_ids": []}
        
        if child_id_str not in tree[partner_id_str]["children_ids"]:
            tree[partner_id_str]["children_ids"].append(child_id_str)
        
        if partner_id_str not in tree[child_id_str]["parent_ids"]:
            tree[child_id_str]["parent_ids"].append(partner_id_str)
    
    save_family_tree(tree)

def can_adopt(parent_id, child_id):
    """Check if parent can adopt child"""
    tree = load_family_tree()
    child_id_str = str(child_id)
    
    # Check if child already has 2 parents
    if child_id_str in tree:
        if len(tree[child_id_str].get("parent_ids", [])) >= 2:
            return False
    
    return True

def get_full_family(user_id):
    """Get complete family tree for user"""
    tree = load_family_tree()
    user_id_str = str(user_id)
    
    family = {
        "user_id": user_id_str,
        "parents": [],
        "children": [],
        "grandparents": [],
        "spouse": None
    }
    
    # Get user data
    user_data = tree.get(user_id_str, {"parent_ids": [], "children_ids": []})
    family["parents"] = user_data.get("parent_ids", [])
    family["children"] = user_data.get("children_ids", [])
    
    # Get spouse
    family["spouse"] = get_partner(user_id)
    
    # Get grandparents
    for parent_id in family["parents"]:
        parent_data = tree.get(parent_id, {"parent_ids": []})
        family["grandparents"].extend(parent_data.get("parent_ids", []))
    
    return family

def remove_child(parent_id, child_id):
    """Remove a child from parent's family (disown)"""
    tree = load_family_tree()
    parent_id_str = str(parent_id)
    child_id_str = str(child_id)
    
    # Check if relationship exists
    if parent_id_str not in tree or child_id_str not in tree:
        return False
    
    # Remove child from parent's children list
    if child_id_str in tree[parent_id_str].get("children_ids", []):
        tree[parent_id_str]["children_ids"].remove(child_id_str)
    
    # Remove parent from child's parents list
    if parent_id_str in tree[child_id_str].get("parent_ids", []):
        tree[child_id_str]["parent_ids"].remove(parent_id_str)
    
    # Also remove from spouse if married
    partner_id = get_partner(parent_id)
    if partner_id:
        partner_id_str = str(partner_id)
        if partner_id_str in tree:
            if child_id_str in tree[partner_id_str].get("children_ids", []):
                tree[partner_id_str]["children_ids"].remove(child_id_str)
            if partner_id_str in tree[child_id_str].get("parent_ids", []):
                tree[child_id_str]["parent_ids"].remove(partner_id_str)
    
    save_family_tree(tree)
    return True

def remove_from_family(user_id):
    """Remove user from entire family tree (runaway)"""
    tree = load_family_tree()
    user_id_str = str(user_id)
    
    if user_id_str not in tree:
        return False
    
    user_data = tree[user_id_str]
    
    # Remove user from all parents' children lists
    for parent_id in user_data.get("parent_ids", []):
        if parent_id in tree:
            if user_id_str in tree[parent_id].get("children_ids", []):
                tree[parent_id]["children_ids"].remove(user_id_str)
    
    # Remove user from all children's parent lists
    for child_id in user_data.get("children_ids", []):
        if child_id in tree:
            if user_id_str in tree[child_id].get("parent_ids", []):
                tree[child_id]["parent_ids"].remove(user_id_str)
    
    # Clear user's family data
    tree[user_id_str] = {
        "parent_ids": [],
        "children_ids": []
    }
    
    save_family_tree(tree)
    return True
