import sys
import os
from ravendb.serverwide.operations.common import GetDatabaseNamesOperation
from dotenv import load_dotenv

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from cogs.utils.ravendb_manager import raven_db

import logging
logging.basicConfig(level=logging.INFO)

def main():
    print("Testing RavenDB Connection...")
    try:
        if not raven_db.store:
            print("FAILED: Store not initialized.")
            return
            
        print("Attempting to load a test document from 'shizu_bot'...")
        with raven_db.store.open_session() as session:
            # Re-disabling topology just in case for this session
            doc = session.load("test_connection_doc")
            print("SUCCESS: Session opened and load command executed (even if doc is None).")
    except Exception:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
