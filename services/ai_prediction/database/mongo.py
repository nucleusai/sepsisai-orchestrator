"""
MongoDB connection helper.

Reads MONGO_HOST, MONGO_PORT, and MONGO_DB from the environment so the same
image works unchanged in Docker Compose and Kubernetes.
"""

import os
from pymongo import MongoClient

_client: MongoClient | None = None

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "SepsisTraining")
COLLECTION = os.getenv("MONGO_COLLECTION", "DataPacientes")


def get_client() -> MongoClient:
    """Return a singleton MongoClient (lazy-initialised)."""
    global _client
    if _client is None:
        uri = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"
        _client = MongoClient(uri)
    return _client


def get_collection():
    """Convenience: return the default collection used for predictions."""
    return get_client()[MONGO_DB][COLLECTION]
