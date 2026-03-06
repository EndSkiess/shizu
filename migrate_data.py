import json
import asyncio
import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    mongo_uri = os.getenv('MONGO_URI')
    db_name = os.getenv('MONGO_DB_NAME', 'shizu_bot')
    
    if not mongo_uri:
        print("Error: MONGO_URI not found in .env file.")
        return

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    data_dir = Path('data')
    if not data_dir.exists():
        print("Error: data/ directory not found.")
        return

    print(f"Starting migration to database: {db_name}")

    for file_path in data_dir.glob('*.json'):
        collection_name = file_path.stem
        print(f"Migrating {file_path.name} to collection '{collection_name}'...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            collection = db[collection_name]
            
            # If it's a dictionary (like economy.json where keys are user IDs)
            if isinstance(data, dict):
                # We store them as standard documents. 
                # For per-user data, we often want the key to be an 'id' field.
                # However, for simple porting, we can store the whole dict as one doc OR individual docs.
                # For many of these (economy, inventories), they are user_id: data maps.
                # Let's check if it's a flat user map.
                
                # Heuristic: if all keys look like IDs, treat as individual docs.
                first_key = next(iter(data.keys())) if data else None
                if first_key and (first_key.isdigit() or len(first_key) > 15):
                    # Migrating as individual documents for better querying
                    operations = []
                    for key, value in data.items():
                        # Ensure 'id' is set to the key if it's missing or different
                        doc = value.copy() if isinstance(value, dict) else {'value': value}
                        doc['_id'] = key 
                        await collection.replace_one({'_id': key}, doc, upsert=True)
                    print(f"  - Migrated {len(data)} individual documents.")
                else:
                    # Global config style (blacklist, shop_items)
                    # For these, we might keep it as one document with a fixed ID or just migrate as is.
                    # Best to keep them as individual items if they are collections (like shop_items)
                    if collection_name == 'shop_items' and 'items' in data:
                         # shop_items.json usually has {"items": {...}} or just {...}
                         # Let's check the structure again from my earlier 'type' output
                         pass # handled by next logic
                    
                    # If it's a fixed-key config like blacklist
                    await collection.replace_one({'_id': 'config'}, data, upsert=True)
                    print(f"  - Migrated as a single config document.")
            
            elif isinstance(data, list):
                # Migrating a list of items
                if data:
                    for item in data:
                        if isinstance(item, dict):
                            # Try to find a unique ID
                            uid = item.get('id') or item.get('user_id') or item.get('_id')
                            if uid:
                                item['_id'] = str(uid)
                                await collection.replace_one({'_id': item['_id']}, item, upsert=True)
                            else:
                                await collection.insert_one(item)
                    print(f"  - Migrated {len(data)} items from list.")
                
        except Exception as e:
            print(f"Error migrating {file_path.name}: {e}")

    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
