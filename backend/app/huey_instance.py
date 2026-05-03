import os

from huey import SqliteHuey

# Use the same data directory as the main DB
huey_db_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "huey.db"
)
os.makedirs(os.path.dirname(huey_db_path), exist_ok=True)

huey = SqliteHuey(filename=huey_db_path)
