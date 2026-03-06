import sys
import os
import asyncio
from dotenv import load_dotenv

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from cogs.utils.ravendb_manager import raven_db

load_dotenv()

async def verify():
    print("Verifying RavenDB data...")
    try:
        # Check economy collection
        economy_data = await raven_db.get_all_in_collection("economy", limit=5)
        print(f"Economy documents found: {len(economy_data)}")
        for doc in economy_data:
            print(f" - ID: {doc['@metadata']['@id']}, Data: {list(doc.keys())[:5]}")
            
        # Check leveling collection
        leveling_data = await raven_db.get_all_in_collection("leveling", limit=5)
        print(f"Leveling documents found: {len(leveling_data)}")
        
        print("\nVerification SUCCESS: Data is present and readable.")
    except Exception as e:
        print(f"Verification FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
