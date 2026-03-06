import sys
import os

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from cogs.utils.ravendb_manager import raven_db
from dotenv import load_dotenv

load_dotenv()

def main():
    print("Connecting to RavenDB to list databases...")
    dbs = raven_db.list_databases()
    print(f"Available databases: {dbs}")

if __name__ == "__main__":
    main()
