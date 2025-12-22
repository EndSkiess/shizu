"""
Pet system utilities - Data management for virtual pets with spawn mechanics
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger('DiscordBot.Pets')

# Constants
MAX_PETS = 5

# Data paths - Use absolute paths based on bot root directory
# Get the bot root directory (3 levels up from this file: cogs/fun/pets_utils.py -> bot root)
BOT_ROOT = Path(__file__).parent.parent.parent
PETS_PATH = BOT_ROOT / "data" / "pets.json"
SPAWNS_PATH = BOT_ROOT / "data" / "pet_spawns.json"
USER_SPAWNS_PATH = BOT_ROOT / "data" / "user_spawns.json"

# Pet definitions with rarity and spawn chances
PET_TYPES = {
    # Common (60%)
    "dog": {"emoji": "<a:69969jump:1445525121942032465>", "name": "Dog", "rarity": "common", "spawn_weight": 20},
    "cat": {"emoji": "<a:774805kittydance:1445525133048418499>", "name": "Cat", "rarity": "common", "spawn_weight": 20},
    "rabbit": {"emoji": "<a:147931yellowbunny:1445525130607460564>", "name": "Rabbit", "rarity": "common", "spawn_weight": 20},
    
    # Uncommon (25%)
    "fox": {"emoji": "<:39119foxydealz:1445525112542724216>", "name": "Fox", "rarity": "uncommon", "spawn_weight": 8},
    "panda": {"emoji": "<:17506pandas:1445525108142899350>", "name": "Panda", "rarity": "uncommon", "spawn_weight": 8},
    "raccoon": {"emoji": "<:60997raccoon:1445525119593091202>", "name": "Raccoon", "rarity": "uncommon", "spawn_weight": 9},
    
    # Rare (10%)
    "lion": {"emoji": "<a:6201lionrun:1445525105374527488>", "name": "Lion", "rarity": "rare", "spawn_weight": 3},
    "wolf": {"emoji": "<:55469wolf:1445525117403795639>", "name": "Wolf", "rarity": "rare", "spawn_weight": 4},
    "eagle": {"emoji": "<:4396cursedeaglestare:1445525098667704532>", "name": "Eagle", "rarity": "rare", "spawn_weight": 3},
    "penguin": {"emoji": "<a:pengutablesmash:1445524691019235518>", "name": "Penguin", "rarity": "rare", "spawn_weight": 3},
    "cyclops": {"emoji": "<:cyclops:1445524684920721528>", "name": "Cyclops", "rarity": "rare", "spawn_weight": 3},
    
    # Epic (3%)
    "dragon": {"emoji": "<:978412nikkiloong:1445530080922173481>", "name": "Dragon", "rarity": "epic", "spawn_weight": 1},
    "unicorn": {"emoji": "<:851525fireunicorn:1445525135682703431>", "name": "Unicorn", "rarity": "epic", "spawn_weight": 1},
    "shark": {"emoji": "<a:74473jeffult:1445525128711635206>", "name": "Shark", "rarity": "epic", "spawn_weight": 1},
    
    # Legendary (1.5%)
    "ancient_dragon": {"emoji": "<:51058blueflamedragon:1445525115029688484>", "name": "Ancient Dragon", "rarity": "legendary", "spawn_weight": 0.75},
    "trex": {"emoji": "<a:1092trexparty:1445525096813957130>", "name": "T-Rex", "rarity": "legendary", "spawn_weight": 0.75},
    "griffin": {"emoji": "<:bloody:1445524682513191065>", "name": "Griffin", "rarity": "legendary", "spawn_weight": 0.75},
    
    # Mythical (0.5%)
    "phoenix": {"emoji": "<a:4726phoenix:1445525103323644005>", "name": "Phoenix", "rarity": "mythical", "spawn_weight": 0.5},
    "cerberus": {"emoji": "<:3headdog:1445528975022620722>", "name": "Cerberus", "rarity": "mythical", "spawn_weight": 0.5},
    "hydra": {"emoji": "<:image:1445524687781363963>", "name": "Hydra", "rarity": "mythical", "spawn_weight": 0.5}
}

# Rarity colors and bonuses
RARITY_INFO = {
    "common": {"color": 0x808080, "xp_bonus": 1.0, "stat_bonus": 1.0},
    "uncommon": {"color": 0x00FF00, "xp_bonus": 1.2, "stat_bonus": 1.1},
    "rare": {"color": 0x0099FF, "xp_bonus": 1.5, "stat_bonus": 1.3},
    "epic": {"color": 0x9B59B6, "xp_bonus": 2.0, "stat_bonus": 1.5},
    "legendary": {"color": 0xFFD700, "xp_bonus": 3.0, "stat_bonus": 2.0},
    "mythical": {"color": 0xFF0000, "xp_bonus": 5.0, "stat_bonus": 3.0}
}

# Rarity-based passive abilities
RARITY_ABILITIES = {
    "mythical": {"name": "Cosmic Power", "desc": "3x XP from all sources", "xp_mult": 3.0},
    "legendary": {"name": "Ancient Wisdom", "desc": "2x XP from battles", "battle_xp_mult": 2.0},
    "epic": {"name": "Rapid Recovery", "desc": "Energy regenerates 50% faster", "energy_regen_mult": 1.5},
    "rare": {"name": "Efficient Metabolism", "desc": "Hunger decreases 25% slower", "hunger_decay_mult": 0.75},
    "uncommon": {"name": "Quick Learner", "desc": "+20% XP from training", "train_xp_mult": 1.2},
    "common": {"name": "Loyal Companion", "desc": "+10% happiness from playing", "play_bonus": 1.1}
}

# Type advantages for battles
TYPE_ADVANTAGES = {
    "dragon": ["lion", "wolf", "eagle", "trex", "cyclops"],
    "ancient_dragon": ["dragon", "lion", "wolf", "eagle", "trex", "griffin"],
    "phoenix": ["dragon", "ancient_dragon", "eagle", "hydra"],
    "trex": ["lion", "wolf", "dog", "cat", "penguin"],
    "lion": ["fox", "rabbit", "raccoon", "dog", "cat"],
    "wolf": ["rabbit", "fox", "raccoon", "penguin"],
    "eagle": ["rabbit", "raccoon", "fox", "penguin"],
    "shark": ["dog", "cat", "rabbit", "penguin"],
    "unicorn": ["wolf", "lion", "cyclops"],
    "fox": ["rabbit"],
    "panda": ["rabbit"],
    "raccoon": [],
    "penguin": ["fish"], # Joke entry, or maybe against shark?
    "cyclops": ["lion", "wolf"],
    "griffin": ["lion", "wolf", "eagle"],
    "cerberus": ["ghost", "skeleton", "human"], # Placeholder types
    "hydra": ["dragon", "ancient_dragon"]
}

# Pet achievements
ACHIEVEMENTS = {
    "first_catch": {"name": "First Companion", "desc": "Caught for the first time", "emoji": "🎉"},
    "level_10": {"name": "Novice Trainer", "desc": "Reached level 10", "emoji": "📈"},
    "level_25": {"name": "Expert Trainer", "desc": "Reached level 25", "emoji": "⭐"},
    "level_50": {"name": "Master Trainer", "desc": "Reached level 50", "emoji": "🏆"},
    "level_100": {"name": "Legendary Trainer", "desc": "Reached level 100", "emoji": "👑"},
    "battle_won": {"name": "First Victory", "desc": "Won first battle", "emoji": "⚔️"},
    "battle_streak_5": {"name": "Winning Streak", "desc": "Won 5 battles in a row", "emoji": "🔥"},
    "battle_streak_10": {"name": "Unstoppable", "desc": "Won 10 battles in a row", "emoji": "💥"},
    "fully_fed": {"name": "Well Fed", "desc": "Fed 50 times", "emoji": "🍖"},
    "well_trained": {"name": "Disciplined", "desc": "Trained 50 times", "emoji": "💪"},
    "evolved_once": {"name": "Evolution", "desc": "Evolved to ⭐", "emoji": "✨"},
    "max_evolution": {"name": "Ultimate Form", "desc": "Reached ⭐⭐⭐", "emoji": "🌟"}
}

# Evolution thresholds
EVOLUTION_LEVELS = {
    1: 25,   # First evolution at level 25
    2: 50,   # Second evolution at level 50
    3: 100   # Third evolution at level 100
}

# Mood definitions
MOODS = {
    "happy": {"threshold": 70, "emoji": "😊", "battle_mult": 1.15, "desc": "Happy"},
    "content": {"threshold": 40, "emoji": "😐", "battle_mult": 1.0, "desc": "Content"},
    "sad": {"threshold": 20, "emoji": "😢", "battle_mult": 0.9, "desc": "Sad"},
    "neglected": {"threshold": 0, "emoji": "😭", "battle_mult": 0.75, "desc": "Neglected"}
}

# Shiny variants (rare spawns)
SHINY_CHANCE = 0.01  # 1% chance
SHINY_STAT_BONUS = 1.2  # 20% bonus to all stats
SHINY_EMOJI_PREFIX = "✨"


def load_pets():
    """Load user pets from JSON file"""
    if not PETS_PATH.exists():
        return {}
    
    try:
        with open(PETS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Pet type migration map (old_key -> new_key)
            PET_TYPE_MIGRATIONS = {
                "t-rex": "trex",
                # Add more migrations here if needed in the future
            }
            
            # Migrate old single-pet format to multi-pet format
            migrated = False
            for user_id, pet_data in list(data.items()):
                # Check if old format (dict with 'type' key directly)
                if isinstance(pet_data, dict) and 'type' in pet_data:
                    # Convert to list format
                    data[user_id] = [pet_data]
                    migrated = True
                    logger.info(f"Migrated pet data for user {user_id} to multi-pet format")
                
                # Ensure pet_data is a list
                if isinstance(data[user_id], list):
                    # Migrate old pet type keys to new ones
                    for pet in data[user_id]:
                        if pet.get("type") in PET_TYPE_MIGRATIONS:
                            old_type = pet["type"]
                            new_type = PET_TYPE_MIGRATIONS[old_type]
                            pet["type"] = new_type
                            migrated = True
                            logger.info(f"Migrated pet type '{old_type}' -> '{new_type}' for user {user_id}")
            
            # Save migrated data
            if migrated:
                save_pets(data)
            
            return data
    except Exception as e:
        logger.error(f"Failed to load pets: {e}")
        return {}

def save_pets(data):
    """Save user pets to JSON file"""
    try:
        PETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PETS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save pets: {e}")

def load_spawns():
    """Load spawn data from JSON file"""
    if not SPAWNS_PATH.exists():
        return {}
    
    try:
        with open(SPAWNS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load spawns: {e}")
        return {}

def save_spawns(data):
    """Save spawn data to JSON file"""
    try:
        SPAWNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SPAWNS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save spawns: {e}")

def load_user_spawns():
    """Load user spawn history from JSON file"""
    if not USER_SPAWNS_PATH.exists():
        return {}
    
    try:
        with open(USER_SPAWNS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load user spawns: {e}")
        return {}

def save_user_spawns(data):
    """Save user spawn history to JSON file"""
    try:
        USER_SPAWNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_SPAWNS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save user spawns: {e}")

def can_user_spawn(user_id):
    """Check if user can spawn a pet (3 times per 4 hours)"""
    user_spawns = load_user_spawns()
    user_str = str(user_id)
    
    if user_str not in user_spawns:
        return True, None
    
    timestamps = user_spawns[user_str]
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=4)
    
    # Filter valid timestamps
    valid_timestamps = [ts for ts in timestamps if datetime.fromisoformat(ts) > cutoff]
    
    if len(valid_timestamps) < 3:
        return True, None
    
    # Calculate time until oldest spawn expires
    oldest = min([datetime.fromisoformat(ts) for ts in valid_timestamps])
    reset_time = oldest + timedelta(hours=4)
    remaining = (reset_time - now).total_seconds()
    
    return False, remaining

def record_user_spawn(user_id):
    """Record a user spawn"""
    user_spawns = load_user_spawns()
    user_str = str(user_id)
    
    if user_str not in user_spawns:
        user_spawns[user_str] = []
    
    now = datetime.utcnow()
    timestamps = user_spawns[user_str]
    
    # Add new timestamp
    timestamps.append(now.isoformat())
    
    # Clean up old timestamps
    cutoff = now - timedelta(hours=4)
    user_spawns[user_str] = [ts for ts in timestamps if datetime.fromisoformat(ts) > cutoff]
    
    save_user_spawns(user_spawns)

def get_random_pet():
    """Get a random pet based on spawn weights"""
    pets = list(PET_TYPES.keys())
    weights = [PET_TYPES[p]["spawn_weight"] for p in pets]
    return random.choices(pets, weights=weights)[0]

def check_evolution(pet):
    """Check and apply evolution if pet reached threshold"""
    if "evolution_level" not in pet:
        pet["evolution_level"] = 0
    
    level = pet.get("level", 1)
    current_evo = pet.get("evolution_level", 0)
    
    # Check each evolution threshold
    new_evo = current_evo
    for evo_level, required_level in EVOLUTION_LEVELS.items():
        if level >= required_level and current_evo < evo_level:
            new_evo = evo_level
    
    # Apply evolution if changed
    if new_evo > current_evo:
        pet["evolution_level"] = new_evo
        # Check for evolution achievements
        check_and_award_achievements(pet)
        return True
    
    return False


async def send_low_energy_warning(bot, user_id, pet):
    """Send DM warning to user about low pet energy"""
    try:
        user = await bot.fetch_user(int(user_id))
        pet_info = PET_TYPES.get(pet["type"])
        
        if not pet_info:
            return
        
        pet_name = pet.get("nickname") or pet_info["name"]
        
        import discord
        embed = discord.Embed(
            title="⚠️ Pet Warning: Critical Energy Level!",
            description=f"Your pet **{pet_name}** is in critical condition!",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name=f"{pet_info['emoji']} {pet_name}",
            value=f"⚡ **Energy: {pet['energy']}/100** 🔴\n"
                  f"💚 Hunger: {pet['hunger']}/100\n"
                  f"😊 Happiness: {pet['happiness']}/100",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ URGENT ACTION REQUIRED",
            value="Your pet's energy is critically low! If you don't take action soon, **you risk losing your pet permanently!**\n\n"
                  "**What to do:**\n"
                  "• Use `/feed` to restore hunger\n"
                  "• Use `/playpet` to increase happiness\n"
                  "• Let your pet rest to regenerate energy\n"
                  "• Avoid battles until energy recovers",
            inline=False
        )
        
        embed.set_footer(text="Energy regenerates at 15 per hour. Take care of your pet!")
        
        await user.send(embed=embed)
        logger.info(f"Sent low energy warning to user {user_id} for pet {pet_name}")
    except Exception as e:
        logger.error(f"Failed to send DM warning to user {user_id}: {e}")


def get_user_pets(user_id, bot=None):
    """Get all user's pets with updated stats"""
    pets = load_pets()
    user_pets = pets.get(str(user_id), [])
    # Ensure it's a list (for migration safety)
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
    
    # Update stats for all pets
    for pet in user_pets:
        update_pet_stats(pet, user_id, bot)
    
    # Save updated stats
    if user_pets:
        pets[str(user_id)] = user_pets
        save_pets(pets)
    
    return user_pets

def get_user_pet_by_name(user_id, pet_name):
    """Get specific pet by name (case-insensitive)"""
    user_pets = get_user_pets(user_id)
    pet_name_lower = pet_name.lower()
    
    for pet in user_pets:
        pet_info = PET_TYPES.get(pet["type"])
        # Check both pet type name and nickname
        if pet_info and pet_info["name"].lower() == pet_name_lower:
            return pet
        # Also check nickname if it exists
        if pet.get("nickname") and pet["nickname"].lower() == pet_name_lower:
            return pet
    
    return None

def update_pet_stats(pet, user_id=None, bot=None):
    """Update pet stats based on time elapsed (stat decay/regeneration)"""
    if "last_updated" not in pet:
        pet["last_updated"] = datetime.utcnow().isoformat()
        return pet
    
    last_updated = datetime.fromisoformat(pet["last_updated"])
    now = datetime.utcnow()
    hours_elapsed = (now - last_updated).total_seconds() / 3600
    
    if hours_elapsed < 0.1:  # Less than 6 minutes, skip update
        return pet
    
    # Get rarity ability modifiers
    rarity = pet.get("rarity", "common")
    ability = RARITY_ABILITIES.get(rarity, {})
    
    # Hunger decay (10 per 6 hours, affected by rarity ability)
    hunger_decay_rate = 10 / 6  # per hour
    hunger_mult = ability.get("hunger_decay_mult", 1.0)
    hunger_loss = int(hours_elapsed * hunger_decay_rate * hunger_mult)
    pet["hunger"] = max(0, pet["hunger"] - hunger_loss)
    
    # Happiness decay (10 per 6 hours)
    happiness_decay_rate = 10 / 6  # per hour
    happiness_loss = int(hours_elapsed * happiness_decay_rate)
    pet["happiness"] = max(0, pet["happiness"] - happiness_loss)
    
    # Energy regeneration (15 per hour, affected by rarity ability)
    energy_regen_rate = 15  # per hour
    energy_mult = ability.get("energy_regen_mult", 1.0)
    energy_gain = int(hours_elapsed * energy_regen_rate * energy_mult)
    pet["energy"] = min(100, pet["energy"] + energy_gain)
    
    # Update timestamp
    pet["last_updated"] = now.isoformat()
    
    # Check for low energy and send DM warning
    if user_id and bot and pet["energy"] < 10:
        # Check if we've already warned about this pet recently
        if "last_warning" not in pet or not pet["last_warning"]:
            should_warn = True
        else:
            last_warning = datetime.fromisoformat(pet["last_warning"])
            # Only warn once per 24 hours
            should_warn = (now - last_warning).total_seconds() > 86400
        
        if should_warn:
            # Send DM warning asynchronously
            import asyncio
            try:
                # Create task to send DM
                asyncio.create_task(send_low_energy_warning(bot, user_id, pet))
                pet["last_warning"] = now.isoformat()
            except Exception as e:
                logger.error(f"Failed to create DM warning task: {e}")
    
    return pet

def get_pet_mood(pet):
    """Calculate pet mood based on stats"""
    avg_stat = (pet["hunger"] + pet["happiness"] + pet["energy"]) / 3
    
    if avg_stat >= MOODS["happy"]["threshold"]:
        return "happy"
    elif avg_stat >= MOODS["content"]["threshold"]:
        return "content"
    elif avg_stat >= MOODS["sad"]["threshold"]:
        return "sad"
    else:
        return "neglected"

def get_pet_display_name(pet):
    """Get display name for pet (nickname or type name)"""
    pet_info = PET_TYPES.get(pet["type"])
    if not pet_info:
        return "Unknown"
    
    nickname = pet.get("nickname")
    if nickname:
        return f"{nickname} ({pet_info['name']})"
    
    # Add shiny prefix if shiny
    if pet.get("is_shiny", False):
        return f"{SHINY_EMOJI_PREFIX} {pet_info['name']}"
    
    return pet_info["name"]

def get_evolution_stars(evolution_level):
    """Get evolution star display"""
    if evolution_level <= 0:
        return ""
    return "⭐" * evolution_level

def check_and_award_achievements(pet, action=None):
    """Check and award achievements based on pet stats and actions"""
    if "achievements" not in pet:
        pet["achievements"] = []
    
    new_achievements = []
    
    # Level-based achievements
    level = pet.get("level", 1)
    if level >= 10 and "level_10" not in pet["achievements"]:
        pet["achievements"].append("level_10")
        new_achievements.append("level_10")
    if level >= 25 and "level_25" not in pet["achievements"]:
        pet["achievements"].append("level_25")
        new_achievements.append("level_25")
    if level >= 50 and "level_50" not in pet["achievements"]:
        pet["achievements"].append("level_50")
        new_achievements.append("level_50")
    if level >= 100 and "level_100" not in pet["achievements"]:
        pet["achievements"].append("level_100")
        new_achievements.append("level_100")
    
    # Evolution achievements
    evo_level = pet.get("evolution_level", 0)
    if evo_level >= 1 and "evolved_once" not in pet["achievements"]:
        pet["achievements"].append("evolved_once")
        new_achievements.append("evolved_once")
    if evo_level >= 3 and "max_evolution" not in pet["achievements"]:
        pet["achievements"].append("max_evolution")
        new_achievements.append("max_evolution")
    
    # Action-based achievements
    if action == "battle_won" and "battle_won" not in pet["achievements"]:
        pet["achievements"].append("battle_won")
        new_achievements.append("battle_won")
    
    # Streak achievements
    streak = pet.get("battle_streak", 0)
    if streak >= 5 and "battle_streak_5" not in pet["achievements"]:
        pet["achievements"].append("battle_streak_5")
        new_achievements.append("battle_streak_5")
    if streak >= 10 and "battle_streak_10" not in pet["achievements"]:
        pet["achievements"].append("battle_streak_10")
        new_achievements.append("battle_streak_10")
    
    # Counter-based achievements
    times_fed = pet.get("times_fed", 0)
    if times_fed >= 50 and "fully_fed" not in pet["achievements"]:
        pet["achievements"].append("fully_fed")
        new_achievements.append("fully_fed")
    
    times_trained = pet.get("times_trained", 0)
    if times_trained >= 50 and "well_trained" not in pet["achievements"]:
        pet["achievements"].append("well_trained")
        new_achievements.append("well_trained")
    
    return new_achievements

def create_pet(user_id, pet_type, is_shiny=False, nickname=None):
    """Create a new pet for user or level up if duplicate"""
    pets = load_pets()
    user_id_str = str(user_id)
    pet_info = PET_TYPES[pet_type]
    
    # Initialize user's pet list if doesn't exist
    if user_id_str not in pets:
        pets[user_id_str] = []
    
    # Ensure it's a list (for migration safety)
    if isinstance(pets[user_id_str], dict):
        pets[user_id_str] = [pets[user_id_str]]
    
    user_pets = pets[user_id_str]
    
    # Check if user already has this pet type
    existing_pet = None
    for pet in user_pets:
        if pet["type"] == pet_type:
            existing_pet = pet
            break
    
    # If user has this pet type, level it up
    if existing_pet:
        # Add XP for catching duplicate (200 base XP)
        base_xp = 200
        rarity_bonus = RARITY_INFO[pet_info["rarity"]]["xp_bonus"]
        xp_gain = int(base_xp * rarity_bonus)
        
        old_level = existing_pet["level"]
        existing_pet["xp"] += xp_gain
        
        # Check for level up
        while existing_pet["xp"] >= xp_for_next_level(existing_pet["level"]):
            existing_pet["xp"] -= xp_for_next_level(existing_pet["level"])
            existing_pet["level"] += 1
        
        save_pets(pets)
        
        return {
            "status": "leveled_up",
            "pet": existing_pet,
            "old_level": old_level,
            "xp_gained": xp_gain
        }
    
    # Check if user has reached max pets
    if len(user_pets) >= MAX_PETS:
        return {
            "status": "max_reached",
            "max_pets": MAX_PETS,
            "current_pets": user_pets
        }
    
    # Create new pet
    new_pet = {
        "type": pet_type,
        "rarity": pet_info["rarity"],
        "level": 1,
        "xp": 0,
        "total_xp": 0,  # Track lifetime XP
        "hunger": 100,
        "happiness": 100,
        "energy": 100,
        "last_fed": None,
        "last_played": None,
        "last_trained": None,
        "last_battled": None,
        "last_updated": datetime.utcnow().isoformat(),
        "caught_at": datetime.utcnow().isoformat(),
        # New fields for enhancements
        "nickname": nickname,
        "is_shiny": is_shiny,
        "evolution_level": 0,
        "achievements": ["first_catch"],  # First achievement!
        "battle_wins": 0,
        "battle_losses": 0,
        "battle_streak": 0,
        "times_fed": 0,
        "times_trained": 0
    }
    
    # Apply shiny stat bonus if shiny
    if is_shiny:
        new_pet["hunger"] = int(100 * SHINY_STAT_BONUS)
        new_pet["happiness"] = int(100 * SHINY_STAT_BONUS)
        new_pet["energy"] = int(100 * SHINY_STAT_BONUS)
    
    user_pets.append(new_pet)
    save_pets(pets)
    
    return {
        "status": "new",
        "pet": new_pet
    }




def remove_pet(user_id, pet_name):
    """Remove a pet by name"""
    pets = load_pets()
    user_id_str = str(user_id)
    
    if user_id_str not in pets:
        return {"status": "no_pets"}
    
    user_pets = pets[user_id_str]
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
        pets[user_id_str] = user_pets
    
    # Find and remove the pet
    pet_name_lower = pet_name.lower()
    removed_pet = None
    
    for i, pet in enumerate(user_pets):
        pet_info = PET_TYPES.get(pet["type"])
        # Check both pet type name and nickname
        if pet_info and pet_info["name"].lower() == pet_name_lower:
            removed_pet = user_pets.pop(i)
            break
        # Also check nickname if it exists
        if pet.get("nickname") and pet["nickname"].lower() == pet_name_lower:
            removed_pet = user_pets.pop(i)
            break
    
    if not removed_pet:
        return {"status": "not_found", "pet_name": pet_name}
    
    save_pets(pets)
    
    return {
        "status": "removed",
        "pet": removed_pet
    }


def can_feed(user_id, pet_name=None):
    """Check if user can feed their pet"""
    if pet_name:
        pet = get_user_pet_by_name(user_id, pet_name)
    else:
        user_pets = get_user_pets(user_id)
        pet = user_pets[0] if user_pets else None
    
    if not pet or not pet.get("last_fed"):
        return True
    
    last_fed = datetime.fromisoformat(pet["last_fed"])
    return datetime.utcnow() - last_fed >= timedelta(hours=1)

def feed_pet(user_id, pet_name=None):
    """Feed user's pet"""
    pets = load_pets()
    user_id_str = str(user_id)
    
    if user_id_str not in pets:
        return None
    
    user_pets = pets[user_id_str]
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
        pets[user_id_str] = user_pets
    
    # Find the pet
    target_pet = None
    if pet_name:
        pet_name_lower = pet_name.lower()
        for pet in user_pets:
            pet_info = PET_TYPES.get(pet["type"])
            # Check both pet type name and nickname
            if pet_info and pet_info["name"].lower() == pet_name_lower:
                target_pet = pet
                break
            # Also check nickname if it exists
            if pet.get("nickname") and pet["nickname"].lower() == pet_name_lower:
                target_pet = pet
                break
    else:
        target_pet = user_pets[0] if user_pets else None
    
    if not target_pet:
        return None
    
    target_pet["hunger"] = min(100, target_pet["hunger"] + 30)
    target_pet["last_fed"] = datetime.utcnow().isoformat()
    
    # Increment counter
    if "times_fed" not in target_pet:
        target_pet["times_fed"] = 0
    target_pet["times_fed"] += 1
    
    # Check achievements
    check_and_award_achievements(target_pet)
    save_pets(pets)
    return target_pet["hunger"]

def can_play(user_id, pet_name=None):
    """Check if user can play with their pet"""
    if pet_name:
        pet = get_user_pet_by_name(user_id, pet_name)
    else:
        user_pets = get_user_pets(user_id)
        pet = user_pets[0] if user_pets else None
    
    if not pet or not pet.get("last_played"):
        return True
    
    last_played = datetime.fromisoformat(pet["last_played"])
    return datetime.utcnow() - last_played >= timedelta(hours=1)

def play_with_pet(user_id, pet_name=None):
    """Play with user's pet"""
    pets = load_pets()
    user_id_str = str(user_id)
    
    if user_id_str not in pets:
        return None
    
    user_pets = pets[user_id_str]
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
        pets[user_id_str] = user_pets
    
    # Find the pet
    target_pet = None
    if pet_name:
        pet_name_lower = pet_name.lower()
        for pet in user_pets:
            pet_info = PET_TYPES.get(pet["type"])
            # Check both pet type name and nickname
            if pet_info and pet_info["name"].lower() == pet_name_lower:
                target_pet = pet
                break
            # Also check nickname if it exists
            if pet.get("nickname") and pet["nickname"].lower() == pet_name_lower:
                target_pet = pet
                break
    else:
        target_pet = user_pets[0] if user_pets else None
    
    if not target_pet:
        return None
    
    # Apply rarity ability bonus
    rarity = target_pet.get("rarity", "common")
    ability = RARITY_ABILITIES.get(rarity, {})
    play_mult = ability.get("play_bonus", 1.0)
    
    happiness_gain = int(30 * play_mult)
    target_pet["happiness"] = min(100, target_pet["happiness"] + happiness_gain)
    target_pet["last_played"] = datetime.utcnow().isoformat()
    save_pets(pets)
    return target_pet["happiness"]

def can_train(user_id, pet_name=None):
    """Check if user can train their pet"""
    if pet_name:
        pet = get_user_pet_by_name(user_id, pet_name)
    else:
        user_pets = get_user_pets(user_id)
        pet = user_pets[0] if user_pets else None
    
    if not pet:
        return False
    
    if pet["energy"] < 20:
        return False
    
    if not pet.get("last_trained"):
        return True
    
    last_trained = datetime.fromisoformat(pet["last_trained"])
    return datetime.utcnow() - last_trained >= timedelta(hours=2)

def train_pet(user_id, pet_name=None):
    """Train user's pet"""
    pets = load_pets()
    user_id_str = str(user_id)
    
    if user_id_str not in pets:
        return None
    
    user_pets = pets[user_id_str]
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
        pets[user_id_str] = user_pets
    
    # Find the pet
    target_pet = None
    if pet_name:
        pet_name_lower = pet_name.lower()
        for pet in user_pets:
            pet_info = PET_TYPES.get(pet["type"])
            # Check both pet type name and nickname
            if pet_info and pet_info["name"].lower() == pet_name_lower:
                target_pet = pet
                break
            # Also check nickname if it exists
            if pet.get("nickname") and pet["nickname"].lower() == pet_name_lower:
                target_pet = pet
                break
    else:
        target_pet = user_pets[0] if user_pets else None
    
    if not target_pet:
        return None
    
    # Deduct energy
    target_pet["energy"] -= 20
    
    # Calculate XP gain with rarity bonus and ability bonus
    base_xp = random.randint(50, 100)
    rarity_bonus = RARITY_INFO[target_pet["rarity"]]["xp_bonus"]
    
    # Apply rarity ability bonus
    rarity = target_pet.get("rarity", "common")
    ability = RARITY_ABILITIES.get(rarity, {})
    train_mult = ability.get("train_xp_mult", 1.0)
    mythical_mult = ability.get("xp_mult", 1.0)
    
    xp_gain = int(base_xp * rarity_bonus * train_mult * mythical_mult)
    
    target_pet["xp"] += xp_gain
    if "total_xp" not in target_pet:
        target_pet["total_xp"] = 0
    target_pet["total_xp"] += xp_gain
    target_pet["last_trained"] = datetime.utcnow().isoformat()
    
    # Increment counter
    if "times_trained" not in target_pet:
        target_pet["times_trained"] = 0
    target_pet["times_trained"] += 1
    
    # Check for level up
    old_level = target_pet["level"]
    while target_pet["xp"] >= xp_for_next_level(target_pet["level"]):
        target_pet["xp"] -= xp_for_next_level(target_pet["level"])
        target_pet["level"] += 1
    
    # Check for evolution
    check_evolution(target_pet)
    
    # Check achievements
    check_and_award_achievements(target_pet)
    
    save_pets(pets)
    return (xp_gain, target_pet["level"], old_level)

def xp_for_next_level(level):
    """Calculate XP needed for next level"""
    return 100 * level

def can_battle(user_id, pet_name=None):
    """Check if user can battle"""
    if pet_name:
        pet = get_user_pet_by_name(user_id, pet_name)
    else:
        user_pets = get_user_pets(user_id)
        pet = user_pets[0] if user_pets else None
    
    if not pet or not pet.get("last_battled"):
        return True
    
    last_battled = datetime.fromisoformat(pet["last_battled"])
    return datetime.utcnow() - last_battled >= timedelta(hours=3)

def battle_pets(user1_id, user2_id, pet1_name=None, pet2_name=None):
    """Battle two pets with type advantages, mood, and critical hits"""
    pets = load_pets()
    user1_str = str(user1_id)
    user2_str = str(user2_id)
    
    if user1_str not in pets or user2_str not in pets:
        return None
    
    # Get user pets
    user1_pets = pets[user1_str]
    user2_pets = pets[user2_str]
    
    if isinstance(user1_pets, dict):
        user1_pets = [user1_pets]
        pets[user1_str] = user1_pets
    if isinstance(user2_pets, dict):
        user2_pets = [user2_pets]
        pets[user2_str] = user2_pets
    
    # Find the pets to battle
    pet1 = None
    if pet1_name:
        pet1_name_lower = pet1_name.lower()
        for pet in user1_pets:
            pet_info = PET_TYPES.get(pet["type"])
            # Check both pet type name and nickname
            if pet_info and pet_info["name"].lower() == pet1_name_lower:
                pet1 = pet
                break
            # Also check nickname if it exists
            if pet.get("nickname") and pet["nickname"].lower() == pet1_name_lower:
                pet1 = pet
                break
    else:
        pet1 = user1_pets[0] if user1_pets else None
    
    pet2 = None
    if pet2_name:
        pet2_name_lower = pet2_name.lower()
        for pet in user2_pets:
            pet_info = PET_TYPES.get(pet["type"])
            # Check both pet type name and nickname
            if pet_info and pet_info["name"].lower() == pet2_name_lower:
                pet2 = pet
                break
            # Also check nickname if it exists
            if pet.get("nickname") and pet["nickname"].lower() == pet2_name_lower:
                pet2 = pet
                break
    else:
        pet2 = user2_pets[0] if user2_pets else None
    
    if not pet1 or not pet2:
        return None
    
    # Calculate battle power with all bonuses
    def get_power(pet):
        base_power = pet["level"] * 10
        stat_bonus = RARITY_INFO[pet["rarity"]]["stat_bonus"]
        energy_mult = pet["energy"] / 100
        
        # Apply evolution bonus
        evo_level = pet.get("evolution_level", 0)
        evo_bonus = 1.0 + (evo_level * 0.2)  # +20% per evolution
        
        # Apply mood multiplier
        mood = get_pet_mood(pet)
        mood_mult = MOODS[mood]["battle_mult"]
        
        # Apply shiny bonus
        shiny_mult = SHINY_STAT_BONUS if pet.get("is_shiny", False) else 1.0
        
        return int(base_power * stat_bonus * energy_mult * evo_bonus * mood_mult * shiny_mult)
    
    power1 = get_power(pet1) + random.randint(-10, 10)
    power2 = get_power(pet2) + random.randint(-10, 10)
    
    # Check for type advantage
    type_advantage_1 = False
    type_advantage_2 = False
    if pet2["type"] in TYPE_ADVANTAGES.get(pet1["type"], []):
        power1 = int(power1 * 1.3)
        type_advantage_1 = True
    if pet1["type"] in TYPE_ADVANTAGES.get(pet2["type"], []):
        power2 = int(power2 * 1.3)
        type_advantage_2 = True
    
    # Check for critical hits (15% chance if happiness > 80)
    crit1 = False
    crit2 = False
    if pet1["happiness"] > 80 and random.random() < 0.15:
        power1 = int(power1 * 1.5)
        crit1 = True
    if pet2["happiness"] > 80 and random.random() < 0.15:
        power2 = int(power2 * 1.5)
        crit2 = True
    
    # Determine winner
    winner_pet = pet1 if power1 > power2 else pet2
    loser_pet = pet2 if winner_pet == pet1 else pet1
    winner_id = user1_str if winner_pet == pet1 else user2_str
    loser_id = user2_str if winner_id == user1_str else user1_str
    
    # Initialize battle stats if not present
    for pet in [pet1, pet2]:
        if "battle_wins" not in pet:
            pet["battle_wins"] = 0
        if "battle_losses" not in pet:
            pet["battle_losses"] = 0
        if "battle_streak" not in pet:
            pet["battle_streak"] = 0
    
    # Update battle stats
    winner_pet["battle_wins"] += 1
    winner_pet["battle_streak"] += 1
    loser_pet["battle_losses"] += 1
    loser_pet["battle_streak"] = 0  # Reset streak
    
    # Calculate XP gain with bonuses
    base_xp = 100
    rarity_bonus = RARITY_INFO[winner_pet["rarity"]]["xp_bonus"]
    
    # Apply rarity ability bonuses
    rarity = winner_pet.get("rarity", "common")
    ability = RARITY_ABILITIES.get(rarity, {})
    battle_xp_mult = ability.get("battle_xp_mult", 1.0)
    mythical_mult = ability.get("xp_mult", 1.0)
    
    # Streak bonus (+10 XP per streak level, max 100)
    streak_bonus = min(winner_pet["battle_streak"] * 10, 100)
    
    xp_gain = int((base_xp + streak_bonus) * rarity_bonus * battle_xp_mult * mythical_mult)
    
    winner_pet["xp"] += xp_gain
    if "total_xp" not in winner_pet:
        winner_pet["total_xp"] = 0
    winner_pet["total_xp"] += xp_gain
    
    winner_pet["last_battled"] = datetime.utcnow().isoformat()
    loser_pet["last_battled"] = datetime.utcnow().isoformat()
    
    # Check for level up
    old_level = winner_pet["level"]
    while winner_pet["xp"] >= xp_for_next_level(winner_pet["level"]):
        winner_pet["xp"] -= xp_for_next_level(winner_pet["level"])
        winner_pet["level"] += 1
    
    # Check for evolution
    evolved = check_evolution(winner_pet)
    
    # Check achievements
    check_and_award_achievements(winner_pet, action="battle_won")
    
    save_pets(pets)
    
    return {
        "winner_id": winner_id,
        "loser_id": loser_id,
        "power1": power1,
        "power2": power2,
        "xp_gain": xp_gain,
        "new_level": winner_pet["level"],
        "old_level": old_level,
        "pet1_type": pet1["type"],
        "pet2_type": pet2["type"],
        "type_advantage_1": type_advantage_1,
        "type_advantage_2": type_advantage_2,
        "crit1": crit1,
        "crit2": crit2,
        "evolved": evolved,
        "streak": winner_pet["battle_streak"],
        "mood1": get_pet_mood(pet1),
        "mood2": get_pet_mood(pet2)
    }

def get_pet_leaderboard(limit=10):
    """Get top pets by level"""
    pets = load_pets()
    
    # Flatten all pets from all users
    all_pets = []
    for user_id, user_pets in pets.items():
        # Handle both old and new format
        if isinstance(user_pets, dict):
            all_pets.append((user_id, user_pets))
        elif isinstance(user_pets, list):
            for pet in user_pets:
                all_pets.append((user_id, pet))
    
    # Sort by level and XP
    sorted_pets = sorted(
        all_pets,
        key=lambda x: (x[1]["level"], x[1]["xp"]),
        reverse=True
    )
    
    return sorted_pets[:limit]

def set_spawn_channel(guild_id, channel_id):
    """Set spawn channel for guild"""
    spawns = load_spawns()
    spawns[str(guild_id)] = {
        "channel_id": str(channel_id),
        "last_spawn": None,
        "current_spawn": None
    }
    save_spawns(spawns)

def get_spawn_channel(guild_id):
    """Get spawn channel for guild"""
    spawns = load_spawns()
    return spawns.get(str(guild_id))

def create_spawn(guild_id):
    """Create a new pet spawn with chance for shiny"""
    spawns = load_spawns()
    guild_str = str(guild_id)
    
    if guild_str in spawns:
        pet_type = get_random_pet()
        
        # Check for shiny (1% chance)
        is_shiny = random.random() < SHINY_CHANCE
        
        spawns[guild_str]["current_spawn"] = pet_type
        spawns[guild_str]["is_shiny"] = is_shiny
        spawns[guild_str]["last_spawn"] = datetime.utcnow().isoformat()
        save_spawns(spawns)
        return {"pet_type": pet_type, "is_shiny": is_shiny}
    
    return None

def clear_spawn(guild_id):
    """Clear current spawn"""
    spawns = load_spawns()
    guild_str = str(guild_id)
    
    if guild_str in spawns:
        spawns[guild_str]["current_spawn"] = None
        spawns[guild_str]["is_shiny"] = False
        save_spawns(spawns)

def get_current_spawn(guild_id):
    """Get current spawn for guild"""
    spawns = load_spawns()
    guild_data = spawns.get(str(guild_id))
    if guild_data:
        pet_type = guild_data.get("current_spawn")
        is_shiny = guild_data.get("is_shiny", False)
        if pet_type:
            return {"pet_type": pet_type, "is_shiny": is_shiny}
    return None

def set_pet_nickname(user_id, pet_name, nickname):
    """Set a nickname for a pet"""
    pets = load_pets()
    user_id_str = str(user_id)
    
    if user_id_str not in pets:
        return {"status": "no_pets"}
    
    user_pets = pets[user_id_str]
    if isinstance(user_pets, dict):
        user_pets = [user_pets]
        pets[user_id_str] = user_pets
    
    # Find the pet
    pet_name_lower = pet_name.lower()
    target_pet = None
    
    for pet in user_pets:
        pet_info = PET_TYPES.get(pet["type"])
        if pet_info and pet_info["name"].lower() == pet_name_lower:
            target_pet = pet
            break
    
    if not target_pet:
        return {"status": "not_found", "pet_name": pet_name}
    
    # Set nickname (or clear if None/empty)
    target_pet["nickname"] = nickname if nickname and nickname.strip() else None
    save_pets(pets)
    
    return {
        "status": "success",
        "pet": target_pet,
        "nickname": target_pet["nickname"]
    }

# UI Helper Functions

def create_progress_bar(current, maximum, length=10):
    """Create a visual progress bar"""
    if maximum == 0:
        return "▱" * length
    filled = int((current / maximum) * length)
    return "▰" * filled + "▱" * (length - filled)

def format_time_remaining(seconds):
    """Format seconds into human-readable time"""
    if seconds <= 0:
        return "Available now"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "<1m"

def get_cooldown_info(last_action_iso, cooldown_hours):
    """Get cooldown information for an action"""
    if not last_action_iso:
        return {"ready": True, "remaining": "Available now"}
    
    last_action = datetime.fromisoformat(last_action_iso)
    time_since = datetime.utcnow() - last_action
    cooldown_delta = timedelta(hours=cooldown_hours)
    
    if time_since >= cooldown_delta:
        return {"ready": True, "remaining": "Available now"}
    
    remaining_seconds = (cooldown_delta - time_since).total_seconds()
    return {
        "ready": False,
        "remaining": format_time_remaining(remaining_seconds)
    }

def get_stat_color_indicator(value):
    """Get color indicator emoji for stat value"""
    if value >= 70:
        return "🟢"  # Green
    elif value >= 40:
        return "🟡"  # Yellow
    else:
        return "🔴"  # Red
