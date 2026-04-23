from pymongo import MongoClient
from pymongo.database import Database
import certifi
import logging

from app.config import settings

client: MongoClient | None = None
db: Database | None = None
logger = logging.getLogger(__name__)


def connect_to_mongo() -> Database | None:
    global client, db

    if not settings.mongodb_uri:
        logger.warning("MongoDB URI is not set; starting without database connectivity.")
        return None

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
        logger.info("Connected to MongoDB database", extra={"database": settings.mongodb_db_name})
        return db
    except Exception as exc:
        client = None
        db = None
        logger.error("MongoDB connection failed; starting without database connectivity: %s", exc)
        return None


def get_database() -> Database:
    if db is None:
        raise RuntimeError("Database connection has not been initialized.")
    return db


def close_mongo_connection() -> None:
    global client, db

    if client is not None:
        client.close()
        logger.info("MongoDB connection closed.")

    client = None
    db = None
