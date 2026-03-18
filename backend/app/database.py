from pymongo import MongoClient
from pymongo.database import Database
import certifi

from app.config import settings

client: MongoClient | None = None
db: Database | None = None


def connect_to_mongo() -> Database:
    global client, db

    if not settings.mongodb_uri:
        raise RuntimeError("MongoDB URI is not set.")

    try:
        client = MongoClient(
            settings.mongodb_uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
        )
        db = client[settings.mongodb_db_name]
        client.admin.command("ping")
        print(f"Connected to MongoDB database: {settings.mongodb_db_name}")
        return db
    except Exception as exc:
        client = None
        db = None
        raise RuntimeError(f"MongoDB connection failed: {exc}") from exc


def get_database() -> Database:
    if db is None:
      raise RuntimeError("Database connection has not been initialized.")
    return db


def close_mongo_connection() -> None:
    global client, db

    if client is not None:
        client.close()
        print("MongoDB connection closed.")

    client = None
    db = None