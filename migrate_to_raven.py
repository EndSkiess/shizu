import json
import os
import asyncio
from pathlib import Path
import sys

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from cogs.utils.ravendb_manager import raven_db
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    data_dir = Path('data')
    if not data_dir.exists():
        print("Error: data/ directory not found.")
        return

    db_name = os.getenv('RAVEN_DATABASE', 'shizu_bot')
    print(f"Starting migration to RavenDB database: {db_name}")

    if not raven_db.store:
        print("Error: RavenDB store not initialized. Check your RAVEN_URL and connection.")
        return

    for file_path in data_dir.glob('*.json'):
        collection_name = file_path.stem
        print(f"Migrating {file_path.name}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Map JSON structure to RavenDB documents
            if isinstance(data, dict):
                if not data:
                    print(f"  - Skipping empty file {file_path.name}")
                    continue

                # Check if it's a user_id: data map (like economy.json)
                first_key = next(iter(data.keys()))
                if first_key and (first_key.isdigit() or (':' in first_key and first_key.split(':')[0].isdigit())):
                    # Individual documents for users/keys
                    # e.g., "economy/123456" or "leveling/guild_id:user_id"
                    for key, value in data.items():
                        # Sanitize key for RavenDB ID (RavenDB handles slashes/colons fine, but let's stay consistent)
                        sanitized_key = key.replace(':', '/')
                        doc_id = f"{collection_name}/{sanitized_key}"
                        
                        # Wrap value in a dict if it's not one (though most are)
                        doc_content = value if isinstance(value, dict) else {"value": value}
                        
                        await raven_db.save_document(doc_id, doc_content)
                    print(f"  - Migrated {len(data)} documents into collection '{collection_name}'.")
                else:
                    # Single config document
                    await raven_db.save_document(f"config/{collection_name}", data)
                    print(f"  - Migrated as a single config document: config/{collection_name}")
            
            elif isinstance(data, list):
                if not data:
                    print(f"  - Skipping empty list {file_path.name}")
                    continue

                counter = 0
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        uid = item.get('id') or item.get('user_id') or item.get('_id')
                        if uid:
                            doc_id = f"{collection_name}/{uid}"
                            await raven_db.save_document(doc_id, item)
                            counter += 1
                        else:
                            # Auto-index if no ID
                            await raven_db.save_document(f"{collection_name}/{i}", item)
                            counter += 1
                
                if counter > 0:
                    print(f"  - Migrated {counter} items from list.")
                else:
                    # store as one lump if no IDs found and not dicts
                    await raven_db.save_document(f"list/{collection_name}", {"items": data})
                    print(f"  - Migrated list as a single document: list/{collection_name}")
                
        except Exception as e:
            print(f"Error migrating {file_path.name}: {e}")

    print("\nMigration to RavenDB complete!")
    print("You can view your data at the RavenDB Studio URL.")

if __name__ == "__main__":
    asyncio.run(migrate())
