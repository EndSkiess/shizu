"""
Shop system utilities - Data management for shop items and user inventories
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('DiscordBot.Shop')

# Data paths
SHOP_ITEMS_PATH = Path("data/shop_items.json")
INVENTORIES_PATH = Path("data/inventories.json")

# Default shop items
DEFAULT_SHOP_ITEMS = {
    "items": {
        # Custom Roles
        "custom_role": {
            "id": "custom_role",
            "name": "Custom Role",
            "description": "Create your own custom role with a name of your choice",
            "price": 5000,
            "category": "role",
            "type": "permanent",
            "emoji": "👑"
        },
        
        # Role Colors
        "color_red": {
            "id": "color_red",
            "name": "Red Role Color",
            "description": "Change your role color to red",
            "price": 1000,
            "category": "color",
            "type": "permanent",
            "color": 0xFF0000,
            "emoji": "🔴"
        },
        "color_blue": {
            "id": "color_blue",
            "name": "Blue Role Color",
            "description": "Change your role color to blue",
            "price": 1000,
            "category": "color",
            "type": "permanent",
            "color": 0x0000FF,
            "emoji": "🔵"
        },
        "color_green": {
            "id": "color_green",
            "name": "Green Role Color",
            "description": "Change your role color to green",
            "price": 1000,
            "category": "color",
            "type": "permanent",
            "color": 0x00FF00,
            "emoji": "🟢"
        },
        "color_purple": {
            "id": "color_purple",
            "name": "Purple Role Color",
            "description": "Change your role color to purple",
            "price": 1500,
            "category": "color",
            "type": "permanent",
            "color": 0x800080,
            "emoji": "🟣"
        },
        "color_gold": {
            "id": "color_gold",
            "name": "Gold Role Color",
            "description": "Change your role color to gold",
            "price": 2000,
            "category": "color",
            "type": "permanent",
            "color": 0xFFD700,
            "emoji": "🟡"
        },
        
        # Gambling Luck Boosters
        "four_leaf_clover": {
            "id": "four_leaf_clover",
            "name": "Four-Leaf Clover",
            "description": "+5% win chance on all gambling games",
            "price": 2500,
            "category": "luck",
            "type": "consumable",
            "uses": 10,
            "luck_boost": 0.05,
            "emoji": "🍀"
        },
        "lucky_gloves": {
            "id": "lucky_gloves",
            "name": "Lucky Gloves",
            "description": "+10% win chance on all gambling games",
            "price": 5000,
            "category": "luck",
            "type": "consumable",
            "uses": 20,
            "luck_boost": 0.10,
            "emoji": "🧤"
        },
        "extra_cards": {
            "id": "extra_cards",
            "name": "Extra Cards",
            "description": "+15% better outcomes in Blackjack",
            "price": 3500,
            "category": "luck",
            "type": "consumable",
            "uses": 15,
            "luck_boost": 0.15,
            "game_specific": "blackjack",
            "emoji": "🃏"
        },
        "golden_dice": {
            "id": "golden_dice",
            "name": "Golden Dice",
            "description": "+20% win chance on dice rolls",
            "price": 4000,
            "category": "luck",
            "type": "consumable",
            "uses": 12,
            "luck_boost": 0.20,
            "game_specific": "dice",
            "emoji": "🎲"
        },
        "rabbits_foot": {
            "id": "rabbits_foot",
            "name": "Rabbit's Foot",
            "description": "+8% win chance on all gambling games",
            "price": 6000,
            "category": "luck",
            "type": "consumable",
            "uses": 25,
            "luck_boost": 0.08,
            "emoji": "🐰"
        },
        
        # Badges
        "badge_achiever": {
            "id": "badge_achiever",
            "name": "Achiever Badge",
            "description": "Show off your achievements",
            "price": 2000,
            "category": "badge",
            "type": "collectible",
            "emoji": "🏆"
        },
        "badge_wealthy": {
            "id": "badge_wealthy",
            "name": "Wealthy Badge",
            "description": "Display your wealth",
            "price": 5000,
            "category": "badge",
            "type": "collectible",
            "emoji": "💰"
        },
        "badge_gambler": {
            "id": "badge_gambler",
            "name": "Gambler Badge",
            "description": "For the risk takers",
            "price": 3000,
            "category": "badge",
            "type": "collectible",
            "emoji": "🎰"
        }
    }
}

def load_shop_items():
    """Load shop items from JSON file"""
    if not SHOP_ITEMS_PATH.exists():
        SHOP_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        save_shop_items(DEFAULT_SHOP_ITEMS)
        return DEFAULT_SHOP_ITEMS
    
    try:
        with open(SHOP_ITEMS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load shop items: {e}")
        return DEFAULT_SHOP_ITEMS

def save_shop_items(data):
    """Save shop items to JSON file"""
    try:
        SHOP_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SHOP_ITEMS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save shop items: {e}")

def load_inventories():
    """Load user inventories from JSON file"""
    if not INVENTORIES_PATH.exists():
        return {}
    
    try:
        with open(INVENTORIES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load inventories: {e}")
        return {}

def save_inventories(data):
    """Save user inventories to JSON file"""
    try:
        INVENTORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INVENTORIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save inventories: {e}")

def get_user_inventory(user_id):
    """Get user's inventory"""
    inventories = load_inventories()
    user_id_str = str(user_id)
    
    if user_id_str not in inventories:
        inventories[user_id_str] = {
            "items": {},
            "active_perks": {},
            "badges": []
        }
        save_inventories(inventories)
    
    return inventories[user_id_str]

def set_user_inventory(user_id, inventory):
    """Set user's inventory"""
    inventories = load_inventories()
    inventories[str(user_id)] = inventory
    save_inventories(inventories)

def add_item_to_inventory(user_id, item_id, quantity=1):
    """Add item to user's inventory"""
    inventory = get_user_inventory(user_id)
    shop_data = load_shop_items()
    item = shop_data["items"].get(item_id)
    
    if not item:
        return False
    
    if item_id not in inventory["items"]:
        inventory["items"][item_id] = {
            "quantity": 0,
            "purchased_at": datetime.utcnow().isoformat()
        }
        
        # Add uses for consumable items
        if item.get("uses"):
            inventory["items"][item_id]["uses_remaining"] = item["uses"]
    
    inventory["items"][item_id]["quantity"] += quantity
    set_user_inventory(user_id, inventory)
    return True

def remove_item_from_inventory(user_id, item_id, quantity=1):
    """Remove item from user's inventory"""
    inventory = get_user_inventory(user_id)
    
    if item_id not in inventory["items"]:
        return False
    
    inventory["items"][item_id]["quantity"] -= quantity
    
    if inventory["items"][item_id]["quantity"] <= 0:
        del inventory["items"][item_id]
    
    set_user_inventory(user_id, inventory)
    return True

def has_item(user_id, item_id):
    """Check if user has an item"""
    inventory = get_user_inventory(user_id)
    return item_id in inventory["items"] and inventory["items"][item_id]["quantity"] > 0


def get_active_luck_boost(user_id, game=None):
    """Get active luck boost percentage"""
    inventory = get_user_inventory(user_id)
    
    if "luck_boost" in inventory["active_perks"]:
        perk = inventory["active_perks"]["luck_boost"]
        
        # Check if uses remaining
        if perk.get("uses_remaining", 0) > 0:
            # Check if game-specific
            shop_data = load_shop_items()
            item = shop_data["items"].get(perk["item_id"])
            
            if item and item.get("game_specific"):
                if game and game.lower() == item["game_specific"].lower():
                    return perk["boost"]
                return 0.0
            
            return perk["boost"]
        else:
            # No uses left, remove it
            del inventory["active_perks"]["luck_boost"]
            set_user_inventory(user_id, inventory)
    
    return 0.0

def use_luck_boost(user_id):
    """Use one charge of active luck boost"""
    inventory = get_user_inventory(user_id)
    
    if "luck_boost" in inventory["active_perks"]:
        inventory["active_perks"]["luck_boost"]["uses_remaining"] -= 1
        
        if inventory["active_perks"]["luck_boost"]["uses_remaining"] <= 0:
            del inventory["active_perks"]["luck_boost"]
        
        set_user_inventory(user_id, inventory)
        return True
    
    return False

def activate_luck_boost(user_id, item_id):
    """Activate luck boost item"""
    shop_data = load_shop_items()
    item = shop_data["items"].get(item_id)
    
    if not item or item["category"] != "luck":
        return False
    
    inventory = get_user_inventory(user_id)
    
    inventory["active_perks"]["luck_boost"] = {
        "boost": item["luck_boost"],
        "uses_remaining": item["uses"],
        "item_id": item_id
    }
    
    set_user_inventory(user_id, inventory)
    return True

def add_badge(user_id, badge_id):
    """Add badge to user's collection"""
    inventory = get_user_inventory(user_id)
    
    if badge_id not in inventory["badges"]:
        inventory["badges"].append(badge_id)
        set_user_inventory(user_id, inventory)
        return True
    
    return False

def get_items_by_category(category=None):
    """Get shop items filtered by category"""
    shop_data = load_shop_items()
    items = shop_data["items"]
    
    if category:
        return {k: v for k, v in items.items() if v.get("category") == category}
    
    return items
