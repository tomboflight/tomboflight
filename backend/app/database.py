from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings

client: MongoClient | None = None
db: Database | None = None


def connect_to_mongo() -> Database | None:
    global client, db

    if not settings.mongodb_uri:
        print("MongoDB URI not set yet. Running without database connection.")
        return None

    try:
        client = MongoClient(settings.mongodb_uri)
        db = client[settings.mongodb_db_name]
        client.admin.command("ping")
        print(f"Connected to MongoDB database: {settings.mongodb_db_name}")
        return db
    except Exception as exc:
        print(f"MongoDB connection failed: {exc}")
        client = None
        db = None
        return None


def get_database() -> Database | None:
    return db


def close_mongo_connection() -> None:
    global client, db

    if client is not None:
        client.close()
        print("MongoDB connection closed.")

    client = None
    db = None